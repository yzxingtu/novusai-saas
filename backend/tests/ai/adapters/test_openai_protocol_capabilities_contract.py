from __future__ import annotations

import pytest

from app.ai.adapters.openai_compatible.capabilities import OpenAIProtocolCapabilities
from app.ai.exceptions import ProviderError


def test_invalid_configured_wire_api_raises_provider_error_with_nested_contract() -> (
    None
):
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


def test_nested_wire_api_alias_sets_primary_wire_api() -> None:
    capabilities = OpenAIProtocolCapabilities.from_provider_config(
        provider_config={
            "protocol_capabilities": {
                "wire_api": "responses",
                "allowed_wire_apis": ["responses", "chat_completions"],
            },
        },
        configured_wire_api=None,
    )

    assert capabilities.primary_wire_api == "responses"
    assert capabilities.allowed_wire_apis == ("responses", "chat_completions")


def test_top_level_wire_api_does_not_relax_nested_contract() -> None:
    capabilities = OpenAIProtocolCapabilities.from_provider_config(
        provider_config={
            "wire_api": "responses",
            "protocol_capabilities": {
                "allowed_wire_apis": ["chat_completions"],
            },
        },
        configured_wire_api="responses",
    )

    assert capabilities.primary_wire_api == "chat_completions"
    assert capabilities.allowed_wire_apis == ("chat_completions",)
    assert capabilities.supports_wire_api("responses") is False


def test_allowed_wire_apis_does_not_auto_generate_cross_protocol_fallbacks() -> None:
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


def test_legacy_transitional_fallback_requires_allow_flag() -> None:
    capabilities = OpenAIProtocolCapabilities.from_provider_config(
        provider_config={
            "protocol_capabilities": {
                "allowed_wire_apis": ["responses", "chat_completions"],
                "allow_adapter_cross_protocol_fallback": False,
            },
        },
        configured_wire_api=None,
    )

    assert capabilities.allowed_cross_protocol_fallbacks == {}
    assert capabilities.allow_adapter_cross_protocol_fallback is False
    assert (
        capabilities.is_cross_protocol_fallback_allowed(
            from_wire_api="responses",
            to_wire_api="chat_completions",
        )
        is False
    )


def test_runtime_force_wire_api_rejects_unknown_token() -> None:
    capabilities = OpenAIProtocolCapabilities.from_provider_config(
        provider_config={"wire_api": "responses"},
        configured_wire_api="responses",
    )

    with pytest.raises(ProviderError, match="runtime_force_wire_api"):
        capabilities.resolve_runtime_wire_api("respones")


def test_contract_primary_missing_from_allowed_wire_apis_raises() -> None:
    with pytest.raises(ProviderError) as exc:
        OpenAIProtocolCapabilities.from_provider_config(
            provider_config={
                "protocol_capabilities": {
                    "primary_wire_api": "responses",
                    "allowed_wire_apis": ["chat_completions"],
                }
            },
            configured_wire_api=None,
        )

    assert exc.value.error_code == "invalid_protocol_contract"


def test_allowed_wire_api_aliases_are_normalized() -> None:
    capabilities = OpenAIProtocolCapabilities.from_provider_config(
        provider_config={
            "protocol_capabilities": {
                "allowed_wire_apis": ["chat-completions", "response"],
            },
        },
        configured_wire_api=None,
    )

    assert capabilities.primary_wire_api == "chat_completions"
    assert capabilities.allowed_wire_apis == ("chat_completions", "responses")


def test_malformed_allowed_wire_apis_payload_raises() -> None:
    with pytest.raises(ProviderError) as exc:
        OpenAIProtocolCapabilities.from_provider_config(
            provider_config={
                "protocol_capabilities": {"allowed_wire_apis": "responses"},
            },
            configured_wire_api=None,
        )

    assert exc.value.error_code == "invalid_protocol_contract"
