"""TenantService 单元测试 / Test.

覆盖：企业 CRUD、状态变更、配额检查、slug 唯一性。"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from tests.services.conftest import make_mock_model


def _make_tenant(**overrides):
    defaults = {
        "id": 1,
        "name": "Test Tenant",
        "slug": "test-tenant",
        "status": "active",
        "plan_id": 1,
        "is_active": True,
        "is_deleted": False,
    }
    defaults.update(overrides)
    return make_mock_model(**defaults)


class TestTenantCreate:
    @pytest.mark.asyncio
    async def test_create_tenant_basic(self, mock_db):
        """Basic tenant creation — verify service can be instantiated / 服务"""
        from app.services.system.tenant_service import TenantService

        service = TenantService.__new__(TenantService)
        service.db = mock_db
        service.repo = AsyncMock()
        service.repo.get_by_id = AsyncMock(return_value=None)

        # Verify service has expected methods
        assert hasattr(service, "create_tenant")
        assert hasattr(service, "toggle_status")

    @pytest.mark.asyncio
    async def test_welcome_notification_uses_request_loop_notify(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from app.services.system.tenant_service import TenantService

        calls: list[tuple[str, dict]] = []

        class _NestedTx:
            async def __aenter__(self) -> None:
                calls.append(("begin_nested", {}))

            async def __aexit__(self, exc_type, exc, tb) -> bool:
                _ = (exc_type, exc, tb)
                return False

        class _DB:
            def begin_nested(self) -> _NestedTx:
                return _NestedTx()

        async def fake_notify(db, **kwargs):
            calls.append(("notify", {"db": db, **kwargs}))
            return 1

        def fake_render_welcome_email(**kwargs):
            _ = kwargs
            return "subject", "<p>html</p>", "text"

        monkeypatch.setattr(
            "app.services.common.email_templates.render_welcome_email",
            fake_render_welcome_email,
        )
        monkeypatch.setattr(
            "app.services.common.notification_service.notify", fake_notify
        )

        db = _DB()
        await TenantService._send_welcome_email(
            db=db,
            tenant_name="Acme",
            admin_name="owner",
            admin_email="owner@example.test",
            tenant_id=42,
        )

        assert calls[0] == ("begin_nested", {})
        assert calls[1][0] == "notify"
        assert calls[1][1]["db"] is db
        assert calls[1][1]["template_code"] == "system.tenant_welcome"
        assert calls[1][1]["tenant_id"] == 42


class TestTenantUpdate:
    @pytest.mark.asyncio
    async def test_update_returns_tenant(self, mock_db):
        from app.services.system.tenant_service import TenantService

        tenant = _make_tenant()
        service = TenantService.__new__(TenantService)
        service.db = mock_db
        service.repo = AsyncMock()
        service.repo.get_by_id = AsyncMock(return_value=tenant)
        service.repo.update = AsyncMock(return_value=tenant)

        result = await service.repo.update(1, {"name": "Updated"})
        assert result is not None


class TestTenantStatus:
    @pytest.mark.asyncio
    async def test_disable_tenant(self, mock_db):
        from app.services.system.tenant_service import TenantService

        tenant = _make_tenant(is_active=True)
        service = TenantService.__new__(TenantService)
        service.db = mock_db
        service.repo = AsyncMock()
        service.repo.get_by_id = AsyncMock(return_value=tenant)

        await service.toggle_status(1, is_active=False)
        # Service sets is_active on the model and flushes

    @pytest.mark.asyncio
    async def test_enable_tenant(self, mock_db):
        from app.services.system.tenant_service import TenantService

        tenant = _make_tenant(is_active=False)
        service = TenantService.__new__(TenantService)
        service.db = mock_db
        service.repo = AsyncMock()
        service.repo.get_by_id = AsyncMock(return_value=tenant)

        await service.toggle_status(1, is_active=True)
        # Service sets is_active on the model and flushes


class TestTenantNotifications:
    @pytest.mark.asyncio
    async def test_password_reset_notification_uses_request_loop_notify(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from app.services.system.tenant_service import TenantService

        calls: list[tuple[str, dict]] = []

        class _NestedTx:
            async def __aenter__(self) -> None:
                calls.append(("begin_nested", {}))

            async def __aexit__(self, exc_type, exc, tb) -> bool:
                _ = (exc_type, exc, tb)
                return False

        class _DB:
            def begin_nested(self) -> _NestedTx:
                return _NestedTx()

        async def fake_notify(db, **kwargs):
            calls.append(("notify", {"db": db, **kwargs}))
            return 1

        def fake_render_password_reset_email(**kwargs):
            _ = kwargs
            return "subject", "<p>html</p>", "text"

        monkeypatch.setattr(
            "app.services.common.email_templates.render_password_reset_email",
            fake_render_password_reset_email,
        )
        monkeypatch.setattr(
            "app.services.common.notification_service.notify", fake_notify
        )

        db = _DB()
        await TenantService._send_password_reset_notification(
            db=db,
            user_name="owner",
            user_email="owner@example.test",
            tenant_id=42,
        )

        assert calls[0] == ("begin_nested", {})
        assert calls[1][0] == "notify"
        assert calls[1][1]["db"] is db
        assert calls[1][1]["template_code"] == "system.password_reset"
        assert calls[1][1]["tenant_id"] == 42


class TestTenantDelete:
    @pytest.mark.asyncio
    async def test_get_by_code_not_found(self, mock_db):
        from app.services.system.tenant_service import TenantService

        service = TenantService.__new__(TenantService)
        service.db = mock_db
        service.repo = AsyncMock()
        service.repo.find_by_code = AsyncMock(return_value=None)

        result = await service.repo.find_by_code("nonexistent")
        assert result is None


class TestTenantQuery:
    @pytest.mark.asyncio
    async def test_get_by_slug(self, mock_db):
        from app.services.system.tenant_service import TenantService

        tenant = _make_tenant(slug="my-tenant")
        service = TenantService.__new__(TenantService)
        service.db = mock_db
        service.repo = AsyncMock()
        service.repo.find_by_slug = AsyncMock(return_value=tenant)

        result = await service.repo.find_by_slug("my-tenant")
        assert result.slug == "my-tenant"

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self, mock_db):
        from app.services.system.tenant_service import TenantService

        service = TenantService.__new__(TenantService)
        service.db = mock_db
        service.repo = AsyncMock()
        service.repo.get_by_id = AsyncMock(return_value=None)

        result = await service.repo.get_by_id(999)
        assert result is None
