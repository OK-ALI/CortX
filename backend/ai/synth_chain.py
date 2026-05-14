from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Sequence

from backend.ai.lcel_chains import get_lcel_chains
from backend.ai.llm_manager import OllamaClient
from backend.processor.ranker import RankedPage


@dataclass
class SynthesisResult:
    """Structured result from answer synthesis."""
    answer: str
    sources: list[str]


def _build_snippet_block(ranked_pages: Sequence[RankedPage], max_pages: int) -> tuple[str, list[str]]:
    """Build numbered snippet text and source list from ranked pages."""
    selected = list(ranked_pages)[:max_pages]
    if not selected:
        return "", []

    snippets: list[str] = []
    sources: list[str] = []
    for idx, page in enumerate(selected, start=1):
        words = page.text.split()
        excerpt = " ".join(words[:200]).strip()
        if excerpt:
            snippets.append(f"[{idx}] {excerpt}")
            sources.append(f"[{idx}] {page.url}")

    return "\n\n".join(snippets), sources


def _synthesize_with_llm(
    query: str,
    ranked_pages: Sequence[RankedPage],
    max_pages: int,
    llm_client: OllamaClient,
    search_snippets: Sequence[str] | None = None,
) -> SynthesisResult | None:
    """Generate a conversational markdown answer using the LLM synthesis chain."""
    snippet_text, sources = _build_snippet_block(ranked_pages, max_pages)
    if not snippet_text:
        return None

    # Add search engine snippets for extra context
    if search_snippets:
        extra = "\n\n".join(f"[Search snippet] {s}" for s in search_snippets if s.strip())
        if extra:
            snippet_text = f"{snippet_text}\n\n{extra}"

    try:
        answer = get_lcel_chains(llm_client).run_synthesis(
            query=query,
            snippets=snippet_text,
            sources="\n".join(sources),
        )
    except Exception:
        return None

    if not answer or len(answer.strip()) < 20:
        return None

    return SynthesisResult(answer=answer.strip(), sources=[s for s in sources])


def _build_fallback_answer(
    query: str,
    ranked_pages: Sequence[RankedPage],
    max_pages: int,
    refined_queries: Sequence[str] | None = None,
) -> SynthesisResult:
    """Fallback: structured snippets when LLM synthesis is unavailable/fails."""
    selected = list(ranked_pages)[:max_pages]
    if not selected:
        return SynthesisResult(
            answer="I couldn't find sufficient information to answer this question. Please try rephrasing your query.",
            sources=[],
        )

    parts: list[str] = []
    sources: list[str] = []
    for idx, page in enumerate(selected, start=1):
        words = page.text.split()
        excerpt = " ".join(words[:140]).strip()
        if excerpt:
            parts.append(f"**From source [{idx}]:**\n{excerpt}...")
            sources.append(f"[{idx}] {page.url}")

    answer = "Here's what I found from web sources:\n\n" + "\n\n".join(parts)
    return SynthesisResult(answer=answer, sources=sources)


def synthesize_answer(
    query: str,
    ranked_pages: Sequence[RankedPage],
    max_pages: int,
    refined_queries: Sequence[str] | None = None,
    llm_client: OllamaClient | None = None,
    enable_llm_synthesis: bool = False,
    enable_llm_result_refinement: bool = False,
    search_snippets: Sequence[str] | None = None,
) -> SynthesisResult:
    """Synthesize an answer from ranked pages.

    If enable_llm_synthesis is True and llm_client is available, produces a
    conversational markdown answer with inline citations.
    Otherwise falls back to structured scrape excerpts.
    """
    # Try LLM synthesis first (new path — conversational answers)
    if enable_llm_synthesis and llm_client is not None:
        result = _synthesize_with_llm(
            query=query,
            ranked_pages=ranked_pages,
            max_pages=max_pages,
            llm_client=llm_client,
            search_snippets=search_snippets,
        )
        if result is not None:
            return result

    # Fallback: structured excerpt output
    return _build_fallback_answer(
        query=query,
        ranked_pages=ranked_pages,
        max_pages=max_pages,
        refined_queries=refined_queries,
    )
