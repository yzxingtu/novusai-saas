"""中文: 测试类型：behavioral。

EN: Test type: behavioral.

中文: 验证插件扩展注册会把 page parent alias 解析为插件菜单 ID，且不加载真实插件包。
EN: Verifies plugin extension registration resolves page parent aliases to
plugin menu ids, without loading real plugin packages.
"""

from types import SimpleNamespace
from typing import Any

from app.plugins._extension_registrar import register_navigation_extensions


class _Registry:
    def __init__(self) -> None:
        self.menus: list[dict[str, Any]] = []

    def register_menu(self, plugin_name: str, **kwargs: Any) -> None:
        self.menus.append({"plugin_name": plugin_name, **kwargs})


def _page(name: str, *, parent: str = "") -> SimpleNamespace:
    return SimpleNamespace(
        name=name,
        path=f"/{name}",
        icon="lucide:file",
        component=f"{name}.vue",
        title={"en": name},
        scope="admin",
        menu=SimpleNamespace(
            parent=parent,
            icon="",
            sort_order=10,
            title={"en": name},
            hidden=False,
        ),
    )


def test_navigation_registration_resolves_page_parent_alias_to_plugin_menu_id() -> None:
    manifest = SimpleNamespace(
        extensions=SimpleNamespace(
            frontend=SimpleNamespace(
                pages=[
                    _page("parent_page"),
                    _page("child_page", parent="parent_page"),
                ],
            ),
        ),
    )
    registry = _Registry()

    register_navigation_extensions(registry, manifest, "demo-plugin")

    child_menu = next(menu for menu in registry.menus if menu["name"] == "child_page")
    assert child_menu["parent"] == "plugin_demo_plugin_parent_page"
