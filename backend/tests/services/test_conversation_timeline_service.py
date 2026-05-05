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
