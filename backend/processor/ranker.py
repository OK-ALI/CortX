from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from database.vector_index import rank_pages_semantic, SemanticRankedPage


@dataclass
class RankedPage:
    url: str
    text: str
    score: float


def rank_pages(query: str, pages: Sequence[object]) -> list[RankedPage]:
    """Rank pages by semantic similarity using embeddings + LanceDB vector search."""
    semantic_results = rank_pages_semantic(query, pages)
    return [
        RankedPage(url=r.url, text=r.text, score=r.score)
        for r in semantic_results
    ]
