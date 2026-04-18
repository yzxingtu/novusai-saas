from __future__ import annotations

import pytest

from app.ai.adapters.openai_compatible.request_payload_builders import (
    build_chat_completions_request,
    build_responses_reasoning_config,
    build_responses_request,
    convert_tools_for_responses,
)
from app.ai.types import ChatMessage


class _BuilderAdapterStub:
    def __init__(self, provider_config: dict | None = None) -> None:
        self.config = {}
        self.provider_config = provider_config or {}

    def resolve_effective_model_request(
        self,
        *,
        model: str,
        model_config=None,
        wire_api: str | None = None,
    ) -> dict:
        _ = model_config, wire_api
        if model == "gpt-5.4-xhigh":
            return {
                "upstream_model": "gpt-5.4",
                "effective_params": {"reasoning": {"effort": "xhigh"}},
            }
        return {"upstream_model": model, "effective_params": {}}

    async def _convert_messages_to_responses_input(
        self,
        messages: list[ChatMessage],
        *,
        supports_vision: bool = True,
        supports_audio: bool = False,
        supports_video: bool = False,
    ) -> list[dict]:
        _ = supports_vision, supports_audio, supports_video
        return [{"type": "message", "role": messages[0].role, "content": messages[0].content}]


def test_convert_tools_for_responses_injects_native_web_search() -> None:
    converted = convert_tools_for_responses(
        [
            {"type": "function", "function": {"name": "web_search", "parameters": {}}},
            {"type": "function", "function": {"name": "fetch_url", "parameters": {}}},
        ]
    )

    assert converted[0] == {"type": "web_search", "search_context_size": "medium"}
    assert converted[1]["type"] == "function"
    assert converted[1]["name"] == "fetch_url"


def test_build_responses_reasoning_config_auto_summary_for_supported_model() -> None:
    reasoning = build_responses_reasoning_config(
        model="gpt-5.4",
        explicit_reasoning={"effort": "high"},
        reasoning_summary_model_prefixes=("gpt-5",),
    )

    assert reasoning == {"effort": "high", "summary": "auto"}


def test_build_chat_completions_request_applies_reasoning_effort() -> None:
    adapter = _BuilderAdapterStub()

    request = build_chat_completions_request(
        adapter=adapter,
        openai_messages=[{"role": "user", "content": "hello"}],
        model="gpt-5.4",
        temperature=0.7,
        max_tokens=128,
        top_p=1.0,
        tools=None,
        tool_choice=None,
        stream=False,
        kwargs={
            "_effective_model_request": {
                "upstream_model": "gpt-5.4",
                "effective_params": {"reasoning_effort": "xhigh"},
            }
        },
    )

    assert request["model"] == "gpt-5.4"
    assert request["reasoning_effort"] == "xhigh"


@pytest.mark.asyncio
async def test_build_responses_request_keeps_required_tool_choice() -> None:
    adapter = _BuilderAdapterStub()

    request = await build_responses_request(
        adapter=adapter,
        messages=[ChatMessage(role="user", content="hello")],
        model="gpt-5.4-xhigh",
        tools=[{"type": "function", "function": {"name": "web_search", "parameters": {}}}],
        tool_choice="required",
        kwargs={},
        reasoning_summary_model_prefixes=("gpt-5",),
    )

    assert request["model"] == "gpt-5.4"
    assert request["tool_choice"] == "required"
    assert request["reasoning"] == {"effort": "xhigh", "summary": "auto"}
    assert request["tools"] == [
        {
            "type": "function",
            "name": "web_search",
            "description": None,
            "parameters": {},
        }
    ]


@pytest.mark.asyncio
async def test_build_responses_request_rewrites_web_search_only_when_provider_opts_in() -> None:
    adapter = _BuilderAdapterStub(
        provider_config={"web_search": {"prefer_hosted_tool": True}}
    )

    request = await build_responses_request(
        adapter=adapter,
        messages=[ChatMessage(role="user", content="hello")],
        model="gpt-5.4-xhigh",
        tools=[{"type": "function", "function": {"name": "web_search", "parameters": {}}}],
        tool_choice="required",
        kwargs={},
        reasoning_summary_model_prefixes=("gpt-5",),
    )

    assert request["tool_choice"] == "required"
    assert request["tools"] == [
        {"type": "web_search", "search_context_size": "medium"}
    ]
