from __future__ import annotations

import pytest

from app.ai.adapters.openai_compatible.capabilities import OpenAIProtocolCapabilities
from app.ai.exceptions import ProviderError


def test_invalid_configured_wire_api_raises_provider_error_with_nested_contract() -> None:
    with pytest.raises(ProviderError, match="Invalid provider wire API in wire_api"):
        OpenAIProtocolCapabilities.from_provider_config(
            provider_config={
                "wire_api": "respones",
                "protocol_capabilities": {
                    "allowed_wire_apis": ["responses"],
                },
            },
            configured_wire_api="respones",
        )


def test_missing_configured_wire_api_keeps_nested_contract_primary() -> None:
    capabilities = OpenAIProtocolCapabilities.from_provider_config(
        provider_config={
            "protocol_capabilities": {
                "allowed_wire_apis": ["responses"],
            },
        },
        configured_wire_api=None,
    )

    assert capabilities.primary_wire_api == "responses"
    assert capabilities.allowed_wire_apis == ("responses",)


def test_allowed_wire_apis_does_not_auto_generate_cross_protocol_fallbacks() -> (
    None
):
    capabilities = OpenAIProtocolCapabilities.from_provider_config(
        provider_config={
            "protocol_capabilities": {
                "allowed_wire_apis": ["responses", "chat_completions"],
                "allow_adapter_cross_protocol_fallback": True,
            },
        },
        configured_wire_api=None,
    )

    assert capabilities.allowed_wire_apis == ("responses", "chat_completions")
    assert capabilities.allowed_cross_protocol_fallbacks == {}
    assert capabilities.allow_adapter_cross_protocol_fallback is True


def test_dynamic_legacy_cross_protocol_check_uses_allow_flag_without_materializing_map() -> (
    None
):
    capabilities = OpenAIProtocolCapabilities.from_provider_config(
        provider_config={
            "protocol_capabilities": {
                "allowed_wire_apis": ["responses", "chat_completions"],
                "allow_adapter_cross_protocol_fallback": True,
            },
        },
        configured_wire_api=None,
    )

    assert capabilities.allowed_cross_protocol_fallbacks == {}
    assert capabilities.is_cross_protocol_fallback_allowed(
        from_wire_api="responses",
        to_wire_api="chat_completions",
    )


def test_runtime_force_wire_api_rejects_unknown_token() -> None:
    capabilities = OpenAIProtocolCapabilities.from_provider_config(
        provider_config={"wire_api": "responses"},
        configured_wire_api="responses",
    )

    with pytest.raises(ProviderError, match="runtime_force_wire_api"):
        capabilities.resolve_runtime_wire_api("respones")
