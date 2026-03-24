"""Plugin menu action compaction regression tests. / 插件菜单 action 压缩回归测试。"""

from __future__ import annotations

from app.enums.rbac import PermissionScope
from app.plugins._extension_registrar import (
    register_frontend_page_extensions,
    register_navigation_extensions,
)
from app.plugins.manifest import PluginManifest
from app.plugins.registry import ExtensionRegistry
from app.rbac.registry import permission_registry

LONG_PLUGIN_NAME = "extremely-long-demo-plugin"
LONG_PAGE_NAME = "extremely-long-demo-plugin-admin-dashboard-home"
LONG_PLUGIN_CODE = "plugin_extremely_long_demo_plugin"


def test_register_menu_keeps_short_action_readable() -> None:
    ExtensionRegistry.reset()
    permission_registry.clear()

    registry = ExtensionRegistry.get_instance()
    registry.register_menu(
        plugin_name="demo-plugin",
        name="home",
        path="/admin/plugins/demo-plugin",
        scope=PermissionScope.ADMIN.value,
        component="DemoHomePage",
    )

    perm = permission_registry.get(
        "menu:admin.plugin_demo_plugin_home",
        PermissionScope.ADMIN,
    )
    assert perm is not None
    assert perm.action == "admin.plugin_demo_plugin_home"


def test_register_menu_compacts_long_action_to_fit_permission_limit() -> None:
    ExtensionRegistry.reset()
    permission_registry.clear()

    registry = ExtensionRegistry.get_instance()
    registry.register_menu(
        plugin_name=LONG_PLUGIN_NAME,
        name=LONG_PAGE_NAME,
        path="/admin/plugins/extremely-long-demo-plugin",
        scope=PermissionScope.ADMIN.value,
        component="ExtremelyLongDemoPluginAdminDashboardHomePage",
    )

    perm = permission_registry.get(
        "menu:admin.plugin_extremely_long_demo_plugin_extremely-long-demo-plugin-admin-dashboard-home",
        PermissionScope.ADMIN,
    )
    assert perm is not None
    assert len(perm.action) <= 50
    assert perm.action.startswith("admin.plugin.")
    assert LONG_PAGE_NAME not in perm.action


def test_register_navigation_extensions_resolves_plugin_page_parent_alias() -> None:
    ExtensionRegistry.reset()
    permission_registry.clear()

    manifest = PluginManifest.model_validate(
        {
            "name": LONG_PLUGIN_NAME,
            "version": "1.0.0",
            "display_name": {"en": "Long Demo Plugin"},
            "scope": "admin_and_selected_tenants",
            "extensions": {
                "frontend": {
                    "pages": [
                        {
                            "name": LONG_PAGE_NAME,
                            "path": "/admin/plugins/extremely-long-demo-plugin",
                            "component": "ExtremelyLongDemoPluginAdminDashboardHomePage",
                            "scope": "admin",
                            "menu": {
                                "title": {"en": "Long Demo Plugin"},
                            },
                        },
                        {
                            "name": "extremely-long-demo-plugin-admin-runtime",
                            "path": "/admin/plugins/extremely-long-demo-plugin/runtime",
                            "component": "ExtremelyLongDemoPluginAdminRuntimePage",
                            "scope": "admin",
                            "menu": {
                                "parent": LONG_PAGE_NAME,
                                "title": {"en": "Runtime"},
                            },
                        },
                    ],
                },
            },
        }
    )

    registry = ExtensionRegistry.get_instance()
    register_navigation_extensions(registry, manifest, LONG_PLUGIN_NAME)

    runtime_menu = next(
        menu
        for menu in registry.get_plugin_menus(LONG_PLUGIN_NAME)
        if menu["name"] == "extremely-long-demo-plugin-admin-runtime"
    )
    expected_parent = f"{LONG_PLUGIN_CODE}_{LONG_PAGE_NAME}"
    assert runtime_menu["parent"] == expected_parent

    runtime_perm = permission_registry.get(
        "menu:admin.plugin_extremely_long_demo_plugin_extremely-long-demo-plugin-admin-runtime",
        PermissionScope.ADMIN,
    )
    assert runtime_perm is not None
    assert runtime_perm.parent_code == (
        "menu:admin.plugin_extremely_long_demo_plugin_extremely-long-demo-plugin-admin-dashboard-home"
    )


def test_register_frontend_page_extensions_keeps_page_access_codes() -> None:
    ExtensionRegistry.reset()
    permission_registry.clear()

    manifest = PluginManifest.model_validate(
        {
            "name": "demo-plugin",
            "version": "1.0.0",
            "display_name": {"en": "Demo Plugin"},
            "scope": "admin_and_selected_tenants",
            "extensions": {
                "frontend": {
                    "pages": [
                        {
                            "name": "demo-plugin-admin-template-detail",
                            "path": "/admin/plugins/demo-plugin/templates/:id",
                            "component": "DemoPluginAdminTemplateDetailPage",
                            "scope": "admin",
                            "title": {"en": "Template Detail"},
                            "access_codes": [
                                "plugin.demo-plugin.platform_template:view",
                            ],
                        },
                    ],
                },
            },
        }
    )

    registry = ExtensionRegistry.get_instance()
    register_frontend_page_extensions(registry, manifest, "demo-plugin")

    slots = registry.get_frontend_slots(slot_type="standalone_page", scope="admin")
    assert len(slots) == 1
    assert slots[0]["name"] == "demo-plugin-admin-template-detail"
    assert slots[0]["access_codes"] == [
        "plugin.demo-plugin.platform_template:view",
    ]


def test_register_frontend_page_extensions_adds_derived_menu_access_code() -> None:
    ExtensionRegistry.reset()
    permission_registry.clear()

    manifest = PluginManifest.model_validate(
        {
            "name": "demo-plugin",
            "version": "1.0.0",
            "display_name": {"en": "Demo Plugin"},
            "scope": "admin_and_selected_tenants",
            "extensions": {
                "frontend": {
                    "pages": [
                        {
                            "name": "demo-plugin-admin-home",
                            "path": "/admin/plugins/demo-plugin",
                            "component": "DemoPluginAdminHomePage",
                            "scope": "admin",
                            "title": {"en": "Demo Plugin"},
                            "menu": {
                                "title": {"en": "Demo Plugin"},
                            },
                        },
                    ],
                },
            },
        }
    )

    registry = ExtensionRegistry.get_instance()
    register_frontend_page_extensions(registry, manifest, "demo-plugin")

    slots = registry.get_frontend_slots(slot_type="standalone_page", scope="admin")
    assert len(slots) == 1
    assert slots[0]["access_codes"] == [
        "menu:admin.plugin_demo_plugin_demo-plugin-admin-home",
    ]


def test_storage_billing_manifest_pages_declare_access_codes() -> None:
    manifest = PluginManifest.model_validate(
        {
            "name": "storage-billing",
            "version": "0.1.0",
            "display_name": {"en": "Storage Billing"},
            "scope": "all_tenants",
            "extensions": {
                "frontend": {
                    "pages": [
                        {
                            "name": "storage-billing-admin-home",
                            "path": "/admin/plugins/storage-billing",
                            "component": "StorageBillingAdminHomePage",
                            "scope": "admin",
                            "title": {"en": "Storage Billing"},
                            "access_codes": [
                                "plugin.storage-billing.billing_admin:view",
                            ],
                        },
                        {
                            "name": "storage-billing-tenant-home",
                            "path": "/tenant/plugins/storage-billing",
                            "component": "StorageBillingTenantHomePage",
                            "scope": "tenant",
                            "title": {"en": "Storage Billing"},
                            "access_codes": [
                                "plugin.storage-billing.billing_portal:view",
                            ],
                        },
                    ],
                },
            },
        }
    )
    pages = manifest.extensions.frontend.pages

    assert pages
    missing = [page.name for page in pages if not page.access_codes]
    assert missing == []
