"""Validate command for plugin_cli. / plugin_cli validate 命令。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from plugin_cli_shared import (
    _collect_frontend_component_export_contract_errors,
    _collect_frontend_i18n_contract_errors,
    _collect_frontend_locale_prefix_contract_issues,
    _collect_missing_i18n_locales,
    _collect_unsupported_manifest_contract_errors,
    _has_local_frontend_dependency,
    _load_frontend_package_json,
    _manifest_has_frontend_extensions,
    _normalize_debug_env_for_cli,
)


def cmd_validate(args: argparse.Namespace) -> None:
    """校验插件"""
    plugin_dir = Path(args.dir)
    if not plugin_dir.is_dir():
        print(f"Error: Not a directory: {plugin_dir}")
        sys.exit(1)

    errors: list[str] = []
    warnings: list[str] = []

    yaml_path = plugin_dir / "plugin.yaml"
    if not yaml_path.is_file():
        errors.append("Missing plugin.yaml")
        manifest = None
        data = {}
    else:
        try:
            _normalize_debug_env_for_cli(warnings)
            import yaml

            from app.plugins.frontend_contract import load_release_manifest
            from app.plugins.manifest import PluginManifest

            with open(yaml_path, encoding="utf-8") as file_handle:
                data = yaml.safe_load(file_handle)
            manifest = PluginManifest.model_validate(data)
            print(f"  [OK] plugin.yaml valid: {manifest.name} v{manifest.version}")

            errors.extend(_collect_unsupported_manifest_contract_errors(data or {}))

            frontend = ((data or {}).get("extensions") or {}).get("frontend") or {}
            legacy_keys = sorted(
                set(frontend).intersection(
                    {"admin", "menus", "npm_dependencies", "standalone_pages", "tenant"}
                )
            )
            if legacy_keys:
                errors.append(
                    "frontend uses legacy fields: "
                    + ", ".join(legacy_keys)
                    + " (migrate to pages + dev.entry + release.manifest)"
                )

            locales_dir = plugin_dir / "locales"
            if locales_dir.is_dir():
                prefix = f"plugin.{manifest.name}."
                for json_file in locales_dir.glob("*.json"):
                    locale_data = json.loads(json_file.read_text(encoding="utf-8"))
                    if (
                        isinstance(locale_data, dict)
                        and isinstance(locale_data.get("plugin"), dict)
                        and isinstance(locale_data["plugin"].get(manifest.name), dict)
                    ):
                        continue

                    for key in locale_data:
                        if not key.startswith(prefix):
                            warnings.append(
                                f"i18n key '{key}' in {json_file.name} should start with '{prefix}'"
                            )

            for page in frontend.get("pages") or []:
                if not isinstance(page, dict):
                    continue
                page_name = str(page.get("name") or page.get("path") or "<unknown>")
                missing_page_title_locales = _collect_missing_i18n_locales(page.get("title"))
                if missing_page_title_locales:
                    warnings.append(
                        "frontend page title should define locales "
                        f"{', '.join(missing_page_title_locales)}: {page_name}"
                    )
                menu = page.get("menu")
                if isinstance(menu, dict):
                    missing_menu_title_locales = _collect_missing_i18n_locales(
                        menu.get("title")
                    )
                    if missing_menu_title_locales:
                        warnings.append(
                            "frontend menu title should define locales "
                            f"{', '.join(missing_menu_title_locales)}: {page_name}"
                        )

            if _manifest_has_frontend_extensions(data or {}):
                frontend_i18n_errors, expected_locales = (
                    _collect_frontend_i18n_contract_errors(data or {})
                )
                errors.extend(frontend_i18n_errors)
                if not frontend_i18n_errors and (frontend.get("pages") or []):
                    print(
                        "  [OK] frontend page/menu i18n covers locales: "
                        + ", ".join(expected_locales)
                    )

                frontend_dir = plugin_dir / "frontend"
                package_json_path = frontend_dir / "package.json"
                frontend_package: dict | None = None
                if package_json_path.is_file():
                    frontend_package = _load_frontend_package_json(package_json_path)
                    if frontend_package is None:
                        errors.append("frontend/package.json invalid JSON object")
                    else:
                        print("  [OK] frontend/package.json exists")
                        if _has_local_frontend_dependency(frontend_package, "vue"):
                            print("  [OK] frontend local build dependency present: vue")
                        else:
                            errors.append(
                                "frontend/package.json must declare local build dependency 'vue' "
                                "in dependencies or devDependencies"
                            )
                else:
                    errors.append("frontend/package.json missing")

                vite_config = frontend_dir / "vite.config.ts"
                if vite_config.is_file():
                    print("  [OK] frontend/vite.config.ts exists")
                else:
                    errors.append("frontend/vite.config.ts missing")

                dev_entry_rel = str(
                    (frontend.get("dev") or {}).get("entry") or "src/index.ts"
                )
                dev_entry = frontend_dir / dev_entry_rel
                if dev_entry.is_file():
                    print(f"  [OK] frontend dev entry exists: {dev_entry_rel}")
                    entry_source = dev_entry.read_text(
                        encoding="utf-8",
                        errors="ignore",
                    )
                    locale_prefix_errors, locale_prefix_warnings = (
                        _collect_frontend_locale_prefix_contract_issues(
                            manifest.name,
                            entry_source,
                        )
                    )
                    errors.extend(locale_prefix_errors)
                    warnings.extend(locale_prefix_warnings)
                    errors.extend(
                        _collect_frontend_component_export_contract_errors(
                            frontend,
                            entry_source,
                        )
                    )
                    if not locale_prefix_errors:
                        print(
                            "  [OK] frontend locale namespace covers canonical root: "
                            f"plugin.{manifest.name}"
                        )
                else:
                    errors.append(f"frontend dev entry missing: frontend/{dev_entry_rel}")

                release_manifest_rel = str(
                    (frontend.get("release") or {}).get("manifest")
                    or "plugin.manifest.json"
                )
                release_manifest_path = (
                    plugin_dir / "frontend" / "dist" / release_manifest_rel
                )
                if release_manifest_path.is_file():
                    try:
                        release_manifest = load_release_manifest(
                            plugin_dir,
                            manifest,
                            strict=True,
                        )
                        print(
                            "  [OK] frontend release manifest valid: "
                            f"{release_manifest_rel} → {release_manifest.entry}"
                        )
                    except Exception as exc:
                        errors.append(f"frontend release manifest invalid: {exc}")
                else:
                    warnings.append(
                        "frontend release manifest missing - run: "
                        f"novusai plugin build {plugin_dir}"
                    )

                vue_files = list((plugin_dir / "frontend" / "src").rglob("*.vue"))
                for vue_file in vue_files:
                    content = vue_file.read_text(encoding="utf-8", errors="ignore")
                    if "<style scoped" in content or "<style scoped>" in content:
                        errors.append(
                            f"{vue_file.relative_to(plugin_dir)}: <style scoped> forbidden"
                        )
                if vue_files and not any(
                    "<style scoped" in file_handle.read_text(encoding="utf-8", errors="ignore")
                    for file_handle in vue_files
                ):
                    print(f"  [OK] {len(vue_files)} .vue file(s) - no <style scoped>")
            else:
                print("  [INFO] No frontend extensions declared")

        except Exception as exc:
            errors.append(f"plugin.yaml validation failed: {exc}")
            manifest = None
            data = {}

    main_path = plugin_dir / "backend" / "main.py"
    if not main_path.is_file():
        errors.append("Missing backend/main.py")
    else:
        print("  [OK] backend/main.py exists")

    try:
        import yaml as yaml_loader

        from app.plugins.manifest import PluginManifest

        with open(yaml_path, encoding="utf-8") as file_handle:
            yaml_payload = yaml_loader.safe_load(file_handle)
        manifest_for_caps = PluginManifest.model_validate(yaml_payload)
        capabilities = set(manifest_for_caps.capabilities)
        extensions = manifest_for_caps.extensions
        if (
            manifest_for_caps.ai_requirements
            and manifest_for_caps.ai_requirements.features
            and "ai:call" not in capabilities
        ):
            warnings.append(
                "ai_requirements.features declared but 'ai:call' not in capabilities"
            )
        if (
            any(
                route.handler
                for route in [
                    *extensions.api.admin_routes,
                    *extensions.api.tenant_routes,
                    *extensions.api.public_routes,
                ]
            )
            and not capabilities
        ):
            pass
        encrypted_fields = []
        if manifest_for_caps.config_schema:
            for key, value in (manifest_for_caps.config_schema.get("properties") or {}).items():
                if isinstance(value, dict) and value.get("x-encrypted"):
                    encrypted_fields.append(key)
        if encrypted_fields:
            print(
                f"  [INFO] x-encrypted fields: {', '.join(encrypted_fields)} "
                "(will be Fernet-encrypted)"
            )
    except Exception:
        pass

    _normalize_debug_env_for_cli(warnings)
    from app.plugins.security_scan import scan_plugin_directory

    scan_result = scan_plugin_directory(plugin_dir)
    if scan_result.has_warnings:
        for warning in scan_result.warnings:
            errors.append(f"Security: {warning}")
    else:
        print(f"  [OK] Security scan clean ({scan_result.files_scanned} files)")

    print(f"\n{'=' * 40}")
    if errors:
        print(f"  [ERROR] {len(errors)} error(s):")
        for error in errors:
            print(f"     - {error}")
    if warnings:
        print(f"  [WARN] {len(warnings)} warning(s):")
        for warning in warnings:
            print(f"     - {warning}")
    if not errors and not warnings:
        print("  [OK] All checks passed!")

    sys.exit(1 if errors else 0)
