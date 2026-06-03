"""Guards for retired AI skill catalog/runtime write paths."""

from __future__ import annotations

import ast
from collections.abc import Mapping, Sequence
from typing import Any

from app.core.i18n import _
from app.exceptions import BusinessException
from app.schemas.ai.invalid_ai_runtime_input import (
    is_retired_online_search_catalog_reference,
)

_TOOL_NAME_KEYS = frozenset(
    {
        "builtin_type",
        "function_name",
        "method",
        "name",
        "semantic_family",
        "source_plugin",
        "source_ref",
        "tool",
        "tool_name",
    }
)
_TOOL_COLLECTION_KEYS = frozenset(
    {
        "allowed_tool_names",
        "inventory_selected_tool_names",
        "preview_semantic_families",
        "preview_tool_names",
        "resolved_tool_names",
        "selected_tool_names",
        "tool_names",
        "tools",
    }
)


def _get_value(source: Any, field_name: str) -> Any:
    if isinstance(source, Mapping):
        return source.get(field_name)
    return getattr(source, field_name, None)


def _iter_text_values(value: Any) -> list[Any]:
    if isinstance(value, Mapping):
        values: list[Any] = []
        for nested in value.values():
            values.extend(_iter_text_values(nested))
        return values
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        values: list[Any] = []
        for nested in value:
            values.extend(_iter_text_values(nested))
        return values
    return [value]


def _iter_tool_name_candidates(value: Any) -> list[Any]:
    if isinstance(value, Mapping):
        candidates: list[Any] = []
        for key, nested in value.items():
            key_text = str(key or "").strip()
            normalized_key = key_text.lower()
            if normalized_key in _TOOL_NAME_KEYS:
                candidates.extend(_iter_text_values(nested))
                continue
            if normalized_key in _TOOL_COLLECTION_KEYS:
                candidates.extend(_iter_tool_name_candidates(nested))
                continue
            if isinstance(nested, Mapping | list | tuple | set):
                candidates.extend(_iter_tool_name_candidates(nested))
        return candidates
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        candidates: list[Any] = []
        for nested in value:
            candidates.extend(_iter_tool_name_candidates(nested))
        return candidates
    return []


def _toolkit_public_method_names(source: Any) -> list[str]:
    text = str(source or "").strip()
    if not text:
        return []
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return []

    names: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef) or node.name != "Tools":
            continue
        for child in node.body:
            if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef):
                method_name = str(child.name or "").strip()
                if method_name and not method_name.startswith("_"):
                    names.append(method_name)
    return names


def _raise_if_retired_reference(values: list[Any], *, message_key: str) -> None:
    if any(is_retired_online_search_catalog_reference(value) for value in values):
        raise BusinessException(message=_(message_key))


def ensure_not_retired_online_search_package(data: Any) -> None:
    """Reject retired online-search package identities at write/sync boundaries."""
    values = [
        _get_value(data, "name"),
        _get_value(data, "source_plugin"),
    ]
    _raise_if_retired_reference(
        values,
        message_key="skill_package.error.retired_online_search",
    )


def ensure_not_retired_online_search_skill(data: Any) -> None:
    """Reject retired online-search skills and executable tool metadata."""
    values = [
        _get_value(data, "name"),
        _get_value(data, "key"),
        _get_value(data, "source_ref"),
    ]
    values.extend(_iter_tool_name_candidates(_get_value(data, "config")))
    values.extend(_iter_tool_name_candidates(_get_value(data, "toolkit_meta")))
    values.extend(_toolkit_public_method_names(_get_value(data, "toolkit_content")))
    values.extend(_iter_tool_name_candidates(_get_value(data, "input_schema")))
    values.extend(_iter_tool_name_candidates(_get_value(data, "output_schema")))
    _raise_if_retired_reference(
        values,
        message_key="skill.error.retired_online_search",
    )


def ensure_not_retired_online_search_plugin_skill(
    *,
    plugin_name: str,
    skill_extension: Any,
    skill_display_name: str,
    skill_key: str,
    source_ref: str,
) -> None:
    """Reject plugin lifecycle sync for retired online-search skill declarations."""
    values: list[Any] = [
        plugin_name,
        _get_value(skill_extension, "name"),
        skill_display_name,
        skill_key,
        source_ref,
        _get_value(skill_extension, "entry_point"),
        _get_value(skill_extension, "executor_entry_point"),
    ]
    values.extend(_iter_text_values(_get_value(skill_extension, "display_name")))
    values.extend(_iter_text_values(_get_value(skill_extension, "description")))
    values.extend(_iter_text_values(_get_value(skill_extension, "preview_tool_names")))
    values.extend(
        _iter_text_values(_get_value(skill_extension, "preview_semantic_families"))
    )
    values.extend(
        _iter_tool_name_candidates(_get_value(skill_extension, "config_schema"))
    )
    _raise_if_retired_reference(
        values,
        message_key="skill.error.retired_online_search",
    )


__all__ = [
    "ensure_not_retired_online_search_package",
    "ensure_not_retired_online_search_plugin_skill",
    "ensure_not_retired_online_search_skill",
]
