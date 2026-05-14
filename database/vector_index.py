"""Semantic vector ranking using sentence-transformers + LanceDB."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import lancedb
import pyarrow as pa


@dataclass
class SemanticRankedPage:
    url: str
    text: str
    score: float


def _get_embedder():
    """Lazy-load sentence-transformers model."""
    try:
        from sentence_transformers import SentenceTransformer
        return SentenceTransformer("all-MiniLM-L6-v2")
    except Exception:
        return None


_CACHED_MODEL = None


def _model():
    global _CACHED_MODEL
    if _CACHED_MODEL is None:
        _CACHED_MODEL = _get_embedder()
    return _CACHED_MODEL


def rank_pages_semantic(
    query: str,
    pages: Sequence[object],
) -> list[SemanticRankedPage]:
    """Rank pages by semantic similarity using embeddings + LanceDB vector search.

    Falls back to keyword overlap if sentence-transformers is unavailable.
    """
    if not pages:
        return []

    model = _model()
    if model is None:
        return _keyword_fallback(query, pages)

    try:
        return _vector_rank(query, pages, model)
    except Exception:
        return _keyword_fallback(query, pages)


def _vector_rank(query: str, pages: Sequence[object], model) -> list[SemanticRankedPage]:
    """Embed pages and query, rank by cosine similarity via LanceDB."""
    texts = []
    urls = []
    full_texts = []
    for page in pages:
        page_text = getattr(page, "text", "")
        page_url = getattr(page, "url", "")
        # Use first 256 words for embedding (enough for semantic signal)
        snippet = " ".join(page_text.split()[:256])
        texts.append(snippet)
        urls.append(page_url)
        full_texts.append(page_text)

    if not texts:
        return []

    # Embed all texts + query  
    all_texts = texts + [query]
    embeddings = model.encode(all_texts, normalize_embeddings=True)
    page_embeddings = embeddings[:-1]
    query_embedding = embeddings[-1]

    ndim = len(query_embedding)

    # Build temporary in-memory LanceDB table
    schema = pa.schema([
        pa.field("idx", pa.int32()),
        pa.field("url", pa.utf8()),
        pa.field("vector", pa.list_(pa.float32(), ndim)),
    ])

    records = []
    for i, (url, emb) in enumerate(zip(urls, page_embeddings)):
        records.append({
            "idx": i,
            "url": url,
            "vector": emb.tolist(),
        })

    db = lancedb.connect(":memory:")
    tbl = db.create_table("_rank_tmp", data=records, schema=schema, mode="overwrite")

    # Vector search
    results = tbl.search(query_embedding.tolist()).limit(len(records)).to_list()

    ranked: list[SemanticRankedPage] = []
    for r in results:
        idx = r["idx"]
        # LanceDB returns _distance (lower = more similar for cosine)
        distance = r.get("_distance", 1.0)
        similarity = max(1.0 - distance, 0.0)
        ranked.append(SemanticRankedPage(
            url=urls[idx],
            text=full_texts[idx],
            score=similarity,
        ))

    return ranked


def _keyword_fallback(query: str, pages: Sequence[object]) -> list[SemanticRankedPage]:
    """Simple keyword overlap fallback."""
    query_terms = {token.lower() for token in query.split() if token.strip()}
    ranked: list[SemanticRankedPage] = []
    for page in pages:
        page_text = getattr(page, "text", "")
        page_url = getattr(page, "url", "")
        page_terms = {token.lower() for token in page_text.split()}
        overlap = len(query_terms.intersection(page_terms))
        score = overlap / max(len(query_terms), 1)
        ranked.append(SemanticRankedPage(url=page_url, text=page_text, score=score))
    ranked.sort(key=lambda item: item.score, reverse=True)
    return ranked
