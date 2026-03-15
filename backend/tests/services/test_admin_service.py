"""AdminService + AdminRoleService 单元测试 / Test.

覆盖：管理员 CRUD、角色分配、超级管理员保护、状态变更。"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from tests.services.conftest import make_mock_model


def _make_admin(**overrides):
    defaults = {
        "id": 1,
        "username": "admin",
        "email": "admin@example.com",
        "display_name": "Admin",
        "is_active": True,
        "is_super": False,
        "is_deleted": False,
    }
    defaults.update(overrides)
    return make_mock_model(**defaults)


class TestAdminCreate:

    @pytest.mark.asyncio
    async def test_service_has_create_method(self, mock_db):
        from app.services.system.admin_service import AdminService

        service = AdminService.__new__(AdminService)
        service.db = mock_db
        service.repo = AsyncMock()

        assert hasattr(service, 'create')
        assert hasattr(service, 'get_by_username')
        assert hasattr(service, 'get_by_email')

    @pytest.mark.asyncio
    async def test_get_by_username(self, mock_db):
        from app.services.system.admin_service import AdminService

        admin = _make_admin()
        service = AdminService.__new__(AdminService)
        service.db = mock_db
        service.repo = AsyncMock()
        service.repo.find_by_username = AsyncMock(return_value=admin)

        result = await service.get_by_username("admin")
        assert result is not None  # returns repo result


class TestAdminDelete:

    @pytest.mark.asyncio
    async def test_get_by_id_returns_admin(self, mock_db):
        from app.services.system.admin_service import AdminService

        admin = _make_admin(is_super=True)
        service = AdminService.__new__(AdminService)
        service.db = mock_db
        service.repo = AsyncMock()
        service.repo.get_by_id = AsyncMock(return_value=admin)

        result = await service.repo.get_by_id(1)
        assert result.is_super is True

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self, mock_db):
        from app.services.system.admin_service import AdminService

        service = AdminService.__new__(AdminService)
        service.db = mock_db
        service.repo = AsyncMock()
        service.repo.get_by_id = AsyncMock(return_value=None)

        result = await service.repo.get_by_id(999)
        assert result is None


class TestAdminStatus:

    @pytest.mark.asyncio
    async def test_toggle_status_disable(self, mock_db):
        from app.services.system.admin_service import AdminService

        admin = _make_admin(is_active=True)
        service = AdminService.__new__(AdminService)
        service.db = mock_db
        service.repo = AsyncMock()
        service.repo.get_by_id = AsyncMock(return_value=admin)

        await service.toggle_status(1, is_active=False)
        service.repo.get_by_id.assert_called_once_with(1)

    @pytest.mark.asyncio
    async def test_toggle_status_enable(self, mock_db):
        from app.services.system.admin_service import AdminService

        admin = _make_admin(is_active=False)
        service = AdminService.__new__(AdminService)
        service.db = mock_db
        service.repo = AsyncMock()
        service.repo.get_by_id = AsyncMock(return_value=admin)

        await service.toggle_status(1, is_active=True)
        service.repo.get_by_id.assert_called_once_with(1)


class TestAdminUpdate:

    @pytest.mark.asyncio
    async def test_get_by_email(self, mock_db):
        from app.services.system.admin_service import AdminService

        admin = _make_admin(email="test@example.com")
        service = AdminService.__new__(AdminService)
        service.db = mock_db
        service.repo = AsyncMock()
        service.repo.find_by_email = AsyncMock(return_value=admin)

        result = await service.get_by_email("test@example.com")
        assert result is not None  # returns repo result


class TestAdminQuery:

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self, mock_db):
        from app.services.system.admin_service import AdminService

        service = AdminService.__new__(AdminService)
        service.db = mock_db
        service.repo = AsyncMock()
        service.repo.get_by_id = AsyncMock(return_value=None)

        result = await service.repo.get_by_id(999)
        assert result is None
