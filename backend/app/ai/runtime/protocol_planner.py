"""Protocol planning for runtime-v2 query engine."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from app.ai.exceptions import ProviderError
from app.ai.runtime.contracts import ProtocolExecutionPlan, ProtocolGuardContract
from app.ai.runtime.types import ContextSource, ProtocolPath

_PROTOCOL_ALIASES: dict[str, ProtocolPath] = {
    "responses": "responses",
    "response": "responses",
    "responses_api": "responses",
    "chat_completions": "chat_completions",
    "chat/completions": "chat_completions",
    "chatcompletion": "chat_completions",
    "chatcompletion_api": "chat_completions",
}

_VALID_PROTOCOLS: tuple[ProtocolPath, ProtocolPath] = ("responses", "chat_completions")


class ProtocolPlanner:
    """Owns protocol chain selection for one runtime turn."""

    def __init__(self, *, adapter: Any) -> None:
        self.adapter = adapter

    @staticmethod
    def _normalize_protocol_token(value: Any) -> str:
        return str(value or "").strip().lower().replace("-", "_")

    @classmethod
    def _normalize_protocol_path(
        cls,
        value: Any,
        *,
        default: ProtocolPath | None = None,
    ) -> ProtocolPath | None:
        normalized = cls._normalize_protocol_token(value)
        if not normalized:
            return default
        mapped = _PROTOCOL_ALIASES.get(normalized)
        if mapped in _VALID_PROTOCOLS:
            return mapped
        return default

    @classmethod
    def _raise_invalid_protocol_token(
        cls,
        *,
        value: Any,
        field_name: str,
        adapter: Any | None,
    ) -> None:
        provider_code = None
        if adapter is not None:
            provider_code = str(getattr(adapter, "provider_code", "") or "").strip() or None
        raise ProviderError(
            message=f"Invalid provider protocol token in {field_name}: {value}",
            provider_code=provider_code,
            error_code="invalid_protocol_contract",
        )

    @classmethod
    def _raise_invalid_protocol_contract(
        cls,
        *,
        message: str,
        adapter: Any | None,
    ) -> None:
        provider_code = None
        if adapter is not None:
            provider_code = str(getattr(adapter, "provider_code", "") or "").strip() or None
        raise ProviderError(
            message=message,
            provider_code=provider_code,
            error_code="invalid_protocol_contract",
        )

    @classmethod
    def _normalize_contract_protocol(
        cls,
        value: Any,
        *,
        field_name: str,
        adapter: Any,
    ) -> ProtocolPath:
        protocol = cls._normalize_protocol_path(value, default=None)
        if protocol is None:
            cls._raise_invalid_protocol_token(
                value=value,
                field_name=field_name,
                adapter=adapter,
            )
        return protocol

    @classmethod
    def resolve_preferred_protocol(cls, adapter: Any) -> ProtocolPath:
        capabilities = getattr(adapter, "protocol_capabilities", None)
        if capabilities is not None:
            return cls._normalize_contract_protocol(
                getattr(capabilities, "primary_wire_api", None),
                field_name="primary_wire_api",
                adapter=adapter,
            )
        wire_api = getattr(adapter, "wire_api", "")
        protocol = cls._normalize_protocol_path(
            wire_api,
            default="chat_completions",
        )
        return protocol or "chat_completions"

    @classmethod
    def _resolve_allowed_protocols(
        cls,
        adapter: Any,
        preferred: ProtocolPath,
    ) -> list[ProtocolPath]:
        capabilities = getattr(adapter, "protocol_capabilities", None)
        raw_allowed = getattr(capabilities, "allowed_wire_apis", None)
        allowed: list[ProtocolPath] = []
        strict_contract = capabilities is not None
        explicit_allowed = False
        if isinstance(raw_allowed, Iterable) and not isinstance(raw_allowed, (str, bytes)):
            explicit_allowed = True
            for value in raw_allowed:
                if strict_contract:
                    protocol = cls._normalize_contract_protocol(
                        value,
                        field_name="allowed_wire_apis",
                        adapter=adapter,
                    )
                else:
                    protocol = cls._normalize_protocol_path(value, default=None)
                    if protocol is None:
                        continue
                if protocol not in allowed:
                    allowed.append(protocol)
        if strict_contract and explicit_allowed and preferred not in allowed:
            cls._raise_invalid_protocol_contract(
                message=(
                    "Provider protocol contract primary_wire_api must be present in "
                    "allowed_wire_apis"
                ),
                adapter=adapter,
            )
        if not allowed:
            if capabilities is None:
                allowed = (
                    ["responses", "chat_completions"]
                    if preferred == "responses"
                    else ["chat_completions"]
                )
            else:
                allowed = [preferred]
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
            return [preferred]

        allowed = cls._resolve_allowed_protocols(adapter, preferred)
        capabilities = getattr(adapter, "protocol_capabilities", None)
        raw_fallbacks = getattr(capabilities, "allowed_cross_protocol_fallbacks", None)
        allow_cross_protocol = None
        if capabilities is not None:
            allow_cross_protocol = getattr(
                capabilities,
                "allow_adapter_cross_protocol_fallback",
                None,
            )
        strict_contract = capabilities is not None

        if isinstance(raw_fallbacks, dict):
            normalized_fallbacks: dict[ProtocolPath, list[ProtocolPath]] = {}
            for raw_from, raw_targets in raw_fallbacks.items():
                if strict_contract:
                    from_protocol = cls._normalize_contract_protocol(
                        raw_from,
                        field_name="allowed_cross_protocol_fallbacks",
                        adapter=adapter,
                    )
                else:
                    from_protocol = cls._normalize_protocol_path(raw_from, default=None)
                    if from_protocol is None:
                        continue
                if not isinstance(raw_targets, Iterable) or isinstance(
                    raw_targets,
                    (str, bytes),
                ):
                    continue
                targets: list[ProtocolPath] = []
                for value in raw_targets:
                    if strict_contract:
                        protocol = cls._normalize_contract_protocol(
                            value,
                            field_name="allowed_cross_protocol_fallbacks",
                            adapter=adapter,
                        )
                    else:
                        protocol = cls._normalize_protocol_path(value, default=None)
                        if protocol is None:
                            continue
                    if (
                        protocol != from_protocol
                        and protocol in allowed
                        and protocol not in targets
                    ):
                        targets.append(protocol)
                if targets:
                    normalized_fallbacks[from_protocol] = targets
            if allow_cross_protocol is False:
                return [preferred]
            if preferred not in normalized_fallbacks:
                return [preferred]
            explicit_targets = normalized_fallbacks.get(preferred, ())
            chain = [preferred]
            for protocol in explicit_targets:
                if protocol != preferred and protocol in allowed and protocol not in chain:
                    chain.append(protocol)
            return chain if len(chain) > 1 else [preferred]

        if capabilities is not None:
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
        guard_contract: ProtocolGuardContract | None = None,
        selected_skill_names: list[str] | None = None,
        context_sources: list[ContextSource] | None = None,
    ) -> ProtocolExecutionPlan:
        preferred_protocol = self.resolve_preferred_protocol(self.adapter)
        resolved_guards = guard_contract or ProtocolGuardContract()
        return ProtocolExecutionPlan(
            preferred_protocol=preferred_protocol,
            protocol_chain=self.build_protocol_chain(
                preferred_protocol,
                adapter=self.adapter,
            ),
            selected_tool_names=self.selected_tool_names(tools),
            selected_skill_names=list(selected_skill_names or []),
            context_sources=list(context_sources or []),
            protocol_guards=resolved_guards,
        )
