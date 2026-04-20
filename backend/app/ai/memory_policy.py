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


def prime_memory_runtime_policy(
    request: Any,
    *,
    thread_memory_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not isinstance(thread_memory_state, dict):
        return _request_policy_payload(request)

    payload = {
        key: value
        for key, value in thread_memory_state.items()
        if key
        in {
            "scene",
            "channel",
            "source",
            "session_memory_runtime_enabled",
            "session_memory_read_enabled",
            "session_memory_write_enabled",
            "long_term_memory_runtime_enabled",
            "long_term_memory_recall_enabled",
            "long_term_memory_capture_enabled",
            "memory_context_enabled",
            "external_context_polluted",
            "external_context_reason",
        }
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
    "detect_external_context_pollution",
    "prime_memory_runtime_policy",
    "resolve_memory_runtime_policy",
]
