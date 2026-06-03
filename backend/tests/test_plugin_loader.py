"""Tests for PluginLoader manifest parsing from arbitrary source paths. / 插件"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.plugins.loader import PluginLoader

_MANIFEST_CONTENT = """name: demo-plugin
version: \"1.0.0\"
display_name:
  en: Demo Plugin
scope: admin_only"""


def _write_manifest(plugin_dir: Path) -> None:
    plugin_dir.mkdir(parents=True, exist_ok=True)
    (plugin_dir / "plugin.yaml").write_text(_MANIFEST_CONTENT, encoding="utf-8")


def test_load_manifest_from_path_supports_temp_source(tmp_path: Path) -> None:
    """Regression: temp source dir should not require living under PLUGINS_DIR. / 插件"""
    plugin_dir = tmp_path / "tmp-source-dir"
    _write_manifest(plugin_dir)

    loader = PluginLoader()

    # Old path-based call style fails when plugin is outside installed plugins root
    with pytest.raises(Exception, match=r"not found|does not exist"):
        loader.load_manifest(plugin_dir.name)

    manifest = loader.load_manifest_from_path(plugin_dir)
    assert manifest.name == "demo-plugin"
    assert manifest.version == "1.0.0"


def test_load_manifest_from_path_missing_yaml(tmp_path: Path) -> None:
    loader = PluginLoader()
    plugin_dir = tmp_path / "empty-plugin-dir"
    plugin_dir.mkdir(parents=True, exist_ok=True)

    with pytest.raises(Exception, match=r"not found|does not exist"):
        loader.load_manifest_from_path(plugin_dir)


def test_load_manifest_from_path_defaults_root_icon_png(tmp_path: Path) -> None:
    loader = PluginLoader()
    plugin_dir = tmp_path / "icon-demo-plugin"
    _write_manifest(plugin_dir)
    (plugin_dir / "icon.png").write_bytes(b"\x89PNG")

    manifest = loader.load_manifest_from_path(plugin_dir)

    assert manifest.icon == "icon.png"
