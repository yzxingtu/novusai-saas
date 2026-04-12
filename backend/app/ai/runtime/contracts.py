"""Runtime contracts for protocol planning/execution."""

from __future__ import annotations

from collections.abc import Mapping, MutableMapping
from dataclasses import dataclass, field
from typing import Any, Protocol

from app.ai.runtime.types import (
    CapabilityBundle,
    ContextSource,
    ProtocolPath,
    TurnRecord,
)
from app.ai.types import ChatChunk, ChatMessage, ChatResponse


@dataclass(frozen=True)
class ProtocolGuardContract:
    """Explicit runtime guards that prevent adapter-local fallback behavior."""

    RUNTIME_DISABLE_CROSS_PROTOCOL_FALLBACK = "_runtime_disable_cross_protocol_fallback"
    RUNTIME_DISABLE_SYNC_RESCUE = "_runtime_disable_sync_rescue"
    _RUNTIME_GUARD_KEYS = (
        RUNTIME_DISABLE_CROSS_PROTOCOL_FALLBACK,
        RUNTIME_DISABLE_SYNC_RESCUE,
    )

    disable_cross_protocol_fallback: bool = True
    disable_sync_rescue: bool = True

    @classmethod
    def runtime_guard_keys(cls) -> tuple[str, str]:
        return cls._RUNTIME_GUARD_KEYS

    @classmethod
    def from_runtime_kwargs(
        cls,
        runtime_kwargs: Mapping[str, Any] | None,
        *,
        default: ProtocolGuardContract | None = None,
    ) -> ProtocolGuardContract:
        base = default or cls()
        if not runtime_kwargs:
            return base
        return cls(
            disable_cross_protocol_fallback=bool(
                runtime_kwargs.get(
                    cls.RUNTIME_DISABLE_CROSS_PROTOCOL_FALLBACK,
                    base.disable_cross_protocol_fallback,
                )
            ),
            disable_sync_rescue=bool(
                runtime_kwargs.get(
                    cls.RUNTIME_DISABLE_SYNC_RESCUE,
                    base.disable_sync_rescue,
                )
            ),
        )

    @classmethod
    def pop_runtime_kwargs(
        cls,
        runtime_kwargs: MutableMapping[str, Any] | None,
        *,
        default: ProtocolGuardContract | None = None,
    ) -> ProtocolGuardContract:
        base = default or cls()
        if not runtime_kwargs:
            return base
        extracted_kwargs = {
            key: runtime_kwargs.pop(key)
            for key in cls.runtime_guard_keys()
            if key in runtime_kwargs
        }
        return cls.from_runtime_kwargs(extracted_kwargs, default=base)

    def to_runtime_kwargs(self) -> dict[str, bool]:
        return {
            self.RUNTIME_DISABLE_CROSS_PROTOCOL_FALLBACK: bool(
                self.disable_cross_protocol_fallback
            ),
            self.RUNTIME_DISABLE_SYNC_RESCUE: bool(self.disable_sync_rescue),
        }


@dataclass
class ProtocolExecutionPlan:
    """Stable protocol plan contract for one turn."""

    preferred_protocol: ProtocolPath
    protocol_chain: list[ProtocolPath] = field(default_factory=list)
    selected_tool_names: list[str] = field(default_factory=list)
    selected_skill_names: list[str] = field(default_factory=list)
    context_sources: list[ContextSource] = field(default_factory=list)
    protocol_guards: ProtocolGuardContract = field(default_factory=ProtocolGuardContract)


@dataclass
class TurnCommand:
    """Stable runtime command contract for one turn."""

    messages: list[ChatMessage] = field(default_factory=list)
    model: str = ""
    temperature: float = 0.0
    max_tokens: int | None = None
    top_p: float = 1.0
    tools: list[dict[str, Any]] | None = None
    tool_choice: str | None = None
    supports_vision: bool = False
    supports_audio: bool = False
    supports_video: bool = False
    selected_skill_names: list[str] = field(default_factory=list)
    context_sources: list[ContextSource] = field(default_factory=list)
    extra_kwargs: dict[str, Any] = field(default_factory=dict)
    protocol_guards: ProtocolGuardContract = field(default_factory=ProtocolGuardContract)

    def to_adapter_kwargs(self, *, protocol_path: ProtocolPath) -> dict[str, Any]:
        payload = dict(self.extra_kwargs or {})
        guard_kwargs: dict[str, Any] = {}
        if self.protocol_guards is not None:
            guard_kwargs.update(self.protocol_guards.to_runtime_kwargs())
        payload.update(
            {
                "messages": self.messages,
                "model": self.model,
                "temperature": self.temperature,
                "max_tokens": self.max_tokens,
                "top_p": self.top_p,
                "tools": self.tools,
                "tool_choice": self.tool_choice,
                "supports_vision": self.supports_vision,
                "supports_audio": self.supports_audio,
                "supports_video": self.supports_video,
                "_runtime_force_wire_api": protocol_path,
                **guard_kwargs,
            }
        )
        return payload


@dataclass
class TurnExecutionResult:
    """Stable runtime result contract for one turn."""

    turn_record: TurnRecord | None = None
    protocol_plan: ProtocolExecutionPlan | None = None
    response: ChatResponse | None = None
    chunks: list[ChatChunk] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ContextCapabilityInputs:
    """Stable capability-assembly inputs emitted by context orchestration."""

    knowledge_base_ids: list[int] = field(default_factory=list)
    requested_knowledge_base_ids: list[int] = field(default_factory=list)
    dropped_knowledge_base_ids: list[int] = field(default_factory=list)
    rag_sources: list[dict[str, Any]] = field(default_factory=list)
    rag_source_kinds: list[str] = field(default_factory=list)
    memory_recalled: bool = False
    session_memory_injected: bool = False
    memory_recall_slice: dict[str, Any] | None = None
    runtime_model_capabilities: dict[str, Any] | None = None

    def to_state_dict(self) -> dict[str, Any]:
        return {
            "knowledge_base_ids": list(self.knowledge_base_ids or []),
            "requested_knowledge_base_ids": list(
                self.requested_knowledge_base_ids or []
            ),
            "dropped_knowledge_base_ids": list(self.dropped_knowledge_base_ids or []),
            "rag_sources": list(self.rag_sources or []),
            "rag_source_kinds": list(self.rag_source_kinds or []),
            "memory_recalled": bool(self.memory_recalled),
            "session_memory_injected": bool(self.session_memory_injected),
            "memory_recall_slice": dict(self.memory_recall_slice or {}),
            "runtime_model_capabilities": dict(self.runtime_model_capabilities or {}),
        }


@dataclass
class ContextCapabilityAwareness:
    """Dynamic capability-awareness snapshot for diagnostics-only surfaces."""

    enabled: bool = False
    categories: list[str] = field(default_factory=list)
    error: str | None = None


@dataclass
class ContextCapabilityFinalization:
    """Final capability bundle and diagnostics produced for one turn."""

    capability_bundle: CapabilityBundle | None = None
    diagnostics: dict[str, Any] = field(default_factory=dict)
    capability_injection_decision: dict[str, Any] = field(default_factory=dict)
    runtime_manifest: dict[str, Any] = field(default_factory=dict)
    runtime_capability_summary: str = ""


class ContextCapabilityBridge(Protocol):
    """Bridge context orchestration to runtime/service-owned capability logic."""

    async def resolve_runtime_model_capabilities(
        self,
        *,
        agent: Any,
    ) -> dict[str, Any]: ...

    def build_provisional_bundle(
        self,
        *,
        agent: Any,
        request: Any,
        skill_result: Any | None,
        capability_inputs: ContextCapabilityInputs,
    ) -> CapabilityBundle: ...

    async def compute_awareness(
        self,
        *,
        db: Any,
        agent: Any,
        request: Any,
        skill_result: Any | None,
        intent_flags: dict[str, bool],
        knowledge_base_ids: list[int],
        long_term_memory_enabled: bool,
    ) -> ContextCapabilityAwareness: ...

    async def finalize_capabilities(
        self,
        *,
        agent: Any,
        request: Any,
        skill_result: Any | None,
        intent_plan: list[Any],
        intent_flags: dict[str, bool],
        capability_inputs: ContextCapabilityInputs,
        capability_injection_decision: dict[str, Any],
    ) -> ContextCapabilityFinalization: ...
