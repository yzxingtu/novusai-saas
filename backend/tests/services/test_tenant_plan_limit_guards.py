"""
Test type: behavioral
Regression for: tenant plan configuration silently producing unlimited or
incorrect entitlements.
Scope: plan permission assignment, plan quota/feature schemas, and tenant plan
binding preflight.
Mock strategy: service collaborators are faked; assertions target service-level
fail-closed contracts instead of mocked downstream success.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import ValidationError

from app.enums.error_code import ErrorCode
from app.exceptions import BusinessException, NotFoundException
from app.schemas.tenant.plan import TenantPlanCreateRequest


class _ScalarsResult:
    def __init__(self, values):
        self._values = values

    def all(self):
        return self._values


class _DBResult:
    def __init__(self, *, scalar=None, scalars=None):
        self._scalar = scalar
        self._scalars = list(scalars or [])

    def scalar_one_or_none(self):
        return self._scalar

    def scalars(self):
        return _ScalarsResult(self._scalars)


class _StatsRowResult:
    def __init__(self, *, used_bytes: int, file_count: int):
        self._row = SimpleNamespace(
            used_bytes=used_bytes,
            file_count=file_count,
        )

    def one(self):
        return self._row


@pytest.mark.asyncio
async def test_assign_permissions_rejects_invalid_ids_without_mutating_plan(
    mock_db,
) -> None:
    from app.services.tenant.tenant_plan_service import TenantPlanService

    plan = SimpleNamespace(id=8, features={}, permissions=["existing"])
    valid_permission = SimpleNamespace(id=101)

    service = TenantPlanService.__new__(TenantPlanService)
    service.db = mock_db
    service.repo = AsyncMock()
    service.repo.get_with_permissions = AsyncMock(return_value=plan)
    service._get_valid_permissions = AsyncMock(return_value=[valid_permission])
    service._sync_plan_plugin_entitlements = AsyncMock()

    with pytest.raises(BusinessException) as exc_info:
        await service.assign_permissions(8, [101, 999, 101])

    assert exc_info.value.data == {"invalid_permission_ids": [999]}
    assert plan.permissions == ["existing"]
    mock_db.flush.assert_not_awaited()
    service._sync_plan_plugin_entitlements.assert_not_awaited()


def test_plan_quota_schema_rejects_unknown_limit_keys() -> None:
    with pytest.raises(ValidationError):
        TenantPlanCreateRequest(
            name="Typo Plan",
            quota={"max_user": 10},
        )


def test_plan_features_schema_rejects_unknown_feature_keys() -> None:
    with pytest.raises(ValidationError):
        TenantPlanCreateRequest(
            name="Typo Plan",
            features={"ai_enable": False},
        )


@pytest.mark.asyncio
async def test_tenant_plan_preflight_snapshot_requires_active_plan(mock_db) -> None:
    from app.services.system.tenant_service import TenantService

    class _Result:
        def scalar_one_or_none(self):
            return None

    captured_statements: list[str] = []

    async def execute(stmt):
        captured_statements.append(str(stmt))
        return _Result()

    mock_db.execute = AsyncMock(side_effect=execute)
    service = TenantService.__new__(TenantService)
    service.db = mock_db

    with pytest.raises(NotFoundException):
        await service._get_plan_preflight_snapshot(12)

    assert captured_statements
    assert "tenant_plans.is_active" in captured_statements[0]


def test_tenant_quota_overrides_require_active_plan() -> None:
    from app.models.tenant.tenant import Tenant
    from app.models.tenant.tenant_plan import TenantPlan

    plan = TenantPlan(
        id=9,
        code="inactive",
        name="Inactive",
        is_active=False,
        quota={"max_custom_domains": 9, "allow_custom_domain": True},
    )
    tenant = Tenant(
        name="Inactive tenant",
        code="inactive-tenant",
        is_active=True,
        plan_id=9,
        quota={"max_custom_domains": 3, "allow_custom_domain": True},
    )
    tenant.tenant_plan = plan

    assert tenant.has_active_plan is False
    assert tenant.get_quota_value("allow_custom_domain", False) is False
    assert tenant.max_custom_domains == 0

    plan.is_active = True

    assert tenant.has_active_plan is True
    assert tenant.get_quota_value("allow_custom_domain", False) is True
    assert tenant.max_custom_domains == 3


def test_tenant_quota_overrides_require_active_tenant() -> None:
    from app.models.tenant.tenant import Tenant
    from app.models.tenant.tenant_plan import TenantPlan

    plan = TenantPlan(
        id=9,
        code="active",
        name="Active",
        is_active=True,
        quota={"allow_custom_domain": True},
    )
    tenant = Tenant(
        name="Disabled tenant",
        code="disabled-tenant",
        is_active=False,
        plan_id=9,
        quota={"allow_custom_domain": True},
    )
    tenant.tenant_plan = plan

    assert tenant.has_active_plan is False
    assert tenant.get_quota_value("allow_custom_domain", False) is False


@pytest.mark.asyncio
async def test_permission_role_assignment_rejects_ids_outside_active_plan(
    mock_db,
) -> None:
    from app.services.tenant.tenant_permission_role_service import (
        TenantPermissionRoleService,
    )

    role = SimpleNamespace(permissions=["existing"])
    plan_permission = SimpleNamespace(
        id=101,
        code="agent:list",
        type="operation",
        is_enabled=True,
        is_deleted=False,
    )
    tenant = SimpleNamespace(
        id=5,
        plan_id=9,
        tenant_plan=SimpleNamespace(is_active=True, permissions=[plan_permission]),
    )
    mock_db.execute = AsyncMock(
        side_effect=[
            _DBResult(scalars=[101, 102]),
            _DBResult(scalar=tenant),
        ]
    )
    service = TenantPermissionRoleService.__new__(TenantPermissionRoleService)
    service.db = mock_db
    service.tenant_id = 5

    with pytest.raises(BusinessException) as exc_info:
        await service._assign_permissions(role, [101, 102])

    assert exc_info.value.code == ErrorCode.FORBIDDEN
    assert exc_info.value.data == {"forbidden_permission_ids": [102]}
    assert role.permissions == ["existing"]
    mock_db.flush.assert_not_awaited()


@pytest.mark.asyncio
async def test_org_node_permission_assignment_rejects_ids_outside_active_plan(
    mock_db,
) -> None:
    from app.services.tenant.tenant_org_node_service import TenantOrgNodeService

    org_node = SimpleNamespace(permissions=["existing"])
    plan_permission = SimpleNamespace(
        id=201,
        code="tenant_user:list",
        type="operation",
        is_enabled=True,
        is_deleted=False,
    )
    tenant = SimpleNamespace(
        id=5,
        plan_id=9,
        tenant_plan=SimpleNamespace(is_active=True, permissions=[plan_permission]),
    )
    mock_db.execute = AsyncMock(
        side_effect=[
            _DBResult(scalars=[201, 202]),
            _DBResult(scalar=tenant),
        ]
    )
    service = TenantOrgNodeService.__new__(TenantOrgNodeService)
    service.db = mock_db
    service.tenant_id = 5

    with pytest.raises(BusinessException) as exc_info:
        await service._assign_permissions(org_node, [201, 202])

    assert exc_info.value.code == ErrorCode.FORBIDDEN
    assert exc_info.value.data == {"forbidden_permission_ids": [202]}
    assert org_node.permissions == ["existing"]
    mock_db.flush.assert_not_awaited()


@pytest.mark.asyncio
async def test_runtime_user_quota_rejects_inactive_plan_before_counting(
    mock_db,
) -> None:
    from app.services.tenant.quota_service import QuotaService

    tenant = SimpleNamespace(
        id=5,
        plan_id=9,
        quota={},
        tenant_plan=SimpleNamespace(is_active=False),
    )
    result = await QuotaService(mock_db, tenant).check_user_quota()

    assert result.allowed is False
    assert result.limit == -1
    mock_db.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_runtime_api_quota_rejects_inactive_plan_before_redis(
    mock_db,
    monkeypatch,
) -> None:
    from app.services.tenant import quota_service as quota_module
    from app.services.tenant.quota_service import QuotaService

    tenant = SimpleNamespace(
        id=5,
        plan_id=9,
        quota={},
        tenant_plan=SimpleNamespace(is_active=False),
    )
    monkeypatch.setattr(
        quota_module,
        "get_redis",
        AsyncMock(side_effect=AssertionError("redis should not be touched")),
    )

    result = await QuotaService(mock_db, tenant).check_api_calls_quota()

    assert result.allowed is False
    assert result.limit == -1
    mock_db.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_runtime_api_quota_rejects_missing_tenant_before_redis(
    mock_db,
    monkeypatch,
) -> None:
    from app.services.tenant import quota_service as quota_module
    from app.services.tenant.quota_service import QuotaService

    class _Result:
        def scalar_one_or_none(self):
            return None

    mock_db.execute = AsyncMock(return_value=_Result())
    monkeypatch.setattr(
        quota_module,
        "get_redis",
        AsyncMock(side_effect=AssertionError("redis should not be touched")),
    )

    result = await QuotaService.check_api_quota_for_tenant_id(mock_db, 404)

    assert result.allowed is False
    assert result.limit == -1


@pytest.mark.asyncio
async def test_chunk_upload_rechecks_plan_before_temporary_write(mock_db) -> None:
    from app.services.tenant.attachment_service import AttachmentService

    service = AttachmentService.__new__(AttachmentService)
    service.db = mock_db
    service.tenant_id = 5
    service._ensure_upload_enabled = AsyncMock()
    service._get_tenant = AsyncMock(
        return_value=SimpleNamespace(
            id=5,
            is_active=True,
            is_deleted=False,
            plan_id=9,
            quota={},
            tenant_plan=SimpleNamespace(is_active=False),
        )
    )
    service._load_session = AsyncMock(
        side_effect=AssertionError("session should not be loaded")
    )
    service._write_chunk = AsyncMock(
        side_effect=AssertionError("chunk should not be written")
    )

    with pytest.raises(BusinessException) as exc_info:
        await service.upload_chunk("upload-1", 0, MagicMock())

    assert exc_info.value.code == ErrorCode.FORBIDDEN
    service._ensure_upload_enabled.assert_awaited_once()
    service._load_session.assert_not_awaited()
    service._write_chunk.assert_not_awaited()


@pytest.mark.asyncio
async def test_storage_quota_stats_do_not_report_unlimited_for_inactive_plan(
    mock_db,
) -> None:
    from app.services.common.storage_quota_service import StorageQuotaService

    tenant = SimpleNamespace(
        id=5,
        is_active=True,
        is_deleted=False,
        plan_id=9,
        quota={"storage_limit_gb": 99, "max_file_size_mb": 512},
        tenant_plan=SimpleNamespace(is_active=False),
    )
    mock_db.execute = AsyncMock(
        side_effect=[
            _StatsRowResult(used_bytes=4096, file_count=2),
            _DBResult(scalar=tenant),
        ]
    )

    stats = await StorageQuotaService(mock_db).get_tenant_storage_stats(5)

    assert stats["used_bytes"] == 4096
    assert stats["file_count"] == 2
    assert stats["plan_available"] is False
    assert stats["unlimited"] is False
    assert stats["limit_gb"] == 0
    assert stats["limit_bytes"] == 0
    assert stats["remaining_bytes"] == 0
    assert stats["max_file_size_mb"] == 0


@pytest.mark.asyncio
async def test_custom_domain_gate_rejects_inactive_plan_quota_overrides(
    mock_db,
) -> None:
    from app.models.tenant.tenant import Tenant
    from app.models.tenant.tenant_plan import TenantPlan
    from app.services.system.tenant_domain_service import TenantDomainService

    class _Result:
        def scalar_one_or_none(self):
            plan = TenantPlan(
                id=7,
                code="inactive",
                name="Inactive",
                is_active=False,
                quota={"allow_custom_domain": True, "max_custom_domains": 5},
            )
            tenant = Tenant(
                id=3,
                name="Inactive tenant",
                code="inactive-tenant",
                plan_id=7,
                quota={"allow_custom_domain": True, "max_custom_domains": 2},
            )
            tenant.tenant_plan = plan
            return tenant

    mock_db.execute = AsyncMock(return_value=_Result())
    service = TenantDomainService.__new__(TenantDomainService)
    service.db = mock_db

    allowed, max_domains = await service._check_custom_domain_allowed(3)

    assert allowed is False
    assert max_domains == 0


@pytest.mark.asyncio
async def test_custom_domain_activation_rejects_inactive_plan(
    mock_db,
) -> None:
    from app.models.tenant.tenant import Tenant
    from app.models.tenant.tenant_plan import TenantPlan
    from app.services.system.tenant_domain_service import TenantDomainTenantService

    class _Result:
        def scalar_one_or_none(self):
            plan = TenantPlan(
                id=7,
                code="inactive",
                name="Inactive",
                is_active=False,
                quota={"allow_custom_domain": True, "max_custom_domains": 5},
            )
            tenant = Tenant(
                id=3,
                name="Inactive tenant",
                code="inactive-tenant",
                plan_id=7,
                quota={"allow_custom_domain": True, "max_custom_domains": 2},
            )
            tenant.tenant_plan = plan
            return tenant

    mock_db.execute = AsyncMock(return_value=_Result())
    service = TenantDomainTenantService.__new__(TenantDomainTenantService)
    service.db = mock_db
    service.tenant_id = 3
    service._get_domain_suffix = AsyncMock(return_value=".tenant.example")

    with pytest.raises(BusinessException) as exc_info:
        await service.ensure_custom_domain_entitled(
            3,
            SimpleNamespace(domain="custom.example.com"),
        )

    assert exc_info.value.code == ErrorCode.FORBIDDEN


@pytest.mark.asyncio
async def test_custom_domain_middleware_refuses_disabled_entitlement(
    mock_db,
) -> None:
    from app.middleware.tenant import TenantMiddleware
    from app.models.tenant.tenant import Tenant
    from app.models.tenant.tenant_domain import TenantDomain
    from app.models.tenant.tenant_plan import TenantPlan

    plan = TenantPlan(
        id=7,
        code="no-custom",
        name="No Custom Domains",
        is_active=True,
        quota={"allow_custom_domain": False, "max_custom_domains": 0},
    )
    tenant = Tenant(
        id=3,
        name="No custom tenant",
        code="no-custom-tenant",
        plan_id=7,
    )
    tenant.tenant_plan = plan
    domain = TenantDomain(
        id=11,
        tenant_id=3,
        domain="custom.example.com",
        is_verified=True,
    )
    domain.tenant = tenant

    class _Result:
        def scalar_one_or_none(self):
            return domain

    mock_db.execute = AsyncMock(return_value=_Result())
    middleware = TenantMiddleware(lambda *_args: None)

    resolved = await middleware._resolve_tenant(
        mock_db,
        tenant_code=None,
        host="custom.example.com",
        domain_type="custom",
    )

    assert resolved is None


@pytest.mark.asyncio
async def test_custom_ssl_quota_rejects_missing_tenant(mock_db) -> None:
    from app.services.system.ssl_certificate_service import SslCertificateService

    class _Result:
        def scalar_one_or_none(self):
            return None

    mock_db.execute = AsyncMock(return_value=_Result())
    service = SslCertificateService.__new__(SslCertificateService)
    service.db = mock_db

    with pytest.raises(BusinessException) as exc_info:
        await service._check_custom_ssl_quota(404)

    assert exc_info.value.code == ErrorCode.FORBIDDEN


@pytest.mark.asyncio
async def test_active_tenant_user_dependency_rejects_disabled_tenant(mock_db) -> None:
    from fastapi import HTTPException

    from app.core.deps import get_current_active_tenant_user

    class _Result:
        def scalar_one_or_none(self):
            return None

    mock_db.execute = AsyncMock(return_value=_Result())

    with pytest.raises(HTTPException) as exc_info:
        await get_current_active_tenant_user(
            db=mock_db,
            current_user=SimpleNamespace(
                id=17,
                is_active=True,
                tenant_id=5,
            ),
        )

    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_tenant_user_menu_hides_ai_pages_when_plan_ai_disabled(mock_db) -> None:
    from app.rbac.services.permission_domains.menu_query import PermissionMenuDomain

    class _Scalars:
        def __init__(self, values):
            self._values = values

        def all(self):
            return self._values

    class _TenantResult:
        def scalar_one_or_none(self):
            return SimpleNamespace(
                id=5,
                is_active=True,
                plan_id=9,
                quota={},
                tenant_plan=SimpleNamespace(
                    is_active=True,
                    get_feature=lambda _key, _default=False: False,
                ),
            )

    class _PermissionResult:
        def scalars(self):
            return _Scalars(
                [
                    SimpleNamespace(
                        id=1,
                        code="menu:user.dashboard",
                        parent_id=None,
                        type="menu",
                    ),
                    SimpleNamespace(
                        id=2,
                        code="menu:user.ai_chat",
                        parent_id=None,
                        type="menu",
                    ),
                ]
            )

    mock_db.execute = AsyncMock(side_effect=[_TenantResult(), _PermissionResult()])

    all_permissions = [
        SimpleNamespace(id=1, code="menu:user.dashboard", parent_id=None, type="menu"),
        SimpleNamespace(id=2, code="menu:user.ai_chat", parent_id=None, type="menu"),
    ]
    captured_codes: list[str] = []

    class _Service:
        db = mock_db

        async def get_enabled_permissions_by_scope(self, _scope):
            return all_permissions

        async def get_tenant_user_effective_permission_ids(self, _tenant_user):
            return {1, 2}

        def _build_menu_tree(self, permissions, _user_permission_codes):
            captured_codes.extend(permission.code for permission in permissions)
            return captured_codes

    menus = await PermissionMenuDomain(_Service()).get_tenant_user_menus(
        SimpleNamespace(tenant_id=5, role_id=3)
    )

    assert menus == ["menu:user.dashboard"]
    assert "menu:user.ai_chat" not in captured_codes
