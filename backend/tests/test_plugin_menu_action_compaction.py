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
        plugin_name="workflow-orchestration",
        name="workflow-orchestration-admin-home",
        path="/admin/plugins/workflow-orchestration",
        scope=PermissionScope.ADMIN.value,
        component="WorkflowOrchestrationAdminHomePage",
    )

    perm = permission_registry.get(
        "menu:admin.plugin_workflow_orchestration_workflow-orchestration-admin-home",
        PermissionScope.ADMIN,
    )
    assert perm is not None
    assert len(perm.action) <= 50
    assert perm.action.startswith("admin.plugin.")
    assert "workflow-orchestration-admin-home" not in perm.action


def test_register_navigation_extensions_resolves_plugin_page_parent_alias() -> None:
    ExtensionRegistry.reset()
    permission_registry.clear()

    manifest = PluginManifest.model_validate(
        {
            "name": "workflow-orchestration",
            "version": "1.0.0",
            "display_name": {"en": "Workflow Orchestration"},
            "scope": "admin_and_selected_tenants",
            "extensions": {
                "frontend": {
                    "pages": [
                        {
                            "name": "workflow-orchestration-admin-home",
                            "path": "/admin/plugins/workflow-orchestration",
                            "component": "WorkflowOrchestrationAdminHomePage",
                            "scope": "admin",
                            "menu": {
                                "title": {"en": "Workflow Orchestration"},
                            },
                        },
                        {
                            "name": "workflow-orchestration-admin-runtime",
                            "path": "/admin/plugins/workflow-orchestration/runtime",
                            "component": "WorkflowOrchestrationAdminRuntimePage",
                            "scope": "admin",
                            "menu": {
                                "parent": "workflow-orchestration-admin-home",
                                "title": {"en": "Runtime"},
                            },
                        },
                    ],
                },
            },
        }
    )

    registry = ExtensionRegistry.get_instance()
    register_navigation_extensions(registry, manifest, "workflow-orchestration")

    runtime_menu = next(
        menu
        for menu in registry.get_plugin_menus("workflow-orchestration")
        if menu["name"] == "workflow-orchestration-admin-runtime"
    )
    expected_parent = "plugin_workflow_orchestration_workflow-orchestration-admin-home"
    assert runtime_menu["parent"] == expected_parent

    runtime_perm = permission_registry.get(
        "menu:admin.plugin_workflow_orchestration_workflow-orchestration-admin-runtime",
        PermissionScope.ADMIN,
    )
    assert runtime_perm is not None
    assert runtime_perm.parent_code == (
        "menu:admin.plugin_workflow_orchestration_workflow-orchestration-admin-home"
    )


def test_register_frontend_page_extensions_keeps_page_access_codes() -> None:
    ExtensionRegistry.reset()
    permission_registry.clear()

    manifest = PluginManifest.model_validate(
        {
            "name": "workflow-orchestration",
            "version": "1.0.0",
            "display_name": {"en": "Workflow Orchestration"},
            "scope": "admin_and_selected_tenants",
            "extensions": {
                "frontend": {
                    "pages": [
                        {
                            "name": "workflow-orchestration-admin-template-detail",
                            "path": "/admin/plugins/workflow-orchestration/templates/:id",
                            "component": "WorkflowOrchestrationAdminTemplateDetailPage",
                            "scope": "admin",
                            "title": {"en": "Template Detail"},
                            "access_codes": [
                                "plugin.workflow-orchestration.platform_template:view",
                            ],
                        },
                    ],
                },
            },
        }
    )

    registry = ExtensionRegistry.get_instance()
    register_frontend_page_extensions(registry, manifest, "workflow-orchestration")

    slots = registry.get_frontend_slots(slot_type="standalone_page", scope="admin")
    assert len(slots) == 1
    assert slots[0]["name"] == "workflow-orchestration-admin-template-detail"
    assert slots[0]["access_codes"] == [
        "plugin.workflow-orchestration.platform_template:view",
    ]


def test_register_frontend_page_extensions_adds_derived_menu_access_code() -> None:
    ExtensionRegistry.reset()
    permission_registry.clear()

    manifest = PluginManifest.model_validate(
        {
            "name": "workflow-orchestration",
            "version": "1.0.0",
            "display_name": {"en": "Workflow Orchestration"},
            "scope": "admin_and_selected_tenants",
            "extensions": {
                "frontend": {
                    "pages": [
                        {
                            "name": "workflow-orchestration-admin-home",
                            "path": "/admin/plugins/workflow-orchestration",
                            "component": "WorkflowOrchestrationAdminHomePage",
                            "scope": "admin",
                            "title": {"en": "Workflow Orchestration"},
                            "menu": {
                                "title": {"en": "Workflow Orchestration"},
                            },
                        },
                    ],
                },
            },
        }
    )

    registry = ExtensionRegistry.get_instance()
    register_frontend_page_extensions(registry, manifest, "workflow-orchestration")

    slots = registry.get_frontend_slots(slot_type="standalone_page", scope="admin")
    assert len(slots) == 1
    assert slots[0]["access_codes"] == [
        "menu:admin.plugin_workflow_orchestration_workflow-orchestration-admin-home",
    ]


def test_workflow_orchestration_manifest_pages_declare_access_codes() -> None:
    from app.plugins.loader import PluginLoader

    manifest = PluginLoader().load_manifest("workflow-orchestration")
    pages = manifest.extensions.frontend.pages

    assert pages
    missing = [page.name for page in pages if not page.access_codes]
    assert missing == []
