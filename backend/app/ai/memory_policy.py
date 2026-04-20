"""
Unified memory runtime policy helpers.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

_EXTERNAL_CONTEXT_TOOL_NAMES = {"web_search", "fetch_url"}
_EXTERNAL_CONTEXT_FAMILIES = {"web_research"}


@dataclass(frozen=True)
class MemoryRuntimePolicy:
    scene: str = ""
    channel: str = ""
    source: str = ""
    session_memory_runtime_enabled: bool = False
    session_memory_read_enabled: bool = False
    session_memory_write_enabled: bool = False
    long_term_memory_runtime_enabled: bool = False
    long_term_memory_recall_enabled: bool = False
    long_term_memory_capture_enabled: bool = False
    memory_context_enabled: bool = False
    external_context_polluted: bool = False
    external_context_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "scene": self.scene,
            "channel": self.channel,
            "source": self.source,
            "session_memory_runtime_enabled": self.session_memory_runtime_enabled,
            "session_memory_read_enabled": self.session_memory_read_enabled,
            "session_memory_write_enabled": self.session_memory_write_enabled,
            "long_term_memory_runtime_enabled": self.long_term_memory_runtime_enabled,
            "long_term_memory_recall_enabled": self.long_term_memory_recall_enabled,
            "long_term_memory_capture_enabled": self.long_term_memory_capture_enabled,
            "memory_context_enabled": self.memory_context_enabled,
            "external_context_polluted": self.external_context_polluted,
            "external_context_reason": self.external_context_reason,
        }

    def to_thread_state(self) -> dict[str, Any]:
        return {
            "scene": self.scene,
            "channel": self.channel,
            "source": self.source,
            "session_memory_runtime_enabled": self.session_memory_runtime_enabled,
            "session_memory_read_enabled": self.session_memory_read_enabled,
            "session_memory_write_enabled": self.session_memory_write_enabled,
            "long_term_memory_runtime_enabled": self.long_term_memory_runtime_enabled,
            "long_term_memory_recall_enabled": self.long_term_memory_recall_enabled,
            "long_term_memory_capture_enabled": self.long_term_memory_capture_enabled,
            "memory_context_enabled": self.memory_context_enabled,
            "external_context_polluted": self.external_context_polluted,
            "external_context_reason": self.external_context_reason,
        }


def _normalize_text(value: Any) -> str:
    return str(value or "").strip()


_THREAD_POLICY_FIELDS = frozenset(MemoryRuntimePolicy.__dataclass_fields__)


def _request_policy_payload(request: Any) -> dict[str, Any]:
    payload = getattr(request, "memory_runtime_policy", None)
    if isinstance(payload, dict):
        return dict(payload)
    return {}


def _iter_result_intents(result: Any | None) -> list[Any]:
    return list(getattr(result, "intent_plan", None) or [])


def detect_external_context_pollution(
    *,
    request: Any | None,
    result: Any | None = None,
    tool_results: list[Any] | None = None,
) -> tuple[bool, str | None]:
    payload = _request_policy_payload(request)
    if bool(payload.get("external_context_polluted")):
        return True, _normalize_text(payload.get("external_context_reason")) or None

    raw_tool_results = (
        list(tool_results or [])
        if tool_results is not None
        else list(getattr(result, "tool_results", []) or [])
    )
    for tool_result in raw_tool_results:
        tool_name = _normalize_text(getattr(tool_result, "name", None))
        if tool_name in _EXTERNAL_CONTEXT_TOOL_NAMES:
            return True, f"tool:{tool_name}"

    planner = getattr(result, "tool_planner", None)
    if isinstance(planner, dict):
        planner_family = _normalize_text(planner.get("family"))
        if planner_family in _EXTERNAL_CONTEXT_FAMILIES:
            return True, f"tool_family:{planner_family}"

    for intent in _iter_result_intents(result):
        if isinstance(intent, dict):
            kind = _normalize_text(intent.get("kind"))
            family = _normalize_text(intent.get("family"))
        else:
            kind = _normalize_text(getattr(intent, "kind", None))
            family = _normalize_text(getattr(intent, "family", None))
        if kind in _EXTERNAL_CONTEXT_FAMILIES:
            return True, f"intent:{kind}"
        if family in _EXTERNAL_CONTEXT_FAMILIES:
            return True, f"intent_family:{family}"

    return False, None


def resolve_memory_runtime_policy(
    request: Any | None,
    *,
    result: Any | None = None,
    tool_results: list[Any] | None = None,
) -> MemoryRuntimePolicy:
    payload = _request_policy_payload(request)
    scene = _normalize_text(
        payload.get("scene") or getattr(request, "memory_scene", "")
    )
    channel = _normalize_text(
        payload.get("channel") or getattr(request, "memory_channel", "")
    )
    source = _normalize_text(
        payload.get("source") or getattr(request, "memory_source", "")
    )

    session_memory_runtime_enabled = bool(
        payload.get(
            "session_memory_runtime_enabled",
            bool(getattr(request, "memory_enabled", False)),
        )
    )
    has_user_scope = getattr(request, "user_id", None) is not None
    has_conversation_scope = getattr(request, "conversation_id", None) is not None
    session_memory_read_enabled = bool(
        session_memory_runtime_enabled and has_user_scope and has_conversation_scope
    )
    session_memory_write_enabled = bool(session_memory_read_enabled)

    long_term_memory_runtime_enabled = (
        bool(
            payload.get(
                "long_term_memory_runtime_enabled",
                bool(getattr(request, "long_term_memory_enabled", False)),
            )
        )
        and has_user_scope
    )

    polluted, polluted_reason = detect_external_context_pollution(
        request=request,
        result=result,
        tool_results=tool_results,
    )
    external_context_reason = (
        _normalize_text(payload.get("external_context_reason")) or polluted_reason
    )

    long_term_memory_recall_enabled = bool(
        long_term_memory_runtime_enabled and not polluted
    )
    long_term_memory_capture_enabled = bool(
        long_term_memory_recall_enabled and has_conversation_scope
    )
    memory_context_enabled = bool(
        session_memory_runtime_enabled or long_term_memory_recall_enabled
    )

    return MemoryRuntimePolicy(
        scene=scene,
        channel=channel,
        source=source,
        session_memory_runtime_enabled=session_memory_runtime_enabled,
        session_memory_read_enabled=session_memory_read_enabled,
        session_memory_write_enabled=session_memory_write_enabled,
        long_term_memory_runtime_enabled=long_term_memory_runtime_enabled,
        long_term_memory_recall_enabled=long_term_memory_recall_enabled,
        long_term_memory_capture_enabled=long_term_memory_capture_enabled,
        memory_context_enabled=memory_context_enabled,
        external_context_polluted=bool(polluted),
        external_context_reason=external_context_reason or None,
    )


def attach_memory_runtime_policy(
    request: Any,
    *,
    result: Any | None = None,
    tool_results: list[Any] | None = None,
) -> MemoryRuntimePolicy:
    policy = resolve_memory_runtime_policy(
        request,
        result=result,
        tool_results=tool_results,
    )
    request.memory_runtime_policy = policy.to_dict()
    return policy


def _normalize_memory_runtime_payload(
    payload: dict[str, Any] | None,
) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}

    filtered_payload = {
        key: value for key, value in payload.items() if key in _THREAD_POLICY_FIELDS
    }
    if not filtered_payload:
        return {}

    return MemoryRuntimePolicy(
        scene=_normalize_text(filtered_payload.get("scene")),
        channel=_normalize_text(filtered_payload.get("channel")),
        source=_normalize_text(filtered_payload.get("source")),
        session_memory_runtime_enabled=bool(
            filtered_payload.get("session_memory_runtime_enabled", False)
        ),
        session_memory_read_enabled=bool(
            filtered_payload.get("session_memory_read_enabled", False)
        ),
        session_memory_write_enabled=bool(
            filtered_payload.get("session_memory_write_enabled", False)
        ),
        long_term_memory_runtime_enabled=bool(
            filtered_payload.get("long_term_memory_runtime_enabled", False)
        ),
        long_term_memory_recall_enabled=bool(
            filtered_payload.get("long_term_memory_recall_enabled", False)
        ),
        long_term_memory_capture_enabled=bool(
            filtered_payload.get("long_term_memory_capture_enabled", False)
        ),
        memory_context_enabled=bool(
            filtered_payload.get("memory_context_enabled", False)
        ),
        external_context_polluted=bool(
            filtered_payload.get("external_context_polluted", False)
        ),
        external_context_reason=_normalize_text(
            filtered_payload.get("external_context_reason")
        )
        or None,
    ).to_dict()


def normalize_memory_runtime_policy(
    memory_runtime_policy: dict[str, Any] | None,
) -> dict[str, Any]:
    return _normalize_memory_runtime_payload(memory_runtime_policy)


def resolve_memory_runtime_mode(
    memory_runtime_policy: dict[str, Any] | None,
) -> str | None:
    normalized = normalize_memory_runtime_policy(memory_runtime_policy)
    if not normalized:
        return None

    session_enabled = bool(normalized.get("session_memory_runtime_enabled"))
    long_term_enabled = bool(normalized.get("long_term_memory_runtime_enabled"))
    if session_enabled and long_term_enabled:
        return "session_and_long_term"
    if session_enabled:
        return "session_only"
    if long_term_enabled:
        return "long_term_only"
    return "disabled"


def build_memory_runtime_projection(
    memory_runtime_policy: dict[str, Any] | None,
) -> dict[str, Any]:
    normalized = normalize_memory_runtime_policy(memory_runtime_policy)
    if not normalized:
        return {}

    projection = {
        "memory_runtime_policy": normalized,
        "memory_mode": resolve_memory_runtime_mode(normalized),
        "external_context_polluted": bool(normalized.get("external_context_polluted")),
    }
    if normalized.get("external_context_reason"):
        projection["external_context_reason"] = normalized.get(
            "external_context_reason"
        )
    return projection


def normalize_thread_memory_state(
    thread_memory_state: dict[str, Any] | None,
) -> dict[str, Any]:
    if not isinstance(thread_memory_state, dict):
        return {}

    normalized = _normalize_memory_runtime_payload(thread_memory_state)
    if not normalized:
        return {}

    normalized = dict(normalized)
    updated_at = _normalize_text(thread_memory_state.get("updated_at"))
    if updated_at:
        normalized["updated_at"] = updated_at
    return normalized


def prime_memory_runtime_policy(
    request: Any,
    *,
    thread_memory_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    normalized_thread_memory_state = normalize_thread_memory_state(thread_memory_state)
    if not normalized_thread_memory_state:
        return _request_policy_payload(request)

    payload = {
        key: value
        for key, value in normalized_thread_memory_state.items()
        if key in _THREAD_POLICY_FIELDS
    }
    payload.update(
        {
            "scene": _normalize_text(getattr(request, "memory_scene", ""))
            or _normalize_text(payload.get("scene")),
            "channel": _normalize_text(getattr(request, "memory_channel", ""))
            or _normalize_text(payload.get("channel")),
            "source": _normalize_text(getattr(request, "memory_source", ""))
            or _normalize_text(payload.get("source")),
            "session_memory_runtime_enabled": bool(
                getattr(
                    request,
                    "memory_enabled",
                    payload.get("session_memory_runtime_enabled", False),
                )
            ),
            "long_term_memory_runtime_enabled": bool(
                getattr(
                    request,
                    "long_term_memory_enabled",
                    payload.get("long_term_memory_runtime_enabled", False),
                )
            ),
        }
    )
    existing_payload = _request_policy_payload(request)
    if existing_payload:
        payload.update(existing_payload)
    request.memory_runtime_policy = payload
    return payload


__all__ = [
    "MemoryRuntimePolicy",
    "attach_memory_runtime_policy",
    "build_memory_runtime_projection",
    "detect_external_context_pollution",
    "normalize_memory_runtime_policy",
    "normalize_thread_memory_state",
    "prime_memory_runtime_policy",
    "resolve_memory_runtime_mode",
    "resolve_memory_runtime_policy",
]
