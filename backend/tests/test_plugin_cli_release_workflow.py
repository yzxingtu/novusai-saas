"""Plugin CLI release/source workflow regression tests. / 插件 CLI 发布/源码工作流回归测试。"""

from __future__ import annotations

import json
import os
import sys
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from app.plugins.manifest import PluginManifest

_SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import plugin_cli as pc  # noqa: E402


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
        """
export function setup() {
  const shared = window.NovusPluginShared;
  if (shared?.registerLocale) {
    shared.registerLocale('zh-CN', 'plugin.demo-plugin', {});
    shared.registerLocale('zh', 'plugin.demo-plugin', {});
    shared.registerLocale('en-US', 'plugin.demo-plugin', {});
    shared.registerLocale('en', 'plugin.demo-plugin', {});
  }
}

export const DemoPage = {};
""".strip()
        + "\n",
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
                "devDependencies": {
                    "vue": "^3.5.0",
                },
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


def _write_captcha_plugin(
    tmp_path: Path,
    *,
    with_release: bool = False,
) -> Path:
    plugin_dir = _write_plugin(tmp_path, with_release=with_release)
    manifest_path = plugin_dir / "plugin.yaml"
    payload = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    payload["extensions"] = {
        "custom": [
            {
                "type": "captcha_provider",
                "name": "demo-slider",
                "description": "Demo slider captcha provider",
                "data": {
                    "entry_point": "captcha_provider.DemoSliderCaptchaProvider",
                    "public_endpoints": ["admin", "tenant"],
                    "display_name": {
                        "zh-CN": "演示滑块验证码",
                        "en": "Demo Slider CAPTCHA",
                    },
                },
            }
        ],
        "frontend": {
            "dev": {"entry": "src/index.ts"},
            "release": {"manifest": "plugin.manifest.json"},
        },
    }
    manifest_path.write_text(
        yaml.safe_dump(payload, sort_keys=False, allow_unicode=True),
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
    assert "frontend page/menu i18n covers locales: zh-CN, en" in out
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


def test_cmd_validate_rejects_unsupported_manifest_contract_overlay_fields(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    plugin_dir = _write_plugin(tmp_path, with_release=True)
    payload = yaml.safe_load((plugin_dir / "plugin.yaml").read_text(encoding="utf-8"))
    payload.setdefault("extensions", {})["capabilities"] = [
        {
            "key": "demo.search",
            "tool_name": "demo_search",
        }
    ]
    payload["extensions"]["skills"] = [
        {
            "name": "demo-search",
            "type": "toolkit",
            "display_name": {"zh-CN": "演示搜索", "en": "Demo Search"},
            "entry_point": "skills.demo_resolver",
            "capabilities": ["demo.search"],
            "skill_md_path": "backend/skills/demo/SKILL.md",
        }
    ]
    (plugin_dir / "plugin.yaml").write_text(
        yaml.safe_dump(payload, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )

    with pytest.raises(SystemExit) as exc:
        pc.cmd_validate(SimpleNamespace(dir=str(plugin_dir)))

    assert exc.value.code == 1
    out = capsys.readouterr().out
    assert "extensions.capabilities is not part of the current manifest schema" in out
    assert (
        "extensions.skills[0].capabilities is not part of the current manifest schema"
        in out
    )
    assert (
        "extensions.skills[0].skill_md_path is not part of the current manifest schema"
        in out
    )


def test_cmd_validate_warns_when_frontend_titles_are_missing_required_locales(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    plugin_dir = _write_plugin(tmp_path, with_release=True)
    payload = yaml.safe_load((plugin_dir / "plugin.yaml").read_text(encoding="utf-8"))
    page = payload["extensions"]["frontend"]["pages"][0]
    page["title"] = {"zh-CN": "演示插件"}
    page["menu"]["title"] = {"en": "Demo Plugin"}
    (plugin_dir / "plugin.yaml").write_text(
        yaml.safe_dump(payload, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )

    with pytest.raises(SystemExit) as exc:
        pc.cmd_validate(SimpleNamespace(dir=str(plugin_dir)))

    assert exc.value.code == 1
    out = capsys.readouterr().out
    assert "frontend.pages[0].title missing locale(s): en" in out
    assert "frontend.pages[0].menu.title missing locale(s): zh-CN" in out
    assert "frontend page title should define locales en: demo_admin_home" in out
    assert "frontend menu title should define locales zh-CN: demo_admin_home" in out


def test_cmd_validate_rejects_missing_frontend_package_json(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    plugin_dir = _write_plugin(tmp_path, with_release=False)
    (plugin_dir / "frontend" / "package.json").unlink()

    with pytest.raises(SystemExit) as exc:
        pc.cmd_validate(SimpleNamespace(dir=str(plugin_dir)))

    assert exc.value.code == 1
    out = capsys.readouterr().out
    assert "frontend/package.json missing" in out


def test_cmd_validate_rejects_missing_frontend_vite_config(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    plugin_dir = _write_plugin(tmp_path, with_release=False)
    (plugin_dir / "frontend" / "vite.config.ts").unlink()

    with pytest.raises(SystemExit) as exc:
        pc.cmd_validate(SimpleNamespace(dir=str(plugin_dir)))

    assert exc.value.code == 1
    out = capsys.readouterr().out
    assert "frontend/vite.config.ts missing" in out


def test_cmd_validate_rejects_peer_only_vue_dependency(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    plugin_dir = _write_plugin(tmp_path, with_release=False)
    (plugin_dir / "frontend" / "package.json").write_text(
        json.dumps(
            {
                "name": "@novus-plugin/demo-plugin",
                "private": True,
                "scripts": {"build": "vite build"},
                "peerDependencies": {
                    "vue": "^3.5.0",
                },
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(SystemExit) as exc:
        pc.cmd_validate(SimpleNamespace(dir=str(plugin_dir)))

    assert exc.value.code == 1
    out = capsys.readouterr().out
    assert "frontend/package.json must declare local build dependency 'vue'" in out


def test_cmd_validate_rejects_missing_frontend_page_title_locale(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    plugin_dir = _write_plugin(tmp_path, with_release=True)
    payload = yaml.safe_load((plugin_dir / "plugin.yaml").read_text(encoding="utf-8"))
    payload["extensions"]["frontend"]["pages"][0]["title"] = {
        "zh-CN": "演示插件",
    }
    (plugin_dir / "plugin.yaml").write_text(
        yaml.safe_dump(payload, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )

    with pytest.raises(SystemExit) as exc:
        pc.cmd_validate(SimpleNamespace(dir=str(plugin_dir)))

    assert exc.value.code == 1
    out = capsys.readouterr().out
    assert "frontend.pages[0].title missing locale(s): en" in out


def test_cmd_validate_rejects_missing_frontend_menu_title_locale(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    plugin_dir = _write_plugin(tmp_path, with_release=True)
    payload = yaml.safe_load((plugin_dir / "plugin.yaml").read_text(encoding="utf-8"))
    payload["extensions"]["frontend"]["pages"][0]["menu"]["title"] = {
        "zh-CN": "演示插件",
    }
    (plugin_dir / "plugin.yaml").write_text(
        yaml.safe_dump(payload, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )

    with pytest.raises(SystemExit) as exc:
        pc.cmd_validate(SimpleNamespace(dir=str(plugin_dir)))

    assert exc.value.code == 1
    out = capsys.readouterr().out
    assert "frontend.pages[0].menu.title missing locale(s): en" in out


def test_cmd_validate_rejects_non_canonical_frontend_locale_prefix(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    plugin_dir = _write_plugin(tmp_path, with_release=True)
    (plugin_dir / "frontend" / "src" / "index.ts").write_text(
        """
export function setup() {
  const shared = window.NovusPluginShared;
  if (shared?.registerLocale) {
    shared.registerLocale('zh-CN', 'plugin.demoPlugin', {});
    shared.registerLocale('en', 'plugin.demoPlugin', {});
  }
}

export const DemoPage = {};
""".strip()
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(SystemExit) as exc:
        pc.cmd_validate(SimpleNamespace(dir=str(plugin_dir)))

    assert exc.value.code == 1
    out = capsys.readouterr().out
    assert (
        "frontend registerLocale() should use canonical prefix 'plugin.demo-plugin'"
        in out
    )
    assert "plugin.demoPlugin" in out


def test_cmd_validate_warns_on_frontend_locale_alias_prefix(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    plugin_dir = _write_plugin(tmp_path, with_release=True)
    (plugin_dir / "frontend" / "src" / "index.ts").write_text(
        """
export function setup() {
  const shared = window.NovusPluginShared;
  if (shared?.registerLocale) {
    shared.registerLocale('zh-CN', 'plugin.demo-plugin', {});
    shared.registerLocale('en', 'plugin.demo-plugin', {});
    shared.registerLocale('zh-CN', 'admin.demoPlugin', {});
    shared.registerLocale('en', 'admin.demoPlugin', {});
  }
}

export const DemoPage = {};
""".strip()
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(SystemExit) as exc:
        pc.cmd_validate(SimpleNamespace(dir=str(plugin_dir)))

    assert exc.value.code == 0
    out = capsys.readouterr().out
    assert "frontend locale alias prefix detected: admin.demoPlugin" in out
    assert "canonical: plugin.demo-plugin" in out


def test_cmd_validate_accepts_helper_wrapped_canonical_locale_prefix(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    plugin_dir = _write_plugin(tmp_path, with_release=True)
    (plugin_dir / "frontend" / "src" / "index.ts").write_text(
        """
const ADMIN_LOCALE_PREFIX = 'plugin.demo-plugin.admin';
const LEGACY_ADMIN_LOCALE_PREFIX = 'plugin.demoPlugin.admin';

function registerLocaleGroup(prefix) {
  const shared = window.NovusPluginShared;
  shared?.registerLocale?.('zh-CN', prefix, {});
  shared?.registerLocale?.('en', prefix, {});
}

export function setup() {
  registerLocaleGroup(ADMIN_LOCALE_PREFIX);
  registerLocaleGroup(LEGACY_ADMIN_LOCALE_PREFIX);
}

export const DemoPage = {};
""".strip()
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(SystemExit) as exc:
        pc.cmd_validate(SimpleNamespace(dir=str(plugin_dir)))

    assert exc.value.code == 0
    out = capsys.readouterr().out
    assert "frontend locale namespace covers canonical root: plugin.demo-plugin" in out
    assert "frontend locale alias prefix detected: plugin.demoPlugin.admin" in out


def test_cmd_validate_treats_captcha_provider_as_frontend_plugin(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    plugin_dir = _write_captcha_plugin(tmp_path, with_release=False)

    with pytest.raises(SystemExit) as exc:
        pc.cmd_validate(SimpleNamespace(dir=str(plugin_dir)))

    assert exc.value.code == 0
    out = capsys.readouterr().out
    assert "No frontend extensions declared" not in out
    assert "frontend/package.json exists" in out
    assert "frontend dev entry exists: src/index.ts" in out
    assert "frontend locale namespace covers canonical root: plugin.demo-plugin" in out


def test_cmd_validate_rejects_missing_declared_frontend_component_export(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    plugin_dir = _write_plugin(tmp_path, with_release=True)
    (plugin_dir / "frontend" / "src" / "index.ts").write_text(
        "export const OtherPage = {};",
        encoding="utf-8",
    )

    with pytest.raises(SystemExit) as exc:
        pc.cmd_validate(SimpleNamespace(dir=str(plugin_dir)))

    assert exc.value.code == 1
    out = capsys.readouterr().out
    assert "frontend dev entry does not export declared component 'DemoPage'" in out


def test_cmd_build_generates_release_manifest(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    plugin_dir = _write_plugin(tmp_path, with_release=False)
    call_order: list[str] = []

    def _fake_run(command, cwd, check):  # noqa: ANN001
        command_text = " ".join(command)
        assert check is True
        if "install" in command_text:
            call_order.append("install")
            (Path(cwd) / "node_modules").mkdir(parents=True, exist_ok=True)
            return
        assert command[-2:] == ["run", "build"] or command[-1:] == ["build"]
        call_order.append("build")
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
    assert call_order == ["install", "build"]


def test_cmd_build_handles_captcha_provider_frontend_plugin(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    plugin_dir = _write_captcha_plugin(tmp_path, with_release=False)
    call_order: list[str] = []

    def _fake_run(command, cwd, check):  # noqa: ANN001
        command_text = " ".join(command)
        assert check is True
        if "install" in command_text:
            call_order.append("install")
            (Path(cwd) / "node_modules").mkdir(parents=True, exist_ok=True)
            return
        assert command[-2:] == ["run", "build"] or command[-1:] == ["build"]
        call_order.append("build")
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
    assert manifest_path.is_file()
    assert call_order == ["install", "build"]


def test_cmd_build_runs_security_scan_before_build_script(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    plugin_dir = _write_plugin(tmp_path, with_release=False)
    call_order: list[str] = []

    class _FakeScanResult:
        files_scanned = 1
        warnings: list[str] = []

        @property
        def has_warnings(self) -> bool:
            return False

    def _fake_scan(_plugin_dir: Path):  # noqa: ANN001
        call_order.append("scan")
        return _FakeScanResult()

    def _fake_run(command, cwd, check):  # noqa: ANN001
        command_text = " ".join(command)
        assert check is True
        if "install" in command_text:
            call_order.append("install")
            (Path(cwd) / "node_modules").mkdir(parents=True, exist_ok=True)
            return
        assert command[-2:] == ["run", "build"] or command[-1:] == ["build"]
        call_order.append("build")
        dist_dir = Path(cwd) / "dist" / "assets"
        dist_dir.mkdir(parents=True, exist_ok=True)
        (Path(cwd) / "dist" / "plugin.js").write_text(
            "window.NovusPlugin_demo_plugin = {};",
            encoding="utf-8",
        )
        (dist_dir / "style.css").write_text(".demo { color: red; }", encoding="utf-8")

    monkeypatch.setattr(
        "app.plugins.security_scan.scan_plugin_directory",
        _fake_scan,
    )
    monkeypatch.setattr(pc.subprocess, "run", _fake_run)

    pc.cmd_build(SimpleNamespace(dir=str(plugin_dir)))

    assert call_order == ["scan", "install", "build"]


def test_cmd_build_skips_dependency_bootstrap_when_node_modules_exists(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    plugin_dir = _write_plugin(tmp_path, with_release=False)
    (plugin_dir / "frontend" / "node_modules").mkdir()
    call_order: list[str] = []

    def _fake_run(command, cwd, check):  # noqa: ANN001
        call_order.append(" ".join(command))
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

    assert call_order == ["npm.cmd run build"] if os.name == "nt" else ["npm run build"]


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


def test_cmd_build_rejects_release_manifest_path_traversal(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    plugin_dir = _write_plugin(tmp_path, with_release=False)
    manifest_data = yaml.safe_load(
        (plugin_dir / "plugin.yaml").read_text(encoding="utf-8")
    )
    manifest_data["extensions"]["frontend"]["release"]["manifest"] = "../escape.json"
    (plugin_dir / "plugin.yaml").write_text(
        yaml.safe_dump(manifest_data, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )

    monkeypatch.setattr(pc.subprocess, "run", lambda *_args, **_kwargs: None)

    with pytest.raises(SystemExit) as exc:
        pc.cmd_build(SimpleNamespace(dir=str(plugin_dir)))

    assert exc.value.code == 1
    out = capsys.readouterr().out
    assert "plugin.yaml validation failed" in out
    assert "safe relative path" in out


def test_cmd_pack_release_rejects_invalid_release_manifest_assets(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    plugin_dir = _write_plugin(tmp_path, with_release=True)
    (plugin_dir / "frontend" / "dist" / "plugin.manifest.json").write_text(
        json.dumps(
            {
                "format": "novus.plugin.release.v1",
                "entry": "missing.js",
                "global_var": "NovusPlugin_demo_plugin",
                "css": ["assets/style.css"],
                "assets": [],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(SystemExit) as exc:
        pc.cmd_pack(
            SimpleNamespace(
                dir=str(plugin_dir),
                output=str(tmp_path / "invalid-release.zip"),
                release=True,
                source=False,
            )
        )

    assert exc.value.code == 1
    out = capsys.readouterr().out
    assert "Frontend release entry missing" in out


def test_cmd_pack_rejects_security_scan_warnings(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    plugin_dir = _write_plugin(tmp_path, with_release=True)

    class _FakeScanResult:
        files_scanned = 1
        warnings = ["backend/main.py:1: dangerous call 'exec()'"]

        @property
        def has_warnings(self) -> bool:
            return True

    monkeypatch.setattr(
        "app.plugins.security_scan.scan_plugin_directory",
        lambda _plugin_dir: _FakeScanResult(),
    )

    with pytest.raises(SystemExit) as exc:
        pc.cmd_pack(
            SimpleNamespace(
                dir=str(plugin_dir),
                output=str(tmp_path / "unsafe.zip"),
                release=True,
                source=False,
            )
        )

    assert exc.value.code == 1
    out = capsys.readouterr().out
    assert "Security scan failed" in out
    assert "dangerous call 'exec()'" in out


def test_cmd_create_full_module_uses_new_frontend_contract(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
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
    assert not (output_dir / "frontend" / "dist" / "plugin.manifest.json").exists()

    with pytest.raises(SystemExit) as exc:
        pc.cmd_validate(SimpleNamespace(dir=str(output_dir)))

    assert exc.value.code == 0
    out = capsys.readouterr().out
    assert "frontend dev entry exists: src/index.ts" in out
    assert "frontend release manifest missing" in out


def test_cmd_create_minimal_generates_manifest_valid_plugin_yaml(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "minimal-demo"

    pc.cmd_create(
        SimpleNamespace(
            name="minimal-demo",
            output=str(output_dir),
            template="minimal",
        )
    )

    manifest_payload = yaml.safe_load(
        (output_dir / "plugin.yaml").read_text(encoding="utf-8"),
    )
    manifest = PluginManifest.model_validate(manifest_payload)

    assert manifest.name == "minimal-demo"
    assert manifest.icon == ""
    assert manifest.dependencies.plugins == []


def test_cmd_pack_release_requires_release_assets(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    plugin_dir = _write_plugin(tmp_path, with_release=True)
    css_path = plugin_dir / "frontend" / "dist" / "assets" / "style.css"
    css_path.unlink()
    output_path = tmp_path / "demo-plugin-release.zip"

    with pytest.raises(SystemExit) as exc:
        pc.cmd_pack(
            SimpleNamespace(
                dir=str(plugin_dir),
                output=str(output_path),
                release=True,
                source=False,
            )
        )

    out = capsys.readouterr().out
    assert exc.value.code == 1
    assert "Frontend release css missing" in out


def test_cmd_pack_rejects_invalid_plugin_name(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    plugin_dir = _write_plugin(tmp_path, with_release=True)
    manifest_path = plugin_dir / "plugin.yaml"
    manifest_data = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    manifest_data["name"] = "InvalidName"
    manifest_path.write_text(
        yaml.safe_dump(manifest_data, sort_keys=False),
        encoding="utf-8",
    )

    with pytest.raises(SystemExit) as exc:
        pc.cmd_pack(
            SimpleNamespace(
                dir=str(plugin_dir),
                output=str(tmp_path / "invalid.zip"),
                release=True,
                source=False,
            )
        )

    out = capsys.readouterr().out
    assert exc.value.code == 1
    assert "Plugin name must be lowercase kebab-case" in out


def test_generate_release_manifest_rejects_escaping_manifest_name(
    tmp_path: Path,
) -> None:
    plugin_dir = _write_plugin(tmp_path, with_release=True)

    with pytest.raises(RuntimeError) as exc:
        pc._generate_release_manifest(plugin_dir, "../escape.json")

    assert "frontend.release.manifest" in str(exc.value)
