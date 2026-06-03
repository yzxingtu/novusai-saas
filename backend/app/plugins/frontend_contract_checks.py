"""Shared plugin frontend contract checks. / 共享插件前端契约校验。"""

from __future__ import annotations

import re
from typing import Any

from app.core.i18n import _

_REGISTER_LOCALE_CALL_PATTERN = re.compile(
    r"registerLocale\(\s*['\"][^'\"]+['\"]\s*,\s*(?P<prefix>['\"][^'\"]+['\"]|[A-Za-z_][A-Za-z0-9_]*)",
)
_LOCALE_PREFIX_CONST_PATTERN = re.compile(
    r"\bconst\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*['\"](?P<value>[^'\"]+)['\"]",
)


def canonical_manifest_locale(locale: str) -> str:
    normalized = (locale or "").strip().replace("_", "-")
    lowered = normalized.lower()
    if lowered.startswith("zh"):
        return "zh-CN"
    if lowered.startswith("en"):
        return "en"
    return normalized


def collect_manifest_locales(*values: object) -> list[str]:
    locales: list[str] = []
    for value in values:
        if not isinstance(value, dict):
            continue
        for locale, text in value.items():
            if not isinstance(text, str) or not text.strip():
                continue
            canonical = canonical_manifest_locale(locale)
            if canonical and canonical not in locales:
                locales.append(canonical)
    return locales or ["zh-CN", "en"]


def missing_manifest_locales(value: object, expected_locales: list[str]) -> list[str]:
    if not expected_locales:
        return []
    if not isinstance(value, dict):
        return expected_locales.copy()

    present = {
        canonical_manifest_locale(locale)
        for locale, text in value.items()
        if isinstance(text, str) and text.strip()
    }
    return [locale for locale in expected_locales if locale not in present]


def collect_missing_i18n_locales(
    value: object,
    *,
    required_locales: tuple[str, ...] = ("zh-CN", "en"),
) -> list[str]:
    if not isinstance(value, dict):
        return []
    return [
        locale
        for locale in required_locales
        if not isinstance(value.get(locale), str) or not value.get(locale, "").strip()
    ]


def collect_frontend_i18n_contract_errors(
    manifest_or_data: Any,
) -> tuple[list[str], list[str]]:
    expected_locales = collect_manifest_locales(
        _manifest_value(manifest_or_data, "display_name"),
        _manifest_value(manifest_or_data, "description"),
    )
    errors: list[str] = []

    for index, page in enumerate(_frontend_pages(manifest_or_data)):
        missing_page_locales = missing_manifest_locales(
            _page_value(page, "title"),
            expected_locales,
        )
        if missing_page_locales:
            errors.append(
                "frontend.pages[{index}].title missing locale(s): {locales}".format(
                    index=index,
                    locales=", ".join(missing_page_locales),
                )
            )

        menu = _page_menu(page)
        if menu is None:
            continue
        missing_menu_locales = missing_manifest_locales(
            _menu_value(menu, "title"),
            expected_locales,
        )
        if missing_menu_locales:
            errors.append(
                "frontend.pages[{index}].menu.title missing locale(s): {locales}".format(
                    index=index,
                    locales=", ".join(missing_menu_locales),
                )
            )

    return errors, expected_locales


def collect_frontend_i18n_warnings(manifest_or_data: Any) -> list[str]:
    warnings: list[str] = []
    expected_locales = collect_manifest_locales(
        _manifest_value(manifest_or_data, "display_name"),
        _manifest_value(manifest_or_data, "description"),
    )

    for index, page in enumerate(_frontend_pages(manifest_or_data)):
        missing_page_locales = missing_manifest_locales(
            _page_value(page, "title"),
            expected_locales,
        )
        if missing_page_locales:
            warnings.append(
                _(
                    "plugin.preview.warning.frontend_page_title_i18n_incomplete",
                    index=index,
                    locales=", ".join(missing_page_locales),
                )
            )

        menu = _page_menu(page)
        if menu is None:
            continue
        missing_menu_locales = missing_manifest_locales(
            _menu_value(menu, "title"),
            expected_locales,
        )
        if missing_menu_locales:
            warnings.append(
                _(
                    "plugin.preview.warning.frontend_menu_title_i18n_incomplete",
                    index=index,
                    locales=", ".join(missing_menu_locales),
                )
            )

    return warnings


def extract_frontend_locale_prefixes(entry_content: str) -> list[str]:
    prefixes: list[str] = []
    prefix_constants = {
        match.group("name"): match.group("value")
        for match in _LOCALE_PREFIX_CONST_PATTERN.finditer(entry_content or "")
    }

    for match in _REGISTER_LOCALE_CALL_PATTERN.finditer(entry_content or ""):
        raw_prefix = (match.group("prefix") or "").strip()
        if not raw_prefix:
            continue
        if raw_prefix.startswith(("'", '"')) and raw_prefix.endswith(("'", '"')):
            value = raw_prefix[1:-1]
        else:
            value = prefix_constants.get(raw_prefix, "")
        value = value.strip()
        if value and value not in prefixes:
            prefixes.append(value)

    for name, value in prefix_constants.items():
        normalized_name = name.lower()
        normalized_value = value.strip()
        if "prefix" not in normalized_name:
            continue
        if not normalized_value.startswith(("plugin.", "admin.", "tenant.")):
            continue
        if normalized_value not in prefixes:
            prefixes.append(normalized_value)

    return prefixes


def collect_frontend_locale_prefix_contract_issues(
    plugin_name: str,
    entry_content: str,
) -> tuple[list[str], list[str]]:
    canonical_root = f"plugin.{plugin_name}"
    prefixes = extract_frontend_locale_prefixes(entry_content)
    if not prefixes:
        return [], []

    errors: list[str] = []
    warnings: list[str] = []
    canonical_prefixes = [
        prefix
        for prefix in prefixes
        if prefix == canonical_root or prefix.startswith(f"{canonical_root}.")
    ]
    compatibility_aliases = [
        prefix for prefix in prefixes if prefix not in canonical_prefixes
    ]

    if not canonical_prefixes:
        errors.append(
            "frontend registerLocale() should use canonical prefix "
            f"'{canonical_root}' or its child namespaces; found: " + ", ".join(prefixes)
        )

    for prefix in compatibility_aliases:
        warnings.append(
            "frontend locale alias prefix detected: "
            f"{prefix} (canonical: {canonical_root})"
        )

    return errors, warnings


def collect_declared_frontend_component_names(frontend: object) -> list[str]:
    names: list[str] = []

    def _visit(node: object) -> None:
        if isinstance(node, dict):
            component = node.get("component")
            if isinstance(component, str):
                normalized = component.strip()
                if normalized and normalized not in names:
                    names.append(normalized)
            for key, child in node.items():
                if key in {"dev", "release"}:
                    continue
                _visit(child)
            return

        if isinstance(node, list):
            for child in node:
                _visit(child)

    _visit(frontend)
    return names


def entry_source_exports_symbol(entry_source: str, symbol: str) -> bool:
    escaped = re.escape(symbol)
    patterns = (
        rf"\bexport\s+const\s+{escaped}\b",
        rf"\bexport\s+(?:async\s+)?function\s+{escaped}\b",
        rf"\bexport\s+class\s+{escaped}\b",
        rf"\bexport\s*\{{[^}}]*\b{escaped}\b[^}}]*\}}",
    )
    return any(re.search(pattern, entry_source, flags=re.S) for pattern in patterns)


def collect_frontend_component_export_contract_errors(
    frontend: dict,
    entry_source: str,
) -> list[str]:
    errors: list[str] = []
    for component_name in collect_declared_frontend_component_names(frontend):
        if entry_source_exports_symbol(entry_source, component_name):
            continue
        errors.append(
            f"frontend dev entry does not export declared component '{component_name}'"
        )
    return errors


def _manifest_value(manifest_or_data: Any, field_name: str) -> object:
    if hasattr(manifest_or_data, field_name):
        return getattr(manifest_or_data, field_name)
    if isinstance(manifest_or_data, dict):
        return manifest_or_data.get(field_name)
    return None


def _frontend_pages(manifest_or_data: Any) -> list[Any]:
    if hasattr(manifest_or_data, "extensions"):
        frontend = getattr(manifest_or_data.extensions, "frontend", None)
        if frontend is not None:
            return list(getattr(frontend, "pages", None) or [])

    if isinstance(manifest_or_data, dict):
        extensions = manifest_or_data.get("extensions") or {}
        if isinstance(extensions, dict):
            frontend = extensions.get("frontend") or {}
            if isinstance(frontend, dict):
                pages = frontend.get("pages") or []
                if isinstance(pages, list):
                    return pages

    return []


def _page_value(page: Any, field_name: str) -> object:
    if hasattr(page, field_name):
        return getattr(page, field_name)
    if isinstance(page, dict):
        return page.get(field_name)
    return None


def _page_menu(page: Any) -> Any | None:
    menu = _page_value(page, "menu")
    if menu is None:
        return None
    if hasattr(menu, "title") or isinstance(menu, dict):
        return menu
    return None


def _menu_value(menu: Any, field_name: str) -> object:
    if hasattr(menu, field_name):
        return getattr(menu, field_name)
    if isinstance(menu, dict):
        return menu.get(field_name)
    return None
