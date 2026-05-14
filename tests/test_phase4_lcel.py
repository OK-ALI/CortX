from __future__ import annotations

from backend.ai.intent_chain import extract_intent
from backend.ai.query_chain import generate_search_queries
from backend.ai.synth_chain import synthesize_answer
from backend.processor.ranker import RankedPage


class _StubLCEL:
    def run_intent(self, query: str) -> str:
        _ = query
        return '{"intent_type": "research", "entities": ["RAG"], "time_sensitivity": "timeless"}'

    def run_queries(
        self,
        original_query: str,
        intent_type: str,
        time_sensitivity: str,
        entities: str,
    ) -> str:
        _ = (original_query, intent_type, time_sensitivity, entities)
        return '{"queries": ["rag architecture", "rag retrieval flow", "rag grounding"]}'

    def run_refinement(
        self,
        query: str,
        refined_queries: str,
        snippets: str,
        allowed_sources: str,
    ) -> str:
        _ = (query, refined_queries, snippets, allowed_sources)
        return (
            "Acknowledgement:\n"
            "Scrape-grounded response only; no free-form LLM answer generation.\n\n"
            "LLM Acknowledgement:\n"
            "Here is what I found from scraped excerpts only.\n\n"
            "User Query:\n"
            "What is RAG?\n\n"
            "Refined Search Queries:\n"
            "- rag architecture\n\n"
            "Scraped Findings:\n"
            "RAG combines retrieval and generation to ground outputs.\n\n"
            "Sources:\n"
            "https://example.com/rag"
        )

    def run_ack(self, query: str, snippet_highlights: str) -> str:
        _ = (query, snippet_highlights)
        return "Here is what I found from local scraped sources."


class _DummyClient:
    pass


def test_intent_chain_uses_lcel(monkeypatch) -> None:
    monkeypatch.setattr("backend.ai.intent_chain.get_lcel_chains", lambda _client: _StubLCEL())
    result = extract_intent("What is RAG?", llm_client=_DummyClient())  # type: ignore[arg-type]

    assert result.intent_type == "research"
    assert result.entities == ["RAG"]
    assert result.time_sensitivity == "timeless"


def test_query_chain_uses_lcel(monkeypatch) -> None:
    monkeypatch.setattr("backend.ai.query_chain.get_lcel_chains", lambda _client: _StubLCEL())
    intent = extract_intent("What is RAG?", llm_client=None)
    queries = generate_search_queries("What is RAG?", intent, llm_client=_DummyClient())  # type: ignore[arg-type]

    assert queries == ["What is RAG?", "rag architecture", "rag retrieval flow"]


def test_synth_chain_uses_lcel_refinement(monkeypatch) -> None:
    monkeypatch.setattr("backend.ai.synth_chain.get_lcel_chains", lambda _client: _StubLCEL())

    ranked_pages = [
        RankedPage(
            url="https://example.com/rag",
            text="RAG improves grounding by retrieving external information.",
            score=1.0,
        )
    ]

    output = synthesize_answer(
        query="What is RAG?",
        ranked_pages=ranked_pages,
        max_pages=1,
        refined_queries=["rag architecture"],
        llm_client=_DummyClient(),  # type: ignore[arg-type]
        enable_llm_result_refinement=True,
    )

    assert "LLM Acknowledgement:" in output
    assert "Here is what I found" in output
    assert "https://example.com/rag" in output
