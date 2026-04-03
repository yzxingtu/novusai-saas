"""
Runtime-v2 feature flags / runtime-v2 特性开关
"""

from __future__ import annotations

import hashlib
import os
import time
from collections import deque
from threading import Lock
from typing import Any, Literal

RuntimeMode = Literal["legacy", "shadow", "pageaware_only", "active"]
_SHADOW_RATE_LIMIT_WINDOW_SEC = 60.0
_shadow_rate_limit_lock = Lock()
_shadow_rate_limit_timestamps: deque[float] = deque()


def get_runtime_mode() -> RuntimeMode:
    raw = str(os.getenv("CLAUDE_CODE_STYLE_RUNTIME", "legacy")).strip().lower()
    if raw in {"shadow", "pageaware_only", "active"}:
        return raw  # type: ignore[return-value]
    return "legacy"


def has_pageaware_tools(tools: list[Any] | None) -> bool:
    if not tools:
        return False
    for tool in tools:
        tool_name = str(getattr(tool, "name", "") or "").strip()
        if not tool_name and isinstance(tool, dict):
            function_block = tool.get("function") or {}
            tool_name = str(
                function_block.get("name") or tool.get("name") or ""
            ).strip()
        if tool_name in {
            "get_page_context",
            "invoke_page_operation",
        } or tool_name.startswith("pageop_"):
            return True
    return False


def should_use_runtime_query_engine(
    *,
    runtime_mode: RuntimeMode,
    tools: list[Any] | None,
    include_shadow: bool = False,
) -> bool:
    if runtime_mode == "active":
        return True
    if runtime_mode == "shadow":
        return include_shadow
    if runtime_mode != "pageaware_only":
        return False
    return has_pageaware_tools(tools)


def is_shadow_mode(runtime_mode: RuntimeMode) -> bool:
    return runtime_mode == "shadow"


def _parse_env_bool(name: str, *, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return str(raw).strip().lower() not in {"0", "false", "no", "off"}


def _parse_env_int(name: str, *, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(str(raw).strip())
    except (TypeError, ValueError):
        return default


def _parse_env_float(name: str, *, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return float(str(raw).strip())
    except (TypeError, ValueError):
        return default


def _normalize_shadow_id(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _parse_shadow_whitelist() -> set[str]:
    raw = str(
        os.getenv("CLAUDE_CODE_STYLE_RUNTIME_SHADOW_WHITELIST", "") or "",
    ).strip()
    if not raw:
        return set()
    return {token.strip().lower() for token in raw.split(",") if token.strip()}


def _is_shadow_whitelisted(
    *,
    agent_id: Any,
    tenant_id: Any,
    conversation_id: Any,
) -> bool:
    whitelist = _parse_shadow_whitelist()
    if not whitelist:
        return True

    candidate_keys: set[str] = set()
    normalized_agent = _normalize_shadow_id(agent_id)
    normalized_tenant = _normalize_shadow_id(tenant_id)
    normalized_conversation = _normalize_shadow_id(conversation_id)
    if normalized_agent:
        candidate_keys.add(normalized_agent.lower())
        candidate_keys.add(f"agent:{normalized_agent.lower()}")
    if normalized_tenant:
        candidate_keys.add(normalized_tenant.lower())
        candidate_keys.add(f"tenant:{normalized_tenant.lower()}")
    if normalized_conversation:
        candidate_keys.add(normalized_conversation.lower())
        candidate_keys.add(f"conversation:{normalized_conversation.lower()}")
        candidate_keys.add(f"conv:{normalized_conversation.lower()}")
    return bool(candidate_keys & whitelist)


def _build_shadow_sample_seed(
    *,
    agent_id: Any,
    tenant_id: Any,
    conversation_id: Any,
) -> str:
    normalized_conversation = _normalize_shadow_id(conversation_id)
    if normalized_conversation:
        return f"conversation:{normalized_conversation}"
    normalized_agent = _normalize_shadow_id(agent_id)
    if normalized_agent:
        return f"agent:{normalized_agent}"
    normalized_tenant = _normalize_shadow_id(tenant_id)
    if normalized_tenant:
        return f"tenant:{normalized_tenant}"
    return "global"


def _is_shadow_sampled_in(
    *,
    sample_rate: float,
    agent_id: Any,
    tenant_id: Any,
    conversation_id: Any,
) -> bool:
    if sample_rate >= 1.0:
        return True
    if sample_rate <= 0.0:
        return False
    seed = _build_shadow_sample_seed(
        agent_id=agent_id,
        tenant_id=tenant_id,
        conversation_id=conversation_id,
    )
    hashed = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    bucket = int(hashed[:8], 16) / float(0xFFFFFFFF)
    return bucket < sample_rate


def _consume_shadow_rate_limit(max_per_minute: int) -> bool:
    if max_per_minute <= 0:
        return True

    now = time.monotonic()
    expire_before = now - _SHADOW_RATE_LIMIT_WINDOW_SEC
    with _shadow_rate_limit_lock:
        while (
            _shadow_rate_limit_timestamps
            and _shadow_rate_limit_timestamps[0] < expire_before
        ):
            _shadow_rate_limit_timestamps.popleft()
        if len(_shadow_rate_limit_timestamps) >= max_per_minute:
            return False
        _shadow_rate_limit_timestamps.append(now)
    return True


def should_run_shadow_probe(
    *,
    agent_id: Any,
    tenant_id: Any,
    conversation_id: Any,
) -> tuple[bool, str]:
    """
    Minimal guardrails for runtime-v2 shadow compare.
    runtime-v2 shadow 对比最小护栏（开关/白名单/采样/限流）。
    """

    if not _parse_env_bool("CLAUDE_CODE_STYLE_RUNTIME_SHADOW_ENABLED", default=True):
        return False, "disabled_by_env"

    if not _is_shadow_whitelisted(
        agent_id=agent_id,
        tenant_id=tenant_id,
        conversation_id=conversation_id,
    ):
        return False, "not_in_whitelist"

    sample_rate = _parse_env_float(
        "CLAUDE_CODE_STYLE_RUNTIME_SHADOW_SAMPLE_RATE",
        default=1.0,
    )
    sample_rate = max(0.0, min(1.0, sample_rate))
    if not _is_shadow_sampled_in(
        sample_rate=sample_rate,
        agent_id=agent_id,
        tenant_id=tenant_id,
        conversation_id=conversation_id,
    ):
        return False, "sampled_out"

    max_per_minute = _parse_env_int(
        "CLAUDE_CODE_STYLE_RUNTIME_SHADOW_MAX_PER_MINUTE",
        default=0,
    )
    if not _consume_shadow_rate_limit(max_per_minute):
        return False, "rate_limited"

    return True, "enabled"


def reset_shadow_rate_limiter_for_tests() -> None:
    with _shadow_rate_limit_lock:
        _shadow_rate_limit_timestamps.clear()
