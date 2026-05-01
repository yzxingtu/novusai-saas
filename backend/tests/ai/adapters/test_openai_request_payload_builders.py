"""Test type: behavioral.

Verifies OpenAI-compatible request payload behavior without mocking the payload
builder decisions that route Responses API continuation state.
"""

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
        self.converted_messages: list[ChatMessage] = []

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
        self.converted_messages = list(messages)
        converted: list[dict] = []
        for message in messages:
            if message.role == "tool":
                converted.append(
                    {
                        "type": "function_call_output",
                        "call_id": message.tool_call_id or "",
                        "output": message.content or "",
                    }
                )
                continue
            if message.role == "assistant" and message.tool_calls:
                for tool_call in message.tool_calls:
                    function = tool_call.get("function") or {}
                    tc_id = (
                        tool_call.get("call_id")
                        or tool_call.get("tool_call_id")
                        or tool_call.get("id")
                        or ""
                    )
                    payload = {
                        "type": "function_call",
                        "call_id": tc_id,
                        "name": function.get("name", ""),
                        "arguments": function.get("arguments", "{}") or "{}",
                        "status": "completed",
                    }
                    item_id = str(tool_call.get("id") or "").strip()
                    if item_id.startswith("fc_"):
                        payload["id"] = item_id
                    converted.append(payload)
                if not (message.content or "").strip():
                    continue
            converted.append(
                {
                    "type": "message",
                    "role": message.role,
                    "content": message.content,
                }
            )
        return converted


def test_convert_tools_for_responses_injects_native_web_search() -> None:
    converted = convert_tools_for_responses(
        [
            {"type": "function", "function": {"name": "web_search", "parameters": {}}},
            {"type": "function", "function": {"name": "fetch_url", "parameters": {}}},
        ],
        rewrite_web_search=True,
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
async def test_build_responses_request_hoists_system_messages_into_instructions() -> None:
    adapter = _BuilderAdapterStub()

    request = await build_responses_request(
        adapter=adapter,
        messages=[
            ChatMessage(role="system", content="You are helpful."),
            ChatMessage(role="user", content="hello"),
            ChatMessage(role="system", content="Only use tools when needed."),
        ],
        model="gpt-5.4-xhigh",
        tools=None,
        tool_choice=None,
        kwargs={},
        reasoning_summary_model_prefixes=("gpt-5",),
    )

    assert request["instructions"] == "You are helpful.\n\nOnly use tools when needed."
    assert [message.role for message in adapter.converted_messages] == ["user"]
    assert request["input"] == [
        {
            "type": "message",
            "role": "user",
            "content": "hello",
        }
    ]


@pytest.mark.asyncio
async def test_build_responses_request_keeps_runtime_web_search_when_provider_search_enabled() -> None:
    adapter = _BuilderAdapterStub(
        provider_config={"web_search": {"enabled": True}}
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
        {
            "type": "function",
            "name": "web_search",
            "description": None,
            "parameters": {},
        }
    ]


@pytest.mark.asyncio
async def test_build_responses_request_ignores_legacy_hosted_search_rewrite_config() -> None:
    adapter = _BuilderAdapterStub(
        provider_config={
            "web_search": {
                "enabled": True,
                "hosted_tool_rewrite_enabled": True,
                "prefer_hosted_tool": True,
            }
        }
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
        {
            "type": "function",
            "name": "web_search",
            "description": None,
            "parameters": {},
        }
    ]


@pytest.mark.asyncio
async def test_build_responses_request_uses_previous_response_id_for_pure_tool_followup() -> (
    None
):
    adapter = _BuilderAdapterStub()

    request = await build_responses_request(
        adapter=adapter,
        messages=[
            ChatMessage(role="system", content="You are helpful."),
            ChatMessage(role="user", content="请搜索当前数据集"),
            ChatMessage(
                role="assistant",
                content="",
                tool_calls=[
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {"name": "crm_update_record", "arguments": '{"target":"x"}'},
                    }
                ],
                metadata={
                    "protocol_path": "responses",
                    "responses_response_id": "resp_tool_round_1",
                },
            ),
            ChatMessage(role="tool", content='{"ok":true}', tool_call_id="call_1"),
        ],
        model="gpt-5.4-xhigh",
        tools=[{"type": "function", "function": {"name": "crm_update_record", "parameters": {}}}],
        tool_choice="required",
        kwargs={},
        reasoning_summary_model_prefixes=("gpt-5",),
    )

    assert request["previous_response_id"] == "resp_tool_round_1"
    assert request["instructions"] == "You are helpful."
    assert [message.role for message in adapter.converted_messages] == ["tool"]
    assert request["input"] == [
        {
            "type": "function_call_output",
            "call_id": "call_1",
            "output": '{"ok":true}',
        }
    ]


@pytest.mark.asyncio
async def test_build_responses_stream_request_omits_previous_response_id_for_tool_followup() -> (
    None
):
    adapter = _BuilderAdapterStub()

    request = await build_responses_request(
        adapter=adapter,
        messages=[
            ChatMessage(role="system", content="You are helpful."),
            ChatMessage(role="user", content="查一下北京天气"),
            ChatMessage(
                role="assistant",
                content="",
                tool_calls=[
                    {
                        "id": "call_weather_1",
                        "type": "function",
                        "function": {
                            "name": "get_current_weather",
                            "arguments": '{"city":"北京"}',
                        },
                    }
                ],
                metadata={
                    "protocol_path": "responses",
                    "responses_response_id": "resp_tool_round_1",
                },
            ),
            ChatMessage(
                role="tool",
                content='{"temperature":"12°C","condition":"晴"}',
                tool_call_id="call_weather_1",
            ),
        ],
        model="gpt-5.4-xhigh",
        tools=[
            {
                "type": "function",
                "function": {
                    "name": "get_current_weather",
                    "parameters": {},
                },
            }
        ],
        tool_choice="required",
        stream=True,
        kwargs={},
        reasoning_summary_model_prefixes=("gpt-5",),
    )

    assert "previous_response_id" not in request
    assert request["stream"] is True
    assert [message.role for message in adapter.converted_messages] == [
        "user",
        "assistant",
        "tool",
    ]
    assert request["input"] == [
        {
            "type": "message",
            "role": "user",
            "content": "查一下北京天气",
        },
        {
            "type": "function_call",
            "call_id": "call_weather_1",
            "name": "get_current_weather",
            "arguments": '{"city":"北京"}',
            "status": "completed",
        },
        {
            "type": "function_call_output",
            "call_id": "call_weather_1",
            "output": '{"temperature":"12°C","condition":"晴"}',
        },
    ]


@pytest.mark.asyncio
async def test_build_responses_stream_follow_up_round_without_tools_keeps_structured_history() -> (
    None
):
    adapter = _BuilderAdapterStub()

    request = await build_responses_request(
        adapter=adapter,
        messages=[
            ChatMessage(role="system", content="You are helpful."),
            ChatMessage(role="user", content="读取客户数据集"),
            ChatMessage(
                role="assistant",
                content="",
                tool_calls=[
                    {
                        "id": "call_crm_lookup_1",
                        "type": "function",
                        "function": {
                            "name": "crm_lookup",
                            "arguments": '{"mode":"compact"}',
                        },
                    }
                ],
                metadata={
                    "protocol_path": "responses",
                    "responses_response_id": "resp_tool_round_1",
                },
            ),
            ChatMessage(
                role="tool",
                content='{"row_count":9,"dataset_id":"crm:admin.dashboard"}',
                tool_call_id="call_crm_lookup_1",
            ),
        ],
        model="gpt-5.4-xhigh",
        tools=None,
        tool_choice=None,
        stream=True,
        kwargs={},
        reasoning_summary_model_prefixes=("gpt-5",),
    )

    assert request["stream"] is True
    assert "previous_response_id" not in request
    assert "tools" not in request
    assert "tool_choice" not in request
    assert request["instructions"] == "You are helpful."
    assert [message.role for message in adapter.converted_messages] == [
        "user",
        "assistant",
        "tool",
    ]
    assert request["input"] == [
        {
            "type": "message",
            "role": "user",
            "content": "读取客户数据集",
        },
        {
            "type": "function_call",
            "call_id": "call_crm_lookup_1",
            "name": "crm_lookup",
            "arguments": '{"mode":"compact"}',
            "status": "completed",
        },
        {
            "type": "function_call_output",
            "call_id": "call_crm_lookup_1",
            "output": (
                '{"row_count":9,"dataset_id":"crm:admin.dashboard"}'
            ),
        },
    ]


@pytest.mark.asyncio
async def test_build_responses_stream_follow_up_preserves_fc_item_id_when_available() -> None:
    adapter = _BuilderAdapterStub()

    request = await build_responses_request(
        adapter=adapter,
        messages=[
            ChatMessage(role="system", content="You are helpful."),
            ChatMessage(role="user", content="填写当前数据集表单"),
            ChatMessage(
                role="assistant",
                content="",
                tool_calls=[
                    {
                        "id": "fc_form_1",
                        "call_id": "call_form_1",
                        "type": "function",
                        "function": {
                            "name": "crm_update_record",
                            "arguments": '{"fields":{"name":"E2E-Test-001"}}',
                        },
                    }
                ],
            ),
            ChatMessage(role="tool", content='{"ok":true}', tool_call_id="call_form_1"),
        ],
        model="gpt-5.4-xhigh",
        tools=[{"type": "function", "function": {"name": "crm_update_record", "parameters": {}}}],
        tool_choice="required",
        stream=True,
        kwargs={},
        reasoning_summary_model_prefixes=("gpt-5",),
    )

    assert request["input"][1] == {
        "type": "function_call",
        "call_id": "call_form_1",
        "id": "fc_form_1",
        "name": "crm_update_record",
        "arguments": '{"fields":{"name":"E2E-Test-001"}}',
        "status": "completed",
    }
    assert request["input"][2] == {
        "type": "function_call_output",
        "call_id": "call_form_1",
        "output": '{"ok":true}',
    }


@pytest.mark.asyncio
async def test_build_responses_request_drops_previous_response_id_after_tool_round_recovery_prompt() -> (
    None
):
    adapter = _BuilderAdapterStub()

    request = await build_responses_request(
        adapter=adapter,
        messages=[
            ChatMessage(role="system", content="You are helpful."),
            ChatMessage(role="user", content="请搜索当前数据集"),
            ChatMessage(
                role="assistant",
                content="",
                tool_calls=[
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {"name": "crm_update_record", "arguments": '{"target":"x"}'},
                    }
                ],
                metadata={
                    "protocol_path": "responses",
                    "responses_response_id": "resp_tool_round_1",
                },
            ),
            ChatMessage(role="tool", content='{"ok":true}', tool_call_id="call_1"),
            ChatMessage(role="system", content="Only continue the unfinished page intent."),
        ],
        model="gpt-5.4-xhigh",
        tools=[{"type": "function", "function": {"name": "crm_update_record", "parameters": {}}}],
        tool_choice="required",
        kwargs={},
        reasoning_summary_model_prefixes=("gpt-5",),
    )

    assert "previous_response_id" not in request
    assert request["instructions"] == (
        "You are helpful.\n\nOnly continue the unfinished page intent."
    )
    assert [message.role for message in adapter.converted_messages] == [
        "user",
        "assistant",
        "tool",
    ]
