from __future__ import annotations

from dataclasses import dataclass
from typing import overload, Literal
from urllib.parse import quote_plus


@dataclass
class SearchResult:
    url: str
    snippet: str


def _dedupe_results(results: list[SearchResult]) -> list[SearchResult]:
    seen: set[str] = set()
    ordered: list[SearchResult] = []
    for result in results:
        normalized = result.url.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        ordered.append(result)
    return ordered


def _dedupe_urls(urls: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for url in urls:
        normalized = url.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        ordered.append(normalized)
    return ordered


def _fallback_urls(queries: list[str]) -> list[str]:
    first = next((query.strip() for query in queries if query.strip()), "")
    if not first:
        return []
    return [f"https://duckduckgo.com/?q={quote_plus(first)}"]


def _resolve_timelimit(time_sensitivity: str | None) -> str | None:
    if not time_sensitivity:
        return None
    lowered = time_sensitivity.strip().lower()
    if lowered == "recent":
        return "w"
    if lowered == "historical":
        return "y"
    return None


def discover_search_results(
    queries: list[str],
    max_urls: int = 8,
    time_sensitivity: str | None = None,
) -> list[SearchResult]:
    """Discover rich URL results (URL + snippet) via DuckDuckGo."""
    discovered: list[SearchResult] = []
    per_query = max(max_urls // max(len(queries), 1), 3)
    timelimit = _resolve_timelimit(time_sensitivity)

    try:
        from ddgs import DDGS  # type: ignore[import-not-found]

        with DDGS() as ddgs:
            for query in queries:
                try:
                    if timelimit:
                        try:
                            results = ddgs.text(query, max_results=per_query, timelimit=timelimit)
                        except TypeError:
                            results = ddgs.text(query, max_results=per_query)
                    else:
                        results = ddgs.text(query, max_results=per_query)
                    for item in results:
                        href = item.get("href") or item.get("url")
                        body = item.get("body") or item.get("text") or ""
                        if href:
                            discovered.append(SearchResult(url=href, snippet=str(body)))
                except Exception:
                    continue
    except Exception:
        pass

    deduped = _dedupe_results(discovered)
    if deduped:
        return deduped[:max_urls]

    return [SearchResult(url=url, snippet="") for url in _fallback_urls(queries)]


@overload
def discover_urls(
    queries: list[str],
    max_urls: int = 8,
    return_results: Literal[False] = False,
    time_sensitivity: str | None = None,
) -> list[str]:
    ...


@overload
def discover_urls(
    queries: list[str],
    max_urls: int = 8,
    return_results: Literal[True] = True,
    time_sensitivity: str | None = None,
) -> list[SearchResult]:
    ...


def discover_urls(
    queries: list[str],
    max_urls: int = 8,
    return_results: bool = False,
    time_sensitivity: str | None = None,
) -> list[str] | list[SearchResult]:
    """Discover URLs via DuckDuckGo.

    By default returns URL strings for compatibility. Set return_results=True
    to return SearchResult entries with snippets.
    """
    results = discover_search_results(
        queries,
        max_urls=max_urls,
        time_sensitivity=time_sensitivity,
    )
    if return_results:
        return results
    return _dedupe_urls([result.url for result in results])
