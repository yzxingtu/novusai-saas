"""
Test type: behavioral
Scope: native web-search readiness gates for provider protocol/config boundaries.
Mock strategy: no LLM or tool executor mocks; verifies deterministic readiness policy.
"""

from types import SimpleNamespace

import pytest

from app.ai.web_search.orchestrator_support.native_target import (
    check_native_runtime_readiness,
)


@pytest.mark.asyncio
async def test_native_readiness_accepts_trusted_openai_host_with_responses_support() -> (
    None
):
    provider = SimpleNamespace(
        id=21,
        is_active=True,
        code="openai",
        type="openai_compatible",
        base_url="https://api.openai.com/v1",
        config={"wire_api": "responses"},
    )

    is_ready, reason = await check_native_runtime_readiness(
        provider,
        model_code="gpt-5.4",
    )

    assert is_ready is True
    assert reason == "trusted_openai_compatible_host:api.openai.com"


@pytest.mark.asyncio
async def test_native_readiness_rejects_trusted_openai_host_without_responses_support() -> (
    None
):
    provider = SimpleNamespace(
        id=22,
        is_active=True,
        code="openai",
        type="openai_compatible",
        base_url="https://api.openai.com/v1",
        config={"wire_api": "chat_completions"},
    )

    is_ready, reason = await check_native_runtime_readiness(
        provider,
        model_code="gpt-5.4",
    )

    assert is_ready is False
    assert reason == "provider_responses_wire_api_unsupported:chat_completions"


@pytest.mark.asyncio
async def test_native_readiness_rejects_trusted_openai_host_when_web_search_disabled() -> (
    None
):
    provider = SimpleNamespace(
        id=23,
        is_active=True,
        code="openai",
        type="openai_compatible",
        base_url="https://api.openai.com/v1",
        config={
            "wire_api": "responses",
            "web_search": {"enabled": False},
        },
    )

    is_ready, reason = await check_native_runtime_readiness(
        provider,
        model_code="gpt-5.4",
    )

    assert is_ready is False
    assert reason == "provider_web_search_disabled"
