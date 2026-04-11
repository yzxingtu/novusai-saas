"""Protocol planning for runtime-v2 query engine."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from app.ai.runtime.contracts import ProtocolExecutionPlan
from app.ai.runtime.types import ContextSource, ProtocolPath


class ProtocolPlanner:
    """Owns protocol chain selection for one runtime turn."""

    def __init__(self, *, adapter: Any) -> None:
        self.adapter = adapter

    @staticmethod
    def _normalize_protocol_path(value: Any) -> ProtocolPath:
        normalized = str(value or "").strip().lower().replace("-", "_")
        return "responses" if normalized == "responses" else "chat_completions"

    @classmethod
    def resolve_preferred_protocol(cls, adapter: Any) -> ProtocolPath:
        capabilities = getattr(adapter, "protocol_capabilities", None)
        wire_api = getattr(capabilities, "primary_wire_api", None)
        if wire_api is None:
            wire_api = getattr(adapter, "wire_api", "")
        wire_api = str(wire_api or "").strip().lower()
        return "responses" if wire_api == "responses" else "chat_completions"

    @classmethod
    def _resolve_allowed_protocols(
        cls,
        adapter: Any,
        preferred: ProtocolPath,
    ) -> list[ProtocolPath]:
        capabilities = getattr(adapter, "protocol_capabilities", None)
        raw_allowed = getattr(capabilities, "allowed_wire_apis", None)
        allowed: list[ProtocolPath] = []
        if isinstance(raw_allowed, Iterable) and not isinstance(raw_allowed, (str, bytes)):
            for value in raw_allowed:
                protocol = cls._normalize_protocol_path(value)
                if protocol not in allowed:
                    allowed.append(protocol)
        if not allowed:
            allowed = ["responses", "chat_completions"] if preferred == "responses" else ["chat_completions"]
        if preferred not in allowed:
            allowed.insert(0, preferred)
        return allowed

    @classmethod
    def build_protocol_chain(
        cls,
        preferred: ProtocolPath,
        *,
        adapter: Any | None = None,
    ) -> list[ProtocolPath]:
        if adapter is None:
            return ["responses", "chat_completions"] if preferred == "responses" else ["chat_completions"]

        allowed = cls._resolve_allowed_protocols(adapter, preferred)
        capabilities = getattr(adapter, "protocol_capabilities", None)
        raw_fallbacks = getattr(capabilities, "allowed_cross_protocol_fallbacks", None)

        if isinstance(raw_fallbacks, dict):
            if preferred not in raw_fallbacks:
                return [preferred]
            explicit_targets = raw_fallbacks.get(preferred, ())
            chain = [preferred]
            if isinstance(explicit_targets, Iterable) and not isinstance(
                explicit_targets,
                (str, bytes),
            ):
                for value in explicit_targets:
                    protocol = cls._normalize_protocol_path(value)
                    if protocol != preferred and protocol in allowed and protocol not in chain:
                        chain.append(protocol)
            if len(chain) > 1:
                return chain

        if capabilities is not None and getattr(
            capabilities,
            "allow_adapter_cross_protocol_fallback",
            None,
        ) is False:
            return [preferred]

        chain = [preferred]
        chain.extend(protocol for protocol in allowed if protocol != preferred)
        return chain

    @staticmethod
    def selected_tool_names(tools: list[dict[str, Any]] | None) -> list[str]:
        if not tools:
            return []
        selected: list[str] = []
        for tool in tools:
            if not isinstance(tool, dict):
                continue
            function_block = tool.get("function") or {}
            tool_name = str(function_block.get("name") or "").strip()
            if tool_name:
                selected.append(tool_name)
        return selected

    def plan_turn(
        self,
        *,
        tools: list[dict[str, Any]] | None,
        selected_skill_names: list[str] | None = None,
        context_sources: list[ContextSource] | None = None,
    ) -> ProtocolExecutionPlan:
        preferred_protocol = self.resolve_preferred_protocol(self.adapter)
        return ProtocolExecutionPlan(
            preferred_protocol=preferred_protocol,
            protocol_chain=self.build_protocol_chain(
                preferred_protocol,
                adapter=self.adapter,
            ),
            selected_tool_names=self.selected_tool_names(tools),
            selected_skill_names=list(selected_skill_names or []),
            context_sources=list(context_sources or []),
        )
