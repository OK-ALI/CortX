from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

import httpx


@dataclass
class RobotsDecision:
    allowed_urls: list[str]
    blocked_urls: list[str]


async def filter_urls_by_robots(
    urls: list[str],
    user_agent: str,
    timeout_seconds: int,
) -> RobotsDecision:
    """Filter URLs according to robots.txt policy, allowing on fetch/parsing failures."""
    if not urls:
        return RobotsDecision(allowed_urls=[], blocked_urls=[])

    parser_by_origin: dict[str, RobotFileParser | None] = {}
    allowed: list[str] = []
    blocked: list[str] = []

    timeout = httpx.Timeout(timeout_seconds)
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        for url in urls:
            parts = urlsplit(url)
            origin = f"{parts.scheme}://{parts.netloc}".lower()

            if origin not in parser_by_origin:
                robots_url = f"{origin}/robots.txt"
                try:
                    response = await client.get(robots_url)
                    if response.status_code >= 400:
                        parser_by_origin[origin] = None
                    else:
                        parser = RobotFileParser()
                        parser.parse(response.text.splitlines())
                        parser_by_origin[origin] = parser
                except Exception:  # noqa: BLE001
                    parser_by_origin[origin] = None

            parser = parser_by_origin[origin]
            if parser is None:
                allowed.append(url)
                continue

            can_fetch = parser.can_fetch(user_agent, url)
            if can_fetch:
                allowed.append(url)
            else:
                blocked.append(url)

    return RobotsDecision(allowed_urls=allowed, blocked_urls=blocked)
