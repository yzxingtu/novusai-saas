"""Thin facade for plugin_cli. / plugin_cli 兼容壳。"""

from __future__ import annotations

import plugin_cli_shared as _plugin_cli_shared
from plugin_cli_build import cmd_build
from plugin_cli_create import cmd_create
from plugin_cli_pack import cmd_pack
from plugin_cli_parser import build_parser, main
from plugin_cli_release import (
    _collect_dist_files,
    _generate_release_manifest,
    _normalize_release_dist_path,
    _pick_release_entry,
    _should_exclude_release_file,
)
from plugin_cli_shared import (
    _PLUGIN_NAME_PATTERN,
    PROJECT_ROOT,
    _collect_declared_frontend_component_names,
    _collect_frontend_component_export_contract_errors,
    _collect_frontend_i18n_contract_errors,
    _collect_frontend_locale_prefix_contract_issues,
    _collect_missing_i18n_locales,
    _collect_unsupported_manifest_contract_errors,
    _detect_package_manager,
    _detect_package_manager_install,
    _entry_source_exports_symbol,
    _extract_frontend_locale_prefixes,
    _frontend_dependencies_need_bootstrap,
    _has_local_frontend_dependency,
    _is_truthy_or_falsy_bool_str,
    _load_frontend_package_json,
    _load_manifest_for_command_or_exit,
    _load_plugin_manifest_for_cli,
    _manifest_has_frontend_extensions,
    _normalize_debug_env_for_cli,
    _print_cli_warnings,
    _run_frontend_command,
    _run_security_scan_or_exit,
)
from plugin_cli_validate import cmd_validate

subprocess = _plugin_cli_shared.subprocess

__all__ = [
    "PROJECT_ROOT",
    "_PLUGIN_NAME_PATTERN",
    "_collect_declared_frontend_component_names",
    "_collect_dist_files",
    "_collect_frontend_component_export_contract_errors",
    "_collect_frontend_i18n_contract_errors",
    "_collect_frontend_locale_prefix_contract_issues",
    "_collect_missing_i18n_locales",
    "_collect_unsupported_manifest_contract_errors",
    "_detect_package_manager",
    "_detect_package_manager_install",
    "_entry_source_exports_symbol",
    "_extract_frontend_locale_prefixes",
    "_frontend_dependencies_need_bootstrap",
    "_generate_release_manifest",
    "_has_local_frontend_dependency",
    "_is_truthy_or_falsy_bool_str",
    "_load_frontend_package_json",
    "_load_manifest_for_command_or_exit",
    "_load_plugin_manifest_for_cli",
    "_manifest_has_frontend_extensions",
    "_normalize_debug_env_for_cli",
    "_normalize_release_dist_path",
    "_pick_release_entry",
    "_print_cli_warnings",
    "_run_frontend_command",
    "_run_security_scan_or_exit",
    "_should_exclude_release_file",
    "build_parser",
    "cmd_build",
    "cmd_create",
    "cmd_pack",
    "cmd_validate",
    "main",
    "subprocess",
]


if __name__ == "__main__":
    main()
