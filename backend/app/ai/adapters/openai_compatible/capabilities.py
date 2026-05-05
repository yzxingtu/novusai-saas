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
_MISSING = object()


def normalize_wire_api(value: Any) -> str:
    normalized = str(value or "").strip().lower().replace("-", "_")
    if not normalized:
        return "chat_completions"
    mapped = _WIRE_API_ALIASES.get(normalized)
    if mapped in _VALID_WIRE_APIS:
        return mapped
    raise ProviderError(
        message=f"Invalid provider wire API token: {value}",
        provider_code="openai_compatible",
        error_code="invalid_protocol_contract",
    )


def _normalize_configured_wire_api(value: Any) -> str | None:
    normalized = str(value or "").strip().lower().replace("-", "_")
    if not normalized:
        return None
    mapped = _WIRE_API_ALIASES.get(normalized)
    if mapped in _VALID_WIRE_APIS:
        return mapped
    raise ProviderError(
        message=f"Invalid provider wire API in wire_api: {value}",
        provider_code="openai_compatible",
        error_code="invalid_protocol_contract",
    )


def _normalize_contract_wire_api(value: Any, *, field_name: str) -> str | None:
    normalized = str(value or "").strip().lower().replace("-", "_")
    if not normalized:
        return None
    mapped = _WIRE_API_ALIASES.get(normalized)
    if mapped in _VALID_WIRE_APIS:
        return mapped
    raise ProviderError(
        message=(
            f"Invalid provider protocol contract wire API in {field_name}: {value}"
        ),
        provider_code="openai_compatible",
        error_code="invalid_protocol_contract",
    )


def _normalize_runtime_wire_api(value: Any) -> str | None:
    return _normalize_contract_wire_api(
        value,
        field_name="runtime_force_wire_api",
    )


def _normalize_wire_api_list(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise ProviderError(
            message="Invalid provider protocol contract allowed_wire_apis payload",
            provider_code="openai_compatible",
            error_code="invalid_protocol_contract",
        )
    collected: list[str] = []
    for item in value:
        wire_api = _normalize_contract_wire_api(
            item,
            field_name="allowed_wire_apis",
        )
        if wire_api is None:
            raise ProviderError(
                message="Empty provider protocol contract allowed_wire_apis entry",
                provider_code="openai_compatible",
                error_code="invalid_protocol_contract",
            )
        if wire_api not in collected:
            collected.append(wire_api)
    return tuple(collected)


def _normalize_fallback_map(value: Any) -> dict[str, tuple[str, ...]]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ProviderError(
            message=(
                "Invalid provider protocol contract allowed_cross_protocol_fallbacks"
                " payload"
            ),
            provider_code="openai_compatible",
            error_code="invalid_protocol_contract",
        )
    normalized: dict[str, tuple[str, ...]] = {}
    for raw_from, raw_targets in value.items():
        from_wire_api = _normalize_contract_wire_api(
            raw_from,
            field_name="allowed_cross_protocol_fallbacks",
        )
        if from_wire_api is None:
            raise ProviderError(
                message=(
                    "Empty provider protocol contract allowed_cross_protocol_fallbacks"
                    " entry"
                ),
                provider_code="openai_compatible",
                error_code="invalid_protocol_contract",
            )
        if not isinstance(raw_targets, list):
            raise ProviderError(
                message=(
                    "Invalid provider protocol contract allowed_cross_protocol_fallbacks"
                    " targets payload"
                ),
                provider_code="openai_compatible",
                error_code="invalid_protocol_contract",
            )
        targets: list[str] = []
        for raw_target in raw_targets:
            target = _normalize_contract_wire_api(
                raw_target,
                field_name="allowed_cross_protocol_fallbacks",
            )
            if target is None:
                raise ProviderError(
                    message=(
                        "Empty provider protocol contract allowed_cross_protocol_fallbacks"
                        " target entry"
                    ),
                    provider_code="openai_compatible",
                    error_code="invalid_protocol_contract",
                )
            if target in targets:
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
) -> tuple[str, bool]:
    contract_primary = _normalize_contract_wire_api(
        contract_payload.get("primary_wire_api"),
        field_name="primary_wire_api",
    )
    if contract_primary is not None:
        return contract_primary, True
    contract_primary = _normalize_contract_wire_api(
        contract_payload.get("wire_api"),
        field_name="wire_api",
    )
    if contract_primary is not None:
        return contract_primary, True

    configured = _normalize_configured_wire_api(configured_wire_api)
    contract_wire_apis = _merge_wire_api_sets(
        explicit_allowed_wire_apis,
        tuple(
            wire_api
            for from_wire_api, targets in allowed_cross_protocol_fallbacks.items()
            for wire_api in (from_wire_api, *targets)
        ),
    )
    if configured is not None and configured in contract_wire_apis:
        return configured, False

    if explicit_allowed_wire_apis:
        return explicit_allowed_wire_apis[0], False

    if allowed_cross_protocol_fallbacks:
        return next(iter(allowed_cross_protocol_fallbacks)), False

    if configured is not None:
        return configured, False

    return "chat_completions", False


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
        if contract is None:
            contract_payload: dict[str, Any] = {}
        elif not isinstance(contract, dict):
            raise ProviderError(
                message="Invalid provider protocol_capabilities payload",
                provider_code="openai_compatible",
                error_code="invalid_protocol_contract",
            )
        else:
            contract_payload = contract
        raw_allowed_wire_apis = contract_payload.get("allowed_wire_apis", _MISSING)
        explicit_allowed_wire_apis = (
            ()
            if raw_allowed_wire_apis is _MISSING
            else _normalize_wire_api_list(raw_allowed_wire_apis)
        )
        raw_cross_fallbacks = contract_payload.get(
            "allowed_cross_protocol_fallbacks", _MISSING
        )
        allowed_cross_protocol_fallbacks = (
            {}
            if raw_cross_fallbacks is _MISSING
            else _normalize_fallback_map(raw_cross_fallbacks)
        )
        primary_wire_api, primary_is_explicit = _resolve_primary_wire_api(
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
        if (
            primary_is_explicit
            and raw_allowed_wire_apis is not _MISSING
            and primary_wire_api not in explicit_allowed_wire_apis
        ):
            raise ProviderError(
                message=(
                    "Provider protocol contract primary_wire_api must be present in "
                    "allowed_wire_apis"
                ),
                provider_code="openai_compatible",
                error_code="invalid_protocol_contract",
            )
        if not allowed_wire_apis:
            allowed_wire_apis = _default_allowed_wire_apis(primary_wire_api)
        elif primary_wire_api not in allowed_wire_apis:
            allowed_wire_apis = (primary_wire_api, *allowed_wire_apis)
        elif allowed_wire_apis[0] != primary_wire_api:
            allowed_wire_apis = (
                primary_wire_api,
                *(
                    wire_api
                    for wire_api in allowed_wire_apis
                    if wire_api != primary_wire_api
                ),
            )

        raw_allow_cross = contract_payload.get("allow_adapter_cross_protocol_fallback")
        if raw_allow_cross is None:
            raw_allow_cross = config.get("allow_adapter_cross_protocol_fallback")
        if raw_allow_cross is None:
            allow_adapter_cross_protocol_fallback = bool(
                allowed_cross_protocol_fallbacks,
            )
        else:
            allow_adapter_cross_protocol_fallback = bool(raw_allow_cross)
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
        explicit_targets = self.allowed_cross_protocol_fallbacks.get(
            normalized_from,
            (),
        )
        if explicit_targets:
            return normalized_to in explicit_targets
        if not self.allowed_cross_protocol_fallbacks:
            return (
                normalized_from in self.allowed_wire_apis
                and normalized_to in self.allowed_wire_apis
            )
        return False

    def resolve_runtime_wire_api(self, runtime_force_wire_api: Any) -> str:
        if runtime_force_wire_api is None:
            return self.primary_wire_api
        requested = _normalize_runtime_wire_api(runtime_force_wire_api)
        if requested is None:
            return self.primary_wire_api
        if self.supports_wire_api(requested):
            return requested
        raise ProviderError(
            message=(
                f"Provider protocol does not support requested wire API: {requested}"
            ),
            provider_code="openai_compatible",
            error_code="unsupported_protocol",
        )
