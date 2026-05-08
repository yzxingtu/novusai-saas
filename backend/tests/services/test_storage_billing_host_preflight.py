"""Storage billing host preflight contract tests.

覆盖：
1. tenant_plan preflight registry 的优先级与阻断语义
2. plan / tenant service 对 preflight 的接入
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.exceptions.base import BusinessException
from app.plugins.tenant_plan_preflight import (
    TenantPlanPreflightRegistry,
    get_tenant_plan_preflight_registry,
    run_tenant_plan_preflight,
)
from app.schemas.tenant.plan import TenantPlanCreateRequest, TenantPlanUpdateRequest


class TestTenantPlanPreflightRegistry:
    @pytest.mark.asyncio
    async def test_registry_stops_on_first_denial_by_priority(self):
        registry = get_tenant_plan_preflight_registry()
        registry.reset()
        registry = get_tenant_plan_preflight_registry()

        calls: list[str] = []

        async def later_handler(_payload):
            calls.append("later")
            return {
                "allowed": True,
                "reason_code": "allowed",
                "message": "",
                "details": {},
            }

        async def deny_handler(_payload):
            calls.append("deny")
            return {
                "allowed": False,
                "reason_code": "storage_billing_missing_driver",
                "message": "blocked",
                "details": {"plugin": "storage-billing"},
            }

        async def should_not_run(_payload):
            calls.append("never")
            return {
                "allowed": True,
                "reason_code": "allowed",
                "message": "",
                "details": {},
            }

        registry.register("later", later_handler, priority=80)
        registry.register("deny", deny_handler, priority=10)
        registry.register("never", should_not_run, priority=90)

        result = await registry.run(
            {
                "operation": "plan_create",
                "plan_id": None,
                "tenant_id": None,
                "features": {"storage_billing_enabled": True},
                "quota": {},
                "context": {},
            }
        )

        assert result["allowed"] is False
        assert result["reason_code"] == "storage_billing_missing_driver"
        assert calls == ["deny"]

    @pytest.mark.asyncio
    async def test_registry_fails_closed_on_malformed_result(self):
        registry = get_tenant_plan_preflight_registry()
        registry.reset()
        registry = get_tenant_plan_preflight_registry()

        async def malformed_handler(_payload):
            return {
                "reason_code": "bad_contract",
                "message": "allowed flag is required",
                "details": {"owner": "storage-billing"},
            }

        registry.register("malformed", malformed_handler, priority=10)

        result = await registry.run(
            {
                "operation": "plan_create",
                "plan_id": None,
                "tenant_id": None,
                "features": {"storage_billing_enabled": True},
                "quota": {},
                "context": {},
            }
        )

        assert result["allowed"] is False
        assert result["reason_code"] == "bad_contract"
        assert result["details"] == {"owner": "storage-billing"}

    @pytest.mark.asyncio
    async def test_registry_rejects_string_allowed_value(self):
        registry = get_tenant_plan_preflight_registry()
        registry.reset()
        registry = get_tenant_plan_preflight_registry()

        async def malformed_handler(_payload):
            return {
                "allowed": "true",
                "reason_code": "bad_allowed_type",
                "message": "allowed must be boolean true",
                "details": {},
            }

        registry.register("malformed", malformed_handler, priority=10)

        result = await registry.run(
            {
                "operation": "tenant_plan_switch",
                "plan_id": 12,
                "tenant_id": 34,
                "features": {},
                "quota": {},
                "context": {},
            }
        )

        assert result["allowed"] is False
        assert result["reason_code"] == "bad_allowed_type"

    @pytest.mark.asyncio
    async def test_runner_bootstraps_storage_billing_host_rules(self, monkeypatch):
        from app.plugins import feature_entitlement_guards as guard_module

        TenantPlanPreflightRegistry.reset()

        async def fake_get_plugin_status_map(_plugin_names):
            return {"storage-billing": "enabled"}

        monkeypatch.setattr(
            guard_module,
            "_get_plugin_status_map",
            fake_get_plugin_status_map,
        )
        monkeypatch.setattr(
            guard_module,
            "_get_platform_storage_driver",
            AsyncMock(return_value="local"),
        )

        result = await run_tenant_plan_preflight(
            {
                "operation": "plan_create",
                "plan_id": None,
                "tenant_id": None,
                "features": {"storage_billing_enabled": True},
                "quota": {},
                "context": {},
            }
        )

        assert result["allowed"] is False
        assert result["reason_code"] == "storage_billing_platform_driver_not_billable"

    @pytest.mark.asyncio
    async def test_runner_allows_billable_platform_driver_when_plugin_and_driver_exist(
        self, monkeypatch
    ):
        from app.plugins import feature_entitlement_guards as guard_module

        TenantPlanPreflightRegistry.reset()

        async def fake_get_plugin_status_map(_plugin_names):
            return {
                "storage-billing": "enabled",
                "tencent-cos": "enabled",
            }

        monkeypatch.setattr(
            guard_module,
            "_get_plugin_status_map",
            fake_get_plugin_status_map,
        )
        monkeypatch.setattr(
            guard_module,
            "_get_platform_storage_driver",
            AsyncMock(return_value="tencent-cos"),
        )

        result = await run_tenant_plan_preflight(
            {
                "operation": "plan_create",
                "plan_id": None,
                "tenant_id": None,
                "features": {"storage_billing_enabled": True},
                "quota": {},
                "context": {},
            }
        )

        assert result["allowed"] is True

    @pytest.mark.asyncio
    async def test_runner_blocks_when_current_platform_driver_plugin_is_disabled(
        self, monkeypatch
    ):
        from app.plugins import feature_entitlement_guards as guard_module

        TenantPlanPreflightRegistry.reset()

        async def fake_get_plugin_status_map(_plugin_names):
            return {
                "storage-billing": "enabled",
                "tencent-cos": "disabled",
                "aliyun-oss": "enabled",
            }

        monkeypatch.setattr(
            guard_module,
            "_get_plugin_status_map",
            fake_get_plugin_status_map,
        )
        monkeypatch.setattr(
            guard_module,
            "_get_platform_storage_driver",
            AsyncMock(return_value="tencent-cos"),
        )

        result = await run_tenant_plan_preflight(
            {
                "operation": "plan_create",
                "plan_id": None,
                "tenant_id": None,
                "features": {"storage_billing_enabled": True},
                "quota": {},
                "context": {},
            }
        )

        assert result["allowed"] is False
        assert (
            result["reason_code"]
            == "storage_billing_platform_driver_plugin_unavailable"
        )

    @pytest.mark.asyncio
    async def test_lifecycle_guard_blocks_disabling_active_platform_driver(
        self, monkeypatch
    ):
        from app.plugins import feature_entitlement_guards as guard_module

        monkeypatch.setattr(
            guard_module,
            "_get_active_feature_plan_summaries",
            AsyncMock(
                return_value=[
                    {
                        "plan_id": 12,
                        "plan_name": "Storage Billing Plan",
                        "features": {"storage_billing_enabled": True},
                    }
                ]
            ),
        )
        monkeypatch.setattr(
            guard_module,
            "_get_plugin_status_map",
            AsyncMock(
                return_value={
                    "tencent-cos": "enabled",
                    "aliyun-oss": "enabled",
                }
            ),
        )
        monkeypatch.setattr(
            guard_module,
            "_get_platform_storage_driver",
            AsyncMock(return_value="tencent-cos"),
        )

        result = await guard_module._feature_managed_lifecycle_guard(
            {"plugin_name": "tencent-cos"}
        )

        assert result is not None
        assert result["allowed"] is False
        assert result["reason_code"] == "storage_billing_active_platform_driver_blocked"

    @pytest.mark.asyncio
    async def test_runner_blocks_when_platform_driver_plugin_is_not_enabled(
        self, monkeypatch
    ):
        from app.plugins import feature_entitlement_guards as guard_module

        TenantPlanPreflightRegistry.reset()

        async def fake_get_plugin_status_map(_plugin_names):
            return {
                "storage-billing": "enabled",
                "aliyun-oss": "enabled",
                "tencent-cos": "disabled",
            }

        monkeypatch.setattr(
            guard_module,
            "_get_plugin_status_map",
            fake_get_plugin_status_map,
        )
        monkeypatch.setattr(
            guard_module,
            "_get_platform_storage_driver",
            AsyncMock(return_value="tencent-cos"),
        )

        result = await run_tenant_plan_preflight(
            {
                "operation": "plan_create",
                "plan_id": None,
                "tenant_id": None,
                "features": {"storage_billing_enabled": True},
                "quota": {},
                "context": {},
            }
        )

        assert result["allowed"] is False
        assert (
            result["reason_code"]
            == "storage_billing_platform_driver_plugin_unavailable"
        )


class TestTenantPlanServicePreflight:
    @pytest.mark.asyncio
    async def test_create_plan_runs_preflight_with_effective_snapshot(self, mock_db):
        from app.services.tenant.tenant_plan_service import TenantPlanService

        service = TenantPlanService.__new__(TenantPlanService)
        service.db = mock_db
        service.repo = AsyncMock()
        service._generate_plan_code = AsyncMock(return_value="plan_test01")
        service._run_plan_preflight = AsyncMock()
        service._sync_plan_plugin_entitlements = AsyncMock()
        service.create = AsyncMock(return_value=type("Plan", (), {"id": 1})())

        request = TenantPlanCreateRequest(
            name="Storage Billing Plan",
            features={"storage_billing_enabled": True},
            quota={"storage_limit_gb": 50},
        )

        await service.create_plan(request)

        service._run_plan_preflight.assert_awaited_once_with(
            operation="plan_create",
            plan_id=None,
            features={"storage_billing_enabled": True},
            quota={"storage_limit_gb": 50},
            context={"code": "plan_test01", "name": "Storage Billing Plan"},
        )
        service._sync_plan_plugin_entitlements.assert_awaited_once_with(
            1,
            {"storage_billing_enabled": True},
        )

    @pytest.mark.asyncio
    async def test_run_plan_preflight_raises_business_exception_on_denial(
        self, mock_db, monkeypatch
    ):
        from app.services.tenant import tenant_plan_service as service_module
        from app.services.tenant.tenant_plan_service import TenantPlanService

        service = TenantPlanService.__new__(TenantPlanService)
        service.db = mock_db
        service.repo = AsyncMock()

        monkeypatch.setattr(
            service_module,
            "run_tenant_plan_preflight",
            AsyncMock(
                return_value={
                    "allowed": False,
                    "reason_code": "storage_billing_plugin_disabled",
                    "message": "blocked by preflight",
                    "details": {"plugin": "storage-billing"},
                }
            ),
        )

        with pytest.raises(BusinessException) as exc_info:
            await service._run_plan_preflight(
                operation="plan_update",
                plan_id=12,
                features={"storage_billing_enabled": True},
                quota={},
                context={"name": "Plan A"},
            )

        assert exc_info.value.data["reason_code"] == "storage_billing_plugin_disabled"
        assert exc_info.value.data["plan_id"] == 12

    @pytest.mark.asyncio
    async def test_run_plan_preflight_raises_on_malformed_allow_result(
        self, mock_db, monkeypatch
    ):
        from app.services.tenant import tenant_plan_service as service_module
        from app.services.tenant.tenant_plan_service import TenantPlanService

        service = TenantPlanService.__new__(TenantPlanService)
        service.db = mock_db
        service.repo = AsyncMock()

        monkeypatch.setattr(
            service_module,
            "run_tenant_plan_preflight",
            AsyncMock(
                return_value={
                    "reason_code": "bad_contract",
                    "message": "blocked by malformed preflight",
                    "details": {"plugin": "storage-billing"},
                }
            ),
        )

        with pytest.raises(BusinessException) as exc_info:
            await service._run_plan_preflight(
                operation="plan_update",
                plan_id=12,
                features={"storage_billing_enabled": True},
                quota={},
                context={"name": "Plan A"},
            )

        assert exc_info.value.data["reason_code"] == "bad_contract"
        assert exc_info.value.data["details"] == {"plugin": "storage-billing"}

    @pytest.mark.asyncio
    async def test_update_plan_uses_existing_snapshot_when_request_omits_features(
        self, mock_db
    ):
        from app.services.tenant.tenant_plan_service import TenantPlanService

        plan = type(
            "Plan",
            (),
            {
                "id": 2,
                "code": "plan_existing",
                "name": "Existing Plan",
                "features": {"storage_billing_enabled": True},
                "quota": {"storage_limit_gb": 20},
            },
        )()

        service = TenantPlanService.__new__(TenantPlanService)
        service.db = mock_db
        service.repo = AsyncMock()
        service.get_by_id = AsyncMock(return_value=plan)
        service._run_plan_preflight = AsyncMock()
        service._sync_plan_plugin_entitlements = AsyncMock()
        service.update = AsyncMock(return_value=plan)

        request = TenantPlanUpdateRequest(name="Renamed Plan")
        await service.update_plan(2, request)

        service._run_plan_preflight.assert_awaited_once_with(
            operation="plan_update",
            plan_id=2,
            features={"storage_billing_enabled": True},
            quota={"storage_limit_gb": 20},
            context={"code": "plan_existing", "name": "Renamed Plan"},
        )
        service._sync_plan_plugin_entitlements.assert_awaited_once_with(
            2,
            {"storage_billing_enabled": True},
        )

    @pytest.mark.asyncio
    async def test_assign_permissions_reapplies_feature_managed_entitlements(
        self, mock_db
    ):
        from app.services.tenant.tenant_plan_service import TenantPlanService

        plan = type(
            "Plan",
            (),
            {
                "id": 8,
                "features": {"storage_billing_enabled": True},
                "permissions": [],
            },
        )()
        valid_permissions = [SimpleNamespace(id=101), SimpleNamespace(id=102)]

        service = TenantPlanService.__new__(TenantPlanService)
        service.db = mock_db
        service.repo = AsyncMock()
        service.repo.get_with_permissions = AsyncMock(return_value=plan)
        service._get_valid_permissions = AsyncMock(return_value=valid_permissions)
        service._sync_plan_plugin_entitlements = AsyncMock()

        await service.assign_permissions(8, [101, 102])

        assert plan.permissions == valid_permissions
        service._sync_plan_plugin_entitlements.assert_awaited_once_with(
            8,
            {"storage_billing_enabled": True},
        )


class TestTenantServicePreflight:
    @pytest.mark.asyncio
    async def test_create_tenant_runs_preflight_when_plan_id_present(self, mock_db):
        from app.services.system.tenant_service import TenantService

        service = TenantService.__new__(TenantService)
        service.db = mock_db
        service.repo = AsyncMock()
        service._generate_tenant_code = AsyncMock(return_value="tabc12345")
        service._get_plan_preflight_snapshot = AsyncMock(
            return_value=(
                {"storage_billing_enabled": True},
                {"storage_limit_gb": 100},
            )
        )
        service._run_plan_preflight = AsyncMock(
            side_effect=BusinessException(message="blocked")
        )

        with pytest.raises(BusinessException):
            await service.create_tenant(
                name="Tenant A",
                admin_username="owner_a",
                admin_email="owner_a@example.com",
                admin_password="secret",
                plan_id=3,
            )

        service._run_plan_preflight.assert_awaited_once_with(
            operation="tenant_create",
            plan_id=3,
            tenant_id=None,
            features={"storage_billing_enabled": True},
            quota={"storage_limit_gb": 100},
            context={"tenant_code": "tabc12345", "tenant_name": "Tenant A"},
        )

    @pytest.mark.asyncio
    async def test_update_tenant_runs_preflight_when_plan_changes(self, mock_db):
        from app.services.system.tenant_service import TenantService

        tenant = type(
            "Tenant",
            (),
            {
                "id": 7,
                "code": "toldplan1",
                "name": "Tenant B",
                "plan_id": 1,
            },
        )()

        service = TenantService.__new__(TenantService)
        service.db = mock_db
        service.repo = AsyncMock()
        service.get_by_id = AsyncMock(return_value=tenant)
        service.update = AsyncMock(return_value=tenant)
        service._get_plan_preflight_snapshot = AsyncMock(
            return_value=(
                {"storage_billing_enabled": True},
                {"storage_limit_gb": 200},
            )
        )
        service._run_plan_preflight = AsyncMock()

        await service.update_tenant(7, {"plan_id": 2})

        service._run_plan_preflight.assert_awaited_once_with(
            operation="tenant_plan_switch",
            plan_id=2,
            tenant_id=7,
            features={"storage_billing_enabled": True},
            quota={"storage_limit_gb": 200},
            context={
                "tenant_code": "toldplan1",
                "tenant_name": "Tenant B",
                "previous_plan_id": 1,
            },
        )
