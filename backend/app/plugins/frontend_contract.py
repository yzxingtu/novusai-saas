"""Plugin frontend dev/release contract helpers. / 插件前端开发/发布契约辅助函数。"""

from __future__ import annotations

import json
from pathlib import Path, PurePosixPath
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.core.config import settings
from app.plugins.exceptions import PluginManifestError
from app.plugins.frontend_contract_checks import (
    collect_frontend_component_export_contract_errors,
    collect_frontend_i18n_contract_errors,
    collect_frontend_locale_prefix_contract_issues,
)


class PluginReleaseManifest(BaseModel):
    """Compiled frontend release manifest. / 编译后的前端发布清单。"""

    model_config = ConfigDict(extra="forbid")

    format: Literal["novus.plugin.release.v1"] = Field(
        default="novus.plugin.release.v1"
    )
    entry: str = Field(default="index.js")
    global_var: str
    css: list[str] = Field(default_factory=list)
    assets: list[str] = Field(default_factory=list)


def default_plugin_global_var(plugin_name: str) -> str:
    """Return the default UMD global variable name. / 返回默认 UMD 全局变量名。"""
    return f"NovusPlugin_{plugin_name.replace('-', '_')}"


def has_frontend_extensions(manifest: Any) -> bool:
    """Whether plugin declares any frontend capability. / 插件是否声明了任何前端能力。"""
    frontend = _get_frontend_decl(manifest)
    has_standard_frontend = any(
        (
            frontend.get("pages"),
            frontend.get("header_widgets"),
            frontend.get("floating_panels"),
            frontend.get("notification_ui"),
            frontend.get("dashboard_widgets"),
            frontend.get("settings_tabs"),
        )
    )
    has_runtime_contract = bool(
        str((frontend.get("dev") or {}).get("entry") or "").strip()
        or str((frontend.get("release") or {}).get("manifest") or "").strip()
    )
    if has_standard_frontend or has_runtime_contract:
        return True

    custom_extensions = _get_custom_ext_decl(manifest)
    return any(
        str(ext.get("type") or "").strip() == "captcha_provider"
        for ext in custom_extensions
    )


def load_release_manifest(
    plugin_root: Path,
    manifest: Any,
    *,
    strict: bool = True,
) -> PluginReleaseManifest | None:
    """Read and validate frontend/dist release manifest. / 读取并校验 frontend/dist 发布清单。"""
    frontend = _get_frontend_decl(manifest)
    release = frontend.get("release", {})
    manifest_rel = str(release.get("manifest") or "plugin.manifest.json")
    manifest_path = _resolve_frontend_dist_relative_file(
        plugin_root,
        manifest_rel,
        field_name="frontend.release.manifest",
    )
    if manifest_path is None or not manifest_path.is_file():
        if strict:
            raise PluginManifestError(
                message=(
                    f"Frontend release manifest missing: frontend/dist/{manifest_rel}"
                ),
            )
        return None

    try:
        release_data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:
        if strict:
            raise PluginManifestError(
                message=f"Invalid frontend release manifest '{manifest_path.name}': {exc}",
            ) from exc
        return None

    try:
        release_manifest = PluginReleaseManifest.model_validate(release_data)
    except Exception as exc:
        if strict:
            raise PluginManifestError(
                message=f"Frontend release manifest validation failed: {exc}",
            ) from exc
        return None

    _assert_release_files_exist(plugin_root, release_manifest)
    return release_manifest


def validate_runtime_frontend_contract(
    plugin_root: Path, manifest: Any
) -> dict[str, Any]:
    """Validate plugin frontend contract according to current runtime mode.
    / 按当前运行模式校验插件前端契约。
    """
    if not has_frontend_extensions(manifest):
        return {"has_frontend": False, "mode": "none"}

    frontend = _get_frontend_decl(manifest)
    plugin_name = _get_manifest_name(manifest)
    frontend_i18n_errors, expected_locales = collect_frontend_i18n_contract_errors(
        manifest
    )
    if frontend_i18n_errors:
        raise PluginManifestError(
            message=(
                "Frontend page/menu i18n contract invalid: "
                + "; ".join(frontend_i18n_errors)
            ),
        )

    runtime_warnings: list[str] = []
    dev = frontend.get("dev", {})
    dev_entry = _resolve_frontend_relative_file(
        plugin_root,
        str(dev.get("entry") or "src/index.ts"),
        field_name="frontend.dev.entry",
    )
    if dev_entry is not None and dev_entry.is_file():
        entry_source = dev_entry.read_text(encoding="utf-8", errors="ignore")
        locale_prefix_errors, locale_prefix_warnings = (
            collect_frontend_locale_prefix_contract_issues(
                plugin_name,
                entry_source,
            )
        )
        if locale_prefix_errors:
            raise PluginManifestError(
                message=(
                    "Frontend locale namespace invalid: "
                    + "; ".join(locale_prefix_errors)
                ),
            )
        component_export_errors = collect_frontend_component_export_contract_errors(
            frontend,
            entry_source,
        )
        if component_export_errors:
            raise PluginManifestError(
                message=(
                    "Frontend component export contract invalid: "
                    + "; ".join(component_export_errors)
                ),
            )
        runtime_warnings.extend(locale_prefix_warnings)

    if settings.DEBUG and dev_entry is not None and dev_entry.is_file():
        return {
            "has_frontend": True,
            "mode": "dev_source",
            "dev_entry": dev_entry,
            "expected_locales": expected_locales,
            "warnings": runtime_warnings,
        }

    release_manifest = load_release_manifest(plugin_root, manifest, strict=True)
    return {
        "has_frontend": True,
        "mode": "release",
        "expected_locales": expected_locales,
        "release_manifest": release_manifest,
        "warnings": runtime_warnings,
    }


def get_release_styles(plugin_root: Path, manifest: Any) -> list[str]:
    """Return css assets declared in release manifest. / 返回发布清单声明的 CSS 资源。"""
    release_manifest = load_release_manifest(plugin_root, manifest, strict=False)
    if not release_manifest:
        return []
    return list(dict.fromkeys(release_manifest.css))


def _get_frontend_decl(manifest: Any) -> dict[str, Any]:
    if hasattr(manifest, "extensions") and getattr(
        manifest.extensions, "frontend", None
    ):
        extensions_fields_set = getattr(manifest.extensions, "model_fields_set", None)
        if (
            extensions_fields_set is not None
            and "frontend" not in extensions_fields_set
        ):
            return {}
        frontend = manifest.extensions.frontend
        if hasattr(frontend, "model_dump"):
            return frontend.model_dump(exclude_none=True)
        if isinstance(frontend, dict):
            return frontend
        if hasattr(frontend, "__dict__"):
            return {
                key: value
                for key, value in vars(frontend).items()
                if not key.startswith("_")
            }
    if isinstance(manifest, dict):
        extensions = manifest.get("extensions") or {}
        if isinstance(extensions, dict):
            frontend = extensions.get("frontend") or {}
            if isinstance(frontend, dict):
                return frontend
    return {}


def _get_custom_ext_decl(manifest: Any) -> list[dict[str, Any]]:
    if hasattr(manifest, "extensions") and getattr(manifest.extensions, "custom", None):
        custom = manifest.extensions.custom
        if isinstance(custom, list):
            result: list[dict[str, Any]] = []
            for item in custom:
                if hasattr(item, "model_dump"):
                    result.append(item.model_dump(exclude_none=True))
                elif isinstance(item, dict):
                    result.append(item)
            return result
    if isinstance(manifest, dict):
        extensions = manifest.get("extensions") or {}
        custom = extensions.get("custom") if isinstance(extensions, dict) else None
        if isinstance(custom, list):
            return [item for item in custom if isinstance(item, dict)]
    return []


def _get_manifest_name(manifest: Any) -> str:
    if hasattr(manifest, "name"):
        return str(manifest.name or "").strip()
    if isinstance(manifest, dict):
        return str(manifest.get("name") or "").strip()
    return ""


def _resolve_frontend_relative_file(
    plugin_root: Path,
    raw_path: str,
    *,
    field_name: str,
) -> Path | None:
    normalized = _normalize_contract_relative_path(raw_path, field_name=field_name)
    if normalized is None:
        return None
    target = (plugin_root / "frontend" / normalized).resolve()
    frontend_root = (plugin_root / "frontend").resolve()
    if frontend_root not in target.parents:
        raise PluginManifestError(
            message=f"{field_name} escapes plugin frontend directory: {raw_path}",
        )
    return target


def _resolve_frontend_dist_relative_file(
    plugin_root: Path,
    raw_path: str,
    *,
    field_name: str,
) -> Path | None:
    normalized = _normalize_contract_relative_path(raw_path, field_name=field_name)
    if normalized is None:
        return None
    target = (plugin_root / "frontend" / "dist" / normalized).resolve()
    dist_root = (plugin_root / "frontend" / "dist").resolve()
    if dist_root not in target.parents and target != dist_root:
        raise PluginManifestError(
            message=f"{field_name} escapes plugin frontend/dist directory: {raw_path}",
        )
    return target


def _normalize_contract_relative_path(
    raw_path: str,
    *,
    field_name: str,
) -> str | None:
    path = str(raw_path or "").strip().replace("\\", "/").lstrip("/")
    normalized = PurePosixPath(path)
    if str(normalized) in {"", "."}:
        return None
    if ".." in normalized.parts:
        raise PluginManifestError(
            message=f"{field_name} cannot contain path traversal: {raw_path}",
        )
    return str(normalized)


def _assert_release_files_exist(
    plugin_root: Path,
    release_manifest: PluginReleaseManifest,
) -> None:
    entry_path = _resolve_frontend_dist_relative_file(
        plugin_root,
        release_manifest.entry,
        field_name="plugin.manifest.entry",
    )
    if entry_path is None or not entry_path.is_file():
        raise PluginManifestError(
            message=(
                "Frontend release entry missing: "
                f"frontend/dist/{release_manifest.entry}"
            ),
        )

    for css_file in release_manifest.css:
        css_path = _resolve_frontend_dist_relative_file(
            plugin_root,
            css_file,
            field_name="plugin.manifest.css",
        )
        if css_path is None or not css_path.is_file():
            raise PluginManifestError(
                message=f"Frontend release css missing: frontend/dist/{css_file}",
            )

    for asset_file in release_manifest.assets:
        asset_path = _resolve_frontend_dist_relative_file(
            plugin_root,
            asset_file,
            field_name="plugin.manifest.assets",
        )
        if asset_path is None or not asset_path.is_file():
            raise PluginManifestError(
                message=f"Frontend release asset missing: frontend/dist/{asset_file}",
            )
