from __future__ import annotations

import asyncio

from backend.scraper.httpx_scraper import RawPage
from backend.scraper.scraper_engine import ScraperEngine


class _MemoryCache:
    def __init__(self) -> None:
        self.data: dict[str, str] = {}

    def get(self, url: str) -> str | None:
        return self.data.get(url)

    def get_fresh(self, url: str, max_age_seconds: int) -> str | None:
        _ = max_age_seconds
        return self.get(url)

    def set(self, url: str, content: str) -> None:
        self.data[url] = content


def test_scraper_escalates_to_playwright_on_http_block(monkeypatch) -> None:
    engine = ScraperEngine(timeout_seconds=5, user_agent="ua", min_words_per_page=5)

    async def _fake_fetch_many(
        urls: list[str],
        timeout_seconds: int,
        user_agent: str,
        delay_min_seconds: int = 1,
        delay_max_seconds: int = 2,
    ) -> list[RawPage]:
        _ = (urls, timeout_seconds, user_agent, delay_min_seconds, delay_max_seconds)
        return [RawPage(url="https://example.com", html="", status_code=403)]

    async def _fake_playwright(urls: list[str], timeout_seconds: int, user_agent: str) -> list[tuple[str, str]]:
        _ = (timeout_seconds, user_agent)
        return [
            (
                urls[0],
                "<html><body><main>Playwright rendered content with enough words for extraction.</main></body></html>",
            )
        ]

    monkeypatch.setattr("backend.scraper.scraper_engine.fetch_many", _fake_fetch_many)
    monkeypatch.setattr("backend.scraper.scraper_engine.scrape_with_playwright", _fake_playwright)
    monkeypatch.setattr("backend.scraper.scraper_engine.scrape_with_selenium_fallback", lambda urls: [])

    pages = asyncio.run(engine.scrape(["https://example.com"]))

    assert len(pages) == 1
    assert pages[0].tier == "playwright"


def test_scraper_uses_tier3_when_tier2_text_short(monkeypatch) -> None:
    engine = ScraperEngine(timeout_seconds=5, user_agent="ua", min_words_per_page=5)

    async def _fake_fetch_many(
        urls: list[str],
        timeout_seconds: int,
        user_agent: str,
        delay_min_seconds: int = 1,
        delay_max_seconds: int = 2,
    ) -> list[RawPage]:
        _ = (urls, timeout_seconds, user_agent, delay_min_seconds, delay_max_seconds)
        return [RawPage(url="https://example.com", html="<html><body>tiny</body></html>", status_code=200)]

    async def _fake_playwright(urls: list[str], timeout_seconds: int, user_agent: str) -> list[tuple[str, str]]:
        _ = (urls, timeout_seconds, user_agent)
        return [("https://example.com", "<html><body>tiny text</body></html>")]

    def _fake_tier3(urls: list[str]) -> list[tuple[str, str]]:
        _ = urls
        return [
            (
                "https://example.com",
                "<html><body><main>Tier three fallback produced enough meaningful content now.</main></body></html>",
            )
        ]

    monkeypatch.setattr("backend.scraper.scraper_engine.fetch_many", _fake_fetch_many)
    monkeypatch.setattr("backend.scraper.scraper_engine.scrape_with_playwright", _fake_playwright)
    monkeypatch.setattr("backend.scraper.scraper_engine.scrape_with_selenium_fallback", _fake_tier3)

    pages = asyncio.run(engine.scrape(["https://example.com"]))

    assert len(pages) == 1
    assert pages[0].tier == "selenium_fallback"
    assert engine.last_stats.tier3_success == 1
    assert engine.last_stats.failed_urls == 0


def test_scraper_uses_cache_without_network(monkeypatch) -> None:
    cache = _MemoryCache()
    cache.set(
        "https://example.com",
        "cached page content that has enough words to pass minimum threshold",
    )
    engine = ScraperEngine(timeout_seconds=5, user_agent="ua", min_words_per_page=5, cache_db=cache)

    async def _fail_if_called(
        urls: list[str],
        timeout_seconds: int,
        user_agent: str,
        delay_min_seconds: int = 1,
        delay_max_seconds: int = 2,
    ) -> list[RawPage]:
        _ = (urls, timeout_seconds, user_agent, delay_min_seconds, delay_max_seconds)
        raise AssertionError("Network should not be called when cache has valid content")

    monkeypatch.setattr("backend.scraper.scraper_engine.fetch_many", _fail_if_called)

    pages = asyncio.run(engine.scrape(["https://example.com"]))

    assert len(pages) == 1
    assert pages[0].tier == "cache"


def test_scraper_writes_successful_httpx_to_cache(monkeypatch) -> None:
    cache = _MemoryCache()
    engine = ScraperEngine(timeout_seconds=5, user_agent="ua", min_words_per_page=5, cache_db=cache)

    async def _fake_fetch_many(
        urls: list[str],
        timeout_seconds: int,
        user_agent: str,
        delay_min_seconds: int = 1,
        delay_max_seconds: int = 2,
    ) -> list[RawPage]:
        _ = (urls, timeout_seconds, user_agent, delay_min_seconds, delay_max_seconds)
        return [
            RawPage(
                url="https://example.com",
                html="<html><body><main>This page has enough words for cache write verification test.</main></body></html>",
                status_code=200,
            )
        ]

    monkeypatch.setattr("backend.scraper.scraper_engine.fetch_many", _fake_fetch_many)
    monkeypatch.setattr("backend.scraper.scraper_engine.scrape_with_playwright", lambda *args, **kwargs: [])
    monkeypatch.setattr("backend.scraper.scraper_engine.scrape_with_selenium_fallback", lambda urls: [])

    pages = asyncio.run(engine.scrape(["https://example.com"]))

    assert len(pages) == 1
    assert pages[0].tier == "httpx"
    assert cache.get("https://example.com") is not None


def test_scraper_refetches_when_cache_is_stale(monkeypatch) -> None:
    class _AlwaysStaleCache(_MemoryCache):
        def get_fresh(self, url: str, max_age_seconds: int) -> str | None:
            _ = (url, max_age_seconds)
            return None

    cache = _AlwaysStaleCache()
    cache.set("https://example.com", "stale cached content with enough words still ignored")
    engine = ScraperEngine(
        timeout_seconds=5,
        user_agent="ua",
        min_words_per_page=5,
        cache_db=cache,
        cache_ttl_seconds=1,
    )

    async def _fake_fetch_many(
        urls: list[str],
        timeout_seconds: int,
        user_agent: str,
        delay_min_seconds: int = 1,
        delay_max_seconds: int = 2,
    ) -> list[RawPage]:
        _ = (urls, timeout_seconds, user_agent, delay_min_seconds, delay_max_seconds)
        return [
            RawPage(
                url="https://example.com",
                html="<html><body><main>freshly refetched content from network path.</main></body></html>",
                status_code=200,
            )
        ]

    monkeypatch.setattr("backend.scraper.scraper_engine.fetch_many", _fake_fetch_many)
    monkeypatch.setattr("backend.scraper.scraper_engine.scrape_with_playwright", lambda *args, **kwargs: [])
    monkeypatch.setattr("backend.scraper.scraper_engine.scrape_with_selenium_fallback", lambda urls: [])

    pages = asyncio.run(engine.scrape(["https://example.com"]))

    assert len(pages) == 1
    assert pages[0].tier == "httpx"


def test_scraper_respects_robots_filter(monkeypatch) -> None:
    engine = ScraperEngine(timeout_seconds=5, user_agent="ua", min_words_per_page=5)

    async def _fake_robots(urls: list[str], user_agent: str, timeout_seconds: int):
        _ = (user_agent, timeout_seconds)
        return type("Decision", (), {"allowed_urls": [], "blocked_urls": list(urls)})()

    async def _fail_if_called(
        urls: list[str],
        timeout_seconds: int,
        user_agent: str,
        delay_min_seconds: int = 1,
        delay_max_seconds: int = 2,
    ) -> list[RawPage]:
        _ = (urls, timeout_seconds, user_agent, delay_min_seconds, delay_max_seconds)
        raise AssertionError("fetch_many should not run when robots blocks all URLs")

    monkeypatch.setattr("backend.scraper.scraper_engine.filter_urls_by_robots", _fake_robots)
    monkeypatch.setattr("backend.scraper.scraper_engine.fetch_many", _fail_if_called)

    pages = asyncio.run(engine.scrape(["https://example.com"]))

    assert pages == []
    assert engine.last_stats.robots_blocked == 1
    assert engine.last_stats.failed_urls == 1


def test_scraper_stats_include_cache_and_tier_success(monkeypatch) -> None:
    cache = _MemoryCache()
    cache.set("https://cached.example.com", "valid cached content with enough words for pass")
    engine = ScraperEngine(timeout_seconds=5, user_agent="ua", min_words_per_page=5, cache_db=cache)

    async def _fake_robots(urls: list[str], user_agent: str, timeout_seconds: int):
        _ = (user_agent, timeout_seconds)
        return type("Decision", (), {"allowed_urls": list(urls), "blocked_urls": []})()

    async def _fake_fetch_many(
        urls: list[str],
        timeout_seconds: int,
        user_agent: str,
        delay_min_seconds: int = 1,
        delay_max_seconds: int = 2,
    ) -> list[RawPage]:
        _ = (timeout_seconds, user_agent, delay_min_seconds, delay_max_seconds)
        return [
            RawPage(
                url=urls[0],
                html="<html><body><main>network path success with enough words to count tier one.</main></body></html>",
                status_code=200,
            )
        ]

    monkeypatch.setattr("backend.scraper.scraper_engine.filter_urls_by_robots", _fake_robots)
    monkeypatch.setattr("backend.scraper.scraper_engine.fetch_many", _fake_fetch_many)

    pages = asyncio.run(engine.scrape(["https://cached.example.com", "https://network.example.com"]))

    assert len(pages) == 2
    assert engine.last_stats.total_requested == 2
    assert engine.last_stats.cache_hits == 1
    assert engine.last_stats.tier1_success == 1
    assert engine.last_stats.failed_urls == 0


def test_scraper_escalates_on_bot_challenge(monkeypatch) -> None:
    engine = ScraperEngine(timeout_seconds=5, user_agent="ua", min_words_per_page=5)

    async def _fake_robots(urls: list[str], user_agent: str, timeout_seconds: int):
        _ = (user_agent, timeout_seconds)
        return type("Decision", (), {"allowed_urls": list(urls), "blocked_urls": []})()

    async def _fake_fetch_many(
        urls: list[str],
        timeout_seconds: int,
        user_agent: str,
        delay_min_seconds: int = 1,
        delay_max_seconds: int = 2,
    ) -> list[RawPage]:
        _ = (timeout_seconds, user_agent, delay_min_seconds, delay_max_seconds)
        return [
            RawPage(
                url=urls[0],
                html="<html><body>Attention Required! verify you are human</body></html>",
                status_code=200,
            )
        ]

    async def _fake_playwright(urls: list[str], timeout_seconds: int, user_agent: str) -> list[tuple[str, str]]:
        _ = (timeout_seconds, user_agent)
        return [
            (
                urls[0],
                "<html><body><main>Playwright bypassed challenge and returned rich content.</main></body></html>",
            )
        ]

    monkeypatch.setattr("backend.scraper.scraper_engine.filter_urls_by_robots", _fake_robots)
    monkeypatch.setattr("backend.scraper.scraper_engine.fetch_many", _fake_fetch_many)
    monkeypatch.setattr("backend.scraper.scraper_engine.scrape_with_playwright", _fake_playwright)
    monkeypatch.setattr("backend.scraper.scraper_engine.scrape_with_selenium_fallback", lambda urls: [])

    pages = asyncio.run(engine.scrape(["https://challenge.example.com"]))

    assert len(pages) == 1
    assert pages[0].tier == "playwright"
    assert engine.last_stats.bot_challenges >= 1
    assert engine.last_stats.tier2_attempted == 1
