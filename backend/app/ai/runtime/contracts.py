"""Runtime contracts for protocol planning/execution."""

from __future__ import annotations

from collections.abc import Mapping, MutableMapping
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

from app.ai.runtime.types import (
    CapabilityBundle,
    ContextSource,
    ProtocolPath,
    TurnRecord,
)
from app.ai.types import ChatChunk, ChatMessage, ChatResponse

TurnFlowStageType = Literal[
    "thinking",
    "tool_selection",
    "tool_execution",
    "retrieval",
    "answer_assembly",
    "completed",
    "failed",
]
TurnFlowStageStatus = Literal[
    "running",
    "completed",
    "skipped",
    "error",
    "interrupted",
]
TurnEvidenceKind = Literal["document", "knowledge_base", "tool", "memory"]


@dataclass
class TurnFlowStage:
    """Stable per-stage timeline item for UI-facing turn-flow rendering."""

    id: str
    type: TurnFlowStageType
    status: TurnFlowStageStatus
    title: str
    summary: str | None = None
    detail_lines: list[str] = field(default_factory=list)
    started_at_ms: int | None = None
    ended_at_ms: int | None = None
    duration_ms: int | None = None
    metrics: dict[str, Any] = field(default_factory=dict)
    tool_call_ids: list[str] = field(default_factory=list)
    source_refs: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "status": self.status,
            "title": self.title,
            "summary": self.summary,
            "detail_lines": list(self.detail_lines or []),
            "started_at_ms": self.started_at_ms,
            "ended_at_ms": self.ended_at_ms,
            "duration_ms": self.duration_ms,
            "metrics": dict(self.metrics or {}),
            "tool_call_ids": list(self.tool_call_ids or []),
            "source_refs": list(self.source_refs or []),
        }


@dataclass
class TurnEvidenceItem:
    """Stable evidence card item for UI-facing turn-flow rendering."""

    id: str
    kind: TurnEvidenceKind
    title: str
    arguments: dict[str, Any] | None = None
    url: str | None = None
    snippet: str | None = None
    badge: str | None = None
    score: float | None = None
    display_name: str | None = None
    duration_ms: int | None = None
    error: str | None = None
    error_type: str | None = None
    output: str | None = None
    result_link: str | None = None
    skill_name: str | None = None
    skill_type: str | None = None
    source_kind: str | None = None
    doc_id: int | None = None
    doc_name: str | None = None
    chunk_id: int | None = None
    knowledge_base_id: int | None = None
    knowledge_base_name: str | None = None
    started_at: int | None = None
    status: Literal["error", "running", "success"] | None = None
    summary_payload: dict[str, Any] | None = None
    tool_call_id: str | None = None
    tool_name: str | None = None
    source_ref: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "title": self.title,
            "arguments": dict(self.arguments or {}) if self.arguments else None,
            "url": self.url,
            "snippet": self.snippet,
            "badge": self.badge,
            "score": self.score,
            "display_name": self.display_name,
            "duration_ms": self.duration_ms,
            "error": self.error,
            "error_type": self.error_type,
            "output": self.output,
            "result_link": self.result_link,
            "skill_name": self.skill_name,
            "skill_type": self.skill_type,
            "source_kind": self.source_kind,
            "doc_id": self.doc_id,
            "doc_name": self.doc_name,
            "chunk_id": self.chunk_id,
            "knowledge_base_id": self.knowledge_base_id,
            "knowledge_base_name": self.knowledge_base_name,
            "started_at": self.started_at,
            "status": self.status,
            "summary_payload": (
                dict(self.summary_payload or {}) if self.summary_payload else None
            ),
            "tool_call_id": self.tool_call_id,
            "tool_name": self.tool_name,
            "source_ref": self.source_ref,
        }


@dataclass
class TurnAnswerCard:
    """Stable answer-card contract projected from one assistant turn."""

    summary: str
    sections: list[dict[str, Any]] = field(default_factory=list)
    source_chip_ids: list[str] = field(default_factory=list)
    confidence_label: str | None = None
    follow_up_suggestions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "summary": self.summary,
            "sections": list(self.sections or []),
            "source_chip_ids": list(self.source_chip_ids or []),
            "confidence_label": self.confidence_label,
            "follow_up_suggestions": list(self.follow_up_suggestions or []),
        }


@dataclass
class TurnFlowViewModel:
    """Stable user-facing turn-flow contract shared by stream/history surfaces."""

    timeline: list[TurnFlowStage] = field(default_factory=list)
    evidence: list[TurnEvidenceItem] = field(default_factory=list)
    answer_card: TurnAnswerCard | None = None
    completion_reason: str | None = None
    interrupted: bool = False
    error_surface: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "timeline": [item.to_dict() for item in (self.timeline or [])],
            "evidence": [item.to_dict() for item in (self.evidence or [])],
            "answer_card": self.answer_card.to_dict() if self.answer_card else None,
            "completion_reason": self.completion_reason,
            "interrupted": bool(self.interrupted),
            "error_surface": (
                dict(self.error_surface)
                if isinstance(self.error_surface, dict)
                else None
            ),
        }


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
    protocol_guards: ProtocolGuardContract = field(
        default_factory=ProtocolGuardContract
    )


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
    protocol_guards: ProtocolGuardContract = field(
        default_factory=ProtocolGuardContract
    )

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
    knowledge_bases: list[dict[str, Any]] = field(default_factory=list)
    knowledge_base_names: list[str] = field(default_factory=list)
    rag_sources: list[dict[str, Any]] = field(default_factory=list)
    rag_source_kinds: list[str] = field(default_factory=list)
    rag_attempted: bool = False
    rag_retrieval_status: str | None = None
    rag_no_hit_reason: str | None = None
    rag_matched_chunk_count: int = 0
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
            "knowledge_bases": list(self.knowledge_bases or []),
            "knowledge_base_names": list(self.knowledge_base_names or []),
            "rag_sources": list(self.rag_sources or []),
            "rag_source_kinds": list(self.rag_source_kinds or []),
            "rag_attempted": bool(self.rag_attempted),
            "rag_retrieval_status": self.rag_retrieval_status,
            "rag_no_hit_reason": self.rag_no_hit_reason,
            "rag_matched_chunk_count": int(self.rag_matched_chunk_count or 0),
            "memory_recalled": bool(self.memory_recalled),
            "session_memory_injected": bool(self.session_memory_injected),
            "memory_recall_slice": dict(self.memory_recall_slice or {}),
            "runtime_model_capabilities": dict(self.runtime_model_capabilities or {}),
        }


@dataclass
class ContextCapabilityAwareness:
    """中文: 动态能力感知快照。

    EN: Dynamic capability-awareness snapshot.
    """

    enabled: bool = False
    categories: list[str] = field(default_factory=list)
    sections: list[dict[str, Any]] = field(default_factory=list)
    knowledge_context: dict[str, Any] | None = None
    error: str | None = None


@dataclass
class ContextCapabilityFinalization:
    """Final capability bundle and diagnostics produced for one turn."""

    capability_bundle: CapabilityBundle | None = None
    diagnostics: dict[str, Any] = field(default_factory=dict)
    capability_injection_decision: dict[str, Any] = field(default_factory=dict)
    runtime_manifest: dict[str, Any] = field(default_factory=dict)
    runtime_capability_summary: dict[str, Any] = field(default_factory=dict)


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
        rag_attempted: bool,
        rag_retrieval_status: str | None,
        rag_no_hit_reason: str | None,
        rag_matched_chunk_count: int,
        long_term_memory_enabled: bool,
    ) -> ContextCapabilityAwareness: ...

    async def finalize_capabilities(
        self,
        *,
        agent: Any,
        request: Any,
        skill_result: Any | None,
        intent_flags: dict[str, bool],
        capability_inputs: ContextCapabilityInputs,
        capability_injection_decision: dict[str, Any],
    ) -> ContextCapabilityFinalization: ...
