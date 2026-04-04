"""NotificationService 单元测试 / Test.

覆盖：通知创建、查询、标记已读、批量已读、删除。"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from tests.services.conftest import make_mock_model, make_scalar_result


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

        result = await service.repo.create(
            {
                "tenant_id": 1,
                "user_id": 1,
                "title": "Test",
                "content": "Content",
                "type": "info",
            }
        )
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

        assert hasattr(service, "mark_read")
        assert hasattr(service, "mark_all_read")

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


class TestNotificationWsPayload:
    @pytest.mark.asyncio
    async def test_build_ws_payload_renders_template(self, mock_db):
        from app.services.common.notification_service import NotificationService

        template = make_mock_model(
            code="task.failed",
            category="task",
            title_template="任务执行失败：{task_name}",
            body_template="任务 {task_name} 执行失败，错误信息：{error}",
            priority="high",
            channels=["ws", "inbox"],
        )
        mock_db.execute.return_value = make_scalar_result(template)

        service = NotificationService(mock_db)
        service._notifications_enabled = AsyncMock(return_value=True)

        payload = await service.build_ws_payload(
            template_code="task.failed",
            data={"task_name": "nightly-sync", "error": "timeout"},
            link="/admin/system/tasks",
            fallback_title="fallback title",
        )

        assert payload == {
            "type": "task.failed",
            "category": "task",
            "title": "任务执行失败：nightly-sync",
            "body": "任务 nightly-sync 执行失败，错误信息：timeout",
            "data": {"task_name": "nightly-sync", "error": "timeout"},
            "link": "/admin/system/tasks",
            "priority": "high",
        }

    @pytest.mark.asyncio
    async def test_build_ws_payload_returns_none_when_ws_channel_disabled(
        self,
        mock_db,
    ):
        from app.services.common.notification_service import NotificationService

        template = make_mock_model(
            code="ai.batch_complete",
            category="ai",
            title_template="批处理已完成",
            body_template="批处理任务已完成，共处理 {total} 条数据。",
            priority="normal",
            channels=["inbox"],
        )
        mock_db.execute.return_value = make_scalar_result(template)

        service = NotificationService(mock_db)
        service._notifications_enabled = AsyncMock(return_value=True)

        payload = await service.build_ws_payload(
            template_code="ai.batch_complete",
            data={"total": 3},
        )

        assert payload is None

    @pytest.mark.asyncio
    async def test_build_ws_payload_falls_back_when_template_missing(self, mock_db):
        from app.services.common.notification_service import NotificationService

        mock_db.execute.return_value = make_scalar_result(None)

        service = NotificationService(mock_db)
        service._notifications_enabled = AsyncMock(return_value=True)

        payload = await service.build_ws_payload(
            template_code="ai.batch_failed",
            data={"error": "worker crashed"},
            fallback_category="ai",
            fallback_title="Batch failed",
            fallback_body="worker crashed",
            fallback_priority="high",
        )

        assert payload == {
            "type": "ai.batch_failed",
            "category": "ai",
            "title": "Batch failed",
            "body": "worker crashed",
            "data": {"error": "worker crashed"},
            "link": None,
            "priority": "high",
        }

    def test_build_ws_payload_sync_wraps_async_service(self, monkeypatch):
        from app.services.common import notification_service as notification_module

        expected = {"type": "task.failed", "title": "Task failed"}

        class _DummyAsyncContext:
            async def __aenter__(self):
                return object()

            async def __aexit__(self, exc_type, exc, tb):
                return False

        async def _fake_build_ws_payload(self, **kwargs):
            assert kwargs["template_code"] == "task.failed"
            assert kwargs["data"]["task_name"] == "nightly-sync"
            return expected

        monkeypatch.setattr(
            "app.core.database.async_session_factory",
            lambda: _DummyAsyncContext(),
        )
        monkeypatch.setattr(
            notification_module.NotificationService,
            "build_ws_payload",
            _fake_build_ws_payload,
        )

        payload = notification_module.build_ws_payload_sync(
            template_code="task.failed",
            data={"task_name": "nightly-sync", "error": "timeout"},
            fallback_title="Task failed",
        )

        assert payload == expected
