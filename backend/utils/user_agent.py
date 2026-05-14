from __future__ import annotations

from fake_useragent import UserAgent


def get_random_user_agent(default_agent: str) -> str:
    """Return a randomized user agent string with safe fallback."""
    try:
        return UserAgent().random
    except Exception:
        return default_agent
