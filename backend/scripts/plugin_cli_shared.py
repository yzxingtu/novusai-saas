"""Shared helpers for plugin_cli. / plugin_cli 共享能力。"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

_PLUGIN_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")


def _is_truthy_or_falsy_bool_str(value: str) -> bool:
    normalized = value.strip().lower()
    return normalized in {"1", "0", "true", "false", "yes", "no", "on", "off"}


def _normalize_debug_env_for_cli(warnings: list[str]) -> None:
    """
    CLI 健壮性保护：
    当 DEBUG 被设置为非布尔字符串（例如 release）时，
    app.core.config 会在 import 阶段抛 ValidationError，导致 validate 中断。
    """

    raw = os.getenv("DEBUG")
    if raw is None:
        return
    if _is_truthy_or_falsy_bool_str(raw):
        return
    os.environ["DEBUG"] = "false"
    warnings.append(
        f"Environment DEBUG='{raw}' is not a valid boolean; fallback to DEBUG=false for CLI validation"
    )


def _manifest_has_frontend_extensions(manifest_data: dict) -> bool:
    from app.plugins.frontend_contract import has_frontend_extensions

    return bool(has_frontend_extensions(manifest_data or {}))


def _collect_frontend_i18n_contract_errors(
    manifest_data: dict,
) -> tuple[list[str], list[str]]:
    from app.plugins.frontend_contract_checks import (
        collect_frontend_i18n_contract_errors,
    )

    return collect_frontend_i18n_contract_errors(manifest_data)


def _collect_unsupported_manifest_contract_errors(manifest_data: dict) -> list[str]:
    errors: list[str] = []
    extensions = manifest_data.get("extensions") or {}

    if "capabilities" in extensions:
        errors.append(
            "extensions.capabilities is not part of the current manifest schema; "
            "move host/runtime capability requirements to top-level capabilities and "
            "keep tool contracts inside the resolver/executor implementation."
        )

    for index, skill in enumerate(extensions.get("skills") or []):
        if not isinstance(skill, dict):
            continue
        if "capabilities" in skill:
            errors.append(
                f"extensions.skills[{index}].capabilities is not part of the current manifest schema"
            )
        if "skill_md_path" in skill:
            errors.append(
                f"extensions.skills[{index}].skill_md_path is not part of the current manifest schema"
            )

    return errors


def _load_frontend_package_json(package_json_path: Path) -> dict | None:
    try:
        payload = json.loads(package_json_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def _collect_missing_i18n_locales(
    value: object,
    *,
    required_locales: tuple[str, ...] = ("zh-CN", "en"),
) -> list[str]:
    from app.plugins.frontend_contract_checks import collect_missing_i18n_locales

    return collect_missing_i18n_locales(
        value,
        required_locales=required_locales,
    )


def _has_local_frontend_dependency(package_data: dict, package_name: str) -> bool:
    for field in ("dependencies", "devDependencies"):
        deps = package_data.get(field)
        if isinstance(deps, dict) and package_name in deps:
            return True
    return False


def _extract_frontend_locale_prefixes(entry_content: str) -> list[str]:
    from app.plugins.frontend_contract_checks import extract_frontend_locale_prefixes

    return extract_frontend_locale_prefixes(entry_content)


def _collect_frontend_locale_prefix_contract_issues(
    plugin_name: str,
    entry_content: str,
) -> tuple[list[str], list[str]]:
    from app.plugins.frontend_contract_checks import (
        collect_frontend_locale_prefix_contract_issues,
    )

    return collect_frontend_locale_prefix_contract_issues(
        plugin_name,
        entry_content,
    )


def _collect_declared_frontend_component_names(frontend: object) -> list[str]:
    from app.plugins.frontend_contract_checks import (
        collect_declared_frontend_component_names,
    )

    return collect_declared_frontend_component_names(frontend)


def _entry_source_exports_symbol(entry_source: str, symbol: str) -> bool:
    from app.plugins.frontend_contract_checks import entry_source_exports_symbol

    return entry_source_exports_symbol(entry_source, symbol)


def _collect_frontend_component_export_contract_errors(
    frontend: dict,
    entry_source: str,
) -> list[str]:
    from app.plugins.frontend_contract_checks import (
        collect_frontend_component_export_contract_errors,
    )

    return collect_frontend_component_export_contract_errors(
        frontend,
        entry_source,
    )


def _load_plugin_manifest_for_cli(plugin_dir: Path):
    import yaml

    from app.plugins.manifest import PluginManifest

    with open(plugin_dir / "plugin.yaml", encoding="utf-8") as file_handle:
        data = yaml.safe_load(file_handle) or {}
    manifest = PluginManifest.model_validate(data)
    return manifest, data


def _print_cli_warnings(warnings: list[str]) -> None:
    for warning in warnings:
        print(f"  [WARN] {warning}")


def _load_manifest_for_command_or_exit(plugin_dir: Path):
    warnings: list[str] = []
    _normalize_debug_env_for_cli(warnings)
    try:
        manifest, data = _load_plugin_manifest_for_cli(plugin_dir)
    except Exception as exc:
        print(f"Error: plugin.yaml validation failed: {exc}")
        sys.exit(1)
    _print_cli_warnings(warnings)
    return manifest, data


def _run_security_scan_or_exit(
    plugin_dir: Path,
    *,
    failure_message: str,
    success_message: str,
) -> None:
    from app.plugins.security_scan import scan_plugin_directory

    scan_result = scan_plugin_directory(plugin_dir)
    if scan_result.has_warnings:
        print(f"Error: {failure_message}")
        for warning in scan_result.warnings:
            print(f"  - {warning}")
        sys.exit(1)
    print(f"  [OK] {success_message} ({scan_result.files_scanned} files)")


def _detect_package_manager(frontend_dir: Path) -> list[str]:
    is_windows = os.name == "nt"
    if (frontend_dir / "pnpm-lock.yaml").is_file():
        return ["pnpm.cmd" if is_windows else "pnpm", "run", "build"]
    if (frontend_dir / "yarn.lock").is_file():
        return ["yarn.cmd" if is_windows else "yarn", "build"]
    return ["npm.cmd" if is_windows else "npm", "run", "build"]


def _detect_package_manager_install(frontend_dir: Path) -> list[str]:
    is_windows = os.name == "nt"
    if (frontend_dir / "pnpm-lock.yaml").is_file():
        return ["pnpm.cmd" if is_windows else "pnpm", "install"]
    if (frontend_dir / "yarn.lock").is_file():
        return ["yarn.cmd" if is_windows else "yarn", "install"]
    return ["npm.cmd" if is_windows else "npm", "install"]


def _frontend_dependencies_need_bootstrap(frontend_dir: Path) -> bool:
    return not (frontend_dir / "node_modules").is_dir()


def _run_frontend_command(
    command: list[str],
    *,
    cwd: Path,
    error_message: str,
) -> None:
    print(f"  [RUN] {' '.join(command)}")
    try:
        subprocess.run(command, cwd=cwd, check=True)
    except subprocess.CalledProcessError as exc:
        print(f"Error: {error_message} (exit={exc.returncode})")
        sys.exit(1)
