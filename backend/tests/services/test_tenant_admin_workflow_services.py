from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.core.security import IMPERSONATE_TOKEN_EXPIRE_SECONDS
from app.enums.error_code import ErrorCode
from app.exceptions import BusinessException
from app.schemas.system import TenantImpersonateResponse
from app.services.system import tenant_impersonation_service as impersonation_module
from app.services.system.tenant_admin_workflow_service import (
    TenantAdminWorkflowService,
)
from app.services.system.tenant_impersonation_service import (
    TenantImpersonationService,
)
from app.services.system.tenant_storage_admin_service import (
    TenantStorageAdminService,
)
from app.services.tenant import tenant_config_workflow_service as workflow_module
from app.services.tenant.tenant_config_workflow_service import (
    TenantConfigWorkflowService,
)


@pytest.mark.asyncio
async def test_tenant_admin_workflow_rejects_owner_disable(monkeypatch) -> None:
    service = TenantAdminWorkflowService.__new__(TenantAdminWorkflowService)
    service._db = SimpleNamespace(flush=AsyncMock())
    service._tenant_service = SimpleNamespace(
        get_by_id=AsyncMock(return_value=object())
    )
    service._auth_service = SimpleNamespace()

    tenant_admin_service = SimpleNamespace(
        get_identity_detail=AsyncMock(return_value=SimpleNamespace(is_owner=True))
    )
    service._get_tenant_admin_service = lambda _tenant_id: tenant_admin_service

    with pytest.raises(Exception) as exc_info:
        await service.update_tenant_admin(
            tenant_id=3,
            admin_id=7,
            data=SimpleNamespace(
                is_active=False,
                password=None,
                model_dump=lambda **_kwargs: {"is_active": False},
            ),
        )

    assert "不能禁用企业所有者" in str(exc_info.value)


@pytest.mark.asyncio
async def test_tenant_admin_workflow_rejects_empty_update(monkeypatch) -> None:
    service = TenantAdminWorkflowService.__new__(TenantAdminWorkflowService)
    service._db = SimpleNamespace(flush=AsyncMock())
    service._tenant_service = SimpleNamespace(
        get_by_id=AsyncMock(return_value=object())
    )
    service._auth_service = SimpleNamespace()

    tenant_admin_service = SimpleNamespace(
        get_identity_detail=AsyncMock(return_value=SimpleNamespace(is_owner=False)),
        reset_password=AsyncMock(),
        update_admin=AsyncMock(),
    )
    service._get_tenant_admin_service = lambda _tenant_id: tenant_admin_service

    with pytest.raises(Exception) as exc_info:
        await service.update_tenant_admin(
            tenant_id=3,
            admin_id=7,
            data=SimpleNamespace(
                is_active=None,
                password=None,
                model_dump=lambda **_kwargs: {},
            ),
        )

    assert "无效请求" in str(exc_info.value)
    tenant_admin_service.reset_password.assert_not_called()
    tenant_admin_service.update_admin.assert_not_called()


@pytest.mark.asyncio
async def test_tenant_admin_workflow_force_logout_delegates(monkeypatch) -> None:
    service = TenantAdminWorkflowService.__new__(TenantAdminWorkflowService)
    service._db = SimpleNamespace()
    service._tenant_service = SimpleNamespace(
        get_by_id=AsyncMock(return_value=object())
    )
    service._auth_service = SimpleNamespace(
        token_sessions=SimpleNamespace(force_logout=AsyncMock())
    )

    tenant_admin_service = SimpleNamespace(
        get_identity_detail=AsyncMock(return_value=SimpleNamespace(username="alice"))
    )
    service._get_tenant_admin_service = lambda _tenant_id: tenant_admin_service

    message = await service.force_logout_tenant_admin(
        tenant_id=5,
        admin_id=9,
    )

    assert "alice" in message
    service._auth_service.token_sessions.force_logout.assert_awaited_once_with(
        user_type="tenant_admin",
        user_id=9,
        tenant_id=5,
    )


@pytest.mark.asyncio
async def test_tenant_storage_admin_service_rejects_local_admin_override() -> None:
    service = TenantStorageAdminService.__new__(TenantStorageAdminService)
    service._db = SimpleNamespace(commit=AsyncMock())
    service._config_service = SimpleNamespace(set_tenant_config=AsyncMock())

    with pytest.raises(BusinessException) as exc_info:
        await service.update_tenant_storage_config(
            tenant_id=12,
            data={
                "tenant_storage_mode": "admin_override",
                "tenant_storage_driver": "local",
                "tenant_storage_root_path": "bucket",
            },
        )

    assert exc_info.value.code == ErrorCode.INVALID_PARAMETER
    service._config_service.set_tenant_config.assert_not_called()
    service._db.commit.assert_not_called()


@pytest.mark.asyncio
async def test_tenant_storage_admin_service_persists_and_commits() -> None:
    service = TenantStorageAdminService.__new__(TenantStorageAdminService)
    service._db = SimpleNamespace(commit=AsyncMock())
    service._config_service = SimpleNamespace(set_tenant_config=AsyncMock())

    await service.update_tenant_storage_config(
        tenant_id=12,
        data={
            "tenant_storage_mode": "admin_override",
            "tenant_storage_driver": "s3",
            "tenant_storage_root_path": "bucket",
            "tenant_storage_base_url": "https://cdn.example.com",
        },
    )

    assert service._config_service.set_tenant_config.await_count == 4
    service._db.commit.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_tenant_impersonation_service_issues_token(monkeypatch) -> None:
    tenant_service = SimpleNamespace(
        get_by_id=AsyncMock(
            return_value=SimpleNamespace(
                code="tenant-a",
                is_active=True,
                name="Tenant A",
            )
        ),
        validate_impersonation_role=AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        impersonation_module,
        "TenantService",
        lambda _db: tenant_service,
    )
    monkeypatch.setattr(
        impersonation_module,
        "create_impersonate_token",
        lambda **_kwargs: "imp-token",
    )

    service = TenantImpersonationService(SimpleNamespace())
    result = await service.issue_tenant_admin_token(
        current_admin=SimpleNamespace(id=5, username="root"),
        role_id=9,
        tenant_id=12,
    )

    assert result == TenantImpersonateResponse(
        impersonate_token="imp-token",
        tenant_code="tenant-a",
        tenant_name="Tenant A",
        expires_in=IMPERSONATE_TOKEN_EXPIRE_SECONDS,
    )
    tenant_service.validate_impersonation_role.assert_awaited_once_with(12, 9)


@pytest.mark.asyncio
async def test_tenant_config_workflow_service_rejects_invalid_group_keys(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        workflow_module.config_registry,
        "get_group",
        lambda _group_code: SimpleNamespace(
            scope=workflow_module.ConfigScope.ALL_TENANTS,
            configs=[SimpleNamespace(key="allowed_key")],
        ),
    )

    service = TenantConfigWorkflowService.__new__(TenantConfigWorkflowService)
    service._db = SimpleNamespace(commit=AsyncMock())
    service._config_service = SimpleNamespace(set_tenant_config=AsyncMock())
    service._role_option_service = SimpleNamespace()

    with pytest.raises(BusinessException) as exc_info:
        await service.update_group_configs(
            configs={"forbidden_key": "value"},
            group_code="security",
            tenant_id=77,
        )

    assert exc_info.value.code == ErrorCode.CONFIG_INVALID_KEYS
    service._config_service.set_tenant_config.assert_not_called()
    service._db.commit.assert_not_called()
