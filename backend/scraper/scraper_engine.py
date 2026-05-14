from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from backend.scraper.bs4_parser import extract_visible_text
from backend.scraper.httpx_scraper import fetch_many
from backend.scraper.playwright_scraper import scrape_with_playwright
from backend.scraper.robots_guard import filter_urls_by_robots
from backend.scraper.selenium_scraper import scrape_with_selenium_fallback


@dataclass
class ScrapedPage:
    url: str
    text: str
    tier: str


@dataclass
class ScrapeStats:
    total_requested: int = 0
    cache_hits: int = 0
    robots_blocked: int = 0
    bot_challenges: int = 0
    tier2_attempted: int = 0
    tier3_attempted: int = 0
    tier1_success: int = 0
    tier2_success: int = 0
    tier3_success: int = 0
    failed_urls: int = 0


class CacheProtocol(Protocol):
    def cache_get(self, url: str) -> str | None:
        ...

    def cache_get_fresh(self, url: str, max_age_seconds: int) -> str | None:
        ...

    def cache_set(self, url: str, content: str) -> None:
        ...


class ScraperEngine:
    def __init__(
        self,
        timeout_seconds: int,
        user_agent: str,
        min_words_per_page: int,
        cache_db: CacheProtocol | None = None,
        cache_ttl_seconds: int = 86400,
        delay_min_seconds: int = 1,
        delay_max_seconds: int = 2,
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self.user_agent = user_agent
        self.min_words_per_page = min_words_per_page
        self.cache_db = cache_db
        self.cache_ttl_seconds = cache_ttl_seconds
        self.delay_min_seconds = delay_min_seconds
        self.delay_max_seconds = delay_max_seconds
        self.last_stats = ScrapeStats()

    def _is_valid_text(self, text: str) -> bool:
        return len(text.split()) >= self.min_words_per_page

    def _looks_like_bot_challenge(self, text: str, html: str) -> bool:
        payload = f"{text}\n{html}".lower()
        patterns = [
            "captcha",
            "verify you are human",
            "attention required",
            "cloudflare",
            "access denied",
            "bot detection",
        ]
        return any(pattern in payload for pattern in patterns)

    def _cache_get(self, url: str) -> str | None:
        if self.cache_db is None:
            return None
        try:
            return self.cache_db.cache_get_fresh(url, self.cache_ttl_seconds)
        except Exception:  # noqa: BLE001
            return None

    def _cache_set(self, url: str, text: str) -> None:
        if self.cache_db is None:
            return
        try:
            self.cache_db.cache_set(url, text)
        except Exception:  # noqa: BLE001
            return

    async def scrape(self, urls: list[str]) -> list[ScrapedPage]:
        self.last_stats = ScrapeStats(total_requested=len(urls))
        pages: list[ScrapedPage] = []
        seen_success_urls: set[str] = set()
        uncached_urls: list[str] = []

        for url in urls:
            cached_text = self._cache_get(url)
            if cached_text and self._is_valid_text(cached_text):
                pages.append(ScrapedPage(url=url, text=cached_text, tier="cache"))
                seen_success_urls.add(url)
                self.last_stats.cache_hits += 1
            else:
                uncached_urls.append(url)

        if not uncached_urls:
            self.last_stats.failed_urls = max(self.last_stats.total_requested - len(seen_success_urls), 0)
            return pages

        robots_decision = await filter_urls_by_robots(
            uncached_urls,
            user_agent=self.user_agent,
            timeout_seconds=self.timeout_seconds,
        )
        self.last_stats.robots_blocked += len(robots_decision.blocked_urls)
        allowed_urls = robots_decision.allowed_urls

        if not allowed_urls:
            self.last_stats.failed_urls = max(self.last_stats.total_requested - len(seen_success_urls), 0)
            return pages

        raw_pages = await fetch_many(
            urls=allowed_urls,
            timeout_seconds=self.timeout_seconds,
            user_agent=self.user_agent,
            delay_min_seconds=self.delay_min_seconds,
            delay_max_seconds=self.delay_max_seconds,
        )

        tier2_urls: list[str] = []

        for page in raw_pages:
            if page.status_code in {0, 403, 429} or page.status_code >= 500:
                tier2_urls.append(page.url)
                continue

            if page.status_code >= 400:
                continue

            text = extract_visible_text(page.html)
            if self._looks_like_bot_challenge(text, page.html):
                self.last_stats.bot_challenges += 1
                tier2_urls.append(page.url)
                continue

            if not self._is_valid_text(text):
                tier2_urls.append(page.url)
                continue

            pages.append(ScrapedPage(url=page.url, text=text, tier="httpx"))
            seen_success_urls.add(page.url)
            self._cache_set(page.url, text)
            self.last_stats.tier1_success += 1

        tier2_urls = [url for url in tier2_urls if url not in seen_success_urls]
        if tier2_urls:
            self.last_stats.tier2_attempted += len(tier2_urls)
            tier2_rendered = await scrape_with_playwright(
                urls=tier2_urls,
                timeout_seconds=self.timeout_seconds,
                user_agent=self.user_agent,
            )

            tier3_urls: list[str] = []
            for url, html in tier2_rendered:
                text = extract_visible_text(html)
                if self._looks_like_bot_challenge(text, html):
                    self.last_stats.bot_challenges += 1
                    tier3_urls.append(url)
                    continue

                if not self._is_valid_text(text):
                    tier3_urls.append(url)
                    continue
                pages.append(ScrapedPage(url=url, text=text, tier="playwright"))
                seen_success_urls.add(url)
                self._cache_set(url, text)
                self.last_stats.tier2_success += 1

            tier3_urls = [url for url in tier3_urls if url not in seen_success_urls]
            # Tier 3 (Selenium) disabled — too slow and rarely succeeds.
            # tier3 URLs are counted as failures below.

        self.last_stats.failed_urls = max(self.last_stats.total_requested - len(seen_success_urls), 0)

        return pages
