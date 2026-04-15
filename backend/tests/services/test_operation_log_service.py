"""OperationLogService 单元测试 / Test.

覆盖：日志记录、查询、清理。"""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from tests.services.conftest import make_mock_model


def _make_log(**overrides):
    defaults = {
        "id": 1,
        "admin_id": 1,
        "tenant_id": None,
        "username": "admin",
        "action": "create",
        "module": "tenant",
        "path": "/admin/tenants",
        "method": "POST",
        "status_code": 200,
        "duration_ms": 50,
    }
    defaults.update(overrides)
    return make_mock_model(**defaults)


class TestLogRecord:
    def test_build_operation_log_payload_infers_module_from_path(self) -> None:
        from app.services.system.operation_log_service_parts.payloads import (
            build_operation_log_payload,
        )

        payload = build_operation_log_payload(
            tenant_id=None,
            user_type="admin",
            user_id=1,
            username="admin",
            module=None,
            action="query",
            resource=None,
            method="GET",
            path="/admin/notifications/unread-count",
        )

        assert payload["module"] == "notification"

    @pytest.mark.asyncio
    async def test_create_log_entry(self, mock_db):
        from app.services.system.operation_log_service import OperationLogService

        service = OperationLogService.__new__(OperationLogService)
        service.db = mock_db
        service.repo = AsyncMock()
        service.repo.create = AsyncMock(return_value=_make_log())

        result = await service.repo.create(
            {
                "admin_id": 1,
                "username": "admin",
                "action": "create",
                "module": "tenant",
                "path": "/admin/tenants",
                "method": "POST",
                "status_code": 200,
            }
        )
        assert result.action == "create"


class TestLogQuery:
    @pytest.mark.asyncio
    async def test_query_returns_list(self, mock_db):
        from app.services.system.operation_log_service import OperationLogService

        logs = [_make_log(id=i) for i in range(5)]
        service = OperationLogService.__new__(OperationLogService)
        service.db = mock_db
        service.repo = AsyncMock()
        service.repo.query_list = AsyncMock(return_value=(logs, 5))

        items, total = await service.repo.query_list(MagicMock())
        assert len(items) == 5
        assert total == 5

    @pytest.mark.asyncio
    async def test_query_empty(self, mock_db):
        from app.services.system.operation_log_service import OperationLogService

        service = OperationLogService.__new__(OperationLogService)
        service.db = mock_db
        service.repo = AsyncMock()
        service.repo.query_list = AsyncMock(return_value=([], 0))

        items, total = await service.repo.query_list(MagicMock())
        assert len(items) == 0
        assert total == 0

    @pytest.mark.asyncio
    async def test_serialize_logs_merges_identity_display_fields(self, mock_db):
        from app.services.system.operation_log_service import OperationLogService

        service = OperationLogService.__new__(OperationLogService)
        service.db = mock_db
        service.repo = AsyncMock()
        service._identity_facade = SimpleNamespace(
            identity_ref=lambda user_type, user_id: (
                (str(user_type), int(user_id))
                if user_type is not None and user_id is not None
                else None
            ),
            load_identity_meta_map=AsyncMock(
                return_value={
                    ("tenant_admin", 12): {
                        "display_name": "Alice",
                        "username": "alice",
                        "nickname": "Alice",
                        "avatar": "22",
                        "org_node_id": 5,
                        "org_node_name": "Ops",
                        "role_name": "Owner",
                        "user_type": "tenant_admin",
                        "is_active": True,
                        "is_leader": True,
                        "is_owner": True,
                    }
                }
            ),
        )

        log = _make_log(
            id=9,
            user_type="tenant_admin",
            user_id=12,
            username=None,
            nickname=None,
            trace_id=None,
            resource=None,
            ip=None,
            created_at=datetime(2026, 4, 5, 0, 0, tzinfo=timezone.utc),
        )

        payloads = await service.serialize_logs([log])

        assert payloads[0]["display_name"] == "Alice"
        assert payloads[0]["username"] == "alice"
        assert payloads[0]["avatar"] == "22"
        assert payloads[0]["org_node_name"] == "Ops"
        assert payloads[0]["role_name"] == "Owner"
        assert payloads[0]["is_leader"] is True
        assert payloads[0]["is_owner"] is True

    @pytest.mark.asyncio
    async def test_serialize_logs_prefers_identity_snapshot_over_live_meta(self, mock_db):
        from app.services.system.operation_log_service import OperationLogService

        service = OperationLogService.__new__(OperationLogService)
        service.db = mock_db
        service.repo = AsyncMock()
        service._identity_facade = SimpleNamespace(
            identity_ref=lambda user_type, user_id: (
                (str(user_type), int(user_id))
                if user_type is not None and user_id is not None
                else None
            ),
            load_identity_meta_map=AsyncMock(
                return_value={
                    ("tenant_admin", 12): {
                        "display_name": "Current Alice",
                        "username": "alice_now",
                        "nickname": "Current Alice",
                        "avatar": "live-avatar",
                        "org_node_id": 9,
                        "org_node_name": "Live Ops",
                        "role_name": "Live Owner",
                        "display_role_name": "Live Owner",
                        "user_type": "tenant_admin",
                        "is_active": False,
                        "is_leader": False,
                        "is_owner": False,
                    }
                }
            ),
        )

        log = _make_log(
            id=18,
            user_type="tenant_admin",
            user_id=12,
            username="alice_old",
            nickname="Alice Old",
            identity_snapshot={
                "display_name": "历史 Alice",
                "username": "alice_old",
                "nickname": "Alice Old",
                "avatar": "snapshot-avatar",
                "org_node_id": 5,
                "org_node_name": "历史组织",
                "role_name": "历史角色",
                "display_role_name": None,
                "is_active": True,
                "is_leader": True,
                "is_owner": True,
            },
            trace_id=None,
            resource=None,
            ip=None,
            created_at=datetime(2026, 4, 5, 0, 0, tzinfo=timezone.utc),
        )

        payloads = await service.serialize_logs([log])

        assert payloads[0]["display_name"] == "历史 Alice"
        assert payloads[0]["username"] == "alice_old"
        assert payloads[0]["avatar"] == "snapshot-avatar"
        assert payloads[0]["org_node_name"] == "历史组织"
        assert payloads[0]["role_name"] is None
        assert payloads[0]["is_active"] is True
        assert payloads[0]["is_leader"] is True
        assert payloads[0]["is_owner"] is True

    @pytest.mark.asyncio
    async def test_serialize_logs_backfills_legacy_module_from_path(self, mock_db):
        from app.services.system.operation_log_service import OperationLogService

        service = OperationLogService.__new__(OperationLogService)
        service.db = mock_db
        service.repo = AsyncMock()
        service._identity_facade = SimpleNamespace(
            identity_ref=lambda user_type, user_id: (
                (str(user_type), int(user_id))
                if user_type is not None and user_id is not None
                else None
            ),
            load_identity_meta_map=AsyncMock(return_value={}),
        )

        log = _make_log(
            id=23,
            user_type="admin",
            user_id=1,
            username="admin",
            nickname="管理员",
            module=None,
            resource=None,
            path="/admin/plugins/weather-widget/api/hourly",
            trace_id=None,
            response_code=200,
            ip=None,
            created_at=datetime(2026, 4, 5, 0, 0, tzinfo=timezone.utc),
        )

        payloads = await service.serialize_logs([log])

        assert payloads[0]["module"] == "plugin"
        assert payloads[0]["module_label"] == "插件"

    @pytest.mark.asyncio
    async def test_serialize_logs_translates_preference_module_from_path(self, mock_db):
        from app.services.system.operation_log_service import OperationLogService

        service = OperationLogService.__new__(OperationLogService)
        service.db = mock_db
        service.repo = AsyncMock()
        service._identity_facade = SimpleNamespace(
            identity_ref=lambda user_type, user_id: (
                (str(user_type), int(user_id))
                if user_type is not None and user_id is not None
                else None
            ),
            load_identity_meta_map=AsyncMock(return_value={}),
        )

        log = _make_log(
            id=24,
            user_type="admin",
            user_id=1,
            username="admin",
            nickname="管理员",
            module=None,
            resource=None,
            path="/admin/preferences/me",
            trace_id=None,
            response_code=200,
            ip=None,
            created_at=datetime(2026, 4, 5, 0, 0, tzinfo=timezone.utc),
        )

        payloads = await service.serialize_logs([log])

        assert payloads[0]["module"] == "preference"
        assert payloads[0]["module_label"] == "偏好设置"

    @pytest.mark.asyncio
    async def test_get_admin_operators_select_returns_remote_identity_options(
        self,
        mock_db,
    ):
        from app.services.system.operation_log_service import OperationLogService

        service = OperationLogService.__new__(OperationLogService)
        service.db = mock_db
        service.repo = AsyncMock()
        expected_items = [
            {
                "label": "Alice Zhang",
                "value": "alice",
                "extra": {
                    "user_id": 7,
                    "display_name": "Alice Zhang",
                    "username": "alice",
                    "nickname": "Alice",
                    "avatar": "22",
                    "org_node_id": 3,
                    "org_node_name": "North Hub",
                    "role_name": "Supervisor",
                    "user_type": "admin",
                    "is_active": True,
                    "is_leader": True,
                    "is_owner": False,
                },
                "disabled": False,
            }
        ]
        service._operator_facade = SimpleNamespace(
            get_admin_operators_select=AsyncMock(return_value=(expected_items, 1))
        )

        items, total = await service.get_admin_operators_select(
            search="alice",
            page=1,
            page_size=10,
        )

        assert total == 1
        assert items == expected_items
        service._operator_facade.get_admin_operators_select.assert_awaited_once_with(
            search="alice",
            page=1,
            page_size=10,
        )

    @pytest.mark.asyncio
    async def test_get_tenant_operators_select_forwards_filters_to_facade(
        self,
        mock_db,
    ):
        from app.services.system.operation_log_service import OperationLogService

        service = OperationLogService.__new__(OperationLogService)
        service.db = mock_db
        service.repo = AsyncMock()
        expected_items = [
            {
                "label": "Jane Doe",
                "value": "jdoe",
                "extra": {"user_type": "tenant_admin"},
                "disabled": False,
            }
        ]
        service._operator_facade = SimpleNamespace(
            get_tenant_operators_select=AsyncMock(return_value=(expected_items, 1))
        )

        items, total = await service.get_tenant_operators_select(
            tenant_id=88,
            search="Jane",
            user_type="tenant_admin",
            page=2,
            page_size=25,
        )

        assert total == 1
        assert items == expected_items
        service._operator_facade.get_tenant_operators_select.assert_awaited_once_with(
            tenant_id=88,
            search="Jane",
            user_type="tenant_admin",
            page=2,
            page_size=25,
        )


class TestLogFilter:
    @pytest.mark.asyncio
    async def test_filter_by_module(self, mock_db):
        from app.services.system.operation_log_service import OperationLogService

        logs = [_make_log(module="tenant")]
        service = OperationLogService.__new__(OperationLogService)
        service.db = mock_db
        service.repo = AsyncMock()
        service.repo.query_list = AsyncMock(return_value=(logs, 1))

        items, total = await service.repo.query_list(MagicMock())
        assert items[0].module == "tenant"

    @pytest.mark.asyncio
    async def test_filter_by_method(self, mock_db):
        from app.services.system.operation_log_service import OperationLogService

        logs = [_make_log(method="DELETE")]
        service = OperationLogService.__new__(OperationLogService)
        service.db = mock_db
        service.repo = AsyncMock()
        service.repo.query_list = AsyncMock(return_value=(logs, 1))

        items, _ = await service.repo.query_list(MagicMock())
        assert items[0].method == "DELETE"


class TestLogCleanup:
    @pytest.mark.asyncio
    async def test_cleanup_old_logs(self, mock_db):
        from app.services.system.operation_log_service import OperationLogService

        service = OperationLogService.__new__(OperationLogService)
        service.db = mock_db
        service.repo = AsyncMock()
        service.repo.delete_before = AsyncMock(return_value=100)

        deleted = await service.repo.delete_before(days=30)
        assert deleted == 100
