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
        "display_name": {"en": "Demo Plugin"},
        "scope": "all_tenants",
        "extensions": {
            "frontend": {
                "pages": [
                    {
                        "name": "demo-page",
                        "path": "/admin/plugins/demo-plugin/page",
                        "component": "DemoPage",
                        "scope": "admin",
                        "title": {"en": "Demo"},
                        "menu": {
                            "title": {"en": "Demo"},
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
    (plugin_root / "frontend" / "src" / "index.ts").write_text("export {};\n", encoding="utf-8")

    monkeypatch.setattr("app.plugins.frontend_contract.settings.DEBUG", True, raising=False)

    result = validate_runtime_frontend_contract(plugin_root, _manifest_with_frontend())

    assert result["has_frontend"] is True
    assert result["mode"] == "dev_source"


def test_validate_runtime_frontend_contract_requires_release_manifest_in_prod(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    plugin_root = tmp_path / "demo-plugin"
    (plugin_root / "frontend" / "dist").mkdir(parents=True)
    (plugin_root / "frontend" / "dist" / "index.js").write_text("window.demo = {};\n", encoding="utf-8")

    monkeypatch.setattr("app.plugins.frontend_contract.settings.DEBUG", False, raising=False)

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
        "display_name": {"en": "Demo Plugin"},
        "scope": "all_tenants",
        "extensions": {
            "frontend": {
                "dev": {"entry": "src/index.ts"},
                "release": {"manifest": "plugin.manifest.json"},
            }
        },
    }

    assert has_frontend_extensions(manifest) is True
