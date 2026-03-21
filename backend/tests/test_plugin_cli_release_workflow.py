"""Plugin CLI release/source workflow regression tests. / 插件 CLI 发布/源码工作流回归测试。"""

from __future__ import annotations

import json
import sys
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest

_SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import plugin_cli as pc


def _write_plugin(
    tmp_path: Path,
    *,
    with_release: bool = False,
) -> Path:
    plugin_dir = tmp_path / "demo-plugin"
    (plugin_dir / "backend").mkdir(parents=True)
    (plugin_dir / "frontend" / "src").mkdir(parents=True)
    (plugin_dir / "locales").mkdir()
    (plugin_dir / "backend" / "main.py").write_text(
        "from app.plugins.base import PluginBase\n\nclass DemoPlugin(PluginBase):\n    pass\n",
        encoding="utf-8",
    )
    (plugin_dir / "frontend" / "src" / "index.ts").write_text(
        "export const DemoPage = {};",
        encoding="utf-8",
    )
    (plugin_dir / "frontend" / "src" / "DemoPage.vue").write_text(
        "<template><section>demo</section></template>\n<style>.demo { color: red; }</style>\n",
        encoding="utf-8",
    )
    (plugin_dir / "frontend" / "package.json").write_text(
        json.dumps(
            {
                "name": "@novus-plugin/demo-plugin",
                "private": True,
                "scripts": {"build": "vite build"},
            }
        ),
        encoding="utf-8",
    )
    (plugin_dir / "frontend" / "vite.config.ts").write_text(
        "export default {};",
        encoding="utf-8",
    )
    (plugin_dir / "backend" / "tests").mkdir()
    (plugin_dir / "backend" / "tests" / "test_should_not_pack.py").write_text(
        "def test_placeholder():\n    assert True\n",
        encoding="utf-8",
    )
    (plugin_dir / "locales" / "zh-CN.json").write_text(
        json.dumps(
            {
                "plugin.demo-plugin.name": "演示插件",
                "plugin.demo-plugin.description": "演示插件",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (plugin_dir / "plugin.yaml").write_text(
        """
name: demo-plugin
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

    if with_release:
        dist_dir = plugin_dir / "frontend" / "dist" / "assets"
        dist_dir.mkdir(parents=True)
        (plugin_dir / "frontend" / "dist" / "plugin.js").write_text(
            "window.NovusPlugin_demo_plugin = {};",
            encoding="utf-8",
        )
        (dist_dir / "style.css").write_text(".demo { color: red; }", encoding="utf-8")
        (plugin_dir / "frontend" / "dist" / "plugin.manifest.json").write_text(
            json.dumps(
                {
                    "format": "novus.plugin.release.v1",
                    "entry": "plugin.js",
                    "global_var": "NovusPlugin_demo_plugin",
                    "css": ["assets/style.css"],
                    "assets": [],
                }
            ),
            encoding="utf-8",
        )

    return plugin_dir


def test_cmd_validate_accepts_new_source_contract_and_warns_missing_release(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    plugin_dir = _write_plugin(tmp_path, with_release=False)

    with pytest.raises(SystemExit) as exc:
        pc.cmd_validate(SimpleNamespace(dir=str(plugin_dir)))

    assert exc.value.code == 0
    out = capsys.readouterr().out
    assert "frontend dev entry exists: src/index.ts" in out
    assert "frontend release manifest missing" in out


def test_cmd_validate_accepts_nested_plugin_locale_tree(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    plugin_dir = _write_plugin(tmp_path, with_release=True)
    (plugin_dir / "locales" / "zh-CN.json").write_text(
        json.dumps(
            {
                "plugin": {
                    "demo-plugin": {
                        "name": "演示插件",
                        "description": "演示插件",
                    }
                }
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    with pytest.raises(SystemExit) as exc:
        pc.cmd_validate(SimpleNamespace(dir=str(plugin_dir)))

    assert exc.value.code == 0
    out = capsys.readouterr().out
    assert "should start with 'plugin.demo-plugin.'" not in out


def test_cmd_build_generates_release_manifest(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    plugin_dir = _write_plugin(tmp_path, with_release=False)

    def _fake_run(command, cwd, check):  # noqa: ANN001
        assert command[-2:] == ["run", "build"] or command[-1:] == ["build"]
        assert check is True
        dist_dir = Path(cwd) / "dist" / "assets"
        dist_dir.mkdir(parents=True, exist_ok=True)
        (Path(cwd) / "dist" / "plugin.js").write_text(
            "window.NovusPlugin_demo_plugin = {};",
            encoding="utf-8",
        )
        (dist_dir / "style.css").write_text(".demo { color: red; }", encoding="utf-8")

    monkeypatch.setattr(pc.subprocess, "run", _fake_run)

    pc.cmd_build(SimpleNamespace(dir=str(plugin_dir)))

    manifest_path = plugin_dir / "frontend" / "dist" / "plugin.manifest.json"
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert payload["entry"] == "plugin.js"
    assert payload["css"] == ["assets/style.css"]
    assert payload["global_var"] == "NovusPlugin_demo_plugin"


def test_cmd_pack_release_excludes_source_and_tests(tmp_path: Path) -> None:
    plugin_dir = _write_plugin(tmp_path, with_release=True)
    output_path = tmp_path / "demo-plugin-release.zip"

    pc.cmd_pack(
        SimpleNamespace(
            dir=str(plugin_dir),
            output=str(output_path),
            release=True,
            source=False,
        )
    )

    with zipfile.ZipFile(output_path) as zf:
        names = set(zf.namelist())

    assert "demo-plugin/plugin.yaml" in names
    assert "demo-plugin/frontend/dist/plugin.manifest.json" in names
    assert "demo-plugin/frontend/dist/plugin.js" in names
    assert "demo-plugin/frontend/src/index.ts" not in names
    assert "demo-plugin/frontend/package.json" not in names
    assert "demo-plugin/backend/tests/test_should_not_pack.py" not in names


def test_cmd_pack_source_keeps_frontend_source(tmp_path: Path) -> None:
    plugin_dir = _write_plugin(tmp_path, with_release=True)
    output_path = tmp_path / "demo-plugin-source.zip"

    pc.cmd_pack(
        SimpleNamespace(
            dir=str(plugin_dir),
            output=str(output_path),
            release=False,
            source=True,
        )
    )

    with zipfile.ZipFile(output_path) as zf:
        names = set(zf.namelist())

    assert "demo-plugin/frontend/src/index.ts" in names
    assert "demo-plugin/frontend/package.json" in names
    assert "demo-plugin/frontend/dist/plugin.manifest.json" in names


def test_cmd_create_full_module_uses_new_frontend_contract(tmp_path: Path) -> None:
    output_dir = tmp_path / "scaffold-demo"

    pc.cmd_create(
        SimpleNamespace(
            name="scaffold-demo",
            output=str(output_dir),
            template="full-module",
        )
    )

    plugin_yaml = (output_dir / "plugin.yaml").read_text(encoding="utf-8")
    assert "pages:" in plugin_yaml
    assert "plugins: []" in plugin_yaml
    assert "release:" in plugin_yaml
    assert "standalone_pages:" not in plugin_yaml
    assert "menus:" not in plugin_yaml
    assert (output_dir / "frontend" / "src" / "ScaffoldDemoPage.vue").is_file()
    assert (output_dir / "frontend" / "dist" / "plugin.manifest.json").is_file()
