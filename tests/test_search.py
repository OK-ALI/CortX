from __future__ import annotations

import sys
import types

from backend.search.web_search import _dedupe_urls, discover_urls


def test_dedupe_urls_preserves_order() -> None:
    urls = [
        "https://example.com/a",
        "https://example.com/b",
        "https://example.com/a",
        "https://example.com/c",
    ]
    assert _dedupe_urls(urls) == [
        "https://example.com/a",
        "https://example.com/b",
        "https://example.com/c",
    ]


def test_discover_urls_uses_ddgs_and_dedupes(monkeypatch) -> None:
    class _FakeDDGS:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            _ = (exc_type, exc, tb)
            return False

        def text(self, query: str, max_results: int):
            _ = max_results
            if "first" in query:
                return [
                    {"href": "https://example.com/a"},
                    {"href": "https://example.com/b"},
                ]
            return [{"href": "https://example.com/a"}]

    fake_module = types.SimpleNamespace(DDGS=_FakeDDGS)
    monkeypatch.setitem(sys.modules, "ddgs", fake_module)

    urls = discover_urls(["first query", "second query"], max_urls=3)

    assert urls == ["https://example.com/a", "https://example.com/b"]


def test_discover_urls_falls_back_when_ddgs_fails(monkeypatch) -> None:
    class _BoomDDGS:
        def __enter__(self):
            raise RuntimeError("ddgs failed")

        def __exit__(self, exc_type, exc, tb):
            _ = (exc_type, exc, tb)
            return False

    fake_module = types.SimpleNamespace(DDGS=_BoomDDGS)
    monkeypatch.setitem(sys.modules, "ddgs", fake_module)

    urls = discover_urls(["hello world", "hello world"], max_urls=3)

    assert urls == ["https://duckduckgo.com/?q=hello+world"]
