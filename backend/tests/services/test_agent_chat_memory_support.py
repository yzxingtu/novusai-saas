from __future__ import annotations

from types import SimpleNamespace

from app.ai.engine.types import ExecutionRequest
from app.services.ai.agent_chat_memory_support import prepare_request_memory_startup


def _make_request(
    *,
    memory_scene: str = "conversation",
    memory_channel: str = "system",
    memory_source: str = "conversation",
    memory_enabled: bool = True,
    long_term_memory_enabled: bool = False,
) -> ExecutionRequest:
    return ExecutionRequest(
        agent_id=1,
        tenant_id=1,
        user_id=10,
        conversation_id=100,
        memory_scene=memory_scene,
        memory_channel=memory_channel,
        memory_source=memory_source,
        memory_enabled=memory_enabled,
        long_term_memory_enabled=long_term_memory_enabled,
    )


def test_prepare_request_memory_startup_normalizes_thread_snapshot_and_preserves_pollution():
    request = _make_request(
        memory_scene="ai_chat_page",
        memory_channel="tenant_chat",
        memory_source="ai_chat_page",
        memory_enabled=True,
        long_term_memory_enabled=False,
    )
    conversation = SimpleNamespace(
        metadata_={
            "thread_memory_state": {
                "scene": "  thread-scene  ",
                "channel": "  tenant_chat  ",
                "source": "  thread-source  ",
                "session_memory_runtime_enabled": 1,
                "session_memory_read_enabled": 1,
                "session_memory_write_enabled": 0,
                "long_term_memory_runtime_enabled": 1,
                "long_term_memory_recall_enabled": 0,
                "long_term_memory_capture_enabled": 1,
                "memory_context_enabled": 1,
                "external_context_polluted": 1,
                "external_context_reason": "  tool:web_search  ",
                "updated_at": " 2026-04-21T10:00:00Z  ",
                "ignored_key": "drop-me",
            }
        }
    )

    startup = prepare_request_memory_startup(
        request=request,
        conversation=conversation,
    )

    assert startup.thread_memory_state == {
        "scene": "thread-scene",
        "channel": "tenant_chat",
        "source": "thread-source",
        "session_memory_runtime_enabled": True,
        "session_memory_read_enabled": True,
        "session_memory_write_enabled": False,
        "session_memory_state": "enabled",
        "long_term_memory_runtime_enabled": True,
        "long_term_memory_recall_enabled": False,
        "long_term_memory_recall_state": "suppressed_external_context",
        "long_term_memory_capture_enabled": False,
        "long_term_memory_capture_state": "suppressed_external_context",
        "memory_context_enabled": True,
        "thread_memory_owner_state": "polluted",
        "thread_memory_owner_reason": "tool:web_search",
        "external_context_polluted": True,
        "external_context_reason": "tool:web_search",
        "updated_at": "2026-04-21T10:00:00Z",
    }
    assert startup.request_memory_runtime_policy["scene"] == "ai_chat_page"
    assert startup.request_memory_runtime_policy["channel"] == "tenant_chat"
    assert startup.request_memory_runtime_policy["source"] == "ai_chat_page"
    assert startup.request_memory_runtime_policy["session_memory_state"] == "enabled"
    assert (
        startup.request_memory_runtime_policy["thread_memory_owner_state"] == "polluted"
    )
    assert (
        startup.request_memory_runtime_policy["thread_memory_owner_reason"]
        == "tool:web_search"
    )
    assert startup.request_memory_runtime_policy["external_context_polluted"] is True
    assert (
        startup.request_memory_runtime_policy["external_context_reason"]
        == "tool:web_search"
    )
    assert (
        startup.request_memory_runtime_policy["session_memory_runtime_enabled"] is True
    )
    assert (
        startup.request_memory_runtime_policy["long_term_memory_runtime_enabled"]
        is False
    )
    assert (
        startup.request_memory_runtime_policy["long_term_memory_recall_state"]
        == "disabled"
    )
    assert (
        startup.request_memory_runtime_policy["long_term_memory_capture_state"]
        == "disabled"
    )
    assert "updated_at" not in startup.request_memory_runtime_policy
    assert request.memory_runtime_policy == startup.request_memory_runtime_policy


def test_prepare_request_memory_startup_lets_request_flags_override_thread_runtime_state():
    request = _make_request(
        memory_scene="admin_chat",
        memory_channel="admin_chat",
        memory_source="admin_chat",
        memory_enabled=False,
        long_term_memory_enabled=True,
    )

    startup = prepare_request_memory_startup(
        request=request,
        thread_memory_state={
            "session_memory_runtime_enabled": True,
            "long_term_memory_runtime_enabled": False,
            "external_context_polluted": True,
            "external_context_reason": "tool:web_search",
        },
    )

    assert startup.request_memory_runtime_policy["scene"] == "admin_chat"
    assert startup.request_memory_runtime_policy["channel"] == "admin_chat"
    assert startup.request_memory_runtime_policy["source"] == "admin_chat"
    assert (
        startup.request_memory_runtime_policy["session_memory_runtime_enabled"] is False
    )
    assert (
        startup.request_memory_runtime_policy["long_term_memory_runtime_enabled"]
        is True
    )
    assert startup.request_memory_runtime_policy["session_memory_state"] == "disabled"
    assert (
        startup.request_memory_runtime_policy["long_term_memory_recall_state"]
        == "suppressed_external_context"
    )
    assert (
        startup.request_memory_runtime_policy["long_term_memory_capture_state"]
        == "suppressed_external_context"
    )
    assert (
        startup.request_memory_runtime_policy["thread_memory_owner_state"] == "polluted"
    )
    assert (
        startup.request_memory_runtime_policy["thread_memory_owner_reason"]
        == "tool:web_search"
    )
    assert startup.request_memory_runtime_policy["external_context_polluted"] is True
    assert (
        startup.request_memory_runtime_policy["external_context_reason"]
        == "tool:web_search"
    )
    assert request.memory_runtime_policy == startup.request_memory_runtime_policy
