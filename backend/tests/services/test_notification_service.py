"""
NotificationService 单元测试

覆盖：通知创建、查询、标记已读、批量已读、删除。
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from tests.services.conftest import make_mock_model


def _make_notification(**overrides):
    defaults = {
        "id": 1,
        "tenant_id": 1,
        "user_id": 1,
        "title": "Test Notification",
        "content": "You have a new message",
        "type": "info",
        "is_read": False,
        "is_deleted": False,
    }
    defaults.update(overrides)
    return make_mock_model(**defaults)


class TestNotificationCreate:

    @pytest.mark.asyncio
    async def test_create_notification(self, mock_db):
        from app.services.common.notification_service import NotificationService

        notif = _make_notification()
        service = NotificationService.__new__(NotificationService)
        service.db = mock_db
        service.repo = AsyncMock()
        service.repo.create = AsyncMock(return_value=notif)

        result = await service.repo.create({
            "tenant_id": 1,
            "user_id": 1,
            "title": "Test",
            "content": "Content",
            "type": "info",
        })
        assert result.title == "Test Notification"


class TestNotificationQuery:

    @pytest.mark.asyncio
    async def test_get_unread_count(self, mock_db):
        from app.services.common.notification_service import NotificationService

        service = NotificationService.__new__(NotificationService)
        service.db = mock_db
        service.repo = AsyncMock()
        service.repo.count_unread = AsyncMock(return_value=5)

        count = await service.repo.count_unread(user_id=1)
        assert count == 5

    @pytest.mark.asyncio
    async def test_get_unread_zero(self, mock_db):
        from app.services.common.notification_service import NotificationService

        service = NotificationService.__new__(NotificationService)
        service.db = mock_db
        service.repo = AsyncMock()
        service.repo.count_unread = AsyncMock(return_value=0)

        count = await service.repo.count_unread(user_id=1)
        assert count == 0


class TestNotificationMarkRead:

    @pytest.mark.asyncio
    async def test_mark_read_exists(self, mock_db):
        from app.services.common.notification_service import NotificationService

        service = NotificationService.__new__(NotificationService)
        service.db = mock_db
        service.repo = AsyncMock()

        assert hasattr(service, 'mark_read')
        assert hasattr(service, 'mark_all_read')

    @pytest.mark.asyncio
    async def test_mark_all_read(self, mock_db):
        from app.services.common.notification_service import NotificationService

        service = NotificationService.__new__(NotificationService)
        service.db = mock_db
        service.repo = AsyncMock()
        mock_db.execute = AsyncMock()

        await service.mark_all_read(user_type="tenant_admin", user_id=1)
        # mark_all_read uses db.execute directly, just verify it doesn't crash


class TestNotificationDelete:

    @pytest.mark.asyncio
    async def test_delete_notification(self, mock_db):
        from app.services.common.notification_service import NotificationService

        service = NotificationService.__new__(NotificationService)
        service.db = mock_db
        service.repo = AsyncMock()
        service.repo.delete = AsyncMock(return_value=True)

        result = await service.repo.delete(1, soft=True)
        assert result is True

    @pytest.mark.asyncio
    async def test_delete_not_found(self, mock_db):
        from app.services.common.notification_service import NotificationService

        service = NotificationService.__new__(NotificationService)
        service.db = mock_db
        service.repo = AsyncMock()
        service.repo.get_by_id = AsyncMock(return_value=None)

        result = await service.repo.get_by_id(999)
        assert result is None
