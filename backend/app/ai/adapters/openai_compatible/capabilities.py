"""Protocol capability contract for OpenAI-compatible adapters."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.ai.exceptions import ProviderError

_WIRE_API_ALIASES: dict[str, str] = {
    "responses": "responses",
    "response": "responses",
    "responses_api": "responses",
    "chat_completions": "chat_completions",
    "chat-completions": "chat_completions",
    "chat/completions": "chat_completions",
    "chatcompletion": "chat_completions",
    "chatcompletion_api": "chat_completions",
}

_VALID_WIRE_APIS: tuple[str, str] = ("responses", "chat_completions")


def normalize_wire_api(value: Any) -> str:
    normalized = str(value or "").strip().lower().replace("-", "_")
    if not normalized:
        return "chat_completions"
    mapped = _WIRE_API_ALIASES.get(normalized)
    if mapped in _VALID_WIRE_APIS:
        return mapped
    return "chat_completions"


def _normalize_wire_api_optional(value: Any) -> str | None:
    normalized = str(value or "").strip().lower().replace("-", "_")
    if not normalized:
        return None
    mapped = _WIRE_API_ALIASES.get(normalized)
    if mapped in _VALID_WIRE_APIS:
        return mapped
    return None


def _normalize_contract_wire_api(value: Any, *, field_name: str) -> str | None:
    normalized = str(value or "").strip().lower().replace("-", "_")
    if not normalized:
        return None
    mapped = _WIRE_API_ALIASES.get(normalized)
    if mapped in _VALID_WIRE_APIS:
        return mapped
    raise ProviderError(
        message=(
            "Invalid provider protocol contract wire API in "
            f"{field_name}: {value}"
        ),
        provider_code="openai_compatible",
        error_code="invalid_protocol_contract",
    )


def _normalize_wire_api_list(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    collected: list[str] = []
    for item in value:
        wire_api = _normalize_contract_wire_api(
            item,
            field_name="allowed_wire_apis",
        )
        if wire_api is None:
            continue
        if wire_api not in collected:
            collected.append(wire_api)
    return tuple(collected)


def _normalize_fallback_map(value: Any) -> dict[str, tuple[str, ...]]:
    if not isinstance(value, dict):
        return {}
    normalized: dict[str, tuple[str, ...]] = {}
    for raw_from, raw_targets in value.items():
        from_wire_api = _normalize_contract_wire_api(
            raw_from,
            field_name="allowed_cross_protocol_fallbacks",
        )
        if from_wire_api is None:
            continue
        if not isinstance(raw_targets, list):
            continue
        targets: list[str] = []
        for raw_target in raw_targets:
            target = _normalize_contract_wire_api(
                raw_target,
                field_name="allowed_cross_protocol_fallbacks",
            )
            if target is None or target in targets:
                continue
            targets.append(target)
        if targets:
            normalized[from_wire_api] = tuple(targets)
    return normalized


def _default_allowed_wire_apis(primary_wire_api: str) -> tuple[str, ...]:
    return (normalize_wire_api(primary_wire_api),)


def _merge_wire_api_sets(*groups: tuple[str, ...]) -> tuple[str, ...]:
    ordered: list[str] = []
    for group in groups:
        for wire_api in group:
            normalized = normalize_wire_api(wire_api)
            if normalized not in ordered:
                ordered.append(normalized)
    return tuple(ordered)


def _resolve_primary_wire_api(
    *,
    configured_wire_api: Any,
    contract_payload: dict[str, Any],
    explicit_allowed_wire_apis: tuple[str, ...],
    allowed_cross_protocol_fallbacks: dict[str, tuple[str, ...]],
) -> str:
    contract_primary = _normalize_contract_wire_api(
        contract_payload.get("primary_wire_api") or contract_payload.get("wire_api"),
        field_name="primary_wire_api",
    )
    if contract_primary is not None:
        return contract_primary

    configured = _normalize_wire_api_optional(configured_wire_api)
    contract_wire_apis = _merge_wire_api_sets(
        explicit_allowed_wire_apis,
        tuple(
            wire_api
            for from_wire_api, targets in allowed_cross_protocol_fallbacks.items()
            for wire_api in (from_wire_api, *targets)
        ),
    )
    if configured is not None and configured in contract_wire_apis:
        return configured

    if explicit_allowed_wire_apis:
        return explicit_allowed_wire_apis[0]

    if allowed_cross_protocol_fallbacks:
        return next(iter(allowed_cross_protocol_fallbacks))

    if configured is not None:
        return configured

    return "chat_completions"


@dataclass(frozen=True)
class OpenAIProtocolCapabilities:
    """Explicit runtime contract for protocol selection/fallback."""

    primary_wire_api: str
    allowed_wire_apis: tuple[str, ...]
    allowed_cross_protocol_fallbacks: dict[str, tuple[str, ...]]
    allow_adapter_cross_protocol_fallback: bool

    @classmethod
    def from_provider_config(
        cls,
        *,
        provider_config: dict[str, Any] | None,
        configured_wire_api: Any,
    ) -> OpenAIProtocolCapabilities:
        config = provider_config if isinstance(provider_config, dict) else {}
        contract = config.get("protocol_capabilities")
        contract_payload = contract if isinstance(contract, dict) else {}
        explicit_allowed_wire_apis = _normalize_wire_api_list(
            contract_payload.get("allowed_wire_apis"),
        )
        allowed_cross_protocol_fallbacks = _normalize_fallback_map(
            contract_payload.get("allowed_cross_protocol_fallbacks"),
        )
        primary_wire_api = _resolve_primary_wire_api(
            configured_wire_api=configured_wire_api,
            contract_payload=contract_payload,
            explicit_allowed_wire_apis=explicit_allowed_wire_apis,
            allowed_cross_protocol_fallbacks=allowed_cross_protocol_fallbacks,
        )
        fallback_wire_apis = tuple(
            wire_api
            for from_wire_api, targets in allowed_cross_protocol_fallbacks.items()
            for wire_api in (from_wire_api, *targets)
        )
        allowed_wire_apis = _merge_wire_api_sets(
            explicit_allowed_wire_apis,
            fallback_wire_apis,
        )
        if not allowed_wire_apis:
            allowed_wire_apis = _default_allowed_wire_apis(primary_wire_api)
        elif primary_wire_api not in allowed_wire_apis:
            allowed_wire_apis = (primary_wire_api, *allowed_wire_apis)
        elif allowed_wire_apis[0] != primary_wire_api:
            allowed_wire_apis = (
                primary_wire_api,
                *(wire_api for wire_api in allowed_wire_apis if wire_api != primary_wire_api),
            )

        raw_allow_cross = contract_payload.get("allow_adapter_cross_protocol_fallback")
        if raw_allow_cross is None:
            raw_allow_cross = config.get("allow_adapter_cross_protocol_fallback")
        if raw_allow_cross is None:
            allow_adapter_cross_protocol_fallback = bool(
                allowed_cross_protocol_fallbacks,
            ) or len(allowed_wire_apis) > 1
        else:
            allow_adapter_cross_protocol_fallback = bool(raw_allow_cross)
        if (
            allow_adapter_cross_protocol_fallback
            and not allowed_cross_protocol_fallbacks
            and len(allowed_wire_apis) > 1
        ):
            allowed_cross_protocol_fallbacks = {
                from_wire_api: tuple(
                    wire_api
                    for wire_api in allowed_wire_apis
                    if wire_api != from_wire_api
                )
                for from_wire_api in allowed_wire_apis
            }
        if len(allowed_wire_apis) <= 1 and not allowed_cross_protocol_fallbacks:
            allow_adapter_cross_protocol_fallback = False

        return cls(
            primary_wire_api=primary_wire_api,
            allowed_wire_apis=allowed_wire_apis,
            allowed_cross_protocol_fallbacks=allowed_cross_protocol_fallbacks,
            allow_adapter_cross_protocol_fallback=allow_adapter_cross_protocol_fallback,
        )

    def supports_wire_api(self, wire_api: str) -> bool:
        return normalize_wire_api(wire_api) in self.allowed_wire_apis

    def is_cross_protocol_fallback_allowed(
        self,
        *,
        from_wire_api: str,
        to_wire_api: str,
    ) -> bool:
        if not self.allow_adapter_cross_protocol_fallback:
            return False
        normalized_from = normalize_wire_api(from_wire_api)
        normalized_to = normalize_wire_api(to_wire_api)
        if normalized_from == normalized_to:
            return True
        return normalized_to in self.allowed_cross_protocol_fallbacks.get(
            normalized_from,
            (),
        )

    def resolve_runtime_wire_api(self, runtime_force_wire_api: Any) -> str:
        if runtime_force_wire_api is None:
            return self.primary_wire_api
        requested = normalize_wire_api(runtime_force_wire_api)
        if self.supports_wire_api(requested):
            return requested
        raise ProviderError(
            message=(
                "Provider protocol does not support requested wire API: "
                f"{requested}"
            ),
            provider_code="openai_compatible",
            error_code="unsupported_protocol",
        )
