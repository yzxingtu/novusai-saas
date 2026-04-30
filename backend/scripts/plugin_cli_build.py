"""Build command for plugin_cli. / plugin_cli build 命令。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from plugin_cli_release import _generate_release_manifest
from plugin_cli_shared import (
    _detect_package_manager,
    _detect_package_manager_install,
    _frontend_dependencies_need_bootstrap,
    _load_manifest_for_command_or_exit,
    _manifest_has_frontend_extensions,
    _run_frontend_command,
    _run_security_scan_or_exit,
)


def cmd_build(args: argparse.Namespace) -> None:
    """构建插件前端产物并生成 release manifest"""

    plugin_dir = Path(args.dir)
    yaml_path = plugin_dir / "plugin.yaml"
    if not yaml_path.is_file():
        print(f"Error: No plugin.yaml in {plugin_dir}")
        sys.exit(1)

    _manifest, data = _load_manifest_for_command_or_exit(plugin_dir)

    if not _manifest_has_frontend_extensions(data):
        print("  [INFO] No frontend extensions declared; nothing to build.")
        return

    frontend = (data.get("extensions") or {}).get("frontend") or {}
    release_manifest_name = str(
        (frontend.get("release") or {}).get("manifest") or "plugin.manifest.json"
    )

    frontend_dir = plugin_dir / "frontend"
    package_json = frontend_dir / "package.json"
    if not package_json.is_file():
        print(f"Error: Missing frontend/package.json in {plugin_dir}")
        sys.exit(1)

    _run_security_scan_or_exit(
        plugin_dir,
        failure_message="Security scan failed before build.",
        success_message="Security scan clean",
    )

    if _frontend_dependencies_need_bootstrap(frontend_dir):
        install_command = _detect_package_manager_install(frontend_dir)
        _run_frontend_command(
            install_command,
            cwd=frontend_dir,
            error_message=(
                "Frontend dependency install failed. "
                "Check frontend/package.json and your package manager environment"
            ),
        )

    command = _detect_package_manager(frontend_dir)
    _run_frontend_command(
        command,
        cwd=frontend_dir,
        error_message="Frontend build command failed",
    )

    try:
        release_manifest_path = _generate_release_manifest(
            plugin_dir,
            release_manifest_name,
        )
    except Exception as exc:
        print(f"Error: Failed to generate frontend release manifest: {exc}")
        sys.exit(1)
    print(f"  [OK] Generated frontend/dist/{release_manifest_path.name}")
