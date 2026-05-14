from __future__ import annotations

from backend.ai.json_utils import extract_json_object
from backend.ai.lcel_chains import get_lcel_chains
from backend.ai.llm_manager import OllamaClient
from backend.ai.intent_chain import IntentResult


def _heuristic_queries(original_query: str, intent: IntentResult) -> list[str]:
    queries = [original_query.strip()]

    if intent.intent_type == "news":
        queries.append(f"{original_query} latest updates")
        queries.append(f"{original_query} official announcement")
    elif intent.intent_type == "comparison":
        queries.append(f"{original_query} benchmark")
        queries.append(f"{original_query} pros and cons")
    elif intent.intent_type == "research":
        queries.append(f"{original_query} technical deep dive")
        queries.append(f"{original_query} architecture overview")
    else:
        queries.append(f"{original_query} explained")
        queries.append(f"{original_query} summary")

    deduped: list[str] = []
    for item in queries:
        if item and item not in deduped:
            deduped.append(item)
    return deduped[:3]


def _sanitize_queries(raw_queries: list[str], original_query: str) -> list[str]:
    deduped: list[str] = []
    for item in [original_query.strip(), *raw_queries]:
        normalized = " ".join(str(item).split()).strip()
        if normalized and normalized not in deduped:
            deduped.append(normalized)
    return deduped[:3]


def generate_search_queries(
    original_query: str,
    intent: IntentResult,
    llm_client: OllamaClient | None = None,
) -> list[str]:
    """Generate three diverse search queries using Ollama with heuristic fallback."""
    if llm_client is None:
        return _heuristic_queries(original_query, intent)

    try:
        raw = get_lcel_chains(llm_client).run_queries(
            original_query=original_query,
            intent_type=intent.intent_type,
            time_sensitivity=intent.time_sensitivity,
            entities=", ".join(intent.entities) if intent.entities else "none",
        )
        data = extract_json_object(raw)
        queries = data.get("queries", [])
        if not isinstance(queries, list):
            return _heuristic_queries(original_query, intent)
        return _sanitize_queries([str(q) for q in queries], original_query)
    except Exception:  # noqa: BLE001
        return _heuristic_queries(original_query, intent)
