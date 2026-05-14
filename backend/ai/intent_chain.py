from __future__ import annotations

from dataclasses import dataclass
import re

from backend.ai.json_utils import extract_json_object
from backend.ai.lcel_chains import get_lcel_chains
from backend.ai.llm_manager import OllamaClient


@dataclass
class IntentResult:
    intent_type: str
    entities: list[str]
    time_sensitivity: str


def _extract_intent_heuristic(query: str) -> IntentResult:
    lowered = query.lower()

    if any(token in lowered for token in ["latest", "today", "news", "202", "recent"]):
        intent_type = "news"
        time_sensitivity = "recent"
    elif any(token in lowered for token in ["compare", "vs", "difference"]):
        intent_type = "comparison"
        time_sensitivity = "timeless"
    elif any(token in lowered for token in ["research", "analyze", "deep"]):
        intent_type = "research"
        time_sensitivity = "timeless"
    else:
        intent_type = "factual"
        time_sensitivity = "timeless"

    entities = re.findall(r"\b[A-Z][a-zA-Z0-9_-]{2,}\b", query)
    return IntentResult(intent_type=intent_type, entities=entities, time_sensitivity=time_sensitivity)


def _normalize_intent_type(value: str) -> str:
    allowed = {"factual", "research", "news", "comparison"}
    lowered = value.strip().lower()
    return lowered if lowered in allowed else "factual"


def _normalize_time_sensitivity(value: str) -> str:
    allowed = {"recent", "historical", "timeless"}
    lowered = value.strip().lower()
    return lowered if lowered in allowed else "timeless"


def extract_intent(query: str, llm_client: OllamaClient | None = None) -> IntentResult:
    """Extract intent via Ollama when available, with heuristic fallback."""
    if llm_client is None:
        return _extract_intent_heuristic(query)

    try:
        raw = get_lcel_chains(llm_client).run_intent(query)
        data = extract_json_object(raw)

        entities = data.get("entities", [])
        if not isinstance(entities, list):
            entities = []

        return IntentResult(
            intent_type=_normalize_intent_type(str(data.get("intent_type", "factual"))),
            entities=[str(item) for item in entities if str(item).strip()],
            time_sensitivity=_normalize_time_sensitivity(str(data.get("time_sensitivity", "timeless"))),
        )
    except Exception:  # noqa: BLE001
        return _extract_intent_heuristic(query)
