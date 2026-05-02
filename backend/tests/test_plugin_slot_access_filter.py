from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest


def _empty_slot_groups() -> dict[str, list[dict[str, object]]]:
    return {
        "dashboard_widgets": [],
        "floating_panels": [],
        "header_widgets": [],
        "notification_ui": [],
        "pages": [],
        "settings_tabs": [],
    }


class _Registry:
    def __init__(self, grouped: dict[str, list[dict[str, object]]]) -> None:
        self._grouped = grouped

    def get_frontend_slots_grouped(
        self,
        scope: str | None = None,
    ) -> dict[str, list[dict[str, object]]]:
        assert scope in {"admin", "tenant"}
        return self._grouped


def _find_route_endpoint(router, path: str):
    for route in router.routes:
        if getattr(route, "path", None) == path:
            return route.endpoint
    raise AssertionError(f"Route {path!r} not found")


class _PluginRow:
    def __init__(
        self,
        name: str,
        *,
        config: dict[str, object] | None = None,
        manifest: dict[str, object] | None = None,
    ) -> None:
        self.name = name
        self._config = config or {}
        self._manifest = manifest or {}

    def to_dict(self) -> dict[str, object]:
        return {
            "config": dict(self._config),
            "manifest": dict(self._manifest),
            "name": self.name,
        }


class _ScalarResult:
    def __init__(self, items: list[object]) -> None:
        self._items = items

    def all(self) -> list[object]:
        return list(self._items)


class _ExecuteResult:
    def __init__(self, items: list[object]) -> None:
        self._items = items

    def scalars(self) -> _ScalarResult:
        return _ScalarResult(self._items)


def test_plugin_slot_filter_hides_permissionless_pages_only() -> None:
    from app.api.shared._plugin_slot_filter import (
        filter_grouped_plugin_slots_by_permission_codes,
    )

    grouped = _empty_slot_groups()
    grouped["pages"] = [
        {
            "plugin_name": "permissionless-plugin",
            "name": "open-looking-page",
            "path": "/tenant/plugins/permissionless-plugin",
        },
        {
            "plugin_name": "alpha-plugin",
            "name": "alpha-home",
            "path": "/tenant/plugins/alpha-plugin",
            "access_codes": ["menu:tenant.plugin_alpha_plugin_alpha-home"],
        },
    ]
    grouped["header_widgets"] = [
        {
            "plugin_name": "weather-widget",
            "name": "weather-widget",
        }
    ]

    result = filter_grouped_plugin_slots_by_permission_codes(
        grouped,
        {"menu:tenant.plugin_alpha_plugin_alpha-home"},
    )

    assert result["pages"] == [
        {
            "plugin_name": "alpha-plugin",
            "name": "alpha-home",
            "path": "/tenant/plugins/alpha-plugin",
            "access_codes": ["menu:tenant.plugin_alpha_plugin_alpha-home"],
        }
    ]
    assert result["header_widgets"] == [
        {
            "plugin_name": "weather-widget",
            "name": "weather-widget",
        }
    ]


@pytest.mark.asyncio
async def test_tenant_plugin_slots_hide_pages_without_current_permission(
    monkeypatch: pytest.MonkeyPatch,
):
    from app.api.tenant.plugins import router as tenant_router

    grouped = _empty_slot_groups()
    grouped["pages"] = [
        {
            "plugin_name": "alpha-plugin",
            "name": "alpha-home",
            "path": "/tenant/plugins/alpha-plugin",
            "access_codes": [
                "menu:tenant.plugin_alpha_plugin_alpha-home"
            ],
        },
        {
            "plugin_name": "beta-plugin",
            "name": "beta-home",
            "path": "/tenant/plugins/beta-plugin",
            "access_codes": [
                "menu:tenant.plugin_beta_plugin_beta-home"
            ],
        },
    ]

    class _PluginService:
        def __init__(self, _db) -> None:
            self._db = _db

        async def get_tenant_visible_plugin_names(
            self,
            tenant_id: int,
        ) -> set[str]:
            assert tenant_id == 42
            return {"alpha-plugin", "beta-plugin"}

    monkeypatch.setattr(
        "app.services.system.plugin_service.PluginService",
        _PluginService,
    )
    monkeypatch.setattr(
        "app.plugins.registry.ExtensionRegistry.get_instance",
        lambda: _Registry(grouped),
    )
    monkeypatch.setattr(
        "app.rbac.services.permission_service.PermissionService.get_tenant_admin_permissions",
        AsyncMock(
            return_value={
                "menu:tenant.plugin_alpha_plugin_alpha-home",
            }
        ),
    )

    endpoint = _find_route_endpoint(tenant_router, "/plugins/slots")
    result = await endpoint(
        db=AsyncMock(),
        tenant_admin=SimpleNamespace(tenant_id=42, role_id=7, is_owner=False),
    )

    assert result["code"] == 0
    assert result["data"]["pages"] == [
        {
            "plugin_name": "alpha-plugin",
            "name": "alpha-home",
            "path": "/tenant/plugins/alpha-plugin",
            "access_codes": [
                "menu:tenant.plugin_alpha_plugin_alpha-home"
            ],
        }
    ]


@pytest.mark.asyncio
async def test_tenant_plugin_list_hides_plugins_without_current_permission(
    monkeypatch: pytest.MonkeyPatch,
):
    from app.api.tenant.plugins import router as tenant_router

    grouped = _empty_slot_groups()
    grouped["pages"] = [
        {
            "plugin_name": "alpha-plugin",
            "name": "alpha-home",
            "path": "/tenant/plugins/alpha-plugin",
            "access_codes": [
                "menu:tenant.plugin_alpha_plugin_alpha-home"
            ],
        },
        {
            "plugin_name": "beta-plugin",
            "name": "beta-home",
            "path": "/tenant/plugins/beta-plugin",
            "access_codes": [
                "menu:tenant.plugin_beta_plugin_beta-home"
            ],
        },
    ]

    class _PluginService:
        def __init__(self, _db) -> None:
            self._db = _db

        async def get_tenant_visible_plugin_names(
            self,
            tenant_id: int,
        ) -> set[str]:
            assert tenant_id == 42
            return {"alpha-plugin", "beta-plugin"}

    monkeypatch.setattr(
        "app.services.system.plugin_service.PluginService",
        _PluginService,
    )
    monkeypatch.setattr(
        "app.plugins.registry.ExtensionRegistry.get_instance",
        lambda: _Registry(grouped),
    )
    monkeypatch.setattr(
        "app.rbac.services.permission_service.PermissionService.get_tenant_admin_permissions",
        AsyncMock(
            return_value={
                "menu:tenant.plugin_alpha_plugin_alpha-home",
            }
        ),
    )

    db = AsyncMock()
    db.execute = AsyncMock(
        return_value=_ExecuteResult(
            [
                _PluginRow("alpha-plugin"),
                _PluginRow("beta-plugin"),
            ]
        )
    )

    endpoint = _find_route_endpoint(tenant_router, "/plugins")
    result = await endpoint(
        db=db,
        tenant_admin=SimpleNamespace(tenant_id=42, role_id=7, is_owner=False),
    )

    assert result["code"] == 0
    assert [item["name"] for item in result["data"]["items"]] == ["alpha-plugin"]
    assert result["data"]["total"] == 1


@pytest.mark.asyncio
async def test_admin_plugin_slots_hide_pages_without_current_permission(
    monkeypatch: pytest.MonkeyPatch,
):
    from app.api.admin.plugins import router as admin_router

    grouped = _empty_slot_groups()
    grouped["pages"] = [
        {
            "plugin_name": "alpha-plugin",
            "name": "alpha-admin-home",
            "path": "/admin/plugins/alpha-plugin",
            "access_codes": [
                "menu:admin.plugin_alpha_plugin_alpha-admin-home"
            ],
        },
        {
            "plugin_name": "beta-plugin",
            "name": "beta-admin-home",
            "path": "/admin/plugins/beta-plugin",
            "access_codes": [
                "menu:admin.plugin_beta_plugin_beta-admin-home"
            ],
        },
    ]

    monkeypatch.setattr(
        "app.plugins.registry.ExtensionRegistry.get_instance",
        lambda: _Registry(grouped),
    )
    monkeypatch.setattr(
        "app.plugins.runtime_gate.evaluate_plugin_runtime_gate",
        AsyncMock(
            side_effect=lambda *args, **kwargs: SimpleNamespace(
                allowed=(kwargs.get("plugin_name") or args[1])
                in {"alpha-plugin", "beta-plugin"}
            )
        ),
    )
    monkeypatch.setattr(
        "app.rbac.services.permission_service.PermissionService.get_admin_permissions",
        AsyncMock(
            return_value={
                "menu:admin.plugin_alpha_plugin_alpha-admin-home",
            }
        ),
    )

    endpoint = _find_route_endpoint(admin_router, "/plugins/slots")
    result = await endpoint(
        db=AsyncMock(),
        admin=SimpleNamespace(is_super=False, role_id=1, org_node_id=None),
    )

    assert result["code"] == 0
    assert result["data"]["pages"] == [
        {
            "plugin_name": "alpha-plugin",
            "name": "alpha-admin-home",
            "path": "/admin/plugins/alpha-plugin",
            "access_codes": [
                "menu:admin.plugin_alpha_plugin_alpha-admin-home"
            ],
        }
    ]
