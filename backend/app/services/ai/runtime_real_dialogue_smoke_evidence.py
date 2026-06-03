"""中文: 真对话 smoke 工具完成证据辅助逻辑。

EN: Tool-completion evidence helpers for real-dialogue smoke checks.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

_TOOL_COMPLETION_NAME_KEYS = frozenset(
    ("completed_by_tool_names", "completed_tool_names", "successful_tool_names")
)
_TOOL_SUCCESS_STATUSES = frozenset({"success", "succeeded", "completed", "ok"})


def build_required_tool_completion_evidence(
    *diagnostic_payloads: Any,
) -> dict[str, Any]:
    required_intents: list[dict[str, Any]] = []
    seen_intents: set[
        tuple[str | None, str | None, str | None, int | None, tuple[str, ...]]
    ] = set()

    for payload in diagnostic_payloads:
        for intent in _collect_intent_plans(payload):
            if not _as_bool(intent.get("requires_tools")):
                continue
            intent_key = (
                _as_name(intent.get("intent_id")),
                _as_name(intent.get("kind")),
                _as_name(intent.get("source_text")),
                int(intent.get("order") or 0) or None,
                tuple(_name_list(intent.get("allowed_tool_names"))),
            )
            if intent_key in seen_intents:
                continue
            seen_intents.add(intent_key)

            required_intents.append(
                {
                    "intent_id": _as_name(intent.get("intent_id")),
                    "kind": _as_name(intent.get("kind")),
                    "family": _as_name(intent.get("family")),
                    "status": _as_name(intent.get("status")),
                    "completed_by_tool_names": _name_list(
                        intent.get("completed_by_tool_names")
                    ),
                    "required_tool_names": _unique_names(
                        [
                            *(_name_list(intent.get("allowed_tool_names"))),
                            *(_name_list(intent.get("preferred_tool_names"))),
                            *(_name_list(intent.get("completion_signals"))),
                        ]
                    ),
                }
            )

    if not required_intents:
        return {"required": False, "passed": True}

    diagnostic_completed_names = _unique_names(
        [
            name
            for payload in diagnostic_payloads
            for name in _collect_tool_completion_names(payload)
        ]
    )
    completed_tool_names = _unique_names(
        [
            *[
                name
                for intent in required_intents
                for name in intent["completed_by_tool_names"]
            ],
            *diagnostic_completed_names,
        ]
    )
    for intent in required_intents:
        intent_completed_names = list(intent["completed_by_tool_names"])
        required_names = list(intent["required_tool_names"])
        if required_names:
            required_tokens = {name.lower() for name in required_names}
            candidate_names = _unique_names(
                [*intent_completed_names, *completed_tool_names]
            )
            matched_tool_names = [
                name for name in candidate_names if name.lower() in required_tokens
            ]
        else:
            intent["missing_required_tool_names"] = True
            matched_tool_names = []
        intent["matched_tool_names"] = matched_tool_names

    return {
        "required": True,
        "passed": all(
            bool(intent["matched_tool_names"]) for intent in required_intents
        ),
        "required_intents": required_intents,
        "required_tool_names": _unique_names(
            [
                name
                for intent in required_intents
                for name in intent["required_tool_names"]
            ]
        ),
        "completed_tool_names": completed_tool_names,
        "matched_tool_names": _unique_names(
            [
                name
                for intent in required_intents
                for name in intent["matched_tool_names"]
            ]
        ),
    }


def _as_mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _as_bool(value: Any) -> bool:
    text = str(value).strip().lower()
    false_values = {"false", "0", "no", "n", "off", "none", "null", ""}
    return value is True or (text not in false_values and bool(value))


def _as_name(value: Any) -> str | None:
    text = str(value or "").strip()
    return text if text and text.lower() not in {"none", "null", "undefined"} else None


def _name_list(value: Any) -> list[str]:
    return _unique_names(list(value)) if isinstance(value, list | tuple | set) else []


def _unique_names(values: list[Any]) -> list[str]:
    return list(dict.fromkeys(name for value in values if (name := _as_name(value))))


def _collect_intent_plans(value: Any, *, depth: int = 0) -> list[dict[str, Any]]:
    if depth > 8:
        return []
    if isinstance(value, list | tuple | set):
        return [
            payload
            for item in value
            for payload in _collect_intent_plans(item, depth=depth + 1)
        ]
    if not isinstance(value, Mapping):
        return []
    plans: list[dict[str, Any]] = []
    for key in ("intent_plan", "intents"):
        raw_plan = value.get(key)
        if isinstance(raw_plan, list):
            plans.extend(payload for item in raw_plan if (payload := _as_mapping(item)))
    for nested in value.values():
        plans.extend(_collect_intent_plans(nested, depth=depth + 1))
    return plans


def _collect_tool_completion_names(value: Any, *, depth: int = 0) -> list[str]:
    if depth > 8:
        return []
    if isinstance(value, list | tuple | set):
        return _unique_names(
            [
                name
                for item in value
                for name in _collect_tool_completion_names(item, depth=depth + 1)
            ]
        )
    if not isinstance(value, Mapping):
        return []

    names: list[str] = []
    payload = _as_mapping(value)
    for key, nested in payload.items():
        if str(key) in _TOOL_COMPLETION_NAME_KEYS:
            names.extend(_name_list(nested))

    event_kind = _as_name(payload.get("kind"))
    if event_kind == "turn.tool_completed":
        data = _as_mapping(payload.get("data"))
        if _as_bool(data.get("success", True)):
            names.extend(_name_list([data.get("tool_name")]))

    if str(payload.get("kind") or "").strip().lower() == "tool":
        status = str(payload.get("status") or "").strip().lower()
        if payload.get("success") is True or status in _TOOL_SUCCESS_STATUSES:
            tool_name = (
                payload.get("tool_name")
                or payload.get("name")
                or payload.get("source_ref")
            )
            names.extend(_name_list([tool_name]))

    for nested in payload.values():
        names.extend(_collect_tool_completion_names(nested, depth=depth + 1))
    return _unique_names(names)
