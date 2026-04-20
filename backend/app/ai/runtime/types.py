"""
Shared runtime-v2 structures / 共享 runtime-v2 结构
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Literal

from app.ai.tools.types import ToolDefinition

CapabilityKind = Literal[
    "capability_pack",
    "prompt_skill",
    "execution_tool",
    "context_provider",
]
ProtocolPath = Literal["responses", "chat_completions", "sync_chat_completions"]
TurnOutcome = Literal["success", "partial", "failed", "tool_round_failed"]
TerminationReason = Literal[
    "completed",
    "tool_round_empty",
    "tool_round_failed",
    "protocol_fallback",
    "stream_empty_after_fallback",
    "interrupted",
    "budget_exit",
    "provider_failure_after_partial_progress",
    "elapsed_budget_exceeded",
    "completion_budget_exceeded",
    "tool_round_budget_exceeded",
    "retry_budget_exhausted",
    "prompt_budget_exceeded",
    "tool_result_budget_exceeded",
    "candidate_tool_budget_exceeded",
    "awaiting_user_consent",
    "error",
]


def is_skill_descriptor_kind(kind: str | None) -> bool:
    normalized = str(kind or "").strip()
    return normalized in {"capability_pack", "prompt_skill"}


@dataclass
class ProviderEvent:
    """Provider/runtime side event for diagnostics / 供应商运行态诊断事件。"""

    kind: str = "none"
    message: str = ""
    retry_count: int = 0
    provider_code: str | None = None
    model_code: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class CapabilityDescriptor:
    name: str
    kind: CapabilityKind
    source: str
    description: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ContextSource:
    kind: str
    name: str
    active: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class CapabilityBundle:
    tools: list[ToolDefinition] = field(default_factory=list)
    tool_consent_modes: dict[str, str] = field(default_factory=dict)
    capability_descriptors: list[CapabilityDescriptor] = field(default_factory=list)
    context_sources: list[ContextSource] = field(default_factory=list)
    selected_tool_names_override: list[str] | None = None
    selected_skill_names_override: list[str] | None = None

    @property
    def selected_tool_names(self) -> list[str]:
        if self.selected_tool_names_override is not None:
            return list(self.selected_tool_names_override)
        return [tool.name for tool in self.tools]

    @property
    def selected_skill_names(self) -> list[str]:
        if self.selected_skill_names_override is not None:
            return list(self.selected_skill_names_override)
        return collect_selected_skill_names(
            descriptors=self.capability_descriptors,
            tools=self.tools,
        )


def _skill_descriptor_tool_names(
    descriptor: Any,
    tools: list[Any],
) -> list[str]:
    metadata = getattr(descriptor, "metadata", {}) or {}
    descriptor_skill_id = metadata.get("skill_id")
    descriptor_name = str(getattr(descriptor, "name", "") or "").strip()
    descriptor_source = str(getattr(descriptor, "source", "") or "").strip()

    matched_tool_names: list[str] = []
    for tool in tools:
        tool_name = str(getattr(tool, "name", "") or "").strip()
        if not tool_name:
            continue
        tool_skill_id = getattr(tool, "source_skill_id", None)
        tool_skill_name = str(getattr(tool, "source_skill_name", "") or "").strip()
        tool_package_name = str(getattr(tool, "source_package_name", "") or "").strip()
        tool_source = f"skill_package:{tool_package_name}" if tool_package_name else ""

        matched = False
        if (
            descriptor_skill_id not in (None, "")
            and tool_skill_id == descriptor_skill_id
        ):
            matched = True
        elif descriptor_name and tool_skill_name == descriptor_name:
            if descriptor_source and tool_source:
                matched = descriptor_source == tool_source
            else:
                matched = True
        elif descriptor_source and tool_source and descriptor_source == tool_source:
            matched = True

        if matched and tool_name not in matched_tool_names:
            matched_tool_names.append(tool_name)
    return matched_tool_names


def project_capability_bundle_to_tools(
    bundle: CapabilityBundle | None,
    tools: list[Any] | None,
) -> CapabilityBundle:
    projected_tools = list(tools or [])
    if bundle is None:
        return CapabilityBundle(tools=projected_tools)

    projected_tool_names = [
        str(getattr(tool, "name", "") or "").strip()
        for tool in projected_tools
        if str(getattr(tool, "name", "") or "").strip()
    ]
    projected_tool_name_set = set(projected_tool_names)
    skill_tool_names = [
        tool_name
        for tool_name, tool in zip(
            projected_tool_names,
            projected_tools,
            strict=False,
        )
        if str(getattr(tool, "source_skill_name", "") or "").strip()
    ]

    projected_descriptors: list[CapabilityDescriptor] = []
    for descriptor in bundle.capability_descriptors:
        kind = str(getattr(descriptor, "kind", "") or "").strip()
        if not is_skill_descriptor_kind(kind):
            projected_descriptors.append(replace(descriptor))
            continue

        matched_tool_names = _skill_descriptor_tool_names(descriptor, projected_tools)
        if not matched_tool_names:
            continue

        metadata = dict(getattr(descriptor, "metadata", {}) or {})
        metadata.update(
            {
                "resolved_tool_names": list(matched_tool_names),
                "resolved_tool_count": len(matched_tool_names),
                "has_execution_tools": True,
            }
        )
        projected_descriptors.append(replace(descriptor, metadata=metadata))

    projected_context_sources: list[ContextSource] = []
    projected_skill_names = collect_selected_skill_names(
        descriptors=projected_descriptors,
        tools=projected_tools,
    )
    for source in bundle.context_sources:
        if str(getattr(source, "kind", "") or "").strip() != "skill":
            projected_context_sources.append(replace(source))
            continue

        if not projected_skill_names and not skill_tool_names:
            continue

        metadata = dict(getattr(source, "metadata", {}) or {})
        metadata.update(
            {
                "tool_count": len(skill_tool_names),
                "selected_tool_names": list(skill_tool_names),
                "skill_count": len(projected_skill_names),
                "selected_skill_names": list(projected_skill_names),
            }
        )
        projected_context_sources.append(replace(source, metadata=metadata))

    projected_tool_consent_modes = {
        name: mode
        for name, mode in (bundle.tool_consent_modes or {}).items()
        if name in projected_tool_name_set
    }

    return CapabilityBundle(
        tools=projected_tools,
        tool_consent_modes=projected_tool_consent_modes,
        capability_descriptors=projected_descriptors,
        context_sources=projected_context_sources,
        selected_tool_names_override=list(projected_tool_names),
        selected_skill_names_override=list(projected_skill_names),
    )


def prompt_skill_descriptor_is_live(descriptor: Any) -> bool:
    kind = str(getattr(descriptor, "kind", "") or "").strip()
    name = str(getattr(descriptor, "name", "") or "").strip()
    if not is_skill_descriptor_kind(kind) or not name:
        return False

    metadata = getattr(descriptor, "metadata", {}) or {}
    return not (
        isinstance(metadata, dict) and metadata.get("has_execution_tools") is False
    )


def collect_selected_skill_names(
    *,
    descriptors: list[Any] | None = None,
    tools: list[Any] | None = None,
) -> list[str]:
    names: list[str] = []

    for descriptor in descriptors or []:
        if not prompt_skill_descriptor_is_live(descriptor):
            continue
        skill_name = str(getattr(descriptor, "name", "") or "").strip()
        if skill_name and skill_name not in names:
            names.append(skill_name)

    for tool in tools or []:
        skill_name = str(getattr(tool, "source_skill_name", "") or "").strip()
        if skill_name and skill_name not in names:
            names.append(skill_name)

    return names


@dataclass
class FallbackRecord:
    from_protocol: ProtocolPath
    to_protocol: ProtocolPath
    reason: str
    recovered: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class TurnRecord:
    turn_outcome: TurnOutcome = "success"
    termination_reason: TerminationReason = "completed"
    protocol_path: ProtocolPath | None = None
    execution_path: str | None = None
    selected_tool_names: list[str] = field(default_factory=list)
    candidate_tool_names: list[str] = field(default_factory=list)
    selected_skill_names: list[str] = field(default_factory=list)
    context_sources: list[ContextSource] = field(default_factory=list)
    fallback_history: list[FallbackRecord] = field(default_factory=list)
    intent_plan: list[dict[str, Any]] = field(default_factory=list)
    completed_intent_ids: list[str] = field(default_factory=list)
    unfinished_intent_ids: list[str] = field(default_factory=list)
    retry_events: list[dict[str, Any]] = field(default_factory=list)
    provider_events: list[ProviderEvent] = field(default_factory=list)
    budget: dict[str, Any] = field(default_factory=dict)
    failure_kind: str = "none"
    metadata: dict[str, Any] = field(default_factory=dict)
