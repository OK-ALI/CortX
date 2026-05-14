from __future__ import annotations

import asyncio
import random


async def polite_delay(min_seconds: int, max_seconds: int) -> None:
    """Inject a short randomized delay between requests."""
    wait_seconds = random.uniform(min_seconds, max_seconds)
    await asyncio.sleep(wait_seconds)
