"""Plugin CLI pack hardening regression tests. / 插件 CLI 打包硬化回归测试。"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.plugins.security_scan import SecurityScanResult

_SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from plugin_cli_pack import cmd_pack  # noqa: E402
from plugin_cli_release import _generate_release_manifest  # noqa: E402


def _write_plugin(
    tmp_path: Path,
    *,
    manifest_plugin_name: str = "demo-plugin",
) -> Path:
    plugin_dir = tmp_path / "demo-plugin"
    (plugin_dir / "backend").mkdir(parents=True)
    (plugin_dir / "frontend" / "src").mkdir(parents=True)
    (plugin_dir / "frontend" / "dist" / "assets").mkdir(parents=True)

    (plugin_dir / "backend" / "main.py").write_text(
        "from app.plugins.base import PluginBase\n\nclass DemoPlugin(PluginBase):\n    pass\n",
        encoding="utf-8",
    )
    (plugin_dir / "frontend" / "src" / "index.ts").write_text(
        "export const DemoPage = {};",
        encoding="utf-8",
    )
    (plugin_dir / "frontend" / "dist" / "plugin.js").write_text(
        "window.NovusPlugin_demo_plugin = {};",
        encoding="utf-8",
    )
    (plugin_dir / "frontend" / "dist" / "assets" / "style.css").write_text(
        ".demo { color: red; }",
        encoding="utf-8",
    )
    (plugin_dir / "frontend" / "dist" / "assets" / "chunk.js").write_text(
        "console.log('chunk');",
        encoding="utf-8",
    )
    (plugin_dir / "frontend" / "dist" / "plugin.manifest.json").write_text(
        json.dumps(
            {
                "format": "novus.plugin.release.v1",
                "entry": "plugin.js",
                "global_var": "NovusPlugin_demo_plugin",
                "css": ["assets/style.css"],
                "assets": ["assets/chunk.js"],
            }
        ),
        encoding="utf-8",
    )
    (plugin_dir / "plugin.yaml").write_text(
        f"""
name: {manifest_plugin_name}
version: "1.0.0"
display_name:
  zh-CN: "演示插件"
  en: "Demo Plugin"
description:
  zh-CN: "演示插件"
  en: "Demo Plugin"
author: "NovusAI"
icon: ""
scope: admin_only
capabilities: []
dependencies:
  python: []
  plugins: []
pricing:
  type: free
extensions:
  frontend:
    pages:
      - name: "demo_admin_home"
        path: "/admin/plugins/demo-plugin"
        component: "DemoPage"
        scope: "admin"
        title:
          zh-CN: "演示插件"
          en: "Demo Plugin"
        menu:
          parent: "system_mgmt"
          title:
            zh-CN: "演示插件"
            en: "Demo Plugin"
    dev:
      entry: "src/index.ts"
    release:
      manifest: "plugin.manifest.json"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    return plugin_dir


def test_generate_release_manifest_rejects_path_traversal(tmp_path: Path) -> None:
    plugin_dir = _write_plugin(tmp_path)

    with pytest.raises(Exception) as exc_info:
        _generate_release_manifest(plugin_dir, "../plugin.manifest.json")

    assert "path traversal" in str(exc_info.value)


def test_cmd_pack_release_rejects_missing_release_asset(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    plugin_dir = _write_plugin(tmp_path)
    (plugin_dir / "frontend" / "dist" / "assets" / "chunk.js").unlink()

    with pytest.raises(SystemExit) as exc:
        cmd_pack(
            SimpleNamespace(
                dir=str(plugin_dir),
                output=str(tmp_path / "demo-plugin.zip"),
                release=True,
                source=False,
            )
        )

    assert exc.value.code == 1
    out = capsys.readouterr().out
    assert "Frontend release asset missing" in out
    assert "Please run: novusai plugin build" in out


def test_cmd_pack_rejects_security_scan_warnings(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    plugin_dir = _write_plugin(tmp_path)
    scan_result = SecurityScanResult()
    scan_result.warnings.append("backend/main.py:1: dangerous call 'eval()'")

    monkeypatch.setattr(
        "app.plugins.security_scan.scan_plugin_directory",
        lambda _plugin_dir: scan_result,
    )

    with pytest.raises(SystemExit) as exc:
        cmd_pack(
            SimpleNamespace(
                dir=str(plugin_dir),
                output=str(tmp_path / "demo-plugin-source.zip"),
                release=False,
                source=True,
            )
        )

    assert exc.value.code == 1
    out = capsys.readouterr().out
    assert "Security scan failed" in out
    assert "dangerous call 'eval()'" in out


def test_cmd_pack_rejects_invalid_plugin_name_in_manifest(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    plugin_dir = _write_plugin(tmp_path, manifest_plugin_name="Demo-Plugin")

    with pytest.raises(SystemExit) as exc:
        cmd_pack(
            SimpleNamespace(
                dir=str(plugin_dir),
                output=str(tmp_path / "demo-plugin-source.zip"),
                release=False,
                source=True,
            )
        )

    assert exc.value.code == 1
    out = capsys.readouterr().out
    assert "plugin.yaml validation failed" in out
    assert "Plugin name must be lowercase kebab-case" in out
