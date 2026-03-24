"""Plugin preview i18n regression tests. / 插件预览多语言回归测试。"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from app.core.i18n import set_locale
from app.plugins.loader import PluginLoader
from app.plugins.preview import generate_preview


def _write_preview_plugin(
    tmp_path: Path,
    *,
    menu_title: dict[str, str] | None = None,
    page_title: dict[str, str] | None = None,
) -> Path:
    plugin_dir = tmp_path / "demo-plugin"
    (plugin_dir / "backend").mkdir(parents=True)
    (plugin_dir / "frontend" / "src").mkdir(parents=True)
    (plugin_dir / "backend" / "main.py").write_text(
        "from app.plugins.base import PluginBase\n\nclass DemoPlugin(PluginBase):\n    pass\n",
        encoding="utf-8",
    )
    (plugin_dir / "frontend" / "src" / "index.ts").write_text(
        "export const DemoDocsPage = {};",
        encoding="utf-8",
    )

    manifest = {
        "name": "demo-plugin",
        "version": "1.0.0",
        "display_name": {
            "zh-CN": "演示插件",
            "en": "Demo Plugin",
        },
        "description": {
            "zh-CN": "预览测试插件",
            "en": "Preview test plugin",
        },
        "author": "NovusAI",
        "icon": "",
        "scope": "admin_only",
        "capabilities": [],
        "dependencies": {"python": [], "plugins": []},
        "pricing": {"type": "free"},
        "extensions": {
            "frontend": {
                "pages": [
                    {
                        "name": "docs",
                        "path": "/admin/plugins/demo-plugin/docs",
                        "component": "DemoDocsPage",
                        "scope": "admin",
                        "title": page_title
                        or {"zh-CN": "文档页", "en": "Docs Page"},
                        "menu": {
                            "parent": "system_mgmt",
                            "title": menu_title
                            or {"zh-CN": "文档菜单", "en": "Docs Menu"},
                        },
                    }
                ],
                "dev": {"entry": "src/index.ts"},
                "release": {"manifest": "plugin.manifest.json"},
            }
        },
    }
    (plugin_dir / "plugin.yaml").write_text(
        yaml.safe_dump(manifest, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    return plugin_dir


@pytest.fixture(autouse=True)
def _reset_locale():
    set_locale("zh_CN")
    yield
    set_locale("zh_CN")


@pytest.mark.asyncio
async def test_generate_preview_resolves_frontend_titles_by_current_locale(
    tmp_path: Path,
) -> None:
    plugin_dir = _write_preview_plugin(tmp_path)
    set_locale("en")

    preview = await generate_preview(
        plugin_dir,
        loader=PluginLoader(plugins_dir=plugin_dir.parent),
    )

    assert preview.plugin_info["display_name"] == "Demo Plugin"
    assert preview.install_manifest["frontend_pages_details"] == ["Docs Page"]
    assert preview.install_manifest["frontend_menus_details"] == ["Docs Menu"]


@pytest.mark.asyncio
async def test_generate_preview_warns_when_page_and_menu_title_locales_missing(
    tmp_path: Path,
) -> None:
    plugin_dir = _write_preview_plugin(
        tmp_path,
        page_title={"zh-CN": "文档页"},
        menu_title={"zh-CN": "文档菜单"},
    )

    preview = await generate_preview(
        plugin_dir,
        loader=PluginLoader(plugins_dir=plugin_dir.parent),
    )

    assert any("pages[0].title missing en" in warning for warning in preview.warnings)
    assert any(
        "pages[0].menu.title missing en" in warning for warning in preview.warnings
    )
