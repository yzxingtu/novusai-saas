"""Pack command for plugin_cli. / plugin_cli pack 命令。"""

from __future__ import annotations

import argparse
import sys
import zipfile
from pathlib import Path

from plugin_cli_release import _should_exclude_release_file
from plugin_cli_shared import (
    _PLUGIN_NAME_PATTERN,
    _load_manifest_for_command_or_exit,
    _manifest_has_frontend_extensions,
    _run_security_scan_or_exit,
)

_PACK_EXCLUDE_DIRS = {"node_modules", "__pycache__", ".git", ".venv"}
_PACK_EXCLUDE_EXTS = {".pyc", ".pyo"}


def cmd_pack(args: argparse.Namespace) -> None:
    """打包插件为 .zip"""
    plugin_dir = Path(args.dir)
    if not (plugin_dir / "plugin.yaml").is_file():
        print(f"Error: No plugin.yaml in {plugin_dir}")
        sys.exit(1)

    manifest, data = _load_manifest_for_command_or_exit(plugin_dir)

    name = manifest.name
    if not _PLUGIN_NAME_PATTERN.match(name):
        print(f"Error: Plugin name must be lowercase kebab-case, got '{name}'")
        sys.exit(1)
    version = manifest.version
    mode = "source" if getattr(args, "source", False) else "release"

    _run_security_scan_or_exit(
        plugin_dir,
        failure_message="Security scan failed.",
        success_message="Security scan clean",
    )

    has_frontend = _manifest_has_frontend_extensions(data or {})
    if has_frontend and mode == "release":
        from app.plugins.exceptions import PluginManifestError
        from app.plugins.frontend_contract import load_release_manifest

        try:
            load_release_manifest(plugin_dir, manifest, strict=True)
        except PluginManifestError as exc:
            print(f"Error: {exc.message}")
            print(f"  Please run: novusai plugin build {plugin_dir}")
            sys.exit(1)
        except Exception as exc:
            print(f"Error: frontend release manifest invalid: {exc}")
            print(f"  Please run: novusai plugin build {plugin_dir}")
            sys.exit(1)

    default_name = (
        f"{name}-{version}-source.zip" if mode == "source" else f"{name}-{version}.zip"
    )
    output_path = Path(args.output) if args.output else Path.cwd() / default_name

    file_count = 0
    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for file_path in plugin_dir.rglob("*"):
            if not file_path.is_file():
                continue
            rel = file_path.relative_to(plugin_dir)
            if any(part in _PACK_EXCLUDE_DIRS for part in rel.parts):
                continue
            if any(part.startswith(".") for part in rel.parts):
                continue
            if file_path.suffix in _PACK_EXCLUDE_EXTS:
                continue
            if mode == "release" and _should_exclude_release_file(rel):
                continue
            zip_file.write(file_path, f"{name}/{rel}")
            file_count += 1

    size_kb = output_path.stat().st_size / 1024
    print(f"Packed: {output_path}")
    print(f"  Mode: {mode}")
    print(f"  {file_count} files, {size_kb:.1f} KB")
