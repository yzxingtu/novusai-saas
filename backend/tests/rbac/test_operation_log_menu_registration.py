"""Test type: structural.

Scope: Operation log menus stay registered under Log Center for admin and tenant.
"""

from importlib import import_module, reload

from app.enums.rbac import PermissionScope
from app.rbac.menus import register_directory_menus
from app.rbac.registry import permission_registry


def _reload_permission_module(module_name: str) -> None:
    module = import_module(module_name)
    reload(module)


def test_admin_operation_log_menu_mounts_under_log_center() -> None:
    permission_registry.clear()
    register_directory_menus()
    _reload_permission_module("app.api.admin.operation_logs")

    menu = permission_registry.get("menu:admin.operation_log", PermissionScope.ADMIN)
    list_action = permission_registry.get("operation_log:list", PermissionScope.ADMIN)
    detail_action = permission_registry.get(
        "operation_log:detail",
        PermissionScope.ADMIN,
    )
    delete_action = permission_registry.get(
        "operation_log:delete",
        PermissionScope.ADMIN,
    )

    assert menu is not None
    assert menu.parent_code == "menu:admin.logs"
    assert menu.path == "/system/operation-logs"
    assert menu.component == "admin/system/operation-logs/index"
    assert list_action is not None
    assert list_action.parent_code == "menu:admin.operation_log"
    assert detail_action is not None
    assert detail_action.parent_code == "menu:admin.operation_log"
    assert delete_action is not None
    assert delete_action.parent_code == "menu:admin.operation_log"


def test_tenant_operation_log_menu_mounts_under_log_center() -> None:
    permission_registry.clear()
    register_directory_menus()
    _reload_permission_module("app.api.tenant.operation_logs")

    menu = permission_registry.get("menu:tenant.operation_log", PermissionScope.TENANT)
    list_action = permission_registry.get("operation_log:list", PermissionScope.TENANT)
    detail_action = permission_registry.get(
        "operation_log:detail",
        PermissionScope.TENANT,
    )
    delete_action = permission_registry.get(
        "operation_log:delete",
        PermissionScope.TENANT,
    )

    assert menu is not None
    assert menu.parent_code == "menu:tenant.logs"
    assert menu.path == "/system/operation-logs"
    assert menu.component == "tenant/system/operation-logs/index"
    assert list_action is not None
    assert list_action.parent_code == "menu:tenant.operation_log"
    assert detail_action is not None
    assert detail_action.parent_code == "menu:tenant.operation_log"
    assert delete_action is None
