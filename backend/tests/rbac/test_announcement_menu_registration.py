"""
Test type: structural
Scope: Announcement menu registration stays reachable in the expected system-management group.
"""

from importlib import import_module, reload

from app.enums.rbac import PermissionScope
from app.rbac.menus import register_directory_menus
from app.rbac.registry import permission_registry


def _reload_permission_module(module_name: str) -> None:
    module = import_module(module_name)
    reload(module)


def test_admin_announcement_menu_mounts_under_system_management() -> None:
    permission_registry.clear()
    register_directory_menus()
    _reload_permission_module("app.api.admin.announcement")

    menu = permission_registry.get("menu:admin.announcement", PermissionScope.ADMIN)

    assert menu is not None
    assert menu.parent_code == "menu:admin.system_mgmt"
    assert menu.path == "/system/announcements"
    assert menu.component == "system/announcements/index"


def test_tenant_announcement_menu_mounts_under_system_management() -> None:
    permission_registry.clear()
    register_directory_menus()
    _reload_permission_module("app.api.tenant.announcement")

    menu = permission_registry.get("menu:tenant.announcement", PermissionScope.TENANT)

    assert menu is not None
    assert menu.parent_code == "menu:tenant.system_mgmt"
    assert menu.path == "/system/announcements"
    assert menu.component == "tenant/system/announcements/index"
