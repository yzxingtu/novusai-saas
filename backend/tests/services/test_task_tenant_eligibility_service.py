"""Task tenant eligibility service tests.

Test type: behavioral
"""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.enums.common import ResourceScopeEnum
from app.enums.plugin import (
    PluginLicenseTypeEnum,
    PluginPricingTypeEnum,
    PluginStatusEnum,
)
from app.services.system.task_tenant_eligibility_service import (
    TaskTenantEligibilityRequirements,
    TaskTenantEligibilityService,
)


@pytest.mark.asyncio
async def test_resolve_tenant_model_eligibility_accepts_active_tenant_with_active_plan(
    mock_db,
) -> None:
    service = TaskTenantEligibilityService(mock_db)
    tenant = SimpleNamespace(
        id=42,
        is_deleted=False,
        is_active=True,
        plan_id=7,
        tenant_plan=SimpleNamespace(is_deleted=False, is_active=True),
    )

    result = await service.resolve_tenant_model_eligibility(42, tenant)

    assert result.is_eligible is True
    assert result.reason is None


@pytest.mark.asyncio
async def test_resolve_tenant_model_eligibility_rejects_missing_required_feature(
    mock_db,
) -> None:
    service = TaskTenantEligibilityService(
        mock_db,
        requirements=TaskTenantEligibilityRequirements(
            feature_codes=("storage_billing_enabled",)
        ),
    )
    tenant = SimpleNamespace(
        id=42,
        is_deleted=False,
        is_active=True,
        plan_id=7,
        tenant_plan=SimpleNamespace(
            is_deleted=False,
            is_active=True,
            features={"storage_billing_enabled": False},
        ),
    )

    result = await service.resolve_tenant_model_eligibility(42, tenant)

    assert result.is_eligible is False
    assert result.reason == "tenant_entitlement_not_available"


@pytest.mark.asyncio
async def test_resolve_tenant_model_eligibility_rejects_missing_active_plan(
    mock_db,
) -> None:
    service = TaskTenantEligibilityService(mock_db)
    tenant = SimpleNamespace(
        id=42,
        is_deleted=False,
        is_active=True,
        plan_id=None,
        tenant_plan=None,
    )

    result = await service.resolve_tenant_model_eligibility(42, tenant)

    assert result.is_eligible is False
    assert result.reason == "tenant_plan_not_available"


def test_resolve_all_tenant_ids_sync_excludes_disabled_all_tenants_binding() -> None:
    tenant_query = MagicMock()
    tenant_query.join.return_value = tenant_query
    tenant_query.filter.return_value = tenant_query
    tenant_query.outerjoin.return_value = tenant_query
    tenant_query.order_by.return_value = tenant_query
    tenant_query.all.return_value = [(7,), (11,)]

    session = MagicMock()
    session.query.return_value = tenant_query

    tenant_ids = TaskTenantEligibilityService.resolve_all_tenant_ids_sync(
        session,
        task_definition_id=18,
    )

    assert tenant_ids == [7, 11]
    tenant_query.outerjoin.assert_called_once()
    assert tenant_query.filter.call_count >= 2


def test_resolve_all_tenant_ids_sync_filters_required_plan_features() -> None:
    tenant_query = MagicMock()
    tenant_query.join.return_value = tenant_query
    tenant_query.filter.return_value = tenant_query
    tenant_query.order_by.return_value = tenant_query
    tenant_query.all.return_value = [
        (7, {"storage_billing_enabled": True}),
        (11, {"storage_billing_enabled": False}),
        (13, {}),
    ]

    session = MagicMock()
    session.query.return_value = tenant_query

    tenant_ids = TaskTenantEligibilityService.resolve_all_tenant_ids_sync(
        session,
        requirements=TaskTenantEligibilityRequirements(
            feature_codes=("storage_billing_enabled",)
        ),
    )

    assert tenant_ids == [7]


class _FakeQuery:
    def __init__(self, *, first_result=None, all_result=None) -> None:
        self._first_result = first_result
        self._all_result = all_result or []

    def filter(self, *_args):
        return self

    def first(self):
        return self._first_result

    def all(self):
        return self._all_result


def test_sync_plugin_requirements_accept_enabled_all_tenants_free_plugin() -> None:
    plugin = SimpleNamespace(
        id=5,
        name="storage-billing",
        status=PluginStatusEnum.ENABLED.value,
        scope=ResourceScopeEnum.ALL_TENANTS.value,
        manifest={"compatibility": {"editions": ["saas"], "surfaces": ["tenant"]}},
        pricing_type=PluginPricingTypeEnum.FREE.value,
    )
    session = MagicMock()
    session.query.return_value = _FakeQuery(first_result=plugin)

    allowed = TaskTenantEligibilityService._plugin_requirements_allow_tenant_sync(
        session,
        42,
        TaskTenantEligibilityRequirements(plugin_names=("storage-billing",)),
    )

    assert allowed is True


def test_sync_plugin_requirements_reject_missing_selected_tenant_assignment() -> None:
    plugin = SimpleNamespace(
        id=5,
        name="storage-billing",
        status=PluginStatusEnum.ENABLED.value,
        scope=ResourceScopeEnum.SELECTED_TENANTS.value,
        manifest={"compatibility": {"editions": ["saas"], "surfaces": ["tenant"]}},
        pricing_type=PluginPricingTypeEnum.FREE.value,
    )
    session = MagicMock()
    session.query.side_effect = [
        _FakeQuery(first_result=plugin),
        _FakeQuery(first_result=None),
    ]

    allowed = TaskTenantEligibilityService._plugin_requirements_allow_tenant_sync(
        session,
        42,
        TaskTenantEligibilityRequirements(plugin_names=("storage-billing",)),
    )

    assert allowed is False


def _paid_all_tenants_plugin() -> SimpleNamespace:
    return SimpleNamespace(
        id=5,
        name="storage-billing",
        status=PluginStatusEnum.ENABLED.value,
        scope=ResourceScopeEnum.ALL_TENANTS.value,
        manifest={"compatibility": {"editions": ["saas"], "surfaces": ["tenant"]}},
        pricing_type=PluginPricingTypeEnum.PAID.value,
    )


def test_sync_plugin_requirements_reject_paid_plugin_without_license() -> None:
    session = MagicMock()
    session.query.side_effect = [
        _FakeQuery(first_result=_paid_all_tenants_plugin()),
        _FakeQuery(all_result=[]),
    ]

    allowed = TaskTenantEligibilityService._plugin_requirements_allow_tenant_sync(
        session,
        42,
        TaskTenantEligibilityRequirements(plugin_names=("storage-billing",)),
    )

    assert allowed is False


def test_sync_plugin_requirements_reject_paid_plugin_with_expired_license() -> None:
    expired_license = SimpleNamespace(
        license_type=PluginLicenseTypeEnum.FIXED_TERM.value,
        expires_at=datetime.now(timezone.utc) - timedelta(days=1),
        trial_expires_at=None,
    )
    session = MagicMock()
    session.query.side_effect = [
        _FakeQuery(first_result=_paid_all_tenants_plugin()),
        _FakeQuery(all_result=[expired_license]),
    ]

    allowed = TaskTenantEligibilityService._plugin_requirements_allow_tenant_sync(
        session,
        42,
        TaskTenantEligibilityRequirements(plugin_names=("storage-billing",)),
    )

    assert allowed is False


def test_sync_plugin_requirements_accept_paid_plugin_with_valid_license() -> None:
    valid_license = SimpleNamespace(
        license_type=PluginLicenseTypeEnum.PERPETUAL.value,
        expires_at=None,
        trial_expires_at=None,
    )
    session = MagicMock()
    session.query.side_effect = [
        _FakeQuery(first_result=_paid_all_tenants_plugin()),
        _FakeQuery(all_result=[valid_license]),
    ]

    allowed = TaskTenantEligibilityService._plugin_requirements_allow_tenant_sync(
        session,
        42,
        TaskTenantEligibilityRequirements(plugin_names=("storage-billing",)),
    )

    assert allowed is True
