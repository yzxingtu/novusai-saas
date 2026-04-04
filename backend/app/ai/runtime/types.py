"""
Shared runtime-v2 structures / 共享 runtime-v2 结构
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from app.ai.tools.types import ToolDefinition

CapabilityKind = Literal["prompt_skill", "execution_tool", "context_provider"]
ProtocolPath = Literal["responses", "chat_completions", "sync_chat_completions"]
TurnOutcome = Literal["success", "partial", "failed", "tool_round_failed"]
TerminationReason = Literal[
    "completed",
    "tool_round_empty",
    "tool_round_failed",
    "protocol_fallback",
    "stream_empty_after_fallback",
    "interrupted",
    "error",
]


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
    prompt_skill_blocks: list[str] = field(default_factory=list)
    capability_descriptors: list[CapabilityDescriptor] = field(default_factory=list)
    context_sources: list[ContextSource] = field(default_factory=list)

    @property
    def selected_tool_names(self) -> list[str]:
        return [tool.name for tool in self.tools]

    @property
    def selected_skill_names(self) -> list[str]:
        return [
            descriptor.name
            for descriptor in self.capability_descriptors
            if descriptor.kind == "prompt_skill"
        ]


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
