"""Plugin preview i18n regression tests. / 插件预览多语言回归测试。"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from app.core.i18n import set_locale
from app.plugins.dependencies import detect_direct_python_dependency_conflicts
from app.plugins.loader import PluginLoader
from app.plugins.preview import generate_preview


def _write_preview_plugin(
    tmp_path: Path,
    *,
    backend_source: str | None = None,
    menu_title: dict[str, str] | None = None,
    page_title: dict[str, str] | None = None,
    include_frontend_slots: bool = False,
    plugin_dependencies: list[object] | None = None,
    pricing: dict[str, object] | None = None,
    python_dependencies: list[str] | None = None,
) -> Path:
    plugin_dir = tmp_path / "demo-plugin"
    (plugin_dir / "backend").mkdir(parents=True)
    (plugin_dir / "frontend" / "src").mkdir(parents=True)
    (plugin_dir / "backend" / "main.py").write_text(
        backend_source
        or (
            "from app.plugins.base import PluginBase\n\n"
            "class DemoPlugin(PluginBase):\n"
            "    pass\n"
        ),
        encoding="utf-8",
    )
    (plugin_dir / "frontend" / "src" / "index.ts").write_text(
        "export const DemoDocsPage = {};",
        encoding="utf-8",
    )

    frontend_extensions: dict[str, object] = {
        "pages": [
            {
                "name": "docs",
                "path": "/admin/plugins/demo-plugin/docs",
                "component": "DemoDocsPage",
                "scope": "admin",
                "title": page_title or {"zh-CN": "文档页", "en": "Docs Page"},
                "menu": {
                    "parent": "system_mgmt",
                    "title": menu_title or {"zh-CN": "文档菜单", "en": "Docs Menu"},
                },
            }
        ],
        "dev": {"entry": "src/index.ts"},
        "release": {"manifest": "plugin.manifest.json"},
    }
    if include_frontend_slots:
        frontend_extensions.update(
            {
                "header_widgets": [
                    {
                        "name": "weather-header",
                        "component": "WeatherHeaderWidget",
                        "scope": "admin",
                    }
                ],
                "floating_panels": [
                    {
                        "name": "ops-panel",
                        "component": "OpsFloatingPanel",
                    }
                ],
                "notification_ui": [
                    {
                        "event": "plugin.demo.notice",
                        "component": "DemoNoticeCard",
                    }
                ],
                "dashboard_widgets": [
                    {
                        "name": "weather-dashboard",
                        "component": "WeatherDashboardWidget",
                        "scope": "admin",
                        "title": {
                            "zh-CN": "天气总览",
                            "en": "Weather Overview",
                        },
                    }
                ],
                "settings_tabs": [
                    {
                        "name": "plugin-settings",
                        "component": "PluginSettingsTab",
                        "scope": "admin",
                        "title": {
                            "zh-CN": "插件设置",
                            "en": "Plugin Settings",
                        },
                    }
                ],
            }
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
        "dependencies": {
            "python": python_dependencies or [],
            "plugins": plugin_dependencies or [],
        },
        "pricing": pricing or {"type": "free"},
        "extensions": {"frontend": frontend_extensions},
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


class _PreviewResult:
    def __init__(self, rows: list[object]) -> None:
        self._rows = rows

    def all(self) -> list[object]:
        return list(self._rows)


class _PreviewDB:
    def __init__(self, *result_sets: list[object]) -> None:
        self._result_sets = list(result_sets)

    async def execute(self, _stmt) -> _PreviewResult:
        rows = self._result_sets.pop(0) if self._result_sets else []
        return _PreviewResult(rows)


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
    assert preview.install_manifest["page_menus_details"] == ["Docs Menu"]


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

    assert "前端页面标题多语言不完整：pages[0].title 缺少 en" in preview.warnings
    assert "前端菜单标题多语言不完整：pages[0].menu.title 缺少 en" in preview.warnings


@pytest.mark.asyncio
async def test_generate_preview_includes_frontend_slot_summaries(
    tmp_path: Path,
) -> None:
    plugin_dir = _write_preview_plugin(tmp_path, include_frontend_slots=True)
    set_locale("en")

    preview = await generate_preview(
        plugin_dir,
        loader=PluginLoader(plugins_dir=plugin_dir.parent),
    )

    assert preview.install_manifest["frontend_pages"] == 1
    assert preview.install_manifest["frontend_pages_details"] == ["Docs Page"]
    assert preview.install_manifest["page_menus"] == 1
    assert preview.install_manifest["page_menus_details"] == ["Docs Menu"]
    assert preview.install_manifest["header_widgets"] == 1
    assert preview.install_manifest["header_widgets_details"] == ["weather-header"]
    assert preview.install_manifest["floating_panels"] == 1
    assert preview.install_manifest["floating_panels_details"] == ["ops-panel"]
    assert preview.install_manifest["notification_ui"] == 1
    assert preview.install_manifest["notification_ui_details"] == ["plugin.demo.notice"]
    assert preview.install_manifest["dashboard_widgets"] == 1
    assert preview.install_manifest["dashboard_widgets_details"] == ["Weather Overview"]
    assert preview.install_manifest["settings_tabs"] == 1
    assert preview.install_manifest["settings_tabs_details"] == ["Plugin Settings"]


@pytest.mark.asyncio
async def test_generate_preview_localizes_diagnostics_in_chinese(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    plugin_dir = _write_preview_plugin(
        tmp_path,
        backend_source=(
            "import os\n\n"
            "from app.plugins.base import PluginBase\n\n"
            "class DemoPlugin(PluginBase):\n"
            "    def run(self):\n"
            "        os.system('echo hi')\n"
        ),
        menu_title={"zh-CN": "文档菜单"},
        page_title={"zh-CN": "文档页"},
        plugin_dependencies=["dep-plugin"],
        pricing={"type": "paid", "price": None},
        python_dependencies=["preview-missing-demo-package>=1.0"],
    )

    monkeypatch.setattr(
        "app.plugins.registry.ExtensionRegistry.get_instance",
        lambda: SimpleNamespace(
            get_conflicts=lambda _manifest: [
                {
                    "type": "adapter",
                    "key": "weather-provider",
                    "owner": "installed-plugin",
                }
            ]
        ),
    )
    monkeypatch.setattr(
        "app.plugins.preview.detect_direct_python_dependency_conflicts",
        lambda *_args, **_kwargs: [
            SimpleNamespace(
                package="shared-demo",
                reason="声明了多个不兼容的精确版本：1.0.0, 2.0.0",
            )
        ],
    )

    preview = await generate_preview(
        plugin_dir,
        loader=PluginLoader(plugins_dir=plugin_dir.parent),
        db=_PreviewDB([], []),
    )

    assert preview.conflicts == [
        {
            "type": "adapter",
            "key": "weather-provider",
            "owner": "installed-plugin",
            "reason": "适配器 'weather-provider' 已被插件 'installed-plugin' 注册",
        }
    ]
    assert preview.dependencies["plugins"][0]["message"] == "插件依赖 dep-plugin 未安装"
    assert (
        preview.dependencies["python"][0]["message"]
        == "Python 依赖 preview-missing-demo-package 缺失或版本不匹配"
    )
    assert "前端页面标题多语言不完整：pages[0].title 缺少 en" in preview.warnings
    assert "前端菜单标题多语言不完整：pages[0].menu.title 缺少 en" in preview.warnings
    assert "检测到 1 个与现有扩展冲突的项目" in preview.warnings
    assert (
        "Python 依赖需要安装或升级：preview-missing-demo-package>=1.0"
        in preview.warnings
    )
    assert "插件依赖存在问题：插件依赖 dep-plugin 未安装" in preview.warnings
    assert (
        "Python 共享环境存在冲突：shared-demo: 声明了多个不兼容的精确版本：1.0.0, 2.0.0"
        in preview.warnings
    )
    assert "插件定价为付费，但未声明价格" in preview.warnings
    assert "安全扫描发现 2 个警告" in preview.warnings
    assert any("导入了危险模块 'os'" in warning for warning in preview.warnings)
    assert any("检测到危险调用 'os.system'" in warning for warning in preview.warnings)


@pytest.mark.asyncio
async def test_generate_preview_localizes_diagnostics_in_english(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    plugin_dir = _write_preview_plugin(
        tmp_path,
        backend_source=(
            "import os\n\n"
            "from app.plugins.base import PluginBase\n\n"
            "class DemoPlugin(PluginBase):\n"
            "    def run(self):\n"
            "        os.system('echo hi')\n"
        ),
        menu_title={"zh-CN": "文档菜单"},
        page_title={"zh-CN": "文档页"},
        plugin_dependencies=["dep-plugin"],
        pricing={"type": "paid", "price": None},
        python_dependencies=["preview-missing-demo-package>=1.0"],
    )
    set_locale("en")

    monkeypatch.setattr(
        "app.plugins.registry.ExtensionRegistry.get_instance",
        lambda: SimpleNamespace(
            get_conflicts=lambda _manifest: [
                {
                    "type": "adapter",
                    "key": "weather-provider",
                    "owner": "installed-plugin",
                }
            ]
        ),
    )
    monkeypatch.setattr(
        "app.plugins.preview.detect_direct_python_dependency_conflicts",
        lambda *_args, **_kwargs: [
            SimpleNamespace(
                package="shared-demo",
                reason="multiple incompatible exact versions declared: 1.0.0, 2.0.0",
            )
        ],
    )

    preview = await generate_preview(
        plugin_dir,
        loader=PluginLoader(plugins_dir=plugin_dir.parent),
        db=_PreviewDB([], []),
    )

    assert preview.conflicts == [
        {
            "type": "adapter",
            "key": "weather-provider",
            "owner": "installed-plugin",
            "reason": "Adapter 'weather-provider' is already registered by plugin 'installed-plugin'",
        }
    ]
    assert (
        preview.dependencies["plugins"][0]["message"]
        == "Plugin dependency dep-plugin is not installed"
    )
    assert (
        preview.dependencies["python"][0]["message"]
        == "Python dependency preview-missing-demo-package is missing or has a version mismatch"
    )
    assert (
        "Frontend page title i18n incomplete: pages[0].title missing en"
        in preview.warnings
    )
    assert (
        "Frontend menu title i18n incomplete: pages[0].menu.title missing en"
        in preview.warnings
    )
    assert "Detected 1 conflict(s) with existing extensions" in preview.warnings
    assert (
        "Python dependencies need install or upgrade: preview-missing-demo-package>=1.0"
        in preview.warnings
    )
    assert (
        "Plugin dependency issues: Plugin dependency dep-plugin is not installed"
        in preview.warnings
    )
    assert (
        "Python shared-env conflicts: shared-demo: multiple incompatible exact versions declared: 1.0.0, 2.0.0"
        in preview.warnings
    )
    assert "Paid plugin but no price specified" in preview.warnings
    assert "Security scan found 2 warning(s)" in preview.warnings
    assert any(
        "imports dangerous module 'os'" in warning for warning in preview.warnings
    )
    assert any("dangerous call 'os.system'" in warning for warning in preview.warnings)


def test_detect_direct_python_dependency_conflicts_localizes_reason_in_chinese() -> (
    None
):
    conflicts = detect_direct_python_dependency_conflicts(
        {
            "shared-demo": [
                ("host", "shared-demo==1.0.0"),
                ("plugin:demo-plugin", "shared-demo==2.0.0"),
            ]
        }
    )

    assert conflicts[0].reason == "声明了多个不兼容的精确版本：1.0.0, 2.0.0"


def test_detect_direct_python_dependency_conflicts_localizes_reason_in_english() -> (
    None
):
    set_locale("en")

    conflicts = detect_direct_python_dependency_conflicts(
        {
            "shared-demo": [
                ("host", "shared-demo==1.0.0"),
                ("plugin:demo-plugin", "shared-demo==2.0.0"),
            ]
        }
    )

    assert (
        conflicts[0].reason
        == "multiple incompatible exact versions declared: 1.0.0, 2.0.0"
    )
