from __future__ import annotations

import asyncio
from dataclasses import dataclass
import random
import time
from urllib.parse import urlsplit

import httpx

from backend.utils.rate_limiter import polite_delay
from backend.utils.user_agent import get_random_user_agent


@dataclass
class RawPage:
    url: str
    html: str
    status_code: int
    error: str | None = None


RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
MAX_RETRIES = 1
BASE_BACKOFF_SECONDS = 0.3
MIN_DOMAIN_INTERVAL_SECONDS = 0.5


async def fetch_url(url: str, timeout_seconds: int, user_agent: str) -> RawPage | None:
    headers = {"User-Agent": user_agent}
    timeout = httpx.Timeout(timeout_seconds)
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True, headers=headers) as client:
        last_error: str | None = None
        for attempt in range(MAX_RETRIES + 1):
            try:
                response = await client.get(url)
                if response.status_code in RETRYABLE_STATUS_CODES and attempt < MAX_RETRIES:
                    backoff = BASE_BACKOFF_SECONDS * (2**attempt) + random.uniform(0.0, 0.2)
                    await asyncio.sleep(backoff)
                    continue
                return RawPage(url=url, html=response.text, status_code=response.status_code)
            except Exception as exc:  # noqa: BLE001
                last_error = str(exc)
                if attempt < MAX_RETRIES:
                    backoff = BASE_BACKOFF_SECONDS * (2**attempt) + random.uniform(0.0, 0.2)
                    await asyncio.sleep(backoff)
                    continue
                return RawPage(url=url, html="", status_code=0, error=last_error)

        return RawPage(url=url, html="", status_code=0, error=last_error)


async def fetch_many(
    urls: list[str],
    timeout_seconds: int,
    user_agent: str,
    delay_min_seconds: int = 0,
    delay_max_seconds: int = 0,
    max_concurrent: int = 4,
) -> list[RawPage]:
    """Fetch URLs concurrently (up to max_concurrent at once)."""
    sem = asyncio.Semaphore(max_concurrent)
    results: list[RawPage | None] = [None] * len(urls)

    async def _fetch_one(idx: int, url: str) -> None:
        async with sem:
            request_ua = get_random_user_agent(user_agent)
            page = await fetch_url(url, timeout_seconds, request_ua)
            results[idx] = page

    tasks = [_fetch_one(i, url) for i, url in enumerate(urls)]
    await asyncio.gather(*tasks)

    return [p for p in results if p is not None]

