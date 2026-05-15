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
    """Rank pages by semantic similarity using embeddings + LanceDB vector search.
    Applies a dynamic score multiplier based on original Search Engine Rank Position (SERP)
    to automatically favor well-known domains for niche topics.
    """
    semantic_results = rank_pages_semantic(query, pages)
    
    # Create a mapping of URL to original search engine rank index
    url_to_index = {getattr(p, "url", ""): i for i, p in enumerate(pages)}
    
    ranked = []
    for r in semantic_results:
        multiplier = 1.0
        idx = url_to_index.get(r.url, 99)
        
        # Boost the top 3 search results from DuckDuckGo, as the search engine 
        # algorithm already knows which sites are most reputable for that specific niche
        if idx == 0:
            multiplier = 1.20  # +20% for #1 search result
        elif idx == 1:
            multiplier = 1.10  # +10% for #2 search result
        elif idx == 2:
            multiplier = 1.05  # +5% for #3 search result
            
        ranked.append(RankedPage(url=r.url, text=r.text, score=r.score * multiplier))
        
    # Re-sort after applying dynamic SERP multipliers
    ranked.sort(key=lambda x: x.score, reverse=True)
    return ranked
