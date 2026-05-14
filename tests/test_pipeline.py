from __future__ import annotations

import asyncio
from dataclasses import dataclass

from backend.ai.followup_intent import FollowupResolution
from backend.ai.pipeline import CortxPipeline
from backend.scraper.scraper_engine import ScrapedPage
from backend.search.web_search import SearchResult
from backend.utils.config import load_settings
from backend.utils.logger import setup_logger


@dataclass
class _StubScraper:
    class _Stats:
        total_requested = 1
        cache_hits = 0
        robots_blocked = 0
        bot_challenges = 0
        tier2_attempted = 0
        tier3_attempted = 0
        tier1_success = 1
        tier2_success = 0
        tier3_success = 0
        failed_urls = 0

    last_stats = _Stats()

    async def scrape(self, urls: list[str]) -> list[ScrapedPage]:
        _ = urls
        return [
            ScrapedPage(
                url="https://example.com/page",
                text="Cortx retrieves and summarizes web content with citations.",
                tier="httpx",
            )
        ]


@dataclass
class _ResolverProbe:
    explicit_context_seen: dict | None = None

    def resolve(self, query: str, conversation_messages, llm_client, explicit_context=None) -> FollowupResolution:
        _ = (query, conversation_messages, llm_client)
        self.explicit_context_seen = explicit_context
        return FollowupResolution(
            standalone_query=query,
            requires_context=False,
            update_intent=False,
            context_focus="",
            action_type="ask",
        )


def test_pipeline_returns_answer(monkeypatch) -> None:
    monkeypatch.setenv("ENABLE_OLLAMA_CHAINS", "false")
    monkeypatch.setenv("WARMUP_OLLAMA_ON_START", "false")
    settings = load_settings("config/settings.yaml")
    logger = setup_logger("INFO")
    pipeline = CortxPipeline(settings=settings, logger=logger)

    monkeypatch.setattr(
        "backend.ai.pipeline.discover_urls",
        lambda queries, max_urls, **kwargs: [SearchResult(url="https://example.com", snippet="")],
    )
    pipeline.scraper = _StubScraper()  # type: ignore[assignment]

    result = asyncio.run(pipeline.run("What does Cortx do?"))

    assert "Acknowledgement:" in result.answer
    assert "LLM Acknowledgement:" in result.answer
    assert "Scraped Findings:" in result.answer
    assert "Sources:" in result.answer
    assert result.urls == ["https://example.com"]


def test_pipeline_forwards_explicit_context(monkeypatch) -> None:
    monkeypatch.setenv("ENABLE_OLLAMA_CHAINS", "false")
    monkeypatch.setenv("WARMUP_OLLAMA_ON_START", "false")
    settings = load_settings("config/settings.yaml")
    logger = setup_logger("INFO")
    pipeline = CortxPipeline(settings=settings, logger=logger)

    monkeypatch.setattr(
        "backend.ai.pipeline.discover_urls",
        lambda queries, max_urls, **kwargs: [SearchResult(url="https://example.com", snippet="")],
    )
    pipeline.scraper = _StubScraper()  # type: ignore[assignment]
    probe = _ResolverProbe()
    pipeline.followup_resolver = probe  # type: ignore[assignment]

    explicit_context = {"action": "reply", "preview": "python release notes", "target_id": "m1"}
    _ = asyncio.run(
        pipeline.run(
            "Can you summarize it?",
            conversation_messages=[{"role": "user", "content": "Tell me about Python 3.13"}],
            explicit_context=explicit_context,
        )
    )

    assert probe.explicit_context_seen == explicit_context
