"""Runtime contracts for protocol planning/execution."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.ai.runtime.types import ContextSource, ProtocolPath, TurnRecord
from app.ai.types import ChatChunk, ChatMessage, ChatResponse


@dataclass
class ProtocolExecutionPlan:
    """Stable protocol plan contract for one turn."""

    preferred_protocol: ProtocolPath
    protocol_chain: list[ProtocolPath] = field(default_factory=list)
    selected_tool_names: list[str] = field(default_factory=list)
    selected_skill_names: list[str] = field(default_factory=list)
    context_sources: list[ContextSource] = field(default_factory=list)


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

    def to_adapter_kwargs(self, *, protocol_path: ProtocolPath) -> dict[str, Any]:
        payload = dict(self.extra_kwargs or {})
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
                "_runtime_disable_cross_protocol_fallback": True,
                "_runtime_disable_sync_rescue": True,
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
