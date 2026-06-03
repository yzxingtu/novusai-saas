"""
Test type: structural
Scope: user directory menu registration contract.
Mock strategy: no mocks; assertions inspect the static menu metadata.
"""

from app.rbac.menus.user_menus import USER_DIRECTORY_MENUS


def test_user_directory_menus_do_not_register_legacy_dashboard_home_code() -> None:
    codes = {menu.code for menu in USER_DIRECTORY_MENUS}

    assert "menu:user.dashboard" not in codes
    assert {"menu:user.agents", "menu:user.ai_chat", "menu:user.help"}.issubset(codes)
