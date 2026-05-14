from __future__ import annotations


def truncate_words(text: str, max_words: int, query: str | None = None) -> str:
    """Truncate to max_words, preferring paragraphs most relevant to the query."""
    words = text.split()
    if len(words) <= max_words:
        return text

    if not query:
        return " ".join(words[:max_words])

    # Split into paragraphs and score each by keyword overlap with query
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    if not paragraphs:
        return " ".join(words[:max_words])

    query_terms = {token.lower() for token in query.split() if len(token) > 2}
    if not query_terms:
        return " ".join(words[:max_words])

    scored: list[tuple[float, int, str]] = []
    for idx, para in enumerate(paragraphs):
        para_words = para.lower().split()
        if not para_words:
            continue
        overlap = sum(1 for w in para_words if w in query_terms)
        density = overlap / max(len(para_words), 1)
        # Slight positional bias: first paragraphs often contain key info
        position_bonus = max(0, 0.1 - idx * 0.01)
        scored.append((density + position_bonus, idx, para))

    # Sort by relevance score, keep top paragraphs up to max_words
    scored.sort(key=lambda x: (-x[0], x[1]))
    selected: list[tuple[int, str]] = []
    total_words = 0
    for _score, idx, para in scored:
        para_word_count = len(para.split())
        if total_words + para_word_count > max_words:
            # Take partial if it's the first one
            if not selected:
                remaining = max_words - total_words
                selected.append((idx, " ".join(para.split()[:remaining])))
            break
        selected.append((idx, para))
        total_words += para_word_count

    if not selected:
        return " ".join(words[:max_words])

    # Restore original order for readability
    selected.sort(key=lambda x: x[0])
    return "\n\n".join(para for _, para in selected)
