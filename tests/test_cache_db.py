from __future__ import annotations

import sqlite3

from database.cache_db import CacheDB


def test_cache_db_get_fresh_respects_ttl(tmp_path) -> None:
    db_path = tmp_path / "cache.db"
    cache = CacheDB(str(db_path))

    cache.set("https://example.com", "fresh content")
    assert cache.get_fresh("https://example.com", max_age_seconds=60) == "fresh content"

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "UPDATE page_cache SET updated_at = datetime('now', '-2 days') WHERE url = ?",
            ("https://example.com",),
        )
        conn.commit()

    assert cache.get_fresh("https://example.com", max_age_seconds=60) is None


def test_cache_db_invalidate_stale_returns_count(tmp_path) -> None:
    db_path = tmp_path / "cache.db"
    cache = CacheDB(str(db_path))

    cache.set("https://fresh.example.com", "fresh")
    cache.set("https://stale.example.com", "stale")

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "UPDATE page_cache SET updated_at = datetime('now', '-2 days') WHERE url = ?",
            ("https://stale.example.com",),
        )
        conn.commit()

    removed = cache.invalidate_stale(max_age_seconds=60)

    assert removed == 1
    assert cache.get("https://fresh.example.com") == "fresh"
    assert cache.get("https://stale.example.com") is None
