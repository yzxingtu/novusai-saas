from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.ai.engine.types import ExecutionResult
from app.core.i18n import _
from app.services.ai.agent_chat_error_surface import build_stream_error_display
from app.services.ai.conversation_stream_persistence_service import (
    ConversationStreamPersistenceService,
)


def _build_result(*, success: bool = False, output: str = "", error: str = "boom"):
    return ExecutionResult(
        success=success,
        output=output,
        messages=[],
        tool_results=[],
        total_tokens=12,
        duration_ms=45,
        conversation_id=99,
        error=error,
        partial=bool(output),
        interrupted=False,
        completion_reason="error" if not success else "completed",
        rag_sources=None,
        rag_source_kinds=[],
        context_compacted=False,
        memory_flush_triggered=False,
        memory_recalled=False,
        prune_stats=None,
        tool_planner=None,
    )


@pytest.mark.asyncio
async def test_persist_stream_completion_delegates_to_service_methods():
    conversation = SimpleNamespace(id=99, metadata_={}, agent=None)
    service = MagicMock()
    service.repo.get_by_id = AsyncMock(return_value=conversation)
    service.persist_chat_messages = AsyncMock(return_value=([], 3))
    service.update_stats = AsyncMock()
    service.db.commit = AsyncMock()

    stream_service = ConversationStreamPersistenceService(service)

    persisted = await stream_service.persist_stream_completion(
        conversation_id=99,
        result=_build_result(success=True, output="done"),
        history_count=2,
        agent_id=7,
        context_diagnostics={"ok": True},
        last_run_summary={"done": True},
        current_agent=SimpleNamespace(id=7),
    )

    assert persisted == 3
    service.persist_chat_messages.assert_awaited_once()
    service.update_stats.assert_awaited_once()
    service.db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_save_stream_error_message_persists_user_and_error_rows():
    conversation = SimpleNamespace(id=99, metadata_={}, message_count=1)
    service = MagicMock()
    service.repo.get_by_id = AsyncMock(return_value=conversation)
    service.message_repo.count_by_conversation = AsyncMock(return_value=1)
    service.message_repo.get_next_sequence = AsyncMock(return_value=2)
    service.message_repo.create = AsyncMock()
    service.db.commit = AsyncMock()

    stream_service = ConversationStreamPersistenceService(service)

    rows = await stream_service.save_stream_error_message(
        conversation_id=99,
        tenant_id=1,
        agent_id=7,
        error_text="fallback",
        user_message="hello",
        result=_build_result(output="partial"),
        context_diagnostics_payload={"persistence_error": True},
        last_run_summary_payload={"turn_outcome": "failed"},
        persist_user_message=True,
        build_stream_error_display=lambda *_args, **_kwargs: {
            "message": "friendly",
            "debug_message": "dbg",
            "error_only": True,
            "trace_id": "trace-1",
            "error_type": "stream_execution_error",
        },
    )

    assert rows == 2
    assert service.message_repo.create.await_count == 2
    assert conversation.message_count == 3
    service.db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_save_stream_error_message_persists_turn_flow_context_for_failed_streams():
    conversation = SimpleNamespace(id=99, metadata_={}, message_count=0)
    service = MagicMock()
    service.repo.get_by_id = AsyncMock(return_value=conversation)
    service.message_repo.count_by_conversation = AsyncMock(return_value=0)
    service.message_repo.get_next_sequence = AsyncMock(return_value=1)
    service.message_repo.create = AsyncMock()
    service.db.commit = AsyncMock()

    result = _build_result(output="我先把已完成部分整理给你：这部分。")
    result.completion_reason = "provider_error"
    result.provider_failure_kind = "provider_http_5xx"
    result.turn_record = {
        "turn_outcome": "partial",
        "termination_reason": "provider_error",
        "protocol_path": "responses",
        "selected_tool_names": ["crm_list_actions"],
        "turn_flow": {
            "completion_reason": "provider_error",
            "timeline": [
                {
                    "id": "thinking",
                    "type": "thinking",
                    "status": "completed",
                    "title": "Thinking",
                    "summary": "Reasoning summary generated",
                },
                {
                    "id": "tool_selection",
                    "type": "tool_selection",
                    "status": "completed",
                    "title": "Tool Selection",
                    "summary": "Selected 1 of 1 tools",
                },
                {
                    "id": "tool_execution",
                    "type": "tool_execution",
                    "status": "completed",
                    "title": "Tool Execution",
                    "summary": "Executed 1 tool call",
                    "tool_call_ids": ["call_1"],
                },
                {
                    "id": "answer_assembly",
                    "type": "answer_assembly",
                    "status": "error",
                    "title": "Answer Assembly",
                    "summary": "Answer assembly failed",
                },
                {
                    "id": "failed",
                    "type": "failed",
                    "status": "error",
                    "title": "Failed",
                    "summary": "provider_error",
                },
            ],
            "answer_card": {
                "summary": "我先把已完成部分整理给你：这部分。",
                "sections": [
                    {
                        "id": "final_answer",
                        "title": "Answer",
                        "content": "我先把已完成部分整理给你：这部分。",
                    }
                ],
            },
        },
    }

    stream_service = ConversationStreamPersistenceService(service)

    rows = await stream_service.save_stream_error_message(
        conversation_id=99,
        tenant_id=1,
        agent_id=7,
        error_text="fallback",
        user_message="hello",
        result=result,
        context_diagnostics_payload=None,
        last_run_summary_payload=None,
        persist_user_message=False,
        build_stream_error_display=lambda *_args, **_kwargs: {
            "message": "friendly",
            "debug_message": "dbg",
            "error_only": True,
            "trace_id": "trace-1",
            "error_type": "provider_http_5xx",
        },
    )

    assert rows == 1
    payload = service.message_repo.create.await_args_list[0].args[0]
    assert payload["metadata_"]["completion_reason"] == "provider_error"
    assert payload["metadata_"]["provider_failure_kind"] == "provider_http_5xx"
    assert payload["metadata_"]["turn_record"]["selected_tool_names"] == [
        "crm_list_actions"
    ]
    assert payload["metadata_"]["turn_flow"]["timeline"][2]["type"] == "tool_execution"
    assert payload["metadata_"]["turn_flow"]["timeline"][2]["status"] == "completed"
    assert (
        payload["metadata_"]["turn_flow"]["answer_card"]["summary"]
        == "我先把已完成部分整理给你：这部分。"
    )
    service.db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_save_stream_error_message_persists_memory_runtime_owner_snapshot():
    conversation = SimpleNamespace(id=99, metadata_={}, message_count=0)
    service = MagicMock()
    service.repo.get_by_id = AsyncMock(return_value=conversation)
    service.message_repo.count_by_conversation = AsyncMock(return_value=0)
    service.message_repo.get_next_sequence = AsyncMock(return_value=1)
    service.message_repo.create = AsyncMock()
    service.db.commit = AsyncMock()

    result = _build_result(output="partial")
    result.memory_runtime_policy = {
        "scene": "ai_chat_page",
        "channel": "tenant_chat",
        "source": "ai_chat_page",
        "session_memory_runtime_enabled": True,
        "session_memory_read_enabled": True,
        "session_memory_write_enabled": True,
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
    }

    stream_service = ConversationStreamPersistenceService(service)

    rows = await stream_service.save_stream_error_message(
        conversation_id=99,
        tenant_id=1,
        agent_id=7,
        error_text="fallback",
        user_message="hello",
        result=result,
        context_diagnostics_payload=None,
        last_run_summary_payload=None,
        persist_user_message=False,
        build_stream_error_display=lambda *_args, **_kwargs: {
            "message": "friendly",
            "debug_message": "dbg",
            "error_only": True,
            "trace_id": "trace-1",
            "error_type": "stream_execution_error",
        },
    )

    assert rows == 1
    payload = service.message_repo.create.await_args_list[0].args[0]
    assert (
        payload["metadata_"]["memory_runtime_policy"]["external_context_polluted"]
        is True
    )
    assert payload["metadata_"]["memory_runtime_policy"][
        "thread_memory_owner_state"
    ] == ("polluted")
    assert (
        conversation.metadata_["thread_memory_state"]["external_context_polluted"]
        is True
    )
    assert conversation.metadata_["thread_memory_state"][
        "thread_memory_owner_state"
    ] == ("polluted")
    assert conversation.metadata_["thread_memory_state"]["updated_at"]
    service.db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_save_stream_error_message_scrubs_html_provider_failure_from_public_metadata():
    conversation = SimpleNamespace(id=99, metadata_={}, message_count=0)
    service = MagicMock()
    service.repo.get_by_id = AsyncMock(return_value=conversation)
    service.message_repo.count_by_conversation = AsyncMock(return_value=0)
    service.message_repo.get_next_sequence = AsyncMock(return_value=1)
    service.message_repo.create = AsyncMock()
    service.db.commit = AsyncMock()

    result = _build_result(
        error="<!DOCTYPE html><html><body>Bad gateway<div>Cloudflare Ray ID</div></body></html>"
    )
    result.provider_failure_kind = "provider_http_5xx"

    stream_service = ConversationStreamPersistenceService(service)

    rows = await stream_service.save_stream_error_message(
        conversation_id=99,
        tenant_id=1,
        agent_id=7,
        error_text="fallback",
        user_message="hello",
        result=result,
        context_diagnostics_payload=None,
        last_run_summary_payload=None,
        persist_user_message=False,
        build_stream_error_display=build_stream_error_display,
    )

    assert rows == 1
    payload = service.message_repo.create.await_args_list[0].args[0]
    assert payload["content"] == _("ai.error.provider_server_error")
    assert payload["metadata_"]["error_message"] == _(
        "ai.error.provider_server_error"
    )
    assert payload["metadata_"]["error_debug_message"] == _(
        "ai.error.provider_server_error"
    )
    assert payload["metadata_"]["raw_error_message"] == _(
        "ai.error.provider_server_error"
    )
    assert conversation.metadata_["last_error"]["friendly_message"] == _(
        "ai.error.provider_server_error"
    )
    assert conversation.metadata_["last_error"]["error_message"] == _(
        "ai.error.provider_server_error"
    )
    assert "Cloudflare Ray ID" not in str(conversation.metadata_)
    service.db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_persist_stream_last_error_marker_updates_conversation_metadata():
    conversation = SimpleNamespace(id=99, metadata_={})
    service = MagicMock()
    service.repo.get_by_id = AsyncMock(return_value=conversation)
    service.db.commit = AsyncMock()

    stream_service = ConversationStreamPersistenceService(service)

    saved = await stream_service.persist_stream_last_error_marker(
        conversation_id=99,
        error_type="stream_failure",
        error_message="provider timeout",
        friendly_message="timeout",
        partial=True,
        extra_payload={"stage": "persist"},
        memory_runtime_policy={
            "scene": "ai_chat_page",
            "channel": "tenant_chat",
            "source": "ai_chat_page",
            "external_context_polluted": True,
            "external_context_reason": "tool:web_search",
            "session_memory_runtime_enabled": True,
            "session_memory_state": "enabled",
            "thread_memory_owner_state": "polluted",
            "thread_memory_owner_reason": "tool:web_search",
        },
    )

    assert saved is True
    assert conversation.metadata_["last_error"]["error_type"] == "stream_failure"
    assert conversation.metadata_["last_error"]["partial"] is True
    assert (
        conversation.metadata_["thread_memory_state"]["external_context_polluted"]
        is True
    )
    assert conversation.metadata_["thread_memory_state"][
        "thread_memory_owner_state"
    ] == ("polluted")
    assert conversation.metadata_["thread_memory_state"]["updated_at"]
    service.db.commit.assert_awaited_once()
