"""Unified LanceDB store for page cache, conversations, and messages."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import lancedb
import pyarrow as pa


# ---------------------------------------------------------------------------
# Arrow schemas
# ---------------------------------------------------------------------------

_PAGE_CACHE_SCHEMA = pa.schema([
    pa.field("url", pa.utf8()),
    pa.field("content", pa.utf8()),
    pa.field("updated_at", pa.utf8()),
])

_CONVERSATIONS_SCHEMA = pa.schema([
    pa.field("id", pa.utf8()),
    pa.field("title", pa.utf8()),
    pa.field("created_at", pa.utf8()),
    pa.field("updated_at", pa.utf8()),
])

_MESSAGES_SCHEMA = pa.schema([
    pa.field("id", pa.utf8()),
    pa.field("conversation_id", pa.utf8()),
    pa.field("role", pa.utf8()),
    pa.field("content", pa.utf8()),
    pa.field("sources_json", pa.utf8()),
    pa.field("created_at", pa.utf8()),
])


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id() -> str:
    return uuid.uuid4().hex


class LanceStore:
    """Embedded LanceDB store for all CortX persistence."""

    def __init__(self, db_path: str = "database/cortx_lance") -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db = lancedb.connect(str(self._db_path))
        self._ensure_tables()

    # ------------------------------------------------------------------
    # Table bootstrapping
    # ------------------------------------------------------------------

    def _ensure_tables(self) -> None:
        existing = set(self._db.table_names())

        if "page_cache" not in existing:
            self._db.create_table("page_cache", schema=_PAGE_CACHE_SCHEMA)

        if "conversations" not in existing:
            self._db.create_table("conversations", schema=_CONVERSATIONS_SCHEMA)

        if "messages" not in existing:
            self._db.create_table("messages", schema=_MESSAGES_SCHEMA)

    # ------------------------------------------------------------------
    # Page cache (replaces old SQLite cache_db)
    # ------------------------------------------------------------------

    def cache_get(self, url: str) -> str | None:
        tbl = self._db.open_table("page_cache")
        try:
            rows = tbl.search().where(f"url = '{_esc(url)}'").limit(1).to_list()
        except Exception:
            return None
        return rows[0]["content"] if rows else None

    def cache_get_fresh(self, url: str, max_age_seconds: int) -> str | None:
        tbl = self._db.open_table("page_cache")
        try:
            rows = tbl.search().where(f"url = '{_esc(url)}'").limit(1).to_list()
        except Exception:
            return None
        if not rows:
            return None

        stored_at = datetime.fromisoformat(rows[0]["updated_at"])
        age = (datetime.now(timezone.utc) - stored_at).total_seconds()
        if age > max_age_seconds:
            return None
        return rows[0]["content"]

    def cache_set(self, url: str, content: str) -> None:
        tbl = self._db.open_table("page_cache")
        # Remove old entry if present, then insert fresh
        try:
            tbl.delete(f"url = '{_esc(url)}'")
        except Exception:
            pass
        tbl.add([{"url": url, "content": content, "updated_at": _now_iso()}])

    def cache_invalidate_stale(self, max_age_seconds: int) -> int:
        tbl = self._db.open_table("page_cache")
        cutoff = datetime.now(timezone.utc)
        try:
            rows = tbl.search().where("url IS NOT NULL").limit(10_000).to_list()
        except Exception:
            return 0
        stale_urls = []
        for row in rows:
            stored_at = datetime.fromisoformat(row["updated_at"])
            if (cutoff - stored_at).total_seconds() > max_age_seconds:
                stale_urls.append(row["url"])
        for url in stale_urls:
            try:
                tbl.delete(f"url = '{_esc(url)}'")
            except Exception:
                pass
        return len(stale_urls)

    # ------------------------------------------------------------------
    # Conversations
    # ------------------------------------------------------------------

    def create_conversation(self, title: str = "New Chat") -> str:
        cid = _new_id()
        now = _now_iso()
        tbl = self._db.open_table("conversations")
        tbl.add([{"id": cid, "title": title, "created_at": now, "updated_at": now}])
        return cid

    def rename_conversation(self, conversation_id: str, new_title: str) -> None:
        tbl = self._db.open_table("conversations")
        tbl.update(
            where=f"id = '{_esc(conversation_id)}'",
            values={"title": new_title, "updated_at": _now_iso()},
        )

    def delete_conversation(self, conversation_id: str) -> None:
        self._db.open_table("conversations").delete(f"id = '{_esc(conversation_id)}'")
        self._db.open_table("messages").delete(
            f"conversation_id = '{_esc(conversation_id)}'"
        )

    def list_conversations(self) -> list[dict[str, Any]]:
        tbl = self._db.open_table("conversations")
        try:
            rows = tbl.search().where("id IS NOT NULL").limit(500).to_list()
        except Exception:
            return []
        # Sort newest-first
        rows.sort(key=lambda r: r.get("updated_at", ""), reverse=True)
        return [
            {
                "id": r["id"],
                "title": r["title"],
                "created_at": r["created_at"],
                "updated_at": r["updated_at"],
            }
            for r in rows
        ]

    # ------------------------------------------------------------------
    # Messages
    # ------------------------------------------------------------------

    def add_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        sources: list[str] | None = None,
    ) -> str:
        mid = _new_id()
        now = _now_iso()
        tbl = self._db.open_table("messages")
        tbl.add([
            {
                "id": mid,
                "conversation_id": conversation_id,
                "role": role,
                "content": content,
                "sources_json": json.dumps(sources or []),
                "created_at": now,
            }
        ])
        # Touch conversation updated_at
        try:
            conv_tbl = self._db.open_table("conversations")
            conv_tbl.update(
                where=f"id = '{_esc(conversation_id)}'",
                values={"updated_at": now},
            )
        except Exception:
            pass
        return mid

    def get_messages(self, conversation_id: str) -> list[dict[str, Any]]:
        tbl = self._db.open_table("messages")
        try:
            rows = (
                tbl.search()
                .where(f"conversation_id = '{_esc(conversation_id)}'")
                .limit(1000)
                .to_list()
            )
        except Exception:
            return []
        rows.sort(key=lambda r: r.get("created_at", ""))
        return [
            {
                "id": r["id"],
                "role": r["role"],
                "content": r["content"],
                "sources": json.loads(r.get("sources_json", "[]")),
                "created_at": r["created_at"],
            }
            for r in rows
        ]


def _esc(value: str) -> str:
    """Escape single quotes for LanceDB SQL-like predicates."""
    return value.replace("'", "''")
