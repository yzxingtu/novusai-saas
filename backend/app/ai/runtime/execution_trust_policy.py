"""
Pure runtime trust-policy helpers shared by engine and service layers.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from app.ai.tools.semantic_defaults import tool_family_from_name
from app.enums.agent import ActionLevelEnum

_RISK_ORDER = {
    ActionLevelEnum.READ.value: 0,
    ActionLevelEnum.SAFE_WRITE.value: 1,
    ActionLevelEnum.DANGEROUS.value: 2,
}


def _normalized_items(values: Iterable[Any] | None) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()

    for value in values or ():
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        normalized.append(text)

    return normalized


def _normalized_policy_ids(values: Iterable[Any] | None) -> list[int]:
    normalized: list[int] = []
    seen: set[int] = set()

    for value in values or ():
        try:
            policy_id = int(value)
        except (TypeError, ValueError):
            continue
        if policy_id in seen:
            continue
        seen.add(policy_id)
        normalized.append(policy_id)

    return normalized


def risk_rank(value: str | None) -> int:
    return _RISK_ORDER.get(str(value or "").strip(), -1)


def tool_family_for_name(tool_name: str) -> str:
    return tool_family_from_name(tool_name)


def tool_risk_level(
    *,
    tool_name: str,
    tool_family: str | None,
) -> str:
    normalized_name = str(tool_name or "").strip().lower()
    normalized_family = str(tool_family or "").strip().lower()

    if normalized_family in {"web_research", "weather"}:
        return ActionLevelEnum.READ.value
    if normalized_name.startswith(("http", "email", "code_", "toolkit")):
        return ActionLevelEnum.DANGEROUS.value
    return ActionLevelEnum.SAFE_WRITE.value


def build_policy_ref(
    *,
    policy_ids: Iterable[Any] | None = None,
    allowed_tool_names: Iterable[Any] | None = None,
    tool_families: Iterable[Any] | None = None,
    risk_level_cap: str | None = None,
) -> dict[str, Any] | None:
    normalized_policy_ids = _normalized_policy_ids(policy_ids)
    normalized_tool_names = _normalized_items(allowed_tool_names)
    normalized_tool_families = _normalized_items(tool_families)
    normalized_risk_cap = str(risk_level_cap or "").strip()

    if (
        not normalized_policy_ids
        and not normalized_tool_names
        and not normalized_tool_families
        and not normalized_risk_cap
    ):
        return None

    return {
        "policy_ids": normalized_policy_ids,
        "allowed_tool_names": normalized_tool_names,
        "tool_families": normalized_tool_families,
        "risk_level_cap": normalized_risk_cap or ActionLevelEnum.READ.value,
    }


def allows_tool(
    *,
    tool_name: str,
    tool_family: str | None,
    policy_ref: dict[str, Any] | None,
) -> bool:
    normalized_policy_ref = build_policy_ref(
        policy_ids=(policy_ref or {}).get("policy_ids"),
        allowed_tool_names=(policy_ref or {}).get("allowed_tool_names"),
        tool_families=(policy_ref or {}).get("tool_families"),
        risk_level_cap=(policy_ref or {}).get("risk_level_cap"),
    )
    if normalized_policy_ref is None:
        return False

    allowed_tool_names = {
        str(name).strip()
        for name in (normalized_policy_ref.get("allowed_tool_names") or [])
        if str(name).strip()
    }
    allowed_families = {
        str(name).strip()
        for name in (normalized_policy_ref.get("tool_families") or [])
        if str(name).strip()
    }
    tool_risk = tool_risk_level(tool_name=tool_name, tool_family=tool_family)
    risk_cap = normalized_policy_ref.get("risk_level_cap")

    if tool_name in allowed_tool_names:
        return risk_rank(tool_risk) <= risk_rank(risk_cap)
    if tool_family and tool_family in allowed_families:
        return risk_rank(tool_risk) <= risk_rank(risk_cap)
    return False


__all__ = [
    "allows_tool",
    "build_policy_ref",
    "risk_rank",
    "tool_family_for_name",
    "tool_risk_level",
]
