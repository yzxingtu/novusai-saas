"""插件菜单 scope 与 PermissionScope 字面量一致 / canonical endpoint scopes."""

from __future__ import annotations

import pytest

from app.plugins.registry import ExtensionRegistry


def test_register_menu_stores_canonical_scopes() -> None:
    reg = ExtensionRegistry.get_instance()
    pname = "menu_scope_ok"
    try:
        reg.register_menu(pname, "adm", "/a", scope="admin")
        reg.register_menu(pname, "ten", "/t", scope="tenant")
        reg.register_menu(pname, "usr", "/u", scope="user")
        menus = {m["name"]: m["scope"] for m in reg.get_plugin_menus(pname)}
        assert menus == {"adm": "admin", "ten": "tenant", "usr": "user"}
    finally:
        reg.unregister_all(pname)


def test_register_menu_rejects_legacy_scope_literals() -> None:
    reg = ExtensionRegistry.get_instance()
    pname = "menu_scope_bad"
    with pytest.raises(ValueError, match="Invalid plugin menu scope"):
        reg.register_menu(pname, "legacy", "/x", scope="admin_only")
    assert pname not in reg._plugin_menus or not reg._plugin_menus.get(pname)
