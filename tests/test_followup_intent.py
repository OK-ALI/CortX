from __future__ import annotations

from backend.ai.followup_intent import FollowupIntentResolver


class _StubChains:
    def run_followup_resolution(self, query: str, conversation_context: str) -> str:
        _ = (query, conversation_context)
        return (
            '{'
            '"standalone_query":"latest updates about llama3.1 benchmarks",'
            '"requires_context":true,'
            '"update_intent":true,'
            '"context_focus":"llama3.1 benchmark results",'
            '"action_type":"update"'
            '}'
        )


class _DummyClient:
    pass


def test_followup_intent_resolver_uses_lcel(monkeypatch) -> None:
    monkeypatch.setattr("backend.ai.followup_intent.get_lcel_chains", lambda _client: _StubChains())

    resolver = FollowupIntentResolver()
    resolution = resolver.resolve(
        query="any new info on that?",
        conversation_messages=[
            {"role": "user", "content": "How is llama3.1 doing?"},
            {"role": "assistant", "content": "It is doing well on multiple benchmarks."},
        ],
        llm_client=_DummyClient(),  # type: ignore[arg-type]
        explicit_context={"action": "update", "preview": "llama3.1 benchmark results", "target_id": "x"},
    )

    assert resolution.requires_context is True
    assert resolution.update_intent is True
    assert resolution.action_type == "update"
    assert "latest updates" in resolution.standalone_query


def test_followup_intent_resolver_standalone_by_default() -> None:
    resolver = FollowupIntentResolver()
    resolution = resolver.resolve(
        query="any new info on that?",
        conversation_messages=[
            {"role": "user", "content": "How is llama3.1 doing?"},
            {"role": "assistant", "content": "It is doing well on multiple benchmarks."},
        ],
        llm_client=_DummyClient(),  # type: ignore[arg-type]
        explicit_context=None,
    )

    assert resolution.requires_context is False
    assert resolution.update_intent is False
    assert resolution.action_type == "ask"
    assert resolution.standalone_query == "any new info on that?"


def test_followup_intent_resolver_explicit_context_without_llm_uses_preview() -> None:
    resolver = FollowupIntentResolver()
    resolution = resolver.resolve(
        query="what changed?",
        conversation_messages=[
            {"role": "assistant", "content": "Release 1.2 shipped."},
        ],
        llm_client=None,
        explicit_context={"action": "update", "preview": "release 1.2 notes", "target_id": "msg-1"},
    )

    assert resolution.requires_context is True
    assert resolution.update_intent is True
    assert resolution.action_type == "update"
    assert "release 1.2 notes" in resolution.standalone_query
