"""Test type: structural + behavioral.

中文: 覆盖插件 edition/surface/tenant exposure contract 与 SaaS fail-closed 运行时闸门。
EN: Covers the plugin edition/surface/tenant exposure contract and the SaaS
fail-closed runtime gate.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.enums.common import ResourceScopeEnum
from app.enums.plugin import PluginStatusEnum
from app.exceptions import BusinessException
from app.plugins.exposure_policy import build_plugin_exposure_profile
from app.plugins.manifest import PluginManifest
from app.plugins.runtime_gate import evaluate_plugin_runtime_gate
from app.services.system.plugin_read_model_service import PluginReadModelService
from app.services.system.plugin_service import PluginService


class _OneOrNoneResult:
    def __init__(self, row: tuple[object, ...] | None) -> None:
        self._row = row

    def one_or_none(self) -> tuple[object, ...] | None:
        return self._row


class _ScalarOneOrNoneResult:
    def __init__(self, value: object | None) -> None:
        self._value = value

    def scalar_one_or_none(self) -> object | None:
        return self._value


class _ScalarsAllResult:
    def __init__(self, values: list[object]) -> None:
        self._values = values

    def scalars(self):
        return self

    def all(self) -> list[object]:
        return self._values


def _base_manifest(scope: str = ResourceScopeEnum.ALL_TENANTS.value) -> dict:
    return {
        "name": "demo-plugin",
        "version": "1.0.0",
        "display_name": {"en": "Demo Plugin"},
        "scope": scope,
    }


def _plugin_row(
    manifest: dict,
    *,
    scope: str = ResourceScopeEnum.ALL_TENANTS.value,
) -> tuple[object, ...]:
    return (
        7,
        "demo-plugin",
        scope,
        PluginStatusEnum.ENABLED.value,
        manifest,
        {},
        [],
        "free",
    )


def test_structural_manifest_compatibility_profile_defaults_and_aliases() -> None:
    """Test type: structural. Manifest compatibility aliases normalize deterministically."""
    legacy_manifest = PluginManifest.model_validate(
        _base_manifest(ResourceScopeEnum.GLOBAL_SHARED.value)
    )

    legacy_profile = build_plugin_exposure_profile(
        legacy_manifest,
        scope=legacy_manifest.scope,
    )

    assert legacy_profile.to_dict() == {
        "current_edition": "saas",
        "editions": ["saas"],
        "declared_editions": ["saas"],
        "surfaces": ["admin", "tenant"],
        "is_saas_compatible": True,
        "is_single_management_compatible": False,
        "tenant_exposure": "scope_default",
        "tenant_assignment_required": False,
        "tenant_runtime_scope": "global_shared",
        "tenant_runtime_denial_reason": None,
    }

    payload = _base_manifest(ResourceScopeEnum.ALL_TENANTS.value)
    payload["compatibility"] = {
        "editions": ["saas", "single-management"],
        "surfaces": ["platform-admin", "tenant-scoped"],
        "tenant_exposure": "tenant-scoped",
    }

    manifest = PluginManifest.model_validate(payload)
    profile = build_plugin_exposure_profile(manifest, scope=manifest.scope)

    assert manifest.compatibility is not None
    assert manifest.compatibility.editions == ["saas", "single_management"]
    assert manifest.compatibility.surfaces == ["admin", "tenant"]
    assert manifest.compatibility.tenant_exposure == "selected_tenants"
    assert profile.to_dict() == {
        "current_edition": "saas",
        "editions": ["saas", "single_management"],
        "declared_editions": ["saas", "single_management"],
        "surfaces": ["admin", "tenant"],
        "is_saas_compatible": True,
        "is_single_management_compatible": True,
        "tenant_exposure": "selected_tenants",
        "tenant_assignment_required": True,
        "tenant_runtime_scope": "selected_tenants",
        "tenant_runtime_denial_reason": None,
    }


def test_structural_read_model_attaches_derived_profile_without_key_churn() -> None:
    """Test type: structural. Read models attach the derived public profile."""
    data = {
        "id": 7,
        "name": "demo-plugin",
        "scope": ResourceScopeEnum.ALL_TENANTS.value,
        "manifest": {
            **_base_manifest(ResourceScopeEnum.ALL_TENANTS.value),
            "compatibility": {
                "editions": ["saas"],
                "surfaces": ["tenant"],
                "tenant_exposure": "selected_tenants",
            },
        },
    }

    payload = PluginReadModelService._attach_compatibility_profile(dict(data))

    assert payload["id"] == 7
    assert payload["name"] == "demo-plugin"
    assert payload["scope"] == "all_tenants"
    assert payload["compatibility_profile"] == {
        "current_edition": "saas",
        "editions": ["saas"],
        "declared_editions": ["saas"],
        "surfaces": ["tenant"],
        "is_saas_compatible": True,
        "is_single_management_compatible": False,
        "tenant_exposure": "selected_tenants",
        "tenant_assignment_required": True,
        "tenant_runtime_scope": "selected_tenants",
        "tenant_runtime_denial_reason": None,
    }


@pytest.mark.asyncio
async def test_behavioral_saas_tenant_gate_denies_single_management_only_plugin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test type: behavioral. SaaS tenant runtime denies single-management-only plugins before scope checks."""
    manifest = _base_manifest(ResourceScopeEnum.ALL_TENANTS.value)
    manifest["compatibility"] = {
        "editions": ["single_management"],
        "surfaces": ["tenant"],
        "tenant_exposure": "all_tenants",
    }

    db = AsyncMock()
    db.execute = AsyncMock(return_value=_OneOrNoneResult(_plugin_row(manifest)))
    monkeypatch.setattr(
        "app.plugins.runtime_gate.get_plugin_runtime_license_status",
        AsyncMock(return_value={"runtime_allowed": True, "status": "not_required"}),
    )
    monkeypatch.setattr(
        "app.plugins.runtime_gate.ScopeChecker.is_visible_to_tenant",
        AsyncMock(side_effect=AssertionError("scope check should not run")),
    )

    gate = await evaluate_plugin_runtime_gate(
        db,
        "demo-plugin",
        tenant_id=42,
        require_enabled=True,
        enforce_scope=True,
    )

    assert gate.allowed is False
    assert gate.reason_code == "edition_denied"
    assert gate.compatibility_profile is not None
    assert gate.compatibility_profile["is_saas_compatible"] is False
    assert gate.compatibility_profile["is_single_management_compatible"] is True
    db.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_behavioral_admin_gate_allows_single_management_management(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test type: behavioral. Platform admins may manage plugins that are not tenant-runnable."""
    manifest = _base_manifest(ResourceScopeEnum.ALL_TENANTS.value)
    manifest["compatibility"] = {
        "editions": ["single_management"],
        "surfaces": ["admin"],
        "tenant_exposure": "none",
    }

    db = AsyncMock()
    db.execute = AsyncMock(return_value=_OneOrNoneResult(_plugin_row(manifest)))
    monkeypatch.setattr(
        "app.plugins.runtime_gate.get_plugin_runtime_license_status",
        AsyncMock(return_value={"runtime_allowed": True, "status": "not_required"}),
    )

    gate = await evaluate_plugin_runtime_gate(
        db,
        "demo-plugin",
        tenant_id=None,
        require_enabled=True,
        enforce_scope=False,
    )

    assert gate.allowed is True
    assert gate.reason_code == "allowed"
    assert gate.compatibility_profile is not None
    assert gate.compatibility_profile["is_saas_compatible"] is False
    assert gate.compatibility_profile["tenant_runtime_denial_reason"] == (
        "edition_denied"
    )
    db.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_behavioral_selected_tenant_exposure_requires_assignment_on_global_scope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test type: behavioral. Selected tenant exposure narrows legacy broad scopes to assignments."""
    manifest = _base_manifest(ResourceScopeEnum.GLOBAL_SHARED.value)
    manifest["compatibility"] = {
        "editions": ["saas"],
        "surfaces": ["admin", "tenant"],
        "tenant_exposure": "selected_tenants",
    }

    db = AsyncMock()
    db.execute = AsyncMock(
        side_effect=[
            _OneOrNoneResult(
                _plugin_row(
                    manifest,
                    scope=ResourceScopeEnum.GLOBAL_SHARED.value,
                )
            ),
            _ScalarOneOrNoneResult(None),
        ]
    )
    monkeypatch.setattr(
        "app.plugins.runtime_gate.get_plugin_runtime_license_status",
        AsyncMock(return_value={"runtime_allowed": True, "status": "not_required"}),
    )

    gate = await evaluate_plugin_runtime_gate(
        db,
        "demo-plugin",
        tenant_id=42,
        require_enabled=True,
        enforce_scope=True,
    )

    assert gate.allowed is False
    assert gate.reason_code == "tenant_assignment_required"
    assert gate.plugin_scope == "global_shared"
    assert gate.compatibility_profile is not None
    assert gate.compatibility_profile["tenant_runtime_scope"] == "selected_tenants"
    assert gate.compatibility_profile["tenant_assignment_required"] is True
    assert db.execute.await_count == 2


def _selected_tenant_plugin() -> SimpleNamespace:
    manifest = _base_manifest(ResourceScopeEnum.GLOBAL_SHARED.value)
    manifest["compatibility"] = {
        "editions": ["saas"],
        "surfaces": ["tenant"],
        "tenant_exposure": "selected_tenants",
    }
    manifest["extensions"] = {
        "permissions": [
            {
                "actions": ["view"],
                "code": "demo_portal",
                "scope": "tenant",
            }
        ]
    }
    return SimpleNamespace(
        id=7,
        manifest=manifest,
        name="demo-plugin",
        scope=ResourceScopeEnum.GLOBAL_SHARED.value,
    )


def _plugin_service_for_assignment(db, plugin: SimpleNamespace) -> PluginService:
    service = PluginService.__new__(PluginService)
    service.db = db
    service.repo = SimpleNamespace(get_by_id=AsyncMock(return_value=plugin))
    return service


def _tenant(
    *,
    permissions: list[SimpleNamespace] | None = None,
    tenant_id: int = 42,
    active: bool = True,
    plan_active: bool = True,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=tenant_id,
        is_active=active,
        is_deleted=False,
        plan_id=12,
        tenant_plan=SimpleNamespace(
            is_active=plan_active,
            permissions=permissions or [],
        ),
    )


@pytest.mark.asyncio
async def test_behavioral_assign_tenants_rejects_inactive_plan_before_writing() -> None:
    """Test type: behavioral. Tenant plugin assignment fails closed for inactive plans."""
    plugin = _selected_tenant_plugin()
    db = AsyncMock()
    db.add = MagicMock()
    db.execute = AsyncMock(return_value=_ScalarsAllResult([_tenant(plan_active=False)]))
    db.flush = AsyncMock()
    service = _plugin_service_for_assignment(db, plugin)

    with pytest.raises(BusinessException) as exc_info:
        await service.assign_tenants(plugin.id, [42])

    assert "42" in exc_info.value.message
    db.add.assert_not_called()
    db.flush.assert_not_awaited()


@pytest.mark.asyncio
async def test_behavioral_assign_tenants_requires_plan_plugin_entitlement() -> None:
    """Test type: behavioral. Tenant plugin assignment fails closed without plan entitlement."""
    plugin = _selected_tenant_plugin()
    db = AsyncMock()
    db.add = MagicMock()
    db.execute = AsyncMock(
        return_value=_ScalarsAllResult(
            [
                _tenant(
                    permissions=[
                        SimpleNamespace(
                            code="plugin.other.demo:view",
                            is_deleted=False,
                            is_enabled=True,
                            scope="tenant",
                        )
                    ]
                )
            ]
        )
    )
    db.flush = AsyncMock()
    service = _plugin_service_for_assignment(db, plugin)

    with pytest.raises(BusinessException) as exc_info:
        await service.assign_tenants(plugin.id, [42])

    assert "42" in exc_info.value.message
    db.add.assert_not_called()
    db.flush.assert_not_awaited()


@pytest.mark.asyncio
async def test_behavioral_toggle_tenant_assignment_validates_before_reenable() -> None:
    """Test type: behavioral. Re-enabling assignment validates the current tenant plan."""
    plugin = _selected_tenant_plugin()
    db = AsyncMock()
    db.add = MagicMock()
    db.execute = AsyncMock(return_value=_ScalarsAllResult([_tenant(active=False)]))
    db.flush = AsyncMock()
    service = _plugin_service_for_assignment(db, plugin)

    with pytest.raises(BusinessException) as exc_info:
        await service.toggle_tenant_assignment(plugin.id, 42, True)

    assert "42" in exc_info.value.message
    assert db.execute.await_count == 1
    db.flush.assert_not_awaited()


@pytest.mark.asyncio
async def test_behavioral_selected_tenant_exposure_allows_active_assignment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test type: behavioral. Selected tenant exposure permits runtime only with an active assignment."""
    manifest = _base_manifest(ResourceScopeEnum.GLOBAL_SHARED.value)
    manifest["compatibility"] = {
        "editions": ["saas"],
        "surfaces": ["tenant"],
        "tenant_exposure": "selected_tenants",
    }

    db = AsyncMock()
    db.execute = AsyncMock(
        side_effect=[
            _OneOrNoneResult(
                _plugin_row(
                    manifest,
                    scope=ResourceScopeEnum.GLOBAL_SHARED.value,
                )
            ),
            _ScalarOneOrNoneResult(99),
        ]
    )
    monkeypatch.setattr(
        "app.plugins.runtime_gate.get_plugin_runtime_license_status",
        AsyncMock(return_value={"runtime_allowed": True, "status": "not_required"}),
    )

    gate = await evaluate_plugin_runtime_gate(
        db,
        "demo-plugin",
        tenant_id=42,
        require_enabled=True,
        enforce_scope=True,
    )

    assert gate.allowed is True
    assert gate.reason_code == "allowed"
    assert gate.compatibility_profile is not None
    assert gate.compatibility_profile["tenant_runtime_scope"] == "selected_tenants"
    assert gate.compatibility_profile["tenant_assignment_required"] is True
    assert db.execute.await_count == 2
