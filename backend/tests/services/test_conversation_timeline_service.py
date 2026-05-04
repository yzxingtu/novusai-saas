"""
Test type: behavioral
Scope: conversation timeline service delegation and message grouping behavior.
Mocked dependencies: repository/db seams only; service logic runs real.
"""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.ai.conversation_service import ConversationService
from app.services.ai.conversation_timeline_service import ConversationTimelineService


@pytest.mark.asyncio
async def test_conversation_service_get_timeline_delegates_to_timeline_service(mock_db):
    service = ConversationService.__new__(ConversationService)
    service.db = mock_db
    service.tenant_id = 1
    service.repo = AsyncMock()
    service.get_accessible_conversation = AsyncMock(
        return_value=SimpleNamespace(id=10, metadata_={}),
    )
    service._message_repo = MagicMock()
    service._message_repo.get_by_conversation = AsyncMock(
        return_value=[SimpleNamespace(id=1)]
    )
    service._timeline_service = MagicMock()
    service._timeline_service.get_conversation_timeline = AsyncMock(
        return_value=[{"ok": True}]
    )

    timeline = await service.get_conversation_timeline(10, user_id=1)

    assert timeline == [{"ok": True}]
    service._timeline_service.get_conversation_timeline.assert_awaited_once()


@pytest.mark.asyncio
async def test_conversation_service_build_call_log_summary_delegates(mock_db):
    service = ConversationService.__new__(ConversationService)
    service.db = mock_db
    service.tenant_id = 1
    service.repo = AsyncMock()
    service._timeline_service = MagicMock()
    service._timeline_service.build_call_log_summary = AsyncMock(
        return_value={"call_count": 1}
    )

    result = await service._build_call_log_summary(12)

    assert result == {"call_count": 1}
    service._timeline_service.build_call_log_summary.assert_awaited_once_with(12)


@pytest.mark.asyncio
async def test_conversation_service_persist_chat_messages_delegates_to_persistence_service(
    mock_db,
):
    service = ConversationService.__new__(ConversationService)
    service.db = mock_db
    service.tenant_id = 1
    service.repo = AsyncMock()
    conversation = SimpleNamespace(id=9, message_count=0)
    result = SimpleNamespace(messages=[{"role": "assistant", "content": "ok"}])

    with patch(
        "app.services.ai.conversation_facade_mixins.persist_chat_messages_persist",
        new=AsyncMock(return_value=([], 2)),
    ) as mock_persist:
        persisted = await service.persist_chat_messages(
            conversation=conversation,
            result=result,
            history_count=0,
        )

    assert persisted == ([], 2)
    mock_persist.assert_awaited_once()


@pytest.mark.asyncio
async def test_conversation_timeline_service_build_call_log_summary(mock_db):
    row = SimpleNamespace(
        call_count=3,
        total_tokens=77,
        total_cost=12.5,
        last_call_at=datetime(2026, 4, 10, 10, 0, tzinfo=timezone.utc),
    )
    mock_db.execute = AsyncMock(
        return_value=SimpleNamespace(one_or_none=lambda: row),
    )
    svc = ConversationTimelineService(
        mock_db,
        memory_tenant_id=1,
        format_dt=lambda value: value.isoformat() if value else None,
    )

    summary = await svc.build_call_log_summary(1203)

    assert summary == {
        "call_count": 3,
        "total_tokens": 77,
        "total_cost": 12.5,
        "last_call_at": datetime(2026, 4, 10, 10, 0, tzinfo=timezone.utc),
    }


@pytest.mark.asyncio
async def test_conversation_timeline_service_get_timeline_includes_summary(mock_db):
    message = SimpleNamespace(
        id=1,
        role="assistant",
        content="hello",
        tool_name=None,
        tool_call_id=None,
        metadata_={
            "interaction_mode": "confirm",
            "nested": {
                "interaction_mode_effective": "trusted_auto",
                "keep": "value",
            },
        },
        created_at=datetime(2026, 4, 10, 10, 0, tzinfo=timezone.utc),
    )
    decision = SimpleNamespace(
        status="approved",
        decision_type="tool_confirm",
        reason="ok",
        tool_name="web_search",
        risk_level="low",
        auto_approved=False,
        correlation_key="corr-1",
        evidence={
            "interaction_mode_effective": "trusted_auto",
            "downgrade_reason": None,
            "keep": "yes",
        },
        created_at=datetime(2026, 4, 10, 10, 1, tzinfo=timezone.utc),
        to_dict=lambda: {
            "id": 1,
            "interaction_mode_effective": "trusted_auto",
            "evidence": {
                "interaction_mode_effective": "trusted_auto",
                "downgrade_reason": "legacy",
                "keep": "yes",
            },
        },
    )
    action_log = SimpleNamespace(
        status="success",
        action_name="web_search",
        error_message=None,
        action_level="normal",
        trace_id="trace-1",
        created_at=datetime(2026, 4, 10, 10, 2, tzinfo=timezone.utc),
        to_dict=lambda: {"id": 2},
    )
    call_log = SimpleNamespace(
        status="success",
        request_type="chat",
        error_message=None,
        trace_id="trace-2",
        created_at=datetime(2026, 4, 10, 10, 3, tzinfo=timezone.utc),
        to_dict=lambda: {"id": 3},
    )
    mock_db.execute = AsyncMock(
        side_effect=[
            SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: [decision])),
            SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: [action_log])),
            SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: [call_log])),
        ]
    )

    svc = ConversationTimelineService(
        mock_db,
        memory_tenant_id=1,
        format_dt=lambda value: value.isoformat() if value else None,
    )
    svc.build_call_log_summary = AsyncMock(
        return_value={
            "call_count": 4,
            "total_tokens": 123,
            "total_cost": 1.2,
            "last_call_at": datetime(2026, 4, 10, 10, 4, tzinfo=timezone.utc),
        }
    )

    items = await svc.get_conversation_timeline(
        conversation_id=1203,
        conversation=SimpleNamespace(metadata_={"interaction_mode": "confirm"}),
        messages=[message],
    )

    assert any(item["type"] == "message:assistant" for item in items)
    assert any(item["type"] == "execution_decision" for item in items)
    assert any(item["type"] == "action_log" for item in items)
    assert any(item["type"] == "call_log" for item in items)
    assert any(item["type"] == "call_log_summary" for item in items)
    assert all("interaction_mode_effective" not in item for item in items)

    message_item = next(item for item in items if item["type"] == "message:assistant")
    assert message_item["detail_payload"]["metadata"] == {"nested": {"keep": "value"}}

    decision_item = next(item for item in items if item["type"] == "execution_decision")
    assert decision_item["detail_payload"] == {
        "id": 1,
        "evidence": {"keep": "yes"},
    }
