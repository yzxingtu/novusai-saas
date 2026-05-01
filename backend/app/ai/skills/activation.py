"""
Turn-level skill activation ownership.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.ai.engine.system_prompt_intent_helpers import is_capability_reporting_query
from app.ai.runtime.types import (
    capability_pack_descriptor_is_live,
    tool_is_auto_injected_runtime_builtin,
    tool_is_retired_ui_builtin,
)
from app.ai.text_semantics_terms import extract_textual_tool_call_names
from app.ai.tools.semantic_defaults import (
    is_retired_page_tool_name,
    tool_family_from_name,
)

_WEB_RESEARCH_TOOL_NAMES = {"web_search", "fetch_url"}


@dataclass
class TurnSkillActivation:
    applied: bool = False
    activated_tool_names: list[str] = field(default_factory=list)
    activated_skill_names: list[str] = field(default_factory=list)
    reason: str | None = None


def _stable_unique(values: list[Any]) -> list[str]:
    normalized: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if text and text not in normalized:
            normalized.append(text)
    return normalized


def _last_user_text(request: Any) -> str:
    messages = list(getattr(request, "messages", None) or [])
    for message in reversed(messages):
        if str(getattr(message, "role", "") or "").strip() != "user":
            continue
        text = str(getattr(message, "content", "") or "").strip()
        if text:
            return text
    return ""


def _descriptor_is_auto_injected_runtime_builtin(descriptor: Any) -> bool:
    metadata = getattr(descriptor, "metadata", {}) or {}
    return isinstance(metadata, dict) and metadata.get("auto_injected") is True


def _turn_activation(skill_result: Any) -> TurnSkillActivation | None:
    activation = getattr(skill_result, "turn_activation", None)
    return activation if isinstance(activation, TurnSkillActivation) else None


def _tool_has_skill_owner(tool: Any) -> bool:
    if tool_is_auto_injected_runtime_builtin(tool) or tool_is_retired_ui_builtin(
        tool
    ):
        return False
    return any(
        str(getattr(tool, attr, "") or "").strip()
        for attr in ("source_skill_id", "source_skill_name", "source_package_name")
    )


def _skill_name_has_live_execution(skill_result: Any, skill_name: str) -> bool:
    normalized_skill_name = str(skill_name or "").strip()
    if not normalized_skill_name:
        return False

    for tool in list(getattr(skill_result, "tools", []) or []):
        if tool_is_auto_injected_runtime_builtin(tool) or tool_is_retired_ui_builtin(
            tool
        ):
            continue
        tool_name = str(getattr(tool, "name", "") or "").strip()
        tool_skill_name = str(getattr(tool, "source_skill_name", "") or "").strip()
        if tool_name and tool_skill_name == normalized_skill_name:
            return True

    for descriptor in list(getattr(skill_result, "capability_descriptors", []) or []):
        descriptor_name = str(getattr(descriptor, "name", "") or "").strip()
        if descriptor_name != normalized_skill_name:
            continue
        if capability_pack_descriptor_is_live(descriptor):
            return True
    return False


def _filter_live_skill_names(
    skill_result: Any,
    skill_names: list[str],
    *,
    allow_catalog_skill_activation: bool,
) -> list[str]:
    if allow_catalog_skill_activation:
        return _stable_unique(skill_names)
    return _stable_unique(
        [
            skill_name
            for skill_name in skill_names
            if _skill_name_has_live_execution(skill_result, skill_name)
        ]
    )


def resolve_startup_intent_flags(request: Any) -> dict[str, bool]:
    user_text = _last_user_text(request)
    if not user_text:
        return {
            "has_page_intent": False,
            "has_web_research_intent": False,
        }

    from app.services.ai.agent_router_policy import requested_tool_families

    requested_families = requested_tool_families(user_text)
    return {
        "has_page_intent": False,
        "has_web_research_intent": "web_research" in requested_families,
    }


def _explicit_skill_mentions(skill_result: Any, user_text: str) -> list[str]:
    normalized_user_text = " ".join(user_text.lower().split())
    if not normalized_user_text:
        return []

    candidates: dict[str, str] = {}
    descriptors = list(getattr(skill_result, "capability_descriptors", []) or [])
    tools = list(getattr(skill_result, "tools", []) or [])

    for descriptor in descriptors:
        if _descriptor_is_auto_injected_runtime_builtin(descriptor):
            continue
        name = str(getattr(descriptor, "name", "") or "").strip()
        if name:
            candidates[" ".join(name.lower().split())] = name
        source = str(getattr(descriptor, "source", "") or "").strip()
        if source.startswith("skill_package:"):
            package_name = source.split(":", 1)[1].strip()
            if package_name:
                candidates[" ".join(package_name.lower().split())] = (
                    name or package_name
                )

    for tool in tools:
        if tool_is_auto_injected_runtime_builtin(tool) or tool_is_retired_ui_builtin(
            tool
        ):
            continue
        skill_name = str(getattr(tool, "source_skill_name", "") or "").strip()
        if skill_name:
            candidates[" ".join(skill_name.lower().split())] = skill_name
        package_name = str(getattr(tool, "source_package_name", "") or "").strip()
        if package_name:
            candidates[" ".join(package_name.lower().split())] = (
                skill_name or package_name
            )

    mentioned: list[str] = []
    for candidate, resolved_name in candidates.items():
        if (
            candidate
            and candidate in normalized_user_text
            and resolved_name not in mentioned
        ):
            mentioned.append(resolved_name)
    return mentioned


def _requested_skill_identifiers(request: Any) -> list[str]:
    raw_names = getattr(request, "selected_skill_names", None)
    if not isinstance(raw_names, (list, tuple, set)):
        return []
    return _stable_unique(list(raw_names))


def _requested_skill_names(
    skill_result: Any,
    requested_identifiers: list[str],
) -> list[str]:
    normalized_requests = _stable_unique(
        [
            " ".join(str(item or "").strip().lower().split())
            for item in requested_identifiers
        ]
    )
    if not normalized_requests:
        return []

    candidate_map: dict[str, list[str]] = {}

    def add_candidate(identifier: str, skill_name: str) -> None:
        normalized_identifier = " ".join(identifier.lower().split())
        normalized_skill_name = str(skill_name or "").strip()
        if not normalized_identifier or not normalized_skill_name:
            return
        bucket = candidate_map.setdefault(normalized_identifier, [])
        if normalized_skill_name not in bucket:
            bucket.append(normalized_skill_name)

    for descriptor in list(getattr(skill_result, "capability_descriptors", []) or []):
        if _descriptor_is_auto_injected_runtime_builtin(descriptor):
            continue
        descriptor_name = str(getattr(descriptor, "name", "") or "").strip()
        if descriptor_name:
            add_candidate(descriptor_name, descriptor_name)
        source = str(getattr(descriptor, "source", "") or "").strip()
        if source.startswith("skill_package:"):
            package_name = source.split(":", 1)[1].strip()
            if package_name and descriptor_name:
                add_candidate(package_name, descriptor_name)

    for tool in list(getattr(skill_result, "tools", []) or []):
        if tool_is_auto_injected_runtime_builtin(tool) or tool_is_retired_ui_builtin(
            tool
        ):
            continue
        skill_name = str(getattr(tool, "source_skill_name", "") or "").strip()
        package_name = str(getattr(tool, "source_package_name", "") or "").strip()
        if skill_name:
            add_candidate(skill_name, skill_name)
        if package_name and skill_name:
            add_candidate(package_name, skill_name)

    resolved: list[str] = []
    for requested in normalized_requests:
        for skill_name in candidate_map.get(requested, []):
            if skill_name not in resolved:
                resolved.append(skill_name)
    return resolved


def _tool_names_for_explicit_skills(
    skill_result: Any,
    skill_names: list[str],
) -> list[str]:
    skill_name_set = {
        str(name or "").strip() for name in skill_names if str(name or "").strip()
    }
    if not skill_name_set:
        return []
    return _stable_unique(
        [
            getattr(tool, "name", None)
            for tool in list(getattr(skill_result, "tools", []) or [])
            if str(getattr(tool, "source_skill_name", "") or "").strip()
            in skill_name_set
        ]
    )


def _tool_alias_map(skill_result: Any) -> dict[str, str]:
    alias_to_tool_name: dict[str, str] = {}
    for tool in list(getattr(skill_result, "tools", []) or []):
        tool_name = str(getattr(tool, "name", "") or "").strip()
        if not tool_name:
            continue
        alias_to_tool_name[tool_name] = tool_name
        spaced_name = tool_name.replace("_", " ").replace("-", " ")
        if spaced_name and spaced_name != tool_name:
            alias_to_tool_name[spaced_name] = tool_name
    return alias_to_tool_name


def _explicit_tool_mentions(
    skill_result: Any,
    user_text: str,
) -> list[str]:
    alias_to_tool_name = _tool_alias_map(skill_result)
    if not alias_to_tool_name:
        return []
    return extract_textual_tool_call_names(
        user_text,
        alias_to_tool_name=alias_to_tool_name,
        known_tool_names=set(alias_to_tool_name.values()),
    )


def _tool_names_for_runtime_policy(
    skill_result: Any,
    *,
    intent_flags: dict[str, Any],
) -> list[str]:
    tools = list(getattr(skill_result, "tools", []) or [])
    selected: list[str] = []
    for tool in tools:
        tool_name = str(getattr(tool, "name", "") or "").strip()
        if not tool_name:
            continue
        if (
            intent_flags.get("has_web_research_intent")
            and tool_name in _WEB_RESEARCH_TOOL_NAMES
        ):
            selected.append(tool_name)
    return _stable_unique(selected)


def _descriptor_semantic_families(descriptor: Any) -> list[str]:
    metadata = getattr(descriptor, "metadata", {}) or {}
    families = _stable_unique(list(metadata.get("preview_semantic_families") or []))
    resolved_tool_names = metadata.get("resolved_tool_names")
    if not isinstance(resolved_tool_names, (list, tuple, set)):
        return families
    for raw_name in resolved_tool_names:
        family = tool_family_from_name(str(raw_name or "").strip())
        if family != "none" and family not in families:
            families.append(family)
    return families


def _skill_names_for_runtime_policy(
    skill_result: Any,
    *,
    intent_flags: dict[str, Any],
    allow_catalog_skill_activation: bool,
) -> list[str]:
    del skill_result, intent_flags, allow_catalog_skill_activation
    return []


def activated_tools_for_turn(skill_result: Any | None) -> list[Any]:
    if skill_result is None:
        return []
    tools = list(getattr(skill_result, "tools", []) or [])
    activation = _turn_activation(skill_result)
    if activation is None or not activation.applied:
        return tools

    activated_tool_names = {
        str(name or "").strip()
        for name in activation.activated_tool_names or []
        if str(name or "").strip()
    }
    if not activated_tool_names:
        return []
    return [
        tool
        for tool in tools
        if str(getattr(tool, "name", "") or "").strip() in activated_tool_names
    ]


def execution_tools_for_turn(skill_result: Any | None) -> list[Any]:
    if skill_result is None:
        return []
    tools = list(getattr(skill_result, "tools", []) or [])
    activation = _turn_activation(skill_result)
    if activation is None or not activation.applied:
        return tools

    activated_tool_names = {
        str(name or "").strip()
        for name in activation.activated_tool_names or []
        if str(name or "").strip()
    }
    return [
        tool
        for tool in tools
        if (
            not _tool_has_skill_owner(tool)
            or str(getattr(tool, "name", "") or "").strip() in activated_tool_names
        )
    ]


def execution_selected_tool_names_for_turn(skill_result: Any | None) -> list[str]:
    return _stable_unique(
        [getattr(tool, "name", None) for tool in execution_tools_for_turn(skill_result)]
    )


def execution_capability_descriptors_for_turn(skill_result: Any | None) -> list[Any]:
    if skill_result is None:
        return []
    descriptors = list(getattr(skill_result, "capability_descriptors", []) or [])
    activation = _turn_activation(skill_result)
    if activation is None or not activation.applied:
        return descriptors

    activated_skill_names = {
        str(name or "").strip()
        for name in activation.activated_skill_names or []
        if str(name or "").strip()
    }
    if not activated_skill_names:
        return []
    return [
        descriptor
        for descriptor in descriptors
        if str(getattr(descriptor, "name", "") or "").strip() in activated_skill_names
    ]


def apply_turn_skill_activation(
    *,
    skill_result: Any | None,
    request: Any,
    intent_flags: dict[str, Any] | None,
    allow_catalog_skill_activation: bool = False,
) -> Any | None:
    if skill_result is None:
        return None

    inventory_tool_names = _stable_unique(
        [getattr(tool, "name", None) for tool in list(skill_result.tools or [])]
    )
    inventory_skill_names = list(
        getattr(skill_result, "inventory_selected_skill_names", []) or []
    )
    last_user_text = _last_user_text(request)
    requested_skill_names = _requested_skill_names(
        skill_result,
        _requested_skill_identifiers(request),
    )

    if is_capability_reporting_query(last_user_text):
        skill_result.turn_activation = TurnSkillActivation(
            applied=True,
            activated_tool_names=inventory_tool_names,
            activated_skill_names=inventory_skill_names,
            reason="capability_reporting_query",
        )
        return skill_result

    explicit_skill_names = _stable_unique(
        requested_skill_names + _explicit_skill_mentions(skill_result, last_user_text)
    )
    explicit_tool_names = _explicit_tool_mentions(skill_result, last_user_text)
    live_explicit_skill_names = _filter_live_skill_names(
        skill_result,
        explicit_skill_names,
        allow_catalog_skill_activation=allow_catalog_skill_activation,
    )
    activated_tool_names = _tool_names_for_explicit_skills(
        skill_result,
        explicit_skill_names,
    )
    activated_tool_names.extend(explicit_tool_names)
    activated_tool_names.extend(
        _tool_names_for_runtime_policy(
            skill_result,
            intent_flags=dict(intent_flags or {}),
        )
    )
    activated_tool_names = [
        name
        for name in _stable_unique(activated_tool_names)
        if not is_retired_page_tool_name(name)
    ]
    runtime_policy_skill_names = _skill_names_for_runtime_policy(
        skill_result,
        intent_flags=dict(intent_flags or {}),
        allow_catalog_skill_activation=allow_catalog_skill_activation,
    )

    activated_skill_names = _stable_unique(
        live_explicit_skill_names
        + runtime_policy_skill_names
        + [
            getattr(tool, "source_skill_name", None)
            for tool in list(skill_result.tools or [])
            if not tool_is_auto_injected_runtime_builtin(tool)
            if not tool_is_retired_ui_builtin(tool)
            if str(getattr(tool, "name", "") or "").strip() in set(activated_tool_names)
        ]
    )

    if requested_skill_names and explicit_tool_names:
        reason = "requested_skill_and_tool_mention"
    elif requested_skill_names:
        reason = "requested_skill_selection"
    elif explicit_skill_names and explicit_tool_names:
        reason = "explicit_skill_and_tool_mention"
    elif explicit_skill_names:
        reason = "explicit_skill_mention"
    elif explicit_tool_names:
        reason = "explicit_tool_mention"
    elif activated_tool_names or activated_skill_names:
        reason = "runtime_policy"
    else:
        reason = "no_turn_skill_activation"

    skill_result.turn_activation = TurnSkillActivation(
        applied=(
            is_capability_reporting_query(last_user_text)
            or bool(activated_tool_names or activated_skill_names)
        ),
        activated_tool_names=activated_tool_names,
        activated_skill_names=activated_skill_names,
        reason=reason,
    )
    return skill_result


__all__ = [
    "activated_tools_for_turn",
    "execution_capability_descriptors_for_turn",
    "execution_selected_tool_names_for_turn",
    "execution_tools_for_turn",
    "TurnSkillActivation",
    "apply_turn_skill_activation",
    "resolve_startup_intent_flags",
]
