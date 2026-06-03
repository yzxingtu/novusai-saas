"""Disallowed AI runtime request guards."""

from __future__ import annotations

import re
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
RETIRED_AI_PROVIDER_PROTOCOL_KEYS = frozenset(
    {
        "allow_adapter_cross_protocol_fallback",
        "allowed_cross_protocol_fallbacks",
        "wire_api",
    }
)
INVALID_AI_PROVIDER_CONFIG_KEYS = frozenset(
    {
        *RETIRED_AI_PROVIDER_PROTOCOL_KEYS,
        "fetch_url",
        "hosted_web_search",
        "hosted_web_search_supported",
        "native_web_search",
        "native_web_search_supported",
        "online_search",
        "search_provider",
        "searchprovider",
        "supports_hosted_web_search",
        "web_search_preview",
        "web_research",
        "web_search",
        "web_search_options",
        "web_search_runtime",
    }
)
RETIRED_ONLINE_SEARCH_CATALOG_TOKENS = frozenset(
    {
        "baidu_public_search",
        "baidu_search",
        "fetch_url",
        "hosted_web_search",
        "hosted_web_search_supported",
        "internet_search",
        "native_web_search",
        "native_web_search_supported",
        "online_search",
        "public_search",
        "response_web_search_call",
        "search_provider",
        "searchprovider",
        "supports_hosted_web_search",
        "web_search_preview",
        "web_research",
        "web_search",
        "web_search_call",
        "web_search_options",
        "web_search_runtime",
        "webresearch",
        "websearch",
    }
)
RETIRED_ONLINE_SEARCH_CATALOG_PHRASES = (
    "fetch url",
    "baidu public search",
    "baidu search",
    "hosted search",
    "public search",
    "internet search",
    "online search",
    "search online",
    "search provider",
    "native search",
    "web research",
    "web search",
    "websearch",
    "在线搜索",
    "网络搜索",
    "网页搜索",
    "联网搜索",
    "公开搜索",
    "百度公开搜索",
    "原生搜索",
    "上网查询",
    "上网搜索",
)
INVALID_AI_RUNTIME_REFERENCE_FRAGMENTS = frozenset(
    {
        "web_search_call",
    }
)
_AI_RUNTIME_TOKEN_SEPARATORS = re.compile(r"[\s.\-:/\\]+")
_OMIT_PROVIDER_CONFIG_VALUE = object()

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


def retired_ai_provider_protocol_field_paths(
    value: Any,
    *,
    path: str = "",
) -> list[str]:
    if isinstance(value, Mapping):
        retired_paths: list[str] = []
        for key, nested in value.items():
            text = str(key or "").strip()
            next_path = f"{path}.{text}" if path and text else text or path
            if normalize_ai_runtime_token(text) in RETIRED_AI_PROVIDER_PROTOCOL_KEYS:
                retired_paths.append(next_path or text)
            retired_paths.extend(
                retired_ai_provider_protocol_field_paths(
                    nested,
                    path=next_path,
                )
            )
        return retired_paths

    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        retired_paths = []
        for index, nested in enumerate(value):
            next_path = f"{path}[{index}]" if path else f"[{index}]"
            retired_paths.extend(
                retired_ai_provider_protocol_field_paths(
                    nested,
                    path=next_path,
                )
            )
        return retired_paths

    return []


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
    return (
        normalized in DISALLOWED_AI_RUNTIME_INPUT_KEYS
        or normalized in INVALID_AI_PROVIDER_CONFIG_KEYS
        or normalized.startswith(DISALLOWED_AI_RUNTIME_INPUT_PREFIXES)
        or is_invalid_ai_runtime_tool_name(text)
        or is_invalid_ai_runtime_tool_family(text)
        or is_retired_online_search_catalog_reference(text)
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
    text = str(value or "").strip().lower()
    return _AI_RUNTIME_TOKEN_SEPARATORS.sub("_", text).strip("_")


def is_invalid_ai_runtime_tool_family(value: Any) -> bool:
    return normalize_ai_runtime_token(value) in {"page_ops", "web_research"}


def is_invalid_ai_runtime_tool_name(name: Any) -> bool:
    normalized = normalize_ai_runtime_token(name)
    return (
        normalized.startswith("ui_")
        or normalized.startswith("pageop_")
        or normalized in INVALID_AI_RUNTIME_TOOL_NAMES
        or is_retired_online_search_catalog_reference(name)
    )


def is_invalid_ai_runtime_reference(value: Any) -> bool:
    normalized = normalize_ai_runtime_token(value)
    return bool(
        normalized
        and (
            normalized in DISALLOWED_AI_RUNTIME_INPUT_KEYS
            or normalized in DISALLOWED_AI_RUNTIME_INPUT_VALUES
            or is_retired_online_search_catalog_reference(value)
            or any(
                fragment in normalized
                for fragment in INVALID_AI_RUNTIME_REFERENCE_FRAGMENTS
            )
            or is_invalid_ai_runtime_tool_name(value)
            or is_invalid_ai_runtime_tool_family(value)
        )
    )


def is_retired_online_search_catalog_reference(value: Any) -> bool:
    text = str(value or "").strip()
    if not text:
        return False
    normalized = normalize_ai_runtime_token(text)
    lowered = text.lower()
    normalized_phrase_text = normalized.replace("_", " ")
    return (
        normalized in RETIRED_ONLINE_SEARCH_CATALOG_TOKENS
        or _contains_retired_online_search_token(normalized)
        or any(
            _contains_retired_online_search_phrase(lowered, phrase)
            for phrase in RETIRED_ONLINE_SEARCH_CATALOG_PHRASES
        )
        or any(
            _contains_retired_online_search_phrase(normalized_phrase_text, phrase)
            for phrase in RETIRED_ONLINE_SEARCH_CATALOG_PHRASES
            if phrase.isascii()
        )
    )


def _contains_retired_online_search_token(normalized: str) -> bool:
    for token in RETIRED_ONLINE_SEARCH_CATALOG_TOKENS:
        start = normalized.find(token)
        while start >= 0:
            end = start + len(token)
            before_boundary = start == 0 or normalized[start - 1] == "_"
            after_boundary = end == len(normalized) or normalized[end] == "_"
            if before_boundary and after_boundary:
                return True
            start = normalized.find(token, start + 1)
    return False


def _contains_retired_online_search_phrase(text: str, phrase: str) -> bool:
    if not phrase.isascii():
        return phrase in text
    start = text.find(phrase)
    while start >= 0:
        end = start + len(phrase)
        before_boundary = start == 0 or not text[start - 1].isalnum()
        after_boundary = end == len(text) or not text[end].isalnum()
        if before_boundary and after_boundary:
            return True
        start = text.find(phrase, start + 1)
    return False


def is_invalid_ai_runtime_tool(tool: Any) -> bool:
    if is_invalid_ai_runtime_tool_name(getattr(tool, "name", "")):
        return True
    if is_invalid_ai_runtime_tool_family(getattr(tool, "semantic_family", "")):
        return True
    identity_values = (
        getattr(tool, "tool_type", None),
        getattr(tool, "source_skill_name", None),
        getattr(tool, "source_package_name", None),
        getattr(tool, "source_plugin", None),
        getattr(tool, "semantic_family", None),
        *(getattr(tool, "semantic_tags", None) or []),
    )
    if any(is_invalid_ai_runtime_reference(value) for value in identity_values):
        return True
    config = getattr(tool, "config", None)
    if isinstance(config, Mapping):
        for key in (
            "plugin_skill_name",
            "skill_name",
            "source_skill_name",
            "package_name",
            "source_package_name",
            "source_plugin",
            "source_ref",
        ):
            if is_invalid_ai_runtime_reference(config.get(key)):
                return True
    return False


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
    sanitized = _strip_invalid_ai_provider_config_value(config)
    return sanitized if isinstance(sanitized, dict) else {}


def _strip_invalid_ai_provider_config_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        cleaned: dict[str, Any] = {}
        for key, nested in value.items():
            if _is_invalid_ai_provider_config_key(key):
                continue
            sanitized_nested = _strip_invalid_ai_provider_config_value(nested)
            if sanitized_nested is _OMIT_PROVIDER_CONFIG_VALUE:
                continue
            cleaned[str(key)] = sanitized_nested
        if not cleaned and value:
            return _OMIT_PROVIDER_CONFIG_VALUE
        return cleaned

    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        cleaned_items: list[Any] = []
        for nested in value:
            sanitized_nested = _strip_invalid_ai_provider_config_value(nested)
            if sanitized_nested is _OMIT_PROVIDER_CONFIG_VALUE:
                continue
            cleaned_items.append(sanitized_nested)
        return cleaned_items

    if is_invalid_ai_runtime_reference(value):
        return _OMIT_PROVIDER_CONFIG_VALUE
    return value


def _is_invalid_ai_provider_config_key(key: Any) -> bool:
    normalized = normalize_ai_runtime_token(key)
    return (
        normalized in INVALID_AI_PROVIDER_CONFIG_KEYS
        or is_invalid_ai_runtime_reference(key)
    )


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
    "RETIRED_AI_PROVIDER_PROTOCOL_KEYS",
    "RETIRED_ONLINE_SEARCH_CATALOG_PHRASES",
    "RETIRED_ONLINE_SEARCH_CATALOG_TOKENS",
    "assert_no_disallowed_ai_runtime_input",
    "ensure_no_disallowed_ai_runtime_input",
    "disallowed_ai_runtime_input_keys",
    "filter_invalid_ai_runtime_references",
    "filter_invalid_ai_runtime_tools",
    "is_invalid_ai_runtime_reference",
    "is_invalid_ai_runtime_tool",
    "is_invalid_ai_runtime_tool_family",
    "is_invalid_ai_runtime_tool_name",
    "is_retired_online_search_catalog_reference",
    "normalize_ai_runtime_token",
    "retired_ai_provider_protocol_field_paths",
    "strip_invalid_ai_provider_config_keys",
]
