from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from backend.ai.json_utils import extract_json_object
from backend.ai.lcel_chains import get_lcel_chains
from backend.ai.llm_manager import OllamaClient


@dataclass
class FollowupResolution:
    standalone_query: str
    requires_context: bool
    update_intent: bool
    context_focus: str
    action_type: str


class FollowupIntentResolver:
    """Dynamic follow-up resolver backed by the local LCEL follow-up chain."""

    def build_conversation_context(self, conversation_messages: list[dict], max_items: int = 8) -> str:
        recent = conversation_messages[-max_items:]
        lines: list[str] = []
        for item in reversed(recent):
            role = str(item.get("role", "user")).strip().lower() or "user"
            content = " ".join(str(item.get("content", "")).split()).strip()
            if not content:
                continue
            lines.append(f"{role}: {content[:320]}")
        return "\n".join(lines)

    def resolve(
        self,
        query: str,
        conversation_messages: list[dict] | None,
        llm_client: OllamaClient | None,
        explicit_context: dict[str, Any] | None = None,
    ) -> FollowupResolution:
        query_clean = " ".join(query.split()).strip() or query
        # Standalone-by-default: context is used only when explicitly selected in UI.
        if not explicit_context:
            return FollowupResolution(
                standalone_query=query_clean,
                requires_context=False,
                update_intent=False,
                context_focus="",
                action_type="ask",
            )

        action_type = str(explicit_context.get("action", "ask")).strip().lower() or "ask"
        if action_type not in {"ask", "reply", "follow", "update"}:
            action_type = "ask"
        preview = " ".join(str(explicit_context.get("preview", "")).split()).strip()
        
        # If user selected specific text, completely bypass LLM context resolution 
        # to guarantee the specific text is targeted.
        if preview:
            if query_clean:
                standalone = f"{query_clean} (Context: '{preview}')"
            else:
                standalone = f"Target: '{preview}'"
            return FollowupResolution(
                standalone_query=standalone,
                requires_context=True,
                update_intent=action_type == "update",
                context_focus=preview,
                action_type=action_type,
            )

        if llm_client is None:
            fallback_query = query_clean if not preview else f"{query_clean} {preview}".strip()
            return FollowupResolution(
                standalone_query=fallback_query,
                requires_context=bool(preview),
                update_intent=action_type == "update",
                context_focus=preview,
                action_type=action_type,
            )

        if not conversation_messages:
            context_text = preview
        else:
            context_text = self.build_conversation_context(conversation_messages)
            if preview:
                context_text = f"selected_context: {preview}\n{context_text}".strip()

        if not context_text:
            return FollowupResolution(
                standalone_query=query_clean,
                requires_context=bool(preview),
                update_intent=action_type == "update",
                context_focus=preview,
                action_type=action_type,
            )

        try:
            raw = get_lcel_chains(llm_client).run_followup_resolution(
                query=query_clean,
                conversation_context=context_text,
            )
            data = extract_json_object(raw)
            standalone = " ".join(str(data.get("standalone_query", query_clean)).split()).strip() or query_clean
            context_focus = " ".join(str(data.get("context_focus", "")).split()).strip()
            resolved_action = str(data.get("action_type", action_type)).strip().lower() or action_type
            if resolved_action not in {"ask", "reply", "follow", "update"}:
                resolved_action = action_type
            return FollowupResolution(
                standalone_query=standalone,
                requires_context=bool(data.get("requires_context", False)) or standalone != query_clean,
                update_intent=bool(data.get("update_intent", False)) or resolved_action == "update",
                context_focus=context_focus or preview,
                action_type=resolved_action,
            )
        except Exception:
            return FollowupResolution(
                standalone_query=query_clean if not preview else f"{query_clean} {preview}".strip(),
                requires_context=bool(preview),
                update_intent=action_type == "update",
                context_focus=preview,
                action_type=action_type,
            )
