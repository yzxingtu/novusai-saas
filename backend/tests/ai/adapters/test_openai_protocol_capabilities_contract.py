"""
Test type: structural
Scope: OpenAI-compatible protocol capability contract parsing.
Mocked dependencies: none; tests construct the contract directly.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.ai.adapters.openai_compatible.capabilities import OpenAIProtocolCapabilities
from app.ai.exceptions import ProviderError
from app.ai.runtime.protocol_planner import ProtocolPlanner


def _responses_contract_config() -> dict[str, object]:
    return {
        "protocol_capabilities": {
            "primary_wire_api": "responses",
            "allowed_wire_apis": ["responses"],
        },
    }


def test_top_level_wire_api_is_retired_even_with_nested_contract() -> None:
    with pytest.raises(ProviderError, match="Retired provider protocol field wire_api"):
        OpenAIProtocolCapabilities.from_provider_config(
            provider_config={
                "wire_api": "responses",
                "protocol_capabilities": {
                    "primary_wire_api": "responses",
                    "allowed_wire_apis": ["responses"],
                },
            },
            configured_wire_api="responses",
        )


def test_missing_configured_wire_api_keeps_nested_contract_primary() -> None:
    capabilities = OpenAIProtocolCapabilities.from_provider_config(
        provider_config=_responses_contract_config(),
        configured_wire_api=None,
    )

    assert capabilities.primary_wire_api == "responses"
    assert capabilities.allowed_wire_apis == ("responses",)
    assert capabilities.allowed_cross_protocol_fallbacks == {}
    assert capabilities.allow_adapter_cross_protocol_fallback is False


def test_nested_wire_api_alias_is_rejected() -> None:
    with pytest.raises(
        ProviderError,
        match="protocol_capabilities.wire_api",
    ):
        OpenAIProtocolCapabilities.from_provider_config(
            provider_config={
                "protocol_capabilities": {
                    "wire_api": "responses",
                    "allowed_wire_apis": ["responses", "chat_completions"],
                },
            },
            configured_wire_api=None,
        )


def test_allowed_wire_apis_does_not_auto_generate_cross_protocol_fallbacks() -> None:
    capabilities = OpenAIProtocolCapabilities.from_provider_config(
        provider_config={
            "protocol_capabilities": {
                "allowed_wire_apis": ["responses", "chat_completions"],
            },
        },
        configured_wire_api=None,
    )

    assert capabilities.primary_wire_api == "responses"
    assert capabilities.allowed_wire_apis == ("responses", "chat_completions")
    assert capabilities.allowed_cross_protocol_fallbacks == {}
    assert capabilities.allow_adapter_cross_protocol_fallback is False
    assert (
        capabilities.is_cross_protocol_fallback_allowed(
            from_wire_api="responses",
            to_wire_api="chat_completions",
        )
        is False
    )


def test_allow_flag_without_fallback_map_is_rejected() -> None:
    with pytest.raises(
        ProviderError,
        match="Adapter-level cross-protocol fallback is retired",
    ):
        OpenAIProtocolCapabilities.from_provider_config(
            provider_config={
                "protocol_capabilities": {
                    "allowed_wire_apis": ["responses", "chat_completions"],
                    "allow_adapter_cross_protocol_fallback": True,
                },
            },
            configured_wire_api=None,
        )


def test_runtime_force_wire_api_rejects_unknown_token() -> None:
    capabilities = OpenAIProtocolCapabilities.from_provider_config(
        provider_config=_responses_contract_config(),
        configured_wire_api=None,
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


def test_allowed_wire_api_aliases_are_rejected() -> None:
    with pytest.raises(ProviderError) as exc:
        OpenAIProtocolCapabilities.from_provider_config(
            provider_config={
                "protocol_capabilities": {
                    "allowed_wire_apis": ["chat-completions", "response"],
                },
            },
            configured_wire_api=None,
        )

    assert exc.value.error_code == "invalid_protocol_contract"


def test_malformed_allowed_wire_apis_payload_raises() -> None:
    with pytest.raises(ProviderError) as exc:
        OpenAIProtocolCapabilities.from_provider_config(
            provider_config={
                "protocol_capabilities": {"allowed_wire_apis": "responses"},
            },
            configured_wire_api=None,
        )

    assert exc.value.error_code == "invalid_protocol_contract"


def test_valid_fallback_map_is_parsed_but_not_exposed_as_live_fallback() -> None:
    capabilities = OpenAIProtocolCapabilities.from_provider_config(
        provider_config={
            "protocol_capabilities": {
                "primary_wire_api": "responses",
                "allowed_wire_apis": ["responses", "chat_completions"],
                "allowed_cross_protocol_fallbacks": {
                    "responses": ["chat_completions"],
                },
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


def test_valid_fallback_map_with_allow_gate_is_rejected() -> None:
    with pytest.raises(
        ProviderError,
        match="Adapter-level cross-protocol fallback is retired",
    ):
        OpenAIProtocolCapabilities.from_provider_config(
            provider_config={
                "protocol_capabilities": {
                    "primary_wire_api": "responses",
                    "allowed_wire_apis": ["responses", "chat_completions"],
                    "allowed_cross_protocol_fallbacks": {
                        "responses": ["chat_completions"],
                    },
                    "allow_adapter_cross_protocol_fallback": True,
                },
            },
            configured_wire_api=None,
        )


def test_protocol_planner_ignores_adapter_wire_api_without_capabilities() -> None:
    adapter = SimpleNamespace(wire_api="responses", protocol_capabilities=None)

    assert ProtocolPlanner.resolve_preferred_protocol(adapter) == "chat_completions"
    assert ProtocolPlanner.build_protocol_chain(
        "chat_completions",
        adapter=adapter,
    ) == ["chat_completions"]


def test_protocol_planner_keeps_single_step_chain_when_guard_disables_fallback() -> (
    None
):
    adapter = SimpleNamespace(
        protocol_capabilities=SimpleNamespace(
            primary_wire_api="responses",
            allowed_wire_apis=("responses", "chat_completions"),
            allowed_cross_protocol_fallbacks={
                "responses": ("chat_completions",),
            },
            allow_adapter_cross_protocol_fallback=True,
        ),
    )

    assert ProtocolPlanner.build_protocol_chain("responses", adapter=adapter) == [
        "responses"
    ]


def test_protocol_planner_keeps_single_step_chain_when_guard_allows_fallback() -> None:
    adapter = SimpleNamespace(
        protocol_capabilities=SimpleNamespace(
            primary_wire_api="responses",
            allowed_wire_apis=("responses", "chat_completions"),
            allowed_cross_protocol_fallbacks={
                "responses": ("chat_completions",),
            },
            allow_adapter_cross_protocol_fallback=True,
        ),
    )

    assert ProtocolPlanner.build_protocol_chain(
        "responses",
        adapter=adapter,
        guard_contract=SimpleNamespace(disable_cross_protocol_fallback=False),
    ) == ["responses"]
