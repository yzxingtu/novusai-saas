"""
Usage recorder diagnostics and serialization helpers.
使用量记录器诊断与序列化辅助。
"""

from __future__ import annotations

import dataclasses
import time
from decimal import Decimal
from typing import Any

from app.ai.types import ChatResponse


def elapsed_milliseconds(start_time: float) -> int:
    """Compute elapsed ms from either wall-clock or monotonic start time / 兼容 wall-clock 与 monotonic 的耗时计算。"""
    candidates: list[float] = []

    wall_elapsed = time.time() - start_time
    if wall_elapsed >= 0:
        candidates.append(wall_elapsed)

    monotonic_elapsed = time.perf_counter() - start_time
    if monotonic_elapsed >= 0:
        candidates.append(monotonic_elapsed)

    if not candidates:
        return 0

    return int(min(candidates) * 1000)


def normalize_turn_record_payload(turn_record: Any) -> dict[str, Any] | None:
    if turn_record is None:
        return None
    if isinstance(turn_record, dict):
        return dict(turn_record)
    if hasattr(turn_record, "__dict__"):
        return {
            str(k): v for k, v in vars(turn_record).items() if not str(k).startswith("_")
        }
    return None


def normalize_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    normalized: list[str] = []
    for item in value:
        text = str(item).strip()
        if text and text not in normalized:
            normalized.append(text)
    return normalized


def normalize_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if value is None:
        return None
    normalized = str(value).strip().lower()
    if normalized in {"true", "1", "yes", "y", "on"}:
        return True
    if normalized in {"false", "0", "no", "n", "off"}:
        return False
    return None


def pick_first_bool(values: list[Any]) -> bool | None:
    for raw in values:
        parsed = normalize_bool(raw)
        if parsed is not None:
            return parsed
    return None


def normalize_context_sources(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    normalized: list[dict[str, Any]] = []
    for raw in value:
        if isinstance(raw, dict):
            source = dict(raw)
        elif hasattr(raw, "__dict__"):
            source = {
                str(k): v for k, v in vars(raw).items() if not str(k).startswith("_")
            }
        else:
            continue
        metadata = source.get("metadata")
        if not isinstance(metadata, dict):
            metadata = {}
        normalized.append(
            {
                "kind": str(source.get("kind") or "").strip(),
                "name": str(source.get("name") or "").strip(),
                "active": bool(source.get("active", True)),
                "metadata": dict(metadata),
            }
        )
    return normalized


def normalize_fallback_history(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    normalized: list[dict[str, Any]] = []
    for raw in value:
        if isinstance(raw, dict):
            item = dict(raw)
        elif hasattr(raw, "__dict__"):
            item = {
                str(k): v for k, v in vars(raw).items() if not str(k).startswith("_")
            }
        else:
            continue
        from_protocol = str(item.get("from_protocol") or "").strip()
        to_protocol = str(item.get("to_protocol") or "").strip()
        reason = str(item.get("reason") or "").strip()
        if not (from_protocol or to_protocol or reason):
            continue
        metadata = item.get("metadata")
        if not isinstance(metadata, dict):
            metadata = {}
        normalized.append(
            {
                "from_protocol": from_protocol or None,
                "to_protocol": to_protocol or None,
                "reason": reason or None,
                "recovered": bool(item.get("recovered", False)),
                "metadata": dict(metadata),
            }
        )
    return normalized


def inject_turn_diagnostics(
    request_data: dict[str, Any] | None,
    *,
    status: str,
    default_termination_reason: str,
    selected_tool_names: list[str] | None = None,
    selected_skill_names: list[str] | None = None,
    turn_record: dict[str, Any] | None = None,
    protocol_path: str | None = None,
    context_sources: list[dict[str, Any]] | None = None,
    fallback_history: list[dict[str, Any]] | None = None,
    sync_rescue: bool | None = None,
    should_record_call_log: bool | None = None,
) -> dict[str, Any]:
    payload = dict(request_data or {})
    normalized_turn_record = normalize_turn_record_payload(
        payload.get("turn_record") or turn_record
    )
    turn_record_metadata = (
        dict((normalized_turn_record or {}).get("metadata") or {})
        if isinstance((normalized_turn_record or {}).get("metadata"), dict)
        else {}
    )
    outcome_from_record = (
        str(normalized_turn_record.get("turn_outcome")).strip()
        if isinstance(normalized_turn_record, dict)
        and str(normalized_turn_record.get("turn_outcome") or "").strip()
        else None
    )
    termination_from_record = (
        str(normalized_turn_record.get("termination_reason")).strip()
        if isinstance(normalized_turn_record, dict)
        and str(normalized_turn_record.get("termination_reason") or "").strip()
        else None
    )
    selected_tools = normalize_string_list(
        (normalized_turn_record or {}).get("selected_tool_names")
        if isinstance(normalized_turn_record, dict)
        else selected_tool_names
    )
    if not selected_tools:
        selected_tools = normalize_string_list(
            payload.get("selected_tool_names") or selected_tool_names
        )
    selected_skills = normalize_string_list(
        (normalized_turn_record or {}).get("selected_skill_names")
        if isinstance(normalized_turn_record, dict)
        else selected_skill_names
    )
    if not selected_skills:
        selected_skills = normalize_string_list(
            payload.get("selected_skill_names") or selected_skill_names
        )
    effective_protocol_path = (
        str((normalized_turn_record or {}).get("protocol_path") or "").strip()
        if isinstance(normalized_turn_record, dict)
        and str((normalized_turn_record or {}).get("protocol_path") or "").strip()
        else (str(protocol_path or "").strip() or None)
    )
    effective_context_sources = (
        (
            normalize_context_sources(
                (normalized_turn_record or {}).get("context_sources")
            )
            if isinstance(normalized_turn_record, dict)
            else []
        )
        or normalize_context_sources(payload.get("context_sources"))
        or normalize_context_sources(context_sources or [])
    )
    effective_fallback_history = (
        (
            normalize_fallback_history(
                (normalized_turn_record or {}).get("fallback_history")
            )
            if isinstance(normalized_turn_record, dict)
            else []
        )
        or normalize_fallback_history(payload.get("fallback_history"))
        or normalize_fallback_history(fallback_history or [])
    )
    effective_sync_rescue = pick_first_bool(
        [
            sync_rescue,
            turn_record_metadata.get("sync_rescue"),
            (normalized_turn_record or {}).get("sync_rescue"),
            payload.get("sync_rescue"),
        ]
    )
    effective_should_record_call_log = pick_first_bool(
        [
            should_record_call_log,
            turn_record_metadata.get("should_record_call_log"),
            (normalized_turn_record or {}).get("should_record_call_log"),
            payload.get("should_record_call_log"),
        ]
    )
    turn_outcome = outcome_from_record or (
        "success" if status == "success" else "failed"
    )
    termination_reason = termination_from_record or default_termination_reason

    turn_diagnostics: dict[str, Any] = {
        "turn_outcome": turn_outcome,
        "termination_reason": termination_reason,
        "selected_tool_names": selected_tools,
        "selected_skill_names": selected_skills,
        "context_sources": effective_context_sources,
    }
    if effective_protocol_path:
        turn_diagnostics["protocol_path"] = effective_protocol_path
    if effective_fallback_history:
        turn_diagnostics["fallback_history"] = effective_fallback_history
    if effective_sync_rescue is not None:
        turn_diagnostics["sync_rescue"] = effective_sync_rescue
    if effective_should_record_call_log is not None:
        turn_diagnostics["should_record_call_log"] = effective_should_record_call_log
    if normalized_turn_record:
        if selected_tools:
            normalized_turn_record["selected_tool_names"] = selected_tools
        if selected_skills:
            normalized_turn_record["selected_skill_names"] = selected_skills
        if effective_protocol_path:
            normalized_turn_record["protocol_path"] = effective_protocol_path
        if effective_context_sources:
            normalized_turn_record["context_sources"] = effective_context_sources
        if effective_fallback_history:
            normalized_turn_record["fallback_history"] = effective_fallback_history
        if effective_sync_rescue is not None or effective_should_record_call_log is not None:
            metadata = (
                dict(normalized_turn_record.get("metadata") or {})
                if isinstance(normalized_turn_record.get("metadata"), dict)
                else {}
            )
            if effective_sync_rescue is not None:
                metadata["sync_rescue"] = effective_sync_rescue
            if effective_should_record_call_log is not None:
                metadata["should_record_call_log"] = effective_should_record_call_log
            normalized_turn_record["metadata"] = metadata
        turn_diagnostics["turn_record"] = normalized_turn_record
        payload["turn_record"] = normalized_turn_record
    if selected_tools:
        payload["selected_tool_names"] = selected_tools
    if selected_skills:
        payload["selected_skill_names"] = selected_skills
    if effective_protocol_path:
        payload["protocol_path"] = effective_protocol_path
    if effective_context_sources:
        payload["context_sources"] = effective_context_sources
    if effective_fallback_history:
        payload["fallback_history"] = effective_fallback_history
    if effective_sync_rescue is not None:
        payload["sync_rescue"] = effective_sync_rescue
    if effective_should_record_call_log is not None:
        payload["should_record_call_log"] = effective_should_record_call_log

    payload["turn_diagnostics"] = turn_diagnostics
    return payload


def serialize_chat_response(response: ChatResponse) -> dict[str, Any]:
    """
    Safely serialize ChatResponse.
    安全序列化 ChatResponse。
    """

    def safe_value(val: Any) -> Any:
        if isinstance(val, Decimal):
            return str(val)
        if dataclasses.is_dataclass(val) and not isinstance(val, type):
            return {k: safe_value(v) for k, v in val.__dict__.items()}
        if isinstance(val, dict):
            return {k: safe_value(v) for k, v in val.items()}
        if isinstance(val, (list, tuple)):
            return [safe_value(item) for item in val]
        return val

    return {
        key: safe_value(value)
        for key, value in response.__dict__.items()
        if key != "raw_response"
    }


__all__ = [
    "elapsed_milliseconds",
    "inject_turn_diagnostics",
    "normalize_bool",
    "normalize_context_sources",
    "normalize_fallback_history",
    "normalize_string_list",
    "normalize_turn_record_payload",
    "pick_first_bool",
    "serialize_chat_response",
]
