"""Disallowed AI runtime request guards."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from typing import Any

from app.core.i18n import _

INVALID_AI_RUNTIME_TOOL_ORDER: tuple[str, ...] = (
    "append_content",
    "editor_ops",
    "fetch_url",
    "get_editor_html",
    "get_editor_text",
    "get_page_context",
    "insert_content",
    "invoke_page_operation",
    "list_page_operations",
    "native_web_search",
    "page_ops",
    "replace_content",
    "replace_section",
    "ui_get_snapshot",
    "ui_read_region",
    "ui_read_table",
    "ui_list_interactables",
    "ui_click",
    "ui_open_surface",
    "ui_get_form_state",
    "ui_set_field",
    "ui_fill_form",
    "ui_submit_form",
    "web_search",
)
INVALID_AI_RUNTIME_TOOL_NAMES = frozenset(INVALID_AI_RUNTIME_TOOL_ORDER)
INVALID_AI_PROVIDER_CONFIG_KEYS = frozenset(
    {
        "hosted_web_search",
        "hosted_web_search_supported",
        "native_web_search_supported",
        "supports_hosted_web_search",
        "web_search",
        "web_search_runtime",
    }
)
INVALID_AI_RUNTIME_REFERENCE_FRAGMENTS = frozenset(
    {
        "web_search_call",
    }
)

DISALLOWED_AI_RUNTIME_INPUT_KEYS = frozenset(
    {
        "append_content",
        "active_surface",
        "current_dom",
        "editor_ops",
        "get_editor_html",
        "get_editor_text",
        "get_page_context",
        "has_page_intent",
        "insert_content",
        "invoke_page_operation",
        "last_page_key",
        "last_page_op",
        "list_page_operations",
        "page_context",
        "page_data",
        "page_intent_kind",
        "page_operation",
        "page_ops",
        "page_runtime",
        "page_session",
        "page_session_id",
        "replace_content",
        "replace_section",
    }
)

DISALLOWED_AI_RUNTIME_INPUT_PREFIXES = ("pageop_", "ui_")
DISALLOWED_AI_RUNTIME_INPUT_VALUES = frozenset(
    {
        "page_awareness",
        "page_awareness_interaction",
        "page_ai",
        "page_operation",
        "page_operations",
        "page_runtime",
        "page_summary",
        "页面感知",
        "页面感知交互",
        "页面操作",
    }
)


def disallowed_ai_runtime_input_keys(
    payload: Mapping[str, Any] | None,
) -> list[str]:
    if not isinstance(payload, Mapping):
        return []
    disallowed_keys: list[str] = []
    _collect_disallowed_ai_runtime_input_keys(payload, "", disallowed_keys)
    return sorted(set(disallowed_keys))


def _collect_disallowed_ai_runtime_input_keys(
    value: Any,
    path: str,
    disallowed_keys: list[str],
) -> None:
    if isinstance(value, Mapping):
        for key, nested in value.items():
            text = str(key or "").strip()
            next_path = f"{path}.{text}" if path and text else text or path
            if _is_disallowed_ai_runtime_key(text):
                disallowed_keys.append(next_path or text)
            _collect_disallowed_ai_runtime_input_keys(
                nested,
                next_path,
                disallowed_keys,
            )
        return

    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        for index, nested in enumerate(value):
            next_path = f"{path}[{index}]" if path else f"[{index}]"
            _collect_disallowed_ai_runtime_input_keys(
                nested,
                next_path,
                disallowed_keys,
            )
        return

    if _is_disallowed_ai_runtime_value(value):
        disallowed_keys.append(path or str(value or "").strip())


def _is_disallowed_ai_runtime_key(key: str) -> bool:
    text = str(key or "").strip()
    if not text:
        return False
    normalized = normalize_ai_runtime_token(text)
    return normalized in DISALLOWED_AI_RUNTIME_INPUT_KEYS or normalized.startswith(
        DISALLOWED_AI_RUNTIME_INPUT_PREFIXES
    )


def _is_disallowed_ai_runtime_value(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    text = value.strip()
    normalized = normalize_ai_runtime_token(text)
    return bool(
        text
        and (
            normalized in DISALLOWED_AI_RUNTIME_INPUT_VALUES
            or is_invalid_ai_runtime_tool_name(text)
            or is_invalid_ai_runtime_tool_family(text)
        )
    )


def normalize_ai_runtime_token(value: Any) -> str:
    return (
        str(value or "")
        .strip()
        .lower()
        .replace("-", "_")
        .replace(" ", "_")
        .replace(".", "_")
        .replace(":", "_")
    )


def is_invalid_ai_runtime_tool_family(value: Any) -> bool:
    return normalize_ai_runtime_token(value) in {"page_ops", "web_research"}


def is_invalid_ai_runtime_tool_name(name: Any) -> bool:
    normalized = normalize_ai_runtime_token(name)
    return (
        normalized.startswith("ui_")
        or normalized.startswith("pageop_")
        or normalized in INVALID_AI_RUNTIME_TOOL_NAMES
    )


def is_invalid_ai_runtime_reference(value: Any) -> bool:
    normalized = normalize_ai_runtime_token(value)
    return bool(
        normalized
        and (
            normalized in DISALLOWED_AI_RUNTIME_INPUT_KEYS
            or normalized in DISALLOWED_AI_RUNTIME_INPUT_VALUES
            or any(
                fragment in normalized
                for fragment in INVALID_AI_RUNTIME_REFERENCE_FRAGMENTS
            )
            or is_invalid_ai_runtime_tool_name(value)
            or is_invalid_ai_runtime_tool_family(value)
        )
    )


def is_invalid_ai_runtime_tool(tool: Any) -> bool:
    if is_invalid_ai_runtime_tool_name(getattr(tool, "name", "")):
        return True
    return is_invalid_ai_runtime_tool_family(getattr(tool, "semantic_family", ""))


def filter_invalid_ai_runtime_tools(tools: Iterable[Any] | None) -> list[Any]:
    return [tool for tool in list(tools or []) if not is_invalid_ai_runtime_tool(tool)]


def filter_invalid_ai_runtime_references(values: Iterable[Any] | None) -> list[str]:
    filtered: list[str] = []
    for value in list(values or []):
        text = str(value or "").strip()
        if not text or is_invalid_ai_runtime_reference(text):
            continue
        if text not in filtered:
            filtered.append(text)
    return filtered


def strip_invalid_ai_provider_config_keys(
    config: Mapping[str, Any] | None,
) -> dict[str, Any]:
    if not isinstance(config, Mapping):
        return {}
    return {
        str(key): value
        for key, value in dict(config).items()
        if normalize_ai_runtime_token(key) not in INVALID_AI_PROVIDER_CONFIG_KEYS
    }


def ensure_no_disallowed_ai_runtime_input(
    payload: Mapping[str, Any] | None,
) -> None:
    disallowed_keys = disallowed_ai_runtime_input_keys(payload)
    if disallowed_keys:
        raise ValueError(
            _(
                "agent_chat.error.invalid_ai_runtime_input_fields",
                fields=", ".join(disallowed_keys),
            )
        )


def assert_no_disallowed_ai_runtime_input(
    payload: Mapping[str, Any] | None,
) -> dict[str, Any]:
    ensure_no_disallowed_ai_runtime_input(payload)
    return dict(payload or {})


__all__ = [
    "DISALLOWED_AI_RUNTIME_INPUT_KEYS",
    "DISALLOWED_AI_RUNTIME_INPUT_PREFIXES",
    "DISALLOWED_AI_RUNTIME_INPUT_VALUES",
    "INVALID_AI_PROVIDER_CONFIG_KEYS",
    "INVALID_AI_RUNTIME_REFERENCE_FRAGMENTS",
    "INVALID_AI_RUNTIME_TOOL_NAMES",
    "INVALID_AI_RUNTIME_TOOL_ORDER",
    "assert_no_disallowed_ai_runtime_input",
    "ensure_no_disallowed_ai_runtime_input",
    "disallowed_ai_runtime_input_keys",
    "filter_invalid_ai_runtime_references",
    "filter_invalid_ai_runtime_tools",
    "is_invalid_ai_runtime_reference",
    "is_invalid_ai_runtime_tool",
    "is_invalid_ai_runtime_tool_family",
    "is_invalid_ai_runtime_tool_name",
    "normalize_ai_runtime_token",
    "strip_invalid_ai_provider_config_keys",
]
