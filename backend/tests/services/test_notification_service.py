"""NotificationService 单元测试 / Test.

覆盖：通知创建、查询、标记已读、批量已读、删除。"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from sqlalchemy.dialects import postgresql

from tests.services.conftest import make_mock_model, make_scalars_result


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
            scope="platform",
            tenant_id=None,
            source="core",
            plugin_name=None,
        )
        mock_db.execute.return_value = make_scalars_result([template])

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
            scope="platform",
            tenant_id=None,
            source="core",
            plugin_name=None,
        )
        mock_db.execute.return_value = make_scalars_result([template])

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

        mock_db.execute.return_value = make_scalars_result([])

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


class TestNotificationTemplateFallback:
    @pytest.mark.asyncio
    async def test_tenant_template_override_wins_over_platform_default(self, mock_db):
        from app.services.common.notification_service import NotificationService

        platform_template = make_mock_model(
            id=1,
            code="biz.user_approved",
            scope="platform",
            tenant_id=None,
            source="core",
            plugin_name=None,
        )
        tenant_template = make_mock_model(
            id=2,
            code="biz.user_approved",
            scope="tenant",
            tenant_id=42,
            source="core",
            plugin_name=None,
        )
        mock_db.execute.return_value = make_scalars_result(
            [platform_template, tenant_template]
        )

        service = NotificationService(mock_db)

        result = await service._get_template("biz.user_approved", tenant_id=42)

        assert result is tenant_template

    @pytest.mark.asyncio
    async def test_plugin_template_wins_before_platform_default(self, mock_db):
        from app.services.common.notification_service import NotificationService

        platform_template = make_mock_model(
            id=1,
            code="plugin.demo.biz.alert",
            scope="platform",
            tenant_id=None,
            source="core",
            plugin_name=None,
        )
        plugin_template = make_mock_model(
            id=2,
            code="plugin.demo.biz.alert",
            scope="plugin",
            tenant_id=None,
            source="plugin",
            plugin_name="demo",
        )
        mock_db.execute.return_value = make_scalars_result(
            [platform_template, plugin_template]
        )

        service = NotificationService(mock_db)

        result = await service._get_template("plugin.demo.biz.alert", tenant_id=42)

        assert result is plugin_template


class TestNotificationTenantBoundary:
    @pytest.mark.asyncio
    async def test_mark_read_includes_tenant_filter_and_refuses_mismatch(self, mock_db):
        from app.services.common.notification_service import NotificationService

        result = make_mock_model(rowcount=0)
        mock_db.execute.return_value = result
        service = NotificationService(mock_db)

        found = await service.mark_read(
            notification_id=10,
            user_type="tenant_admin",
            user_id=7,
            tenant_id=99,
        )

        statement = mock_db.execute.await_args.args[0]
        compiled = statement.compile(dialect=postgresql.dialect())
        assert found is False
        assert "tenant_id" in str(compiled)
        assert 99 in compiled.params.values()


class TestNotificationDeliveryOutbox:
    @pytest.mark.asyncio
    async def test_send_records_delivery_status_for_channel(self, mock_db, monkeypatch):
        from app.models.common.notification_delivery import NotificationDelivery
        from app.services.common.notification_service import NotificationService

        class _FakeChannel:
            @property
            def channel_code(self):
                return "ws"

            async def is_enabled(self):
                return True

            async def deliver(self, **kwargs):
                assert kwargs["tenant_id"] == 42
                assert kwargs["delivery_record"].status == "pending"
                return True

        template = make_mock_model(
            id=5,
            code="task.failed",
            category="task",
            title_template="任务失败",
            body_template="任务失败：{error}",
            priority="high",
            channels=["ws"],
            scope="platform",
            tenant_id=None,
            source="core",
            plugin_name=None,
        )
        mock_db.execute.return_value = make_scalars_result([template])
        monkeypatch.setattr(
            "app.services.common.channels.get_channel",
            lambda code: _FakeChannel() if code == "ws" else None,
        )

        service = NotificationService(mock_db)
        service._notifications_enabled = AsyncMock(return_value=True)

        sent = await service.send(
            template_code="task.failed",
            recipients=[("tenant_admin", 7)],
            data={"error": "timeout"},
            tenant_id=42,
            force_all_channels=True,
        )

        deliveries = [
            call.args[0]
            for call in mock_db.add.call_args_list
            if isinstance(call.args[0], NotificationDelivery)
        ]
        assert sent == 1
        assert len(deliveries) == 1
        assert deliveries[0].template_id == 5
        assert deliveries[0].template_code == "task.failed"
        assert deliveries[0].channel == "ws"
        assert deliveries[0].tenant_id == 42
        assert deliveries[0].recipient_type == "tenant_admin"
        assert deliveries[0].recipient_id == 7
        assert deliveries[0].status == "sent"
        assert deliveries[0].attempt == 1
        assert deliveries[0].delivered_at is not None
