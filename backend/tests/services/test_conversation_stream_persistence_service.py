from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.ai.engine.types import ExecutionResult
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
        route_source="mention",
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
    )

    assert saved is True
    assert conversation.metadata_["last_error"]["error_type"] == "stream_failure"
    assert conversation.metadata_["last_error"]["partial"] is True
    service.db.commit.assert_awaited_once()
