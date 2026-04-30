"""Release helpers for plugin_cli. / plugin_cli release 资产辅助。"""

from __future__ import annotations

import json
from pathlib import Path

from plugin_cli_shared import _load_plugin_manifest_for_cli


def _collect_dist_files(dist_dir: Path) -> list[str]:
    return sorted(
        str(path.relative_to(dist_dir)).replace("\\", "/")
        for path in dist_dir.rglob("*")
        if path.is_file()
        and path.name != "plugin.manifest.json"
        and not path.name.endswith(".map")
    )


def _pick_release_entry(js_files: list[str]) -> str | None:
    for candidate in ("plugin.js", "index.js"):
        if candidate in js_files:
            return candidate
    return js_files[0] if js_files else None


def _normalize_release_dist_path(
    plugin_dir: Path, raw_path: str, field_name: str
) -> str:
    from app.plugins.exceptions import PluginManifestError
    from app.plugins.frontend_contract import _resolve_frontend_dist_relative_file

    try:
        resolved = _resolve_frontend_dist_relative_file(
            plugin_dir,
            raw_path,
            field_name=field_name,
        )
    except PluginManifestError as exc:
        raise RuntimeError(f"{field_name}: {exc.message}") from exc
    if resolved is None:
        raise RuntimeError(f"{field_name} cannot be empty")
    dist_root = (plugin_dir / "frontend" / "dist").resolve()
    try:
        return str(resolved.relative_to(dist_root).as_posix())
    except ValueError as exc:
        raise RuntimeError(f"{field_name} escapes frontend/dist: {raw_path}") from exc


def _generate_release_manifest(plugin_dir: Path, manifest_name: str) -> Path:
    from app.plugins.exceptions import PluginManifestError
    from app.plugins.frontend_contract import (
        _resolve_frontend_dist_relative_file,
        default_plugin_global_var,
    )

    manifest, _ = _load_plugin_manifest_for_cli(plugin_dir)

    dist_dir = plugin_dir / "frontend" / "dist"
    if not dist_dir.is_dir():
        raise RuntimeError("frontend/dist missing after build")

    files = _collect_dist_files(dist_dir)
    js_files = [file for file in files if file.endswith(".js")]
    css_files = [file for file in files if file.endswith(".css")]
    entry = _pick_release_entry(js_files)
    if not entry:
        raise RuntimeError("No release JavaScript entry found under frontend/dist")

    sanitized_entry = _normalize_release_dist_path(
        plugin_dir,
        entry,
        field_name="plugin.manifest.entry",
    )
    sanitized_css = [
        _normalize_release_dist_path(
            plugin_dir, css_file, field_name="plugin.manifest.css"
        )
        for css_file in css_files
    ]
    asset_candidates = [file for file in files if file not in {entry, *css_files}]
    sanitized_assets = [
        _normalize_release_dist_path(
            plugin_dir,
            asset,
            field_name="plugin.manifest.assets",
        )
        for asset in asset_candidates
    ]
    payload = {
        "format": "novus.plugin.release.v1",
        "entry": sanitized_entry,
        "global_var": default_plugin_global_var(manifest.name),
        "css": sanitized_css,
        "assets": sanitized_assets,
    }

    try:
        manifest_path = _resolve_frontend_dist_relative_file(
            plugin_dir,
            manifest_name,
            field_name="frontend.release.manifest",
        )
    except PluginManifestError as exc:
        raise RuntimeError(f"frontend.release.manifest: {exc.message}") from exc
    if manifest_path is None:
        raise RuntimeError("frontend.release.manifest cannot be empty")
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest_path


def _should_exclude_release_file(rel_path: Path) -> bool:
    rel_posix = str(rel_path).replace("\\", "/")
    if rel_posix.startswith("frontend/src/") or rel_posix.startswith("backend/tests/"):
        return True
    if rel_posix in {
        "frontend/package-lock.json",
        "frontend/package.json",
        "frontend/pnpm-lock.yaml",
        "frontend/tsconfig.json",
        "frontend/vite.config.js",
        "frontend/vite.config.mjs",
        "frontend/vite.config.ts",
        "frontend/yarn.lock",
    }:
        return True
    if any(marker in rel_path.parts for marker in {"__tests__", "tests"}):
        return True
    return rel_path.name.endswith(
        (
            ".spec.ts",
            ".spec.tsx",
            ".test.ts",
            ".test.tsx",
        )
    ) or (
        rel_posix.startswith("backend/")
        and rel_path.name.startswith("test_")
        and rel_path.suffix == ".py"
    )
