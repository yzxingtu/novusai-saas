"""Frontend dev/release contract regression tests. / 前端开发/发布契约回归测试。"""

from __future__ import annotations

import json

import pytest

from app.plugins.exceptions import PluginManifestError
from app.plugins.frontend_contract import (
    default_plugin_global_var,
    get_release_styles,
    has_frontend_extensions,
    validate_runtime_frontend_contract,
)


def _manifest_with_frontend() -> dict:
    return {
        "name": "demo-plugin",
        "version": "1.0.0",
        "display_name": {"zh-CN": "演示插件", "en": "Demo Plugin"},
        "description": {"zh-CN": "演示插件", "en": "Demo Plugin"},
        "scope": "all_tenants",
        "extensions": {
            "frontend": {
                "pages": [
                    {
                        "name": "demo-page",
                        "path": "/admin/plugins/demo-plugin/page",
                        "component": "DemoPage",
                        "scope": "admin",
                        "title": {"zh-CN": "演示页面", "en": "Demo"},
                        "menu": {
                            "title": {"zh-CN": "演示页面", "en": "Demo"},
                        },
                    }
                ],
                "dev": {"entry": "src/index.ts"},
                "release": {"manifest": "plugin.manifest.json"},
            }
        },
    }


def test_validate_runtime_frontend_contract_prefers_dev_source_in_debug(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    plugin_root = tmp_path / "demo-plugin"
    (plugin_root / "frontend" / "src").mkdir(parents=True)
    (plugin_root / "frontend" / "src" / "index.ts").write_text(
        "export const DemoPage = {};\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "app.plugins.frontend_contract.settings.DEBUG", True, raising=False
    )

    result = validate_runtime_frontend_contract(plugin_root, _manifest_with_frontend())

    assert result["has_frontend"] is True
    assert result["mode"] == "dev_source"


def test_validate_runtime_frontend_contract_requires_release_manifest_in_prod(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    plugin_root = tmp_path / "demo-plugin"
    (plugin_root / "frontend" / "dist").mkdir(parents=True)
    (plugin_root / "frontend" / "dist" / "index.js").write_text(
        "window.demo = {};\n", encoding="utf-8"
    )

    monkeypatch.setattr(
        "app.plugins.frontend_contract.settings.DEBUG", False, raising=False
    )

    with pytest.raises(PluginManifestError, match="Frontend release manifest missing"):
        validate_runtime_frontend_contract(plugin_root, _manifest_with_frontend())


def test_release_styles_are_read_from_release_manifest(
    tmp_path,
) -> None:
    plugin_root = tmp_path / "demo-plugin"
    dist_dir = plugin_root / "frontend" / "dist"
    dist_dir.mkdir(parents=True)
    (dist_dir / "index.js").write_text("window.demo = {};\n", encoding="utf-8")
    (dist_dir / "style.css").write_text(".demo{}\n", encoding="utf-8")
    (dist_dir / "plugin.manifest.json").write_text(
        json.dumps(
            {
                "format": "novus.plugin.release.v1",
                "entry": "index.js",
                "global_var": default_plugin_global_var("demo-plugin"),
                "css": ["style.css"],
            }
        ),
        encoding="utf-8",
    )

    styles = get_release_styles(plugin_root, _manifest_with_frontend())

    assert styles == ["style.css"]


def test_has_frontend_extensions_true_when_only_dev_release_declared() -> None:
    manifest = {
        "name": "demo-plugin",
        "version": "1.0.0",
        "display_name": {"zh-CN": "演示插件", "en": "Demo Plugin"},
        "scope": "all_tenants",
        "extensions": {
            "frontend": {
                "dev": {"entry": "src/index.ts"},
                "release": {"manifest": "plugin.manifest.json"},
            }
        },
    }

    assert has_frontend_extensions(manifest) is True


def test_backend_only_plugin_does_not_require_frontend_release_manifest(
    tmp_path,
) -> None:
    from app.plugins.manifest import PluginManifest

    manifest = PluginManifest.model_validate(
        {
            "name": "storage-plugin",
            "version": "1.0.0",
            "display_name": {"zh-CN": "存储插件", "en": "Storage Plugin"},
            "scope": "global_shared",
            "extensions": {
                "storage_drivers": [
                    {
                        "code": "storage-demo",
                        "display_name": {
                            "zh-CN": "演示存储",
                            "en": "Demo Storage",
                        },
                        "entry_point": "driver.DemoStorageDriver",
                    }
                ]
            },
        }
    )

    assert has_frontend_extensions(manifest) is False
    assert validate_runtime_frontend_contract(
        tmp_path / "storage-plugin", manifest
    ) == {
        "has_frontend": False,
        "mode": "none",
    }


def test_validate_runtime_frontend_contract_rejects_missing_page_and_menu_locales(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    plugin_root = tmp_path / "demo-plugin"
    (plugin_root / "frontend" / "src").mkdir(parents=True)
    (plugin_root / "frontend" / "src" / "index.ts").write_text(
        "export const DemoPage = {};\n",
        encoding="utf-8",
    )
    manifest = _manifest_with_frontend()
    page = manifest["extensions"]["frontend"]["pages"][0]
    page["title"] = {"zh-CN": "演示页面"}
    page["menu"]["title"] = {"en": "Demo"}

    monkeypatch.setattr(
        "app.plugins.frontend_contract.settings.DEBUG", True, raising=False
    )

    with pytest.raises(PluginManifestError) as exc:
        validate_runtime_frontend_contract(plugin_root, manifest)

    message = str(exc.value)
    assert "frontend.pages[0].title missing locale(s): en" in message
    assert "frontend.pages[0].menu.title missing locale(s): zh-CN" in message


def test_validate_runtime_frontend_contract_rejects_non_canonical_locale_prefix(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    plugin_root = tmp_path / "demo-plugin"
    (plugin_root / "frontend" / "src").mkdir(parents=True)
    (plugin_root / "frontend" / "src" / "index.ts").write_text(
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

    monkeypatch.setattr(
        "app.plugins.frontend_contract.settings.DEBUG", True, raising=False
    )

    with pytest.raises(
        PluginManifestError, match="canonical prefix 'plugin.demo-plugin'"
    ):
        validate_runtime_frontend_contract(plugin_root, _manifest_with_frontend())


def test_validate_runtime_frontend_contract_accepts_helper_wrapped_locale_prefixes(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    plugin_root = tmp_path / "demo-plugin"
    (plugin_root / "frontend" / "src").mkdir(parents=True)
    (plugin_root / "frontend" / "src" / "index.ts").write_text(
        """
const ROOT_LOCALE_PREFIX = 'plugin.demo-plugin.admin';
const LEGACY_LOCALE_PREFIX = 'plugin.demoPlugin.admin';

function registerLocaleGroup(prefix) {
  const shared = window.NovusPluginShared;
  shared?.registerLocale?.('zh-CN', prefix, {});
  shared?.registerLocale?.('en', prefix, {});
}

export function setup() {
  registerLocaleGroup(ROOT_LOCALE_PREFIX);
  registerLocaleGroup(LEGACY_LOCALE_PREFIX);
}

export const DemoPage = {};
""".strip()
        + "\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "app.plugins.frontend_contract.settings.DEBUG", True, raising=False
    )

    result = validate_runtime_frontend_contract(plugin_root, _manifest_with_frontend())

    assert result["mode"] == "dev_source"
    assert any("plugin.demoPlugin.admin" in warning for warning in result["warnings"])


def test_validate_runtime_frontend_contract_rejects_missing_declared_component_export(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    plugin_root = tmp_path / "demo-plugin"
    (plugin_root / "frontend" / "src").mkdir(parents=True)
    (plugin_root / "frontend" / "src" / "index.ts").write_text(
        "export const OtherPage = {};\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "app.plugins.frontend_contract.settings.DEBUG", True, raising=False
    )

    with pytest.raises(
        PluginManifestError,
        match="frontend dev entry does not export declared component 'DemoPage'",
    ):
        validate_runtime_frontend_contract(plugin_root, _manifest_with_frontend())
