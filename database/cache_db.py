from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Optional


class CacheDB:
    def __init__(self, db_path: str = "database/cortx_cache.db") -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _initialize(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS page_cache (
                    url TEXT PRIMARY KEY,
                    content TEXT NOT NULL,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.commit()

    def get(self, url: str) -> Optional[str]:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute("SELECT content FROM page_cache WHERE url = ?", (url,)).fetchone()
            return row[0] if row else None

    def get_fresh(self, url: str, max_age_seconds: int) -> Optional[str]:
        """Return cached content only if it is within the allowed age."""
        ttl_clause = f"-{max(max_age_seconds, 0)} seconds"
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                """
                SELECT content
                FROM page_cache
                WHERE url = ?
                  AND updated_at >= datetime('now', ?)
                """,
                (url, ttl_clause),
            ).fetchone()
            return row[0] if row else None

    def invalidate_stale(self, max_age_seconds: int) -> int:
        """Delete cache entries older than max_age_seconds and return deleted row count."""
        ttl_clause = f"-{max(max_age_seconds, 0)} seconds"
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                DELETE FROM page_cache
                WHERE updated_at < datetime('now', ?)
                """,
                (ttl_clause,),
            )
            conn.commit()
            return cursor.rowcount

    def set(self, url: str, content: str) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO page_cache (url, content, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(url) DO UPDATE SET
                    content = excluded.content,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (url, content),
            )
            conn.commit()
