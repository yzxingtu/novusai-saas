"""插件静态资源路径解析器安全策略测试。 / Plugin."""

from __future__ import annotations

from pathlib import Path

from app.plugins.asset_resolver import resolve_plugin_asset_file


def test_resolve_plugin_asset_file_allows_dist_file(tmp_path: Path) -> None:
    plugins_root = tmp_path / "plugins"
    asset_file = plugins_root / "demo-plugin" / "frontend" / "dist" / "index.js"
    asset_file.parent.mkdir(parents=True)
    asset_file.write_text("console.log('ok')", encoding="utf-8")

    resolved = resolve_plugin_asset_file(plugins_root, "demo-plugin", "index.js")

    assert resolved == asset_file.resolve()


def test_resolve_plugin_asset_file_rejects_plugin_root_fallback(tmp_path: Path) -> None:
    plugins_root = tmp_path / "plugins"
    root_secret = plugins_root / "demo-plugin" / "plugin.yaml"
    root_secret.parent.mkdir(parents=True)
    root_secret.write_text("name: demo-plugin", encoding="utf-8")

    resolved = resolve_plugin_asset_file(plugins_root, "demo-plugin", "plugin.yaml")

    assert resolved is None


def test_resolve_plugin_asset_file_rejects_path_traversal(tmp_path: Path) -> None:
    plugins_root = tmp_path / "plugins"

    resolved = resolve_plugin_asset_file(plugins_root, "demo-plugin", "../backend/main.py")

    assert resolved is None


def test_resolve_plugin_asset_file_rejects_invalid_plugin_name(tmp_path: Path) -> None:
    plugins_root = tmp_path / "plugins"

    resolved = resolve_plugin_asset_file(plugins_root, "../demo", "index.js")

    assert resolved is None


def test_resolve_plugin_asset_file_allows_root_icon(tmp_path: Path) -> None:
    """插件根目录下的图标文件（如 icon.png）应可访问。 / Plugin."""
    plugins_root = tmp_path / "plugins"
    icon_file = plugins_root / "weather-widget" / "icon.png"
    icon_file.parent.mkdir(parents=True)
    icon_file.write_bytes(b"\x89PNG")

    resolved = resolve_plugin_asset_file(plugins_root, "weather-widget", "icon.png")

    assert resolved == icon_file.resolve()


def test_resolve_plugin_asset_file_allows_root_svg_icon(tmp_path: Path) -> None:
    """SVG 图标也应可从根目录访问。 / SVG 。"""
    plugins_root = tmp_path / "plugins"
    icon_file = plugins_root / "my-plugin" / "logo.svg"
    icon_file.parent.mkdir(parents=True)
    icon_file.write_text("<svg></svg>", encoding="utf-8")

    resolved = resolve_plugin_asset_file(plugins_root, "my-plugin", "logo.svg")

    assert resolved == icon_file.resolve()


def test_resolve_plugin_asset_file_rejects_root_non_icon(tmp_path: Path) -> None:
    """根目录下非图标扩展名的文件仍应拒绝。 / 。"""
    plugins_root = tmp_path / "plugins"
    py_file = plugins_root / "demo-plugin" / "main.py"
    py_file.parent.mkdir(parents=True)
    py_file.write_text("print('hello')", encoding="utf-8")

    resolved = resolve_plugin_asset_file(plugins_root, "demo-plugin", "main.py")

    assert resolved is None


def test_resolve_plugin_asset_file_rejects_subdirectory_icon(tmp_path: Path) -> None:
    """仅允许根目录顶层图标，子目录下的图标文件应走 frontend/dist 路径。"""
    plugins_root = tmp_path / "plugins"
    nested_icon = plugins_root / "demo-plugin" / "backend" / "icon.png"
    nested_icon.parent.mkdir(parents=True)
    nested_icon.write_bytes(b"\x89PNG")

    resolved = resolve_plugin_asset_file(plugins_root, "demo-plugin", "backend/icon.png")

    assert resolved is None
