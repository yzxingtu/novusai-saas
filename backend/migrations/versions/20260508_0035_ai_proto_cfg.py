"""中文: 规范化 AI 供应商协议配置。

EN: Canonicalize AI provider protocol configuration.

Revision ID: 20260508_0035_ai_proto_cfg
Revises: 20260508_0034_task_contract
Create Date: 2026-05-08

"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from copy import deepcopy
from typing import Any

import sqlalchemy as sa
from alembic import op

revision: str = "20260508_0035_ai_proto_cfg"
down_revision: str | Sequence[str] | None = "20260508_0034_task_contract"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_VALID_WIRE_APIS = ("responses", "chat_completions")
_PROVIDER_PROTOCOL_WIRE_API_KEY = "wire_api"
_PROVIDER_PROTOCOL_CAPABILITIES_KEY = "protocol_capabilities"
_RETIRED_PROVIDER_PROTOCOL_KEYS = frozenset(
    {
        "wire_api",
        "allow_adapter_cross_protocol_fallback",
        "allowed_cross_protocol_fallbacks",
    }
)
_RETIRED_PROVIDER_CONFIG_KEYS = frozenset(
    {
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
_RETIRED_ONLINE_SEARCH_CATALOG_TOKENS = frozenset(
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
_RETIRED_ONLINE_SEARCH_CATALOG_PHRASES = (
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
_AI_RUNTIME_TOKEN_SEPARATORS = re.compile(r"[\s.\-:/\\]+")
_OMIT_PROVIDER_CONFIG_VALUE = object()


def _has_table(bind: sa.Connection, table_name: str) -> bool:
    return sa.inspect(bind).has_table(table_name)


def _columns(bind: sa.Connection, table_name: str) -> set[str]:
    if not _has_table(bind, table_name):
        return set()
    return {column["name"] for column in sa.inspect(bind).get_columns(table_name)}


def _ai_providers_table(columns: set[str]) -> sa.TableClause:
    typed_columns = {
        "id": sa.Integer(),
        "config": sa.JSON(),
    }
    return sa.table(
        "ai_providers",
        *(
            sa.column(column_name, typed_columns.get(column_name))
            for column_name in columns
        ),
    )


def _now_value(columns: set[str]) -> dict[str, Any]:
    if "updated_at" not in columns:
        return {}
    return {"updated_at": sa.func.now()}


def _normalize_ai_runtime_token(value: Any) -> str:
    text = str(value or "").strip().lower()
    return _AI_RUNTIME_TOKEN_SEPARATORS.sub("_", text).strip("_")


def _normalize_wire_api(value: Any) -> str | None:
    normalized = str(value or "").strip().lower()
    return normalized if normalized in _VALID_WIRE_APIS else None


def _pop_normalized_key(payload: dict[str, Any], normalized_key: str) -> Any:
    values: list[Any] = []
    for key in list(payload.keys()):
        if _normalize_ai_runtime_token(key) == normalized_key:
            values.append(payload.pop(key))
    for value in values:
        if _normalize_wire_api(value) is not None:
            return value
    return values[0] if values else None


def _contains_retired_online_search_token(normalized: str) -> bool:
    for token in _RETIRED_ONLINE_SEARCH_CATALOG_TOKENS:
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


def _is_retired_online_search_reference(value: Any) -> bool:
    text = str(value or "").strip()
    if not text:
        return False
    normalized = _normalize_ai_runtime_token(text)
    lowered = text.lower()
    normalized_phrase_text = normalized.replace("_", " ")
    return (
        normalized in _RETIRED_ONLINE_SEARCH_CATALOG_TOKENS
        or _contains_retired_online_search_token(normalized)
        or any(
            _contains_retired_online_search_phrase(lowered, phrase)
            for phrase in _RETIRED_ONLINE_SEARCH_CATALOG_PHRASES
        )
        or any(
            _contains_retired_online_search_phrase(normalized_phrase_text, phrase)
            for phrase in _RETIRED_ONLINE_SEARCH_CATALOG_PHRASES
            if phrase.isascii()
        )
    )


def _is_retired_provider_config_key(key: Any) -> bool:
    normalized = _normalize_ai_runtime_token(key)
    return (
        normalized in _RETIRED_PROVIDER_CONFIG_KEYS
        or normalized in _RETIRED_PROVIDER_PROTOCOL_KEYS
        or _is_retired_online_search_reference(key)
    )


def _strip_retired_provider_config_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        cleaned: dict[str, Any] = {}
        for key, nested in value.items():
            if _is_retired_provider_config_key(key):
                continue
            sanitized_nested = _strip_retired_provider_config_value(nested)
            if sanitized_nested is _OMIT_PROVIDER_CONFIG_VALUE:
                continue
            cleaned[str(key)] = sanitized_nested
        if not cleaned and value:
            return _OMIT_PROVIDER_CONFIG_VALUE
        return cleaned

    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        cleaned_items: list[Any] = []
        for nested in value:
            sanitized_nested = _strip_retired_provider_config_value(nested)
            if sanitized_nested is _OMIT_PROVIDER_CONFIG_VALUE:
                continue
            cleaned_items.append(sanitized_nested)
        return cleaned_items

    if _is_retired_online_search_reference(value):
        return _OMIT_PROVIDER_CONFIG_VALUE
    return value


def _normalize_allowed_wire_apis(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    allowed_wire_apis: list[str] = []
    for item in value:
        wire_api = _normalize_wire_api(item)
        if wire_api is not None and wire_api not in allowed_wire_apis:
            allowed_wire_apis.append(wire_api)
    return allowed_wire_apis


def _canonicalize_protocol_capabilities(config: dict[str, Any]) -> None:
    top_level_wire_api = _pop_normalized_key(
        config,
        _PROVIDER_PROTOCOL_WIRE_API_KEY,
    )
    for retired_key in _RETIRED_PROVIDER_PROTOCOL_KEYS.difference({"wire_api"}):
        _pop_normalized_key(config, retired_key)

    raw_protocol = config.get(_PROVIDER_PROTOCOL_CAPABILITIES_KEY)
    protocol = deepcopy(raw_protocol) if isinstance(raw_protocol, Mapping) else {}
    if _PROVIDER_PROTOCOL_CAPABILITIES_KEY in config:
        config.pop(_PROVIDER_PROTOCOL_CAPABILITIES_KEY)

    nested_wire_api = _pop_normalized_key(protocol, _PROVIDER_PROTOCOL_WIRE_API_KEY)
    for retired_key in _RETIRED_PROVIDER_PROTOCOL_KEYS.difference({"wire_api"}):
        _pop_normalized_key(protocol, retired_key)

    primary_wire_api = _normalize_wire_api(protocol.get("primary_wire_api"))
    if primary_wire_api is None:
        primary_wire_api = _normalize_wire_api(top_level_wire_api)
    if primary_wire_api is None:
        primary_wire_api = _normalize_wire_api(nested_wire_api)

    allowed_wire_apis = _normalize_allowed_wire_apis(protocol.get("allowed_wire_apis"))
    if primary_wire_api is None and allowed_wire_apis:
        primary_wire_api = allowed_wire_apis[0]

    protocol.pop("primary_wire_api", None)
    protocol.pop("allowed_wire_apis", None)

    if primary_wire_api is not None:
        protocol["primary_wire_api"] = primary_wire_api
        ordered_allowed = [
            primary_wire_api,
            *(item for item in allowed_wire_apis if item != primary_wire_api),
        ]
        protocol["allowed_wire_apis"] = ordered_allowed
    elif allowed_wire_apis:
        protocol["primary_wire_api"] = allowed_wire_apis[0]
        protocol["allowed_wire_apis"] = allowed_wire_apis

    if protocol:
        config[_PROVIDER_PROTOCOL_CAPABILITIES_KEY] = protocol


def _canonicalize_provider_config(config: Any) -> dict[str, Any] | None:
    if not isinstance(config, Mapping):
        return None

    canonical = deepcopy(dict(config))
    _canonicalize_protocol_capabilities(canonical)
    canonical = _strip_retired_provider_config_value(canonical)
    if canonical is _OMIT_PROVIDER_CONFIG_VALUE or not isinstance(canonical, dict):
        return None
    return canonical or None


def _canonicalize_ai_provider_config_rows(bind: sa.Connection) -> None:
    columns = _columns(bind, "ai_providers")
    required = {"id", "config"}
    if not required.issubset(columns):
        return

    ai_providers = _ai_providers_table(columns)
    rows = (
        bind.execute(sa.select(ai_providers.c.id, ai_providers.c.config))
        .mappings()
        .all()
    )
    for row in rows:
        current_config = row["config"]
        canonical_config = _canonicalize_provider_config(current_config)
        if canonical_config == current_config:
            continue
        bind.execute(
            sa.update(ai_providers)
            .where(ai_providers.c.id == int(row["id"]))
            .values(config=canonical_config, **_now_value(columns))
        )


def upgrade() -> None:
    bind = op.get_bind()
    _canonicalize_ai_provider_config_rows(bind)


def downgrade() -> None:
    pass
