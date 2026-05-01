"""
Test type: behavioral
Scope: OpenAI-compatible adapter responses/chat protocol handling and error mapping.
Mocked dependencies: OpenAI clients and HTTP responses are local fakes; adapter
mapping/recovery logic executes real code.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from openai import BadRequestError, PermissionDeniedError, RateLimitError

from app.ai.adapters.openai_adapter import OpenAIAdapter
from app.ai.adapters.openai_compatible.support.usage_support import (
    RESPONSES_USAGE_RETRIEVE_TIMEOUT_SECONDS,
)
from app.ai.exceptions import (
    ProviderAuthError,
    ProviderConnectionError,
    ProviderError,
    ProviderRateLimitError,
    ProviderTimeoutError,
    convert_openai_error,
)
from app.ai.runtime.protocol_recovery_policy import ProtocolRecoveryPolicy
from app.ai.runtime.query_engine import ConversationQueryEngine
from app.ai.types import ChatChunk, ChatMessage, ChatResponse


class _FakeStatusError(Exception):
    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.response = SimpleNamespace(
            status_code=status_code,
            text=message,
            headers={"content-type": "application/json"},
            request=SimpleNamespace(url="https://api.example.com/responses"),
        )


class _FakeChatCompletions:
    def __init__(self, response):
        self.response = response
        self.last_kwargs = None

    async def create(self, **kwargs):
        self.last_kwargs = kwargs
        return self.response


class _FakeResponses:
    def __init__(self, response):
        self.response = response
        self.last_kwargs = None

    async def create(self, **kwargs):
        self.last_kwargs = kwargs
        return self.response


class _FakeChatCompletionsStream:
    def __init__(self, events):
        self._events = events
        self.aclose_called = False

    def __aiter__(self):
        self._iter = iter(self._events)
        return self

    async def __anext__(self):
        try:
            return next(self._iter)
        except StopIteration as exc:
            raise StopAsyncIteration from exc

    async def aclose(self) -> None:
        self.aclose_called = True


class _FakeClient:
    def __init__(self, chat_response, responses_response):
        self.chat = SimpleNamespace(completions=_FakeChatCompletions(chat_response))
        self.responses = _FakeResponses(responses_response)


class _FakeClientWithOptions:
    def __init__(self, chat_response, responses_response):
        self.chat = SimpleNamespace(completions=_FakeChatCompletions(chat_response))
        self.responses = _FakeResponses(responses_response)
        self.with_options_calls: list[dict[str, object]] = []

    def with_options(self, **kwargs):
        self.with_options_calls.append(dict(kwargs))
        return self


def _make_responses_message(text: str):
    return SimpleNamespace(
        type="message",
        content=[SimpleNamespace(type="output_text", text=text)],
    )


def _make_responses_function_call(name: str, arguments: str, call_id: str):
    return SimpleNamespace(
        type="function_call",
        name=name,
        arguments=arguments,
        call_id=call_id,
        id=call_id,
    )


def _make_chat_completion_response(text: str = "ok"):
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    role="assistant",
                    content=text,
                    tool_calls=None,
                ),
                finish_reason="stop",
            )
        ],
        usage=SimpleNamespace(prompt_tokens=3, completion_tokens=2, total_tokens=5),
        model_dump=lambda: {"ok": True},
    )


def _make_openai_rate_limit_error(
    message: str = "too many concurrent sessions",
) -> RateLimitError:
    request = httpx.Request("POST", "https://api.example.com/v1/responses")
    response = httpx.Response(429, request=request)
    return RateLimitError(
        "Error code: 429",
        response=response,
        body={
            "type": "rate_limit_error",
            "message": message,
            "code": "rate_limit_exceeded",
        },
    )


def _responses_cross_protocol_provider_config() -> dict[str, object]:
    return {
        "wire_api": "responses",
        "protocol_capabilities": {
            "allowed_wire_apis": ["responses", "chat_completions"],
            "allow_adapter_cross_protocol_fallback": True,
        },
    }


_RESPONSES_TOOL_FALLBACK_DISABLED = {"0", "false", "no", "off"}


def _responses_tool_call_fallback_enabled(
    provider_config: dict[str, object] | None,
) -> bool:
    raw_value = (provider_config or {}).get("responses_tool_call_fallback_enabled")
    if raw_value is None:
        return True
    if isinstance(raw_value, bool):
        return raw_value
    return str(raw_value).strip().lower() not in _RESPONSES_TOOL_FALLBACK_DISABLED


def test_adapter_rejects_primary_not_in_allowed_wire_apis() -> None:
    with pytest.raises(ProviderError) as exc:
        OpenAIAdapter(
            api_key="test-key",
            base_url="https://api.example.com",
            provider_config={
                "protocol_capabilities": {
                    "primary_wire_api": "responses",
                    "allowed_wire_apis": ["chat_completions"],
                }
            },
        )

    assert exc.value.error_code == "invalid_protocol_contract"


def test_convert_openai_rate_limit_preserves_provider_message() -> None:
    request = httpx.Request("POST", "https://api.example.com/v1/responses")
    response = httpx.Response(429, request=request)
    error = RateLimitError(
        "Error code: 429",
        response=response,
        body={
            "type": "rate_limit_error",
            "message": "并发 Session 超限：当前 3 个（限制：3 个）。",
            "code": "rate_limit_exceeded",
        },
    )

    converted = convert_openai_error(
        error,
        provider_code="openai_compatible",
        model_code="gpt-5.4",
    )

    assert isinstance(converted, ProviderRateLimitError)
    assert str(converted) == "并发 Session 超限：当前 3 个（限制：3 个）。"


def test_convert_openai_permission_denied_preserves_provider_message_and_status() -> (
    None
):
    request = httpx.Request("POST", "https://api.example.com/v1/responses")
    response = httpx.Response(403, request=request)
    error = PermissionDeniedError(
        "Error code: 403",
        response=response,
        body={
            "type": "invalid_request_error",
            "message": "余额不足，请充值后再试。",
            "code": "insufficient_quota",
        },
    )

    converted = convert_openai_error(
        error,
        provider_code="openai_compatible",
        model_code="gpt-5.4",
    )

    assert isinstance(converted, ProviderAuthError)
    assert converted.status_code == 403
    assert converted.error_code == "insufficient_quota"
    assert str(converted) == "余额不足，请充值后再试。"


def test_convert_openai_bad_request_preserves_non_5xx_status_on_provider_error() -> (
    None
):
    request = httpx.Request("POST", "https://api.example.com/v1/responses")
    response = httpx.Response(400, request=request)
    error = BadRequestError(
        "Error code: 400",
        response=response,
        body={
            "type": "invalid_request_error",
            "message": "messages 不能为空",
            "code": "invalid_request_error",
        },
    )

    converted = convert_openai_error(
        error,
        provider_code="openai_compatible",
        model_code="gpt-5.4",
    )

    assert isinstance(converted, ProviderError)
    assert converted.status_code == 400
    assert converted.error_code == "invalid_request_error"
    assert str(converted) == "messages 不能为空"


def test_responses_rate_limit_does_not_cross_protocol_fallback() -> None:
    adapter = OpenAIAdapter(api_key="test-key", base_url="https://api.example.com")

    assert (
        ProtocolRecoveryPolicy.should_cross_protocol_fallback_from_responses_error(
            capabilities=adapter.protocol_capabilities,
            error=_make_openai_rate_limit_error(),
            tools=[
                {
                    "type": "function",
                    "function": {"name": "crm_lookup", "parameters": {}},
                }
            ],
            tool_choice="required",
            use_responses_api=True,
            fallback_switch_enabled=_responses_tool_call_fallback_enabled(
                adapter.provider_config,
            ),
        )
        is False
    )


def test_responses_timeout_does_not_cross_protocol_fallback() -> None:
    adapter = OpenAIAdapter(
        api_key="test-key",
        base_url="https://api.example.com",
        provider_config=_responses_cross_protocol_provider_config(),
    )

    assert (
        ProtocolRecoveryPolicy.should_cross_protocol_fallback_from_responses_error(
            capabilities=adapter.protocol_capabilities,
            error=ProviderTimeoutError(
                "provider timed out",
                provider_code="openai_compatible",
                model_code="gpt-5.4",
            ),
            tools=[
                {
                    "type": "function",
                    "function": {"name": "crm_lookup", "parameters": {}},
                }
            ],
            tool_choice="required",
            use_responses_api=True,
            fallback_switch_enabled=_responses_tool_call_fallback_enabled(
                adapter.provider_config,
            ),
        )
        is False
    )


def test_rate_limit_stream_error_skips_sync_rescue() -> None:
    assert ProtocolRecoveryPolicy.should_skip_sync_rescue_after_stream_error(
        _make_openai_rate_limit_error()
    )


@pytest.mark.asyncio
async def test_chat_applies_runtime_reasoning_override_to_responses_request() -> None:
    adapter = OpenAIAdapter(
        api_key="test-key",
        base_url="https://api.example.com",
        provider_config={"wire_api": "responses"},
    )
    response_obj = SimpleNamespace(
        object="response",
        status="completed",
        usage=SimpleNamespace(input_tokens=12, output_tokens=8, total_tokens=20),
        output=[_make_responses_message("hello from responses")],
        output_text="hello from responses",
        model_dump=lambda: {"ok": True},
    )
    adapter.client = _FakeClient(
        chat_response=_make_chat_completion_response(),
        responses_response=response_obj,
    )

    result = await adapter.chat(
        messages=[ChatMessage(role="user", content="hello")],
        model="gpt-5.4-xhigh",
        _runtime_reasoning_effort_override="low",
    )

    assert result.metadata["effective_reasoning_effort"] == "low"
    assert adapter.client.responses.last_kwargs is not None
    assert adapter.client.responses.last_kwargs["reasoning"]["effort"] == "low"


@pytest.mark.asyncio
async def test_chat_falls_back_to_responses_when_chat_payload_has_no_choices() -> None:
    adapter = OpenAIAdapter(
        api_key="test-key",
        base_url="https://api.example.com",
        provider_config={
            "wire_api": "chat_completions",
            "protocol_capabilities": {
                "allowed_wire_apis": ["chat_completions", "responses"],
                "allow_adapter_cross_protocol_fallback": True,
            },
        },
    )
    response_obj = SimpleNamespace(
        object="response",
        status="completed",
        usage=SimpleNamespace(input_tokens=12, output_tokens=8, total_tokens=20),
        output=[
            _make_responses_message("hello from responses"),
            _make_responses_function_call(
                "lookup_weather", '{"city":"Shanghai"}', "call_1"
            ),
        ],
        output_text="hello from responses",
        model_dump=lambda: {"ok": True},
    )
    # Misrouted: chat.completions returns a Responses-shaped body (no choices) / 误走路由：chat 返回 Responses 形响应
    adapter.client = _FakeClient(
        chat_response=response_obj, responses_response=response_obj
    )


@pytest.mark.asyncio
async def test_chat_public_entrypoint_does_not_fallback_to_responses_on_misrouted_payload() -> (
    None
):
    adapter = OpenAIAdapter(
        api_key="test-key",
        base_url="https://api.example.com",
        provider_config={
            "wire_api": "chat_completions",
            "protocol_capabilities": {
                "allowed_wire_apis": ["chat_completions", "responses"],
                "allow_adapter_cross_protocol_fallback": True,
            },
        },
    )
    response_obj = SimpleNamespace(
        object="response",
        status="completed",
        usage=SimpleNamespace(input_tokens=12, output_tokens=8, total_tokens=20),
        output=[_make_responses_message("hello from responses")],
        output_text="hello from responses",
        model_dump=lambda: {"ok": True},
    )
    adapter.client = _FakeClient(
        chat_response=response_obj,
        responses_response=SimpleNamespace(output_text="should not be used"),
    )

    with pytest.raises(ProviderError, match="AI 请求失败"):
        await adapter.chat(
            messages=[ChatMessage(role="user", content="hello")],
            model="gpt-5.4-xhigh",
        )

    assert adapter.client.responses.last_kwargs is None


@pytest.mark.asyncio
async def test_stream_chat_public_entrypoint_does_not_fallback_to_responses_on_misrouted_payload() -> (
    None
):
    adapter = OpenAIAdapter(
        api_key="test-key",
        base_url="https://api.example.com",
        provider_config={
            "wire_api": "chat_completions",
            "protocol_capabilities": {
                "allowed_wire_apis": ["chat_completions", "responses"],
                "allow_adapter_cross_protocol_fallback": True,
            },
        },
    )
    response_obj = SimpleNamespace(
        object="response",
        status="completed",
        usage=SimpleNamespace(input_tokens=12, output_tokens=8, total_tokens=20),
        output=[_make_responses_message("hello from responses")],
        output_text="hello from responses",
        model_dump=lambda: {"ok": True},
    )
    misrouted_stream = _FakeChatCompletionsStream([response_obj])
    adapter.client = SimpleNamespace(
        chat=SimpleNamespace(completions=_FakeChatCompletions(misrouted_stream)),
        responses=_FakeResponses(SimpleNamespace(output_text="should not be used")),
    )

    with pytest.raises(ProviderError, match="AI 请求失败"):
        async for _ in adapter.stream_chat(
            messages=[ChatMessage(role="user", content="hello")],
            model="gpt-5.4-xhigh",
        ):
            pass

    assert adapter.client.responses.last_kwargs is None


@pytest.mark.asyncio
async def test_chat_does_not_fallback_when_payload_is_plain_html() -> None:
    """HTML or non-Responses garbage must not trigger responses.create / 非 Responses 结构不二次请求。"""
    adapter = OpenAIAdapter(api_key="test-key", base_url="https://api.example.com")
    adapter.client = _FakeClient(
        chat_response="<!doctype html><html></html>",
        responses_response=SimpleNamespace(output_text="should not be used"),
    )
    adapter._chat_completions_v1_retry_client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=_FakeChatCompletions("<!doctype html><html></html>"),
        ),
    )
    adapter._chat_completions_v1_retry_base_url = "https://api.example.com/v1"
    with pytest.raises(ProviderError, match="AI 请求失败"):
        await adapter.chat(
            messages=[ChatMessage(role="user", content="hello")],
            model="gpt-4",
        )


@pytest.mark.asyncio
async def test_chat_accepts_plain_text_response_from_chat_completions_gateway() -> None:
    adapter = OpenAIAdapter(api_key="test-key", base_url="https://api.example.com")
    adapter.client = _FakeClient(
        chat_response="raw text reply from gateway",
        responses_response=SimpleNamespace(output_text="should not be used"),
    )

    result = await adapter.chat(
        messages=[ChatMessage(role="user", content="hello")],
        model="gpt-4",
    )

    assert result.message.content == "raw text reply from gateway"
    assert result.metadata["protocol_path"] == "chat_completions"
    assert result.metadata["response_shape"] == "raw_text"


@pytest.mark.asyncio
async def test_chat_retries_chat_completions_with_v1_when_root_endpoint_returns_html() -> (
    None
):
    adapter = OpenAIAdapter(
        api_key="test-key",
        base_url="https://codex.2api.com.cn",
    )
    adapter.client = _FakeClient(
        chat_response="<!doctype html><html></html>",
        responses_response=SimpleNamespace(output_text="should not be used"),
    )
    retry_completions = _FakeChatCompletions(
        _make_chat_completion_response("v1 retry ok"),
    )
    adapter._chat_completions_v1_retry_client = SimpleNamespace(
        chat=SimpleNamespace(completions=retry_completions),
    )
    adapter._chat_completions_v1_retry_base_url = "https://codex.2api.com.cn/v1"

    result = await adapter.chat(
        messages=[ChatMessage(role="user", content="hello")],
        model="gpt-5.4-xhigh",
    )

    assert result.message.content == "v1 retry ok"
    assert retry_completions.last_kwargs is not None


@pytest.mark.asyncio
async def test_chat_does_not_fallback_on_error_payload_without_choices() -> None:
    adapter = OpenAIAdapter(api_key="test-key", base_url="https://api.example.com")
    adapter.client = _FakeClient(
        chat_response=SimpleNamespace(
            error={"message": "invalid", "type": "invalid_request_error"}
        ),
        responses_response=SimpleNamespace(output_text="should not be used"),
    )
    with pytest.raises(ProviderError, match="AI 请求失败"):
        await adapter.chat(
            messages=[ChatMessage(role="user", content="hello")],
            model="gpt-4",
        )


@pytest.mark.asyncio
async def test_chat_forwards_required_tool_choice_and_subset_tools_to_chat_completions() -> (
    None
):
    adapter = OpenAIAdapter(api_key="test-key", base_url="https://api.example.com")
    completions = _FakeChatCompletions(_make_chat_completion_response())
    adapter.client = SimpleNamespace(
        chat=SimpleNamespace(completions=completions),
        responses=_FakeResponses(None),
    )

    await adapter.chat(
        messages=[ChatMessage(role="user", content="hello")],
        model="gpt-5.4-xhigh",
        tools=[
            {"type": "function", "function": {"name": "web_search", "parameters": {}}},
            {"type": "function", "function": {"name": "fetch_url", "parameters": {}}},
        ],
        tool_choice="required",
    )

    assert completions.last_kwargs is not None
    assert completions.last_kwargs["tool_choice"] == "required"
    assert [tool["function"]["name"] for tool in completions.last_kwargs["tools"]] == [
        "web_search",
        "fetch_url",
    ]


@pytest.mark.asyncio
async def test_chat_runtime_force_wire_api_uses_responses_path() -> None:
    adapter = OpenAIAdapter(
        api_key="test-key",
        base_url="https://api.example.com",
        provider_config={
            "wire_api": "chat_completions",
            "protocol_capabilities": {
                "allowed_wire_apis": ["chat_completions", "responses"],
                "allow_adapter_cross_protocol_fallback": True,
            },
        },
    )
    response_obj = SimpleNamespace(
        object="response",
        status="completed",
        usage=SimpleNamespace(input_tokens=10, output_tokens=5, total_tokens=15),
        output=[_make_responses_message("forced responses")],
        output_text="forced responses",
        model_dump=lambda: {"ok": True},
    )
    responses_create = AsyncMock(return_value=response_obj)
    completions_create = AsyncMock(
        return_value=_make_chat_completion_response("chat path")
    )
    adapter.client = SimpleNamespace(
        responses=SimpleNamespace(create=responses_create),
        chat=SimpleNamespace(completions=SimpleNamespace(create=completions_create)),
    )

    result = await adapter.chat(
        messages=[ChatMessage(role="user", content="hello")],
        model="gpt-5.4-xhigh",
        _runtime_force_wire_api="responses",
        _runtime_disable_cross_protocol_fallback=True,
    )

    assert result.message.content == "forced responses"
    assert result.metadata["protocol_path"] == "responses"
    assert responses_create.await_count == 1
    assert completions_create.await_count == 0


@pytest.mark.asyncio
async def test_chat_public_entrypoint_keeps_protocol_safe_responses_error_without_legacy_fallback() -> (
    None
):
    adapter = OpenAIAdapter(
        api_key="test-key",
        base_url="https://api.example.com",
        provider_config=_responses_cross_protocol_provider_config(),
    )
    completions = _FakeChatCompletions(_make_chat_completion_response("fallback ok"))
    adapter.client = SimpleNamespace(
        responses=SimpleNamespace(
            create=AsyncMock(
                side_effect=_FakeStatusError(502, "Upstream request failed")
            ),
        ),
        chat=SimpleNamespace(completions=completions),
    )

    with pytest.raises(ProviderError, match="AI 请求失败"):
        await adapter.chat(
            messages=[ChatMessage(role="user", content="hello")],
            model="gpt-5.4-xhigh",
            tools=[
                {
                    "type": "function",
                    "function": {"name": "crm_lookup", "parameters": {}},
                }
            ],
            tool_choice="required",
        )

    assert completions.last_kwargs is None


def test_responses_provider_defaults_to_primary_only_protocol_capabilities() -> None:
    adapter = OpenAIAdapter(
        api_key="test-key",
        base_url="https://api.example.com",
        provider_config={"wire_api": "responses"},
    )

    assert adapter.protocol_capabilities.primary_wire_api == "responses"
    assert adapter.protocol_capabilities.allowed_wire_apis == ("responses",)
    assert adapter.protocol_capabilities.allow_adapter_cross_protocol_fallback is False


def test_nested_protocol_capabilities_without_top_level_wire_api_stays_responses_only() -> (
    None
):
    adapter = OpenAIAdapter(
        api_key="test-key",
        base_url="https://api.example.com",
        provider_config={
            "protocol_capabilities": {
                "allowed_wire_apis": ["responses"],
            },
        },
    )

    assert adapter.protocol_capabilities.primary_wire_api == "responses"
    assert adapter.protocol_capabilities.allowed_wire_apis == ("responses",)
    assert adapter.protocol_capabilities.allow_adapter_cross_protocol_fallback is False


def test_nested_protocol_capabilities_without_top_level_wire_api_preserves_first_allowed_primary() -> (
    None
):
    adapter = OpenAIAdapter(
        api_key="test-key",
        base_url="https://api.example.com",
        provider_config={
            "protocol_capabilities": {
                "allowed_wire_apis": ["responses", "chat_completions"],
            },
        },
    )

    assert adapter.protocol_capabilities.primary_wire_api == "responses"
    assert adapter.protocol_capabilities.allowed_wire_apis == (
        "responses",
        "chat_completions",
    )


def test_top_level_wire_api_respected_when_supported_by_nested_protocol_contract() -> (
    None
):
    adapter = OpenAIAdapter(
        api_key="test-key",
        base_url="https://api.example.com",
        provider_config={
            "wire_api": "responses",
            "protocol_capabilities": {
                "allowed_wire_apis": ["chat_completions", "responses"],
            },
        },
    )

    assert adapter.protocol_capabilities.primary_wire_api == "responses"
    assert adapter.protocol_capabilities.allowed_wire_apis == (
        "responses",
        "chat_completions",
    )


def test_conflicting_top_level_wire_api_does_not_widen_nested_responses_only_contract() -> (
    None
):
    adapter = OpenAIAdapter(
        api_key="test-key",
        base_url="https://api.example.com",
        provider_config={
            "wire_api": "chat_completions",
            "protocol_capabilities": {
                "allowed_wire_apis": ["responses"],
            },
        },
    )

    assert adapter.protocol_capabilities.primary_wire_api == "responses"
    assert adapter.protocol_capabilities.allowed_wire_apis == ("responses",)
    assert adapter.protocol_capabilities.allow_adapter_cross_protocol_fallback is False


def test_invalid_protocol_token_in_allowed_wire_apis_raises_provider_error() -> None:
    with pytest.raises(
        ProviderError, match="Invalid provider protocol contract wire API"
    ):
        OpenAIAdapter(
            api_key="test-key",
            base_url="https://api.example.com",
            provider_config={
                "protocol_capabilities": {
                    "allowed_wire_apis": ["respones"],
                },
            },
        )


def test_invalid_top_level_wire_api_raises_provider_error() -> None:
    with pytest.raises(ProviderError, match="Invalid provider wire API in wire_api"):
        OpenAIAdapter(
            api_key="test-key",
            base_url="https://api.example.com",
            provider_config={
                "wire_api": "chat_completionz",
            },
        )


def test_invalid_protocol_token_in_fallback_map_raises_provider_error() -> None:
    with pytest.raises(
        ProviderError, match="Invalid provider protocol contract wire API"
    ):
        OpenAIAdapter(
            api_key="test-key",
            base_url="https://api.example.com",
            provider_config={
                "protocol_capabilities": {
                    "allowed_cross_protocol_fallbacks": {
                        "responses": ["chat_completionz"],
                    },
                },
            },
        )


def test_runtime_query_engine_default_responses_provider_plans_responses_only_protocol() -> (
    None
):
    adapter = OpenAIAdapter(
        api_key="test-key",
        base_url="https://api.example.com",
        provider_config={"wire_api": "responses"},
    )

    plan = ConversationQueryEngine(
        adapter=adapter, strict_contract=False
    ).planner.plan_turn(
        tools=[
            {
                "type": "function",
                "function": {"name": "web_search", "parameters": {}},
            }
        ],
    )

    assert plan.protocol_chain == ["responses"]


@pytest.mark.asyncio
async def test_runtime_force_wire_api_rejects_unsupported_protocol_for_responses_only_provider() -> (
    None
):
    adapter = OpenAIAdapter(
        api_key="test-key",
        base_url="https://api.example.com",
        provider_config={
            "wire_api": "responses",
            "protocol_capabilities": {
                "allowed_wire_apis": ["responses"],
                "allow_adapter_cross_protocol_fallback": False,
            },
        },
    )
    adapter.client = _FakeClient(
        chat_response=_make_chat_completion_response(),
        responses_response=SimpleNamespace(output_text="should not be used"),
    )

    with pytest.raises(
        ProviderError,
        match="requested wire API: chat_completions",
    ):
        await adapter.chat(
            messages=[ChatMessage(role="user", content="hello")],
            model="gpt-5.4-xhigh",
            _runtime_force_wire_api="chat_completions",
        )


@pytest.mark.asyncio
async def test_runtime_force_wire_api_rejects_unsupported_protocol_for_nested_responses_only_contract() -> (
    None
):
    adapter = OpenAIAdapter(
        api_key="test-key",
        base_url="https://api.example.com",
        provider_config={
            "protocol_capabilities": {
                "allowed_wire_apis": ["responses"],
                "allow_adapter_cross_protocol_fallback": False,
            },
        },
    )
    adapter.client = _FakeClient(
        chat_response=_make_chat_completion_response(),
        responses_response=SimpleNamespace(output_text="should not be used"),
    )

    with pytest.raises(
        ProviderError,
        match="requested wire API: chat_completions",
    ):
        await adapter.chat(
            messages=[ChatMessage(role="user", content="hello")],
            model="gpt-5.4-xhigh",
            _runtime_force_wire_api="chat_completions",
        )


def _fake_chat_completion_chunk(delta_text: str, finish_reason: str | None = None):
    choice = SimpleNamespace(
        delta=SimpleNamespace(
            content=delta_text,
            reasoning_content=None,
            role=None,
            tool_calls=None,
        ),
        finish_reason=finish_reason,
    )
    return SimpleNamespace(choices=[choice], usage=None)


class _FakeChatStream:
    def __init__(self, chunks: list):
        self._chunks = list(chunks)
        self._iter = iter(self._chunks)
        self.aclose_called = False

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            return next(self._iter)
        except StopIteration as exc:
            raise StopAsyncIteration from exc

    async def aclose(self) -> None:
        self.aclose_called = True


class _FakeResponsesStream:
    def __init__(self, events: list):
        self._events = list(events)
        self._iter = iter(self._events)
        self.aclose_called = False

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            return next(self._iter)
        except StopIteration as exc:
            raise StopAsyncIteration from exc

    async def aclose(self) -> None:
        self.aclose_called = True


@pytest.mark.asyncio
async def test_stream_chat_chat_completions_breaks_on_finish_reason_and_acloses() -> (
    None
):
    adapter = OpenAIAdapter(api_key="test-key", base_url="https://api.example.com")
    poison = object()
    stream = _FakeChatStream(
        [
            _fake_chat_completion_chunk("hi", None),
            _fake_chat_completion_chunk("", "stop"),
            poison,
        ]
    )
    adapter.client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(create=AsyncMock(return_value=stream))
        ),
        responses=SimpleNamespace(create=AsyncMock()),
    )

    chunks: list = []
    async for chunk in adapter.stream_chat(
        messages=[ChatMessage(role="user", content="hello")],
        model="gpt-4",
    ):
        chunks.append(chunk)

    assert "".join(c.delta for c in chunks) == "hi"
    assert chunks[-1].finish_reason == "stop"
    assert stream.aclose_called is True


@pytest.mark.asyncio
async def test_stream_chat_chat_completions_maps_timeout_seconds_to_timeout() -> None:
    adapter = OpenAIAdapter(api_key="test-key", base_url="https://api.example.com")
    stream = _FakeChatStream(
        [
            _fake_chat_completion_chunk("hi", None),
            _fake_chat_completion_chunk("", "stop"),
        ]
    )
    chat_create = AsyncMock(return_value=stream)
    adapter.client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=chat_create)),
        responses=SimpleNamespace(create=AsyncMock()),
    )

    chunks: list[ChatChunk] = []
    async for chunk in adapter.stream_chat(
        messages=[ChatMessage(role="user", content="hello")],
        model="gpt-4",
        timeout_seconds=7,
    ):
        chunks.append(chunk)

    assert "".join(chunk.delta for chunk in chunks) == "hi"
    assert chunks[-1].finish_reason == "stop"
    assert chat_create.await_args is not None
    assert chat_create.await_args.kwargs["timeout"] == 7.0
    assert "timeout_seconds" not in chat_create.await_args.kwargs
    assert stream.aclose_called is True


@pytest.mark.asyncio
async def test_chat_responses_maps_timeout_seconds_to_timeout() -> None:
    adapter = OpenAIAdapter(
        api_key="test-key",
        base_url="https://api.example.com",
        provider_config={"wire_api": "responses"},
    )
    response_obj = SimpleNamespace(
        id="resp_sync_1",
        object="response",
        status="completed",
        usage=SimpleNamespace(input_tokens=3, output_tokens=2, total_tokens=5),
        output=[_make_responses_message("OK")],
        output_text="OK",
        model_dump=lambda: {"ok": True},
    )
    responses_create = AsyncMock(return_value=response_obj)
    adapter.client = SimpleNamespace(
        responses=SimpleNamespace(create=responses_create),
        chat=SimpleNamespace(completions=SimpleNamespace(create=AsyncMock())),
    )

    response = await adapter.chat(
        messages=[ChatMessage(role="user", content="hello")],
        model="gpt-5.4-xhigh",
        timeout_seconds=7,
    )

    assert response.message.content == "OK"
    assert response.metadata["protocol_path"] == "responses"
    assert response.metadata["responses_response_id"] == "resp_sync_1"
    assert responses_create.await_args is not None
    assert responses_create.await_args.kwargs["timeout"] == 7.0
    assert "timeout_seconds" not in responses_create.await_args.kwargs


@pytest.mark.asyncio
async def test_stream_chat_responses_defaults_timeout_without_timeout_seconds_payload() -> (
    None
):
    adapter = OpenAIAdapter(
        api_key="test-key",
        base_url="https://api.example.com",
        provider_config={"wire_api": "responses"},
    )
    completed_response = SimpleNamespace(
        usage=SimpleNamespace(input_tokens=11, output_tokens=4, total_tokens=15),
        output_text="OK",
        output=[],
    )
    stream = _FakeResponsesStream(
        [
            SimpleNamespace(type="response.output_text.delta", delta="O"),
            SimpleNamespace(type="response.output_text.delta", delta="K"),
            SimpleNamespace(type="response.completed", response=completed_response),
        ]
    )
    responses_create = AsyncMock(return_value=stream)
    adapter.client = SimpleNamespace(
        responses=SimpleNamespace(create=responses_create),
        chat=SimpleNamespace(completions=SimpleNamespace(create=AsyncMock())),
    )

    chunks: list[ChatChunk] = []
    async for chunk in adapter.stream_chat(
        messages=[ChatMessage(role="user", content="hello")],
        model="gpt-5.4-xhigh",
    ):
        chunks.append(chunk)

    assert "".join(chunk.delta for chunk in chunks) == "OK"
    assert chunks[-1].finish_reason == "stop"
    assert responses_create.await_args is not None
    assert responses_create.await_args.kwargs["timeout"] == 120.0
    assert "timeout_seconds" not in responses_create.await_args.kwargs
    assert stream.aclose_called is True


@pytest.mark.asyncio
async def test_stream_chat_responses_low_reasoning_override_uses_fast_path_timeout_floor() -> (
    None
):
    adapter = OpenAIAdapter(
        api_key="test-key",
        base_url="https://api.example.com",
        provider_config={"wire_api": "responses"},
    )
    completed_response = SimpleNamespace(
        usage=SimpleNamespace(input_tokens=11, output_tokens=4, total_tokens=15),
        output_text="OK",
        output=[],
    )
    stream = _FakeResponsesStream(
        [
            SimpleNamespace(type="response.output_text.delta", delta="O"),
            SimpleNamespace(type="response.output_text.delta", delta="K"),
            SimpleNamespace(type="response.completed", response=completed_response),
        ]
    )
    responses_create = AsyncMock(return_value=stream)
    adapter.client = SimpleNamespace(
        responses=SimpleNamespace(create=responses_create),
        chat=SimpleNamespace(completions=SimpleNamespace(create=AsyncMock())),
    )

    chunks: list[ChatChunk] = []
    async for chunk in adapter.stream_chat(
        messages=[ChatMessage(role="user", content="hello")],
        model="gpt-5.4-xhigh",
        _runtime_reasoning_effort_override="low",
    ):
        chunks.append(chunk)

    assert "".join(chunk.delta for chunk in chunks) == "OK"
    assert chunks[-1].finish_reason == "stop"
    assert responses_create.await_args is not None
    assert responses_create.await_args.kwargs["reasoning"]["effort"] == "low"
    assert responses_create.await_args.kwargs["timeout"] == 60.0
    assert "timeout_seconds" not in responses_create.await_args.kwargs
    assert stream.aclose_called is True


@pytest.mark.asyncio
async def test_stream_chat_public_entrypoint_keeps_protocol_safe_responses_error_without_legacy_rescue() -> (
    None
):
    adapter = OpenAIAdapter(
        api_key="test-key",
        base_url="https://api.example.com",
        provider_config=_responses_cross_protocol_provider_config(),
    )
    chat_create = AsyncMock(
        return_value=_FakeChatStream(
            [
                _fake_chat_completion_chunk("fallback", None),
                _fake_chat_completion_chunk("", "stop"),
            ]
        ),
    )
    adapter.client = SimpleNamespace(
        responses=SimpleNamespace(
            create=AsyncMock(
                side_effect=_FakeStatusError(502, "Upstream request failed")
            ),
        ),
        chat=SimpleNamespace(completions=SimpleNamespace(create=chat_create)),
    )

    with pytest.raises(ProviderError, match="AI 请求失败"):
        async for _ in adapter.stream_chat(
            messages=[ChatMessage(role="user", content="hello")],
            model="gpt-5.4-xhigh",
            tools=[
                {
                    "type": "function",
                    "function": {"name": "crm_lookup", "parameters": {}},
                }
            ],
            tool_choice="required",
        ):
            pass

    assert chat_create.await_count == 0


@pytest.mark.asyncio
async def test_stream_chat_responses_native_web_search_emits_progress_chunk() -> None:
    class _FakeResponsesStream:
        def __init__(self, events):
            self._events = events
            self.aclose_called = False

        def __aiter__(self):
            self._iter = iter(self._events)
            return self

        async def __anext__(self):
            try:
                return next(self._iter)
            except StopIteration as exc:
                raise StopAsyncIteration from exc

        async def aclose(self) -> None:
            self.aclose_called = True

    adapter = OpenAIAdapter(
        api_key="test-key",
        base_url="https://api.example.com",
        provider_config={"wire_api": "responses"},
    )
    rs = _FakeResponsesStream(
        [
            SimpleNamespace(type="response.web_search_call.in_progress"),
            SimpleNamespace(type="response.output_text.delta", delta="A"),
            SimpleNamespace(
                type="response.output_text.done",
                text="",
                usage=SimpleNamespace(input_tokens=2, output_tokens=3, total_tokens=5),
            ),
        ]
    )
    adapter.client = SimpleNamespace(
        responses=SimpleNamespace(create=_FakeResponses(rs).create),
        chat=SimpleNamespace(completions=_FakeChatCompletions(None)),
    )

    chunks = []
    async for chunk in adapter.stream_chat(
        messages=[ChatMessage(role="user", content="hello")],
        model="gpt-5.4-xhigh",
    ):
        chunks.append(chunk)

    progress_idx = next(
        index
        for index, chunk in enumerate(chunks)
        if (chunk.metadata or {}).get("web_search_in_progress")
    )
    text_idx = next(index for index, chunk in enumerate(chunks) if chunk.delta == "A")

    assert progress_idx < text_idx
    assert chunks[-1].finish_reason == "stop"
    assert rs.aclose_called is True


class _RuntimeFakeAdapter:
    def __init__(
        self,
        *,
        wire_api: str = "responses",
        protocol_capabilities: object | None = None,
    ):
        self.wire_api = wire_api
        self.protocol_capabilities = protocol_capabilities
        self.stream_calls: list[dict] = []
        self.chat_calls: list[dict] = []
        self._stream_behaviors: dict[str, list] = {
            "responses": [],
            "chat_completions": [],
        }
        self._chat_behaviors: dict[str, object] = {
            "responses": None,
            "chat_completions": None,
        }

    def set_stream(self, protocol: str, chunks: list) -> None:
        self._stream_behaviors[protocol] = list(chunks)

    def set_chat(self, protocol: str, response: object) -> None:
        self._chat_behaviors[protocol] = response

    async def stream_chat(self, **kwargs):
        forced = kwargs.get("_runtime_force_wire_api") or self.wire_api
        protocol = (
            "responses" if str(forced).startswith("responses") else "chat_completions"
        )
        self.stream_calls.append({"protocol": protocol, **kwargs})
        for chunk in list(self._stream_behaviors.get(protocol, [])):
            if isinstance(chunk, Exception):
                raise chunk
            yield chunk

    async def chat(self, **kwargs):
        forced = kwargs.get("_runtime_force_wire_api") or self.wire_api
        protocol = (
            "responses" if str(forced).startswith("responses") else "chat_completions"
        )
        self.chat_calls.append({"protocol": protocol, **kwargs})
        result = self._chat_behaviors.get(protocol)
        if isinstance(result, Exception):
            raise result
        return result


class _ProtocolOnlyRuntimeAdapter(_RuntimeFakeAdapter):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.protocol_chat_calls: list[dict] = []
        self.protocol_stream_calls: list[dict] = []

    async def execute_protocol_chat(self, *, wire_api: str, **kwargs):
        protocol = (
            "responses" if str(wire_api).startswith("responses") else "chat_completions"
        )
        self.protocol_chat_calls.append({"protocol": protocol, **kwargs})
        result = self._chat_behaviors.get(protocol)
        if isinstance(result, Exception):
            raise result
        return result

    async def execute_protocol_stream(self, *, wire_api: str, **kwargs):
        protocol = (
            "responses" if str(wire_api).startswith("responses") else "chat_completions"
        )
        self.protocol_stream_calls.append({"protocol": protocol, **kwargs})
        for chunk in list(self._stream_behaviors.get(protocol, [])):
            if isinstance(chunk, Exception):
                raise chunk
            yield chunk

    async def chat(self, **_kwargs):
        raise AssertionError("ProtocolRunner should use execute_protocol_chat()")

    async def stream_chat(self, **_kwargs):
        raise AssertionError("ProtocolRunner should use execute_protocol_stream()")


@pytest.mark.asyncio
async def test_runtime_query_engine_required_empty_without_tool_calls_fails() -> None:
    adapter = _RuntimeFakeAdapter(wire_api="chat_completions")
    adapter.set_stream(
        "chat_completions",
        [
            SimpleNamespace(
                delta="",
                tool_calls=None,
                metadata={},
                input_tokens=None,
                output_tokens=None,
                total_tokens=None,
            )
        ],
    )
    query_engine = ConversationQueryEngine(adapter=adapter, strict_contract=True)

    with pytest.raises(RuntimeError, match="required_tool_round_empty_no_tool_calls"):
        await query_engine.run_stream_turn(
            messages=[ChatMessage(role="user", content="请调用工具")],
            model="gpt-5.4-xhigh",
            temperature=0.7,
            max_tokens=None,
            top_p=1.0,
            tools=[
                {
                    "type": "function",
                    "function": {"name": "web_search", "parameters": {}},
                }
            ],
            tool_choice="required",
            supports_vision=True,
            supports_audio=False,
            supports_video=False,
        )


@pytest.mark.asyncio
async def test_runtime_query_engine_uses_protocol_specific_adapter_entrypoints() -> (
    None
):
    adapter = _ProtocolOnlyRuntimeAdapter(
        wire_api="responses",
        protocol_capabilities=SimpleNamespace(
            primary_wire_api="responses",
            allowed_wire_apis=("responses",),
            allowed_cross_protocol_fallbacks={},
            allow_adapter_cross_protocol_fallback=False,
        ),
    )
    adapter.set_chat(
        "responses",
        ChatResponse(
            message=ChatMessage(role="assistant", content="hello from protocol client"),
            finish_reason="stop",
            model="gpt-5.4-xhigh",
        ),
    )
    query_engine = ConversationQueryEngine(adapter=adapter, strict_contract=False)

    response = await query_engine.run_chat_turn(
        messages=[ChatMessage(role="user", content="hello")],
        model="gpt-5.4-xhigh",
        temperature=0.7,
        max_tokens=None,
        top_p=1.0,
        tools=None,
        tool_choice=None,
        supports_vision=True,
        supports_audio=False,
        supports_video=False,
    )

    assert response.message.content == "hello from protocol client"
    assert [call["protocol"] for call in adapter.protocol_chat_calls] == ["responses"]
    assert adapter.chat_calls == []


@pytest.mark.asyncio
async def test_runtime_query_engine_uses_protocol_specific_stream_entrypoint() -> None:
    adapter = _ProtocolOnlyRuntimeAdapter(
        wire_api="responses",
        protocol_capabilities=SimpleNamespace(
            primary_wire_api="responses",
            allowed_wire_apis=("responses",),
            allowed_cross_protocol_fallbacks={},
            allow_adapter_cross_protocol_fallback=False,
        ),
    )
    adapter.set_stream(
        "responses",
        [
            ChatChunk(delta="hello from stream"),
            ChatChunk(delta="", finish_reason="stop", total_tokens=5),
        ],
    )
    query_engine = ConversationQueryEngine(adapter=adapter, strict_contract=False)

    chunks = [
        chunk
        async for chunk in query_engine.iter_stream_turn(
            messages=[ChatMessage(role="user", content="hello")],
            model="gpt-5.4-xhigh",
            temperature=0.7,
            max_tokens=None,
            top_p=1.0,
            tools=None,
            tool_choice=None,
            supports_vision=True,
            supports_audio=False,
            supports_video=False,
        )
    ]

    assert "".join(chunk.delta for chunk in chunks) == "hello from stream"
    assert [call["protocol"] for call in adapter.protocol_stream_calls] == ["responses"]
    assert adapter.stream_calls == []


@pytest.mark.asyncio
async def test_runtime_query_engine_iter_stream_turn_yields_progress_before_final_text() -> (
    None
):
    adapter = _RuntimeFakeAdapter(wire_api="responses")
    adapter.set_stream(
        "responses",
        [
            ChatChunk(delta="", metadata={"web_search_in_progress": True}),
            ChatChunk(delta="found it"),
            ChatChunk(delta="", finish_reason="stop", total_tokens=5),
        ],
    )
    query_engine = ConversationQueryEngine(adapter=adapter, strict_contract=False)

    chunks = [
        chunk
        async for chunk in query_engine.iter_stream_turn(
            messages=[ChatMessage(role="user", content="继续查")],
            model="gpt-5.4-xhigh",
            temperature=0.7,
            max_tokens=None,
            top_p=1.0,
            tools=[
                {
                    "type": "function",
                    "function": {"name": "web_search", "parameters": {}},
                }
            ],
            tool_choice="auto",
            supports_vision=True,
            supports_audio=False,
            supports_video=False,
        )
    ]

    assert len(chunks) == 3
    assert (chunks[0].metadata or {}).get("web_search_in_progress") is True
    assert chunks[1].delta == "found it"
    assert chunks[2].finish_reason == "stop"
    assert chunks[2].total_tokens == 5
    assert query_engine.turn_record.turn_outcome == "success"
    assert query_engine.turn_record.metadata["stream_progress_event_count"] == 1
    assert query_engine.turn_record.metadata["stream_progress_kinds"] == [
        "web_search_in_progress"
    ]
    assert query_engine.turn_record.provider_events == [
        {
            "kind": "web_search_in_progress",
            "protocol_path": "responses",
            "tool_family": "web_research",
        }
    ]


@pytest.mark.asyncio
async def test_runtime_query_engine_progress_only_stream_sync_rescue_success() -> None:
    adapter = _RuntimeFakeAdapter(wire_api="responses")
    adapter.set_stream(
        "responses",
        [
            ChatChunk(delta="", metadata={"web_search_in_progress": True}),
            ChatChunk(delta="", finish_reason="stop", total_tokens=4),
        ],
    )
    adapter.set_stream("chat_completions", [])
    adapter.set_chat(
        "chat_completions",
        SimpleNamespace(
            message=SimpleNamespace(
                role="assistant",
                content="rescued after progress",
                reasoning_content=None,
                tool_calls=None,
            ),
            finish_reason="stop",
            input_tokens=5,
            output_tokens=7,
            total_tokens=12,
            tool_calls=None,
            metadata={},
        ),
    )
    query_engine = ConversationQueryEngine(adapter=adapter, strict_contract=False)

    chunks = await query_engine.run_stream_turn(
        messages=[ChatMessage(role="user", content="hello")],
        model="gpt-5.4-xhigh",
        temperature=0.7,
        max_tokens=None,
        top_p=1.0,
        tools=[
            {"type": "function", "function": {"name": "web_search", "parameters": {}}}
        ],
        tool_choice="auto",
        supports_vision=True,
        supports_audio=False,
        supports_video=False,
    )

    assert len(chunks) == 2
    assert (chunks[0].metadata or {}).get("web_search_in_progress") is True
    assert chunks[1].delta == "rescued after progress"
    assert query_engine.turn_record.termination_reason == "protocol_fallback"
    assert query_engine.turn_record.metadata["sync_rescue"] is True
    assert query_engine.turn_record.metadata["stream_progress_event_count"] == 1
    assert query_engine.turn_record.fallback_history[0].reason == (
        "stream_progress_only_no_meaningful_output"
    )
    assert [call["protocol"] for call in adapter.stream_calls] == [
        "responses",
        "chat_completions",
    ]
    assert [call["protocol"] for call in adapter.chat_calls] == ["chat_completions"]


@pytest.mark.asyncio
async def test_runtime_query_engine_progress_only_does_not_satisfy_required_tool_contract() -> (
    None
):
    adapter = _RuntimeFakeAdapter(wire_api="responses")
    adapter.set_stream(
        "responses",
        [
            ChatChunk(delta="", metadata={"web_search_in_progress": True}),
            ChatChunk(delta="", finish_reason="stop", total_tokens=4),
        ],
    )
    query_engine = ConversationQueryEngine(adapter=adapter, strict_contract=True)

    progress_chunks: list[ChatChunk] = []
    with pytest.raises(RuntimeError, match="required_tool_round_empty_no_tool_calls"):
        async for chunk in query_engine.iter_stream_turn(
            messages=[ChatMessage(role="user", content="请调用工具")],
            model="gpt-5.4-xhigh",
            temperature=0.7,
            max_tokens=None,
            top_p=1.0,
            tools=[
                {
                    "type": "function",
                    "function": {"name": "web_search", "parameters": {}},
                }
            ],
            tool_choice="required",
            supports_vision=True,
            supports_audio=False,
            supports_video=False,
        ):
            progress_chunks.append(chunk)

    assert len(progress_chunks) == 1
    assert (progress_chunks[0].metadata or {}).get("web_search_in_progress") is True
    assert query_engine.turn_record.turn_outcome == "tool_round_failed"
    assert query_engine.turn_record.termination_reason == "tool_round_empty"
    assert query_engine.turn_record.metadata["stream_progress_event_count"] == 1
    assert query_engine.turn_record.fallback_history == []


@pytest.mark.asyncio
async def test_runtime_query_engine_progress_only_then_exception_falls_back() -> None:
    adapter = _RuntimeFakeAdapter(wire_api="responses")
    adapter.set_stream(
        "responses",
        [
            ChatChunk(delta="", metadata={"web_search_in_progress": True}),
            RuntimeError("responses stream interrupted"),
        ],
    )
    adapter.set_stream(
        "chat_completions",
        [ChatChunk(delta="fallback text", finish_reason="stop", total_tokens=9)],
    )
    query_engine = ConversationQueryEngine(adapter=adapter, strict_contract=False)

    chunks = await query_engine.run_stream_turn(
        messages=[ChatMessage(role="user", content="hello")],
        model="gpt-5.4-xhigh",
        temperature=0.7,
        max_tokens=None,
        top_p=1.0,
        tools=[
            {"type": "function", "function": {"name": "web_search", "parameters": {}}}
        ],
        tool_choice="auto",
        supports_vision=True,
        supports_audio=False,
        supports_video=False,
    )

    assert len(chunks) == 2
    assert (chunks[0].metadata or {}).get("web_search_in_progress") is True
    assert chunks[1].delta == "fallback text"
    assert query_engine.turn_record.turn_outcome == "success"
    assert query_engine.turn_record.termination_reason == "protocol_fallback"
    assert query_engine.turn_record.fallback_history[0].reason == (
        "stream_exception_after_progress_before_meaningful_chunk:RuntimeError"
    )
    assert [call["protocol"] for call in adapter.stream_calls] == [
        "responses",
        "chat_completions",
    ]


@pytest.mark.asyncio
async def test_runtime_query_engine_responses_only_provider_never_plans_chat_completions_fallback() -> (
    None
):
    adapter = _RuntimeFakeAdapter(
        wire_api="responses",
        protocol_capabilities=SimpleNamespace(
            primary_wire_api="responses",
            allowed_wire_apis=("responses",),
            allowed_cross_protocol_fallbacks={},
            allow_adapter_cross_protocol_fallback=False,
        ),
    )
    adapter.set_stream(
        "responses",
        [RuntimeError("responses stream interrupted")],
    )
    adapter.set_stream(
        "chat_completions",
        [ChatChunk(delta="should not be used", finish_reason="stop", total_tokens=9)],
    )
    query_engine = ConversationQueryEngine(adapter=adapter, strict_contract=False)

    with pytest.raises(RuntimeError, match="responses stream interrupted"):
        await query_engine.run_stream_turn(
            messages=[ChatMessage(role="user", content="hello")],
            model="gpt-5.4-xhigh",
            temperature=0.7,
            max_tokens=None,
            top_p=1.0,
            tools=[
                {
                    "type": "function",
                    "function": {"name": "web_search", "parameters": {}},
                }
            ],
            tool_choice="auto",
            supports_vision=True,
            supports_audio=False,
            supports_video=False,
        )

    assert query_engine.planner.plan_turn(
        tools=[
            {
                "type": "function",
                "function": {"name": "web_search", "parameters": {}},
            }
        ],
    ).protocol_chain == ["responses"]
    assert [call["protocol"] for call in adapter.stream_calls] == ["responses"]
    assert [call["protocol"] for call in adapter.chat_calls] == ["responses"]
    assert query_engine.turn_record.metadata["sync_rescue_attempted"] is True


@pytest.mark.asyncio
async def test_runtime_query_engine_provider_rate_limit_stream_does_not_cross_fallback() -> (
    None
):
    adapter = _RuntimeFakeAdapter(wire_api="responses")
    adapter.set_stream(
        "responses",
        [ProviderRateLimitError("too many concurrent sessions")],
    )
    adapter.set_stream(
        "chat_completions",
        [ChatChunk(delta="should not be used", finish_reason="stop", total_tokens=9)],
    )
    query_engine = ConversationQueryEngine(adapter=adapter, strict_contract=False)

    with pytest.raises(ProviderRateLimitError):
        await query_engine.run_stream_turn(
            messages=[ChatMessage(role="user", content="hello")],
            model="gpt-5.4-xhigh",
            temperature=0.7,
            max_tokens=None,
            top_p=1.0,
            tools=None,
            tool_choice=None,
            supports_vision=True,
            supports_audio=False,
            supports_video=False,
        )

    assert query_engine.turn_record.turn_outcome == "failed"
    assert query_engine.turn_record.termination_reason == "error"
    assert query_engine.turn_record.fallback_history == []
    assert query_engine.turn_record.metadata["protocol_fallback_blocked_reason"] == (
        "provider_rate_limit"
    )
    assert [call["protocol"] for call in adapter.stream_calls] == ["responses"]


@pytest.mark.asyncio
async def test_runtime_query_engine_provider_timeout_stream_does_not_cross_fallback() -> (
    None
):
    adapter = _RuntimeFakeAdapter(wire_api="responses")
    adapter.set_stream(
        "responses",
        [
            ProviderTimeoutError(
                "provider timed out",
                provider_code="openai_compatible",
                model_code="gpt-5.4",
            )
        ],
    )
    adapter.set_stream(
        "chat_completions",
        [ChatChunk(delta="should not be used", finish_reason="stop", total_tokens=9)],
    )
    query_engine = ConversationQueryEngine(adapter=adapter, strict_contract=False)

    with pytest.raises(ProviderTimeoutError, match="provider timed out"):
        await query_engine.run_stream_turn(
            messages=[ChatMessage(role="user", content="hello")],
            model="gpt-5.4-xhigh",
            temperature=0.7,
            max_tokens=None,
            top_p=1.0,
            tools=None,
            tool_choice=None,
            supports_vision=True,
            supports_audio=False,
            supports_video=False,
        )

    assert query_engine.turn_record.turn_outcome == "failed"
    assert query_engine.turn_record.termination_reason == "error"
    assert query_engine.turn_record.fallback_history == []
    assert query_engine.turn_record.metadata["protocol_fallback_blocked_reason"] == (
        "provider_timeout"
    )
    assert [call["protocol"] for call in adapter.stream_calls] == ["responses"]


@pytest.mark.asyncio
async def test_runtime_query_engine_provider_connection_stream_does_not_cross_fallback() -> (
    None
):
    adapter = _RuntimeFakeAdapter(wire_api="responses")
    adapter.set_stream(
        "responses",
        [ProviderConnectionError("Connection error.")],
    )
    adapter.set_stream(
        "chat_completions",
        [ChatChunk(delta="should not be used", finish_reason="stop", total_tokens=9)],
    )
    query_engine = ConversationQueryEngine(adapter=adapter, strict_contract=False)

    with pytest.raises(ProviderConnectionError, match="Connection error\\."):
        await query_engine.run_stream_turn(
            messages=[ChatMessage(role="user", content="hello")],
            model="gpt-5.4-xhigh",
            temperature=0.7,
            max_tokens=None,
            top_p=1.0,
            tools=None,
            tool_choice=None,
            supports_vision=True,
            supports_audio=False,
            supports_video=False,
        )

    assert query_engine.turn_record.turn_outcome == "failed"
    assert query_engine.turn_record.termination_reason == "error"
    assert query_engine.turn_record.fallback_history == []
    assert query_engine.turn_record.metadata["protocol_fallback_blocked_reason"] == (
        "provider_connection_error"
    )
    assert [call["protocol"] for call in adapter.stream_calls] == ["responses"]


@pytest.mark.asyncio
async def test_runtime_query_engine_reasoning_only_then_exception_falls_back() -> None:
    adapter = _RuntimeFakeAdapter(wire_api="responses")
    adapter.set_stream(
        "responses",
        [
            ChatChunk(delta="", reasoning_delta="thinking..."),
            RuntimeError("responses stream interrupted"),
        ],
    )
    adapter.set_stream(
        "chat_completions",
        [ChatChunk(delta="fallback text", finish_reason="stop", total_tokens=9)],
    )
    query_engine = ConversationQueryEngine(adapter=adapter, strict_contract=False)

    chunks = await query_engine.run_stream_turn(
        messages=[ChatMessage(role="user", content="hello")],
        model="gpt-5.4-xhigh",
        temperature=0.7,
        max_tokens=None,
        top_p=1.0,
        tools=[
            {"type": "function", "function": {"name": "web_search", "parameters": {}}}
        ],
        tool_choice="auto",
        supports_vision=True,
        supports_audio=False,
        supports_video=False,
    )

    assert len(chunks) == 2
    assert chunks[0].reasoning_delta == "thinking..."
    assert chunks[1].delta == "fallback text"
    assert query_engine.turn_record.turn_outcome == "success"
    assert query_engine.turn_record.termination_reason == "protocol_fallback"
    assert (
        query_engine.turn_record.metadata[
            "stream_failure_reasoning_only_before_visible_output"
        ]
        is True
    )
    assert query_engine.turn_record.metadata["stream_failure_blocks_fallback"] is False
    assert [call["protocol"] for call in adapter.stream_calls] == [
        "responses",
        "chat_completions",
    ]


@pytest.mark.asyncio
async def test_runtime_query_engine_reasoning_only_stream_sync_rescue_success() -> None:
    adapter = _RuntimeFakeAdapter(wire_api="responses")
    adapter.set_stream(
        "responses",
        [
            ChatChunk(delta="", reasoning_delta="thinking..."),
            ChatChunk(delta="", finish_reason="stop", total_tokens=4),
        ],
    )
    adapter.set_stream("chat_completions", [])
    adapter.set_chat(
        "chat_completions",
        SimpleNamespace(
            message=SimpleNamespace(
                role="assistant",
                content="rescued after reasoning",
                reasoning_content=None,
                tool_calls=None,
            ),
            finish_reason="stop",
            input_tokens=5,
            output_tokens=7,
            total_tokens=12,
            tool_calls=None,
            metadata={},
        ),
    )
    query_engine = ConversationQueryEngine(adapter=adapter, strict_contract=False)

    chunks = await query_engine.run_stream_turn(
        messages=[ChatMessage(role="user", content="hello")],
        model="gpt-5.4-xhigh",
        temperature=0.7,
        max_tokens=None,
        top_p=1.0,
        tools=[
            {"type": "function", "function": {"name": "web_search", "parameters": {}}}
        ],
        tool_choice="auto",
        supports_vision=True,
        supports_audio=False,
        supports_video=False,
    )

    assert len(chunks) == 2
    assert chunks[0].reasoning_delta == "thinking..."
    assert chunks[1].delta == "rescued after reasoning"
    assert query_engine.turn_record.turn_outcome == "success"
    assert query_engine.turn_record.termination_reason == "protocol_fallback"
    assert query_engine.turn_record.metadata["sync_rescue"] is True
    assert [call["protocol"] for call in adapter.stream_calls] == [
        "responses",
        "chat_completions",
    ]
    assert [call["protocol"] for call in adapter.chat_calls] == ["chat_completions"]


@pytest.mark.asyncio
async def test_runtime_query_engine_stream_empty_after_fallback_sync_rescue_success() -> (
    None
):
    adapter = _RuntimeFakeAdapter(wire_api="responses")
    adapter.set_stream("responses", [])
    adapter.set_stream("chat_completions", [])
    adapter.set_chat(
        "chat_completions",
        SimpleNamespace(
            message=SimpleNamespace(
                role="assistant",
                content="rescued reply",
                reasoning_content=None,
                tool_calls=None,
            ),
            finish_reason="stop",
            input_tokens=5,
            output_tokens=7,
            total_tokens=12,
            tool_calls=None,
            metadata={},
        ),
    )
    query_engine = ConversationQueryEngine(adapter=adapter, strict_contract=False)

    chunks = await query_engine.run_stream_turn(
        messages=[ChatMessage(role="user", content="hello")],
        model="gpt-5.4-xhigh",
        temperature=0.7,
        max_tokens=None,
        top_p=1.0,
        tools=[
            {"type": "function", "function": {"name": "web_search", "parameters": {}}}
        ],
        tool_choice="required",
        supports_vision=True,
        supports_audio=False,
        supports_video=False,
    )

    assert len(chunks) == 1
    assert chunks[0].delta == "rescued reply"
    assert query_engine.turn_record.termination_reason == "protocol_fallback"
    assert query_engine.turn_record.metadata["sync_rescue"] is True
    assert [call["protocol"] for call in adapter.stream_calls] == [
        "responses",
        "chat_completions",
    ]
    assert [call["protocol"] for call in adapter.chat_calls] == ["chat_completions"]


@pytest.mark.asyncio
async def test_runtime_query_engine_chat_turn_records_protocol_fallback_history() -> (
    None
):
    adapter = _RuntimeFakeAdapter(wire_api="responses")
    adapter.set_chat("responses", RuntimeError("responses upstream timeout"))
    adapter.set_chat(
        "chat_completions",
        SimpleNamespace(
            message=SimpleNamespace(
                role="assistant",
                content="fallback chat result",
                reasoning_content=None,
                tool_calls=None,
            ),
            finish_reason="stop",
            input_tokens=9,
            output_tokens=6,
            total_tokens=15,
            tool_calls=None,
            metadata={},
        ),
    )
    query_engine = ConversationQueryEngine(adapter=adapter, strict_contract=False)

    response = await query_engine.run_chat_turn(
        messages=[ChatMessage(role="user", content="hello")],
        model="gpt-5.4-xhigh",
        temperature=0.7,
        max_tokens=None,
        top_p=1.0,
        tools=[
            {"type": "function", "function": {"name": "web_search", "parameters": {}}}
        ],
        tool_choice="auto",
        supports_vision=True,
        supports_audio=False,
        supports_video=False,
    )

    assert response.message.content == "fallback chat result"
    assert query_engine.turn_record.termination_reason == "protocol_fallback"
    assert len(query_engine.turn_record.fallback_history) == 1
    assert query_engine.turn_record.fallback_history[0].from_protocol == "responses"
    assert (
        query_engine.turn_record.fallback_history[0].to_protocol == "chat_completions"
    )
    assert (
        query_engine.turn_record.fallback_history[0].reason == "exception:RuntimeError"
    )
    assert response.metadata["runtime_turn_record"] is query_engine.turn_record
    assert [call["protocol"] for call in adapter.chat_calls] == [
        "responses",
        "chat_completions",
    ]


@pytest.mark.asyncio
async def test_runtime_query_engine_chat_turn_reasoning_only_response_falls_back() -> (
    None
):
    adapter = _RuntimeFakeAdapter(wire_api="responses")
    adapter.set_chat(
        "responses",
        SimpleNamespace(
            message=SimpleNamespace(
                role="assistant",
                content="",
                reasoning_content="thinking only",
                tool_calls=None,
            ),
            finish_reason="stop",
            input_tokens=5,
            output_tokens=4,
            total_tokens=9,
            tool_calls=None,
            metadata={},
        ),
    )
    adapter.set_chat(
        "chat_completions",
        SimpleNamespace(
            message=SimpleNamespace(
                role="assistant",
                content="fallback chat result",
                reasoning_content=None,
                tool_calls=None,
            ),
            finish_reason="stop",
            input_tokens=9,
            output_tokens=6,
            total_tokens=15,
            tool_calls=None,
            metadata={},
        ),
    )
    query_engine = ConversationQueryEngine(adapter=adapter, strict_contract=False)

    response = await query_engine.run_chat_turn(
        messages=[ChatMessage(role="user", content="hello")],
        model="gpt-5.4-xhigh",
        temperature=0.7,
        max_tokens=None,
        top_p=1.0,
        tools=[
            {"type": "function", "function": {"name": "web_search", "parameters": {}}}
        ],
        tool_choice="auto",
        supports_vision=True,
        supports_audio=False,
        supports_video=False,
    )

    assert response.message.content == "fallback chat result"
    assert query_engine.turn_record.turn_outcome == "success"
    assert query_engine.turn_record.termination_reason == "protocol_fallback"
    assert query_engine.turn_record.fallback_history[0].reason == "chat_empty_no_output"
    assert [call["protocol"] for call in adapter.chat_calls] == [
        "responses",
        "chat_completions",
    ]


@pytest.mark.asyncio
async def test_stream_chat_responses_output_text_done_without_completed() -> None:
    """兼容网关只发 output_text.done、不发 response.completed 时也必须结束迭代。"""

    class _FakeResponsesStream:
        def __init__(self, events):
            self._events = events
            self.aclose_called = False

        def __aiter__(self):
            self._iter = iter(self._events)
            return self

        async def __anext__(self):
            try:
                return next(self._iter)
            except StopIteration as exc:
                raise StopAsyncIteration from exc

        async def aclose(self) -> None:
            self.aclose_called = True

    adapter = OpenAIAdapter(
        api_key="test-key",
        base_url="https://api.example.com",
        provider_config={"wire_api": "responses"},
    )
    rs = _FakeResponsesStream(
        [
            SimpleNamespace(type="response.output_text.delta", delta="A"),
            SimpleNamespace(
                type="response.output_text.done",
                text="",
                usage=SimpleNamespace(input_tokens=2, output_tokens=3, total_tokens=5),
            ),
        ]
    )
    adapter.client = SimpleNamespace(
        responses=SimpleNamespace(create=_FakeResponses(rs).create),
        chat=SimpleNamespace(completions=_FakeChatCompletions(None)),
    )

    chunks = []
    async for chunk in adapter.stream_chat(
        messages=[ChatMessage(role="user", content="hello")],
        model="gpt-x",
    ):
        chunks.append(chunk)

    assert "".join(c.delta for c in chunks) == "A"
    assert chunks[-1].finish_reason == "stop"
    assert chunks[-1].total_tokens == 5
    assert rs.aclose_called is True


@pytest.mark.asyncio
async def test_stream_chat_responses_output_text_done_retrieves_usage_when_event_omits_it() -> (
    None
):
    class _FakeResponsesStream:
        def __init__(self, events):
            self._events = events
            self.aclose_called = False

        def __aiter__(self):
            self._iter = iter(self._events)
            return self

        async def __anext__(self):
            try:
                return next(self._iter)
            except StopIteration as exc:
                raise StopAsyncIteration from exc

        async def aclose(self) -> None:
            self.aclose_called = True

    adapter = OpenAIAdapter(
        api_key="test-key",
        base_url="https://api.example.com",
        provider_config={"wire_api": "responses"},
    )
    created_response = SimpleNamespace(id="resp_123")
    retrieved_response = SimpleNamespace(
        usage=SimpleNamespace(input_tokens=17, output_tokens=9, total_tokens=26),
    )
    rs = _FakeResponsesStream(
        [
            SimpleNamespace(type="response.created", response=created_response),
            SimpleNamespace(type="response.output_text.delta", delta="A"),
            SimpleNamespace(type="response.output_text.done", text="", usage=None),
        ]
    )
    adapter.client = SimpleNamespace(
        responses=SimpleNamespace(
            create=_FakeResponses(rs).create,
            retrieve=AsyncMock(return_value=retrieved_response),
        ),
        chat=SimpleNamespace(completions=_FakeChatCompletions(None)),
    )

    chunks = []
    async for chunk in adapter.stream_chat(
        messages=[ChatMessage(role="user", content="hello")],
        model="gpt-x",
    ):
        chunks.append(chunk)

    assert "".join(c.delta for c in chunks) == "A"
    assert chunks[-1].input_tokens == 17
    assert chunks[-1].output_tokens == 9
    assert chunks[-1].total_tokens == 26
    adapter.client.responses.retrieve.assert_awaited_once_with("resp_123")
    assert rs.aclose_called is True


@pytest.mark.asyncio
async def test_stream_chat_responses_output_text_done_uses_fast_usage_backfill_client() -> (
    None
):
    class _FakeResponsesStream:
        def __init__(self, events):
            self._events = events
            self.aclose_called = False

        def __aiter__(self):
            self._iter = iter(self._events)
            return self

        async def __anext__(self):
            try:
                return next(self._iter)
            except StopIteration as exc:
                raise StopAsyncIteration from exc

        async def aclose(self) -> None:
            self.aclose_called = True

    adapter = OpenAIAdapter(
        api_key="test-key",
        base_url="https://api.example.com",
        provider_config={"wire_api": "responses"},
    )
    created_response = SimpleNamespace(id="resp_123")
    retrieved_response = SimpleNamespace(
        usage=SimpleNamespace(input_tokens=17, output_tokens=9, total_tokens=26),
    )
    rs = _FakeResponsesStream(
        [
            SimpleNamespace(type="response.created", response=created_response),
            SimpleNamespace(type="response.output_text.delta", delta="A"),
            SimpleNamespace(type="response.output_text.done", text="", usage=None),
        ]
    )
    retrieve_mock = AsyncMock(return_value=retrieved_response)
    with_options_mock = MagicMock(
        return_value=SimpleNamespace(
            responses=SimpleNamespace(retrieve=retrieve_mock),
        )
    )
    base_retrieve_mock = AsyncMock()
    adapter.client = SimpleNamespace(
        with_options=with_options_mock,
        responses=SimpleNamespace(
            create=_FakeResponses(rs).create,
            retrieve=base_retrieve_mock,
        ),
        chat=SimpleNamespace(completions=_FakeChatCompletions(None)),
    )

    chunks = []
    async for chunk in adapter.stream_chat(
        messages=[ChatMessage(role="user", content="hello")],
        model="gpt-x",
    ):
        chunks.append(chunk)

    assert "".join(c.delta for c in chunks) == "A"
    assert chunks[-1].total_tokens == 26
    with_options_mock.assert_called_once_with(
        timeout=RESPONSES_USAGE_RETRIEVE_TIMEOUT_SECONDS,
        max_retries=0,
    )
    retrieve_mock.assert_awaited_once_with("resp_123")
    base_retrieve_mock.assert_not_called()
    assert rs.aclose_called is True


@pytest.mark.asyncio
async def test_stream_chat_responses_output_text_done_estimates_usage_when_retrieve_unavailable() -> (
    None
):
    class _FakeResponsesStream:
        def __init__(self, events):
            self._events = events
            self.aclose_called = False

        def __aiter__(self):
            self._iter = iter(self._events)
            return self

        async def __anext__(self):
            try:
                return next(self._iter)
            except StopIteration as exc:
                raise StopAsyncIteration from exc

        async def aclose(self) -> None:
            self.aclose_called = True

    adapter = OpenAIAdapter(
        api_key="test-key",
        base_url="https://api.example.com",
        provider_config={"wire_api": "responses"},
    )
    rs = _FakeResponsesStream(
        [
            SimpleNamespace(
                type="response.created",
                response=SimpleNamespace(id="resp_404"),
            ),
            SimpleNamespace(type="response.output_text.delta", delta="你好"),
            SimpleNamespace(type="response.output_text.done", text="", usage=None),
        ]
    )
    adapter.client = SimpleNamespace(
        responses=SimpleNamespace(
            create=_FakeResponses(rs).create,
            retrieve=AsyncMock(side_effect=RuntimeError("404 page not found")),
        ),
        chat=SimpleNamespace(completions=_FakeChatCompletions(None)),
    )

    chunks = []
    async for chunk in adapter.stream_chat(
        messages=[ChatMessage(role="user", content="测试输入")],
        model="gpt-5.4-xhigh",
    ):
        chunks.append(chunk)

    assert "".join(c.delta for c in chunks) == "你好"
    assert chunks[-1].input_tokens > 0
    assert chunks[-1].output_tokens > 0
    assert chunks[-1].total_tokens == chunks[-1].input_tokens + chunks[-1].output_tokens
    assert chunks[-1].metadata["usage_mode"] == "estimated"
    assert rs.aclose_called is True


@pytest.mark.asyncio
async def test_stream_chat_responses_done_event_text_when_no_prior_deltas() -> None:
    class _FakeResponsesStream:
        def __init__(self, events):
            self._events = events

        def __aiter__(self):
            self._iter = iter(self._events)
            return self

        async def __anext__(self):
            try:
                return next(self._iter)
            except StopIteration as exc:
                raise StopAsyncIteration from exc

        async def aclose(self) -> None:
            return None

    adapter = OpenAIAdapter(
        api_key="test-key",
        base_url="https://api.example.com",
        provider_config={"wire_api": "responses"},
    )
    adapter.client = SimpleNamespace(
        responses=SimpleNamespace(
            create=_FakeResponses(
                _FakeResponsesStream(
                    [
                        SimpleNamespace(
                            type="response.output_text.done", text="Body", usage=None
                        ),
                    ]
                )
            ).create,
        ),
        chat=SimpleNamespace(completions=_FakeChatCompletions(None)),
    )

    chunks = []
    async for chunk in adapter.stream_chat(
        messages=[ChatMessage(role="user", content="hello")],
        model="gpt-x",
    ):
        chunks.append(chunk)

    assert "".join(c.delta for c in chunks) == "Body"
    assert chunks[-1].finish_reason == "stop"


@pytest.mark.asyncio
async def test_stream_chat_uses_responses_protocol_when_configured() -> None:
    class _FakeResponsesStream:
        def __init__(self, events):
            self._events = events
            self.aclose_called = False

        def __aiter__(self):
            self._iter = iter(self._events)
            return self

        async def __anext__(self):
            try:
                return next(self._iter)
            except StopIteration as exc:
                raise StopAsyncIteration from exc

        async def aclose(self) -> None:
            self.aclose_called = True

    adapter = OpenAIAdapter(
        api_key="test-key",
        base_url="https://api.example.com",
        provider_config={"wire_api": "responses"},
    )
    completed_response = SimpleNamespace(
        usage=SimpleNamespace(input_tokens=11, output_tokens=4, total_tokens=15),
        output_text="OK",
        output=[],
    )
    rs = _FakeResponsesStream(
        [
            SimpleNamespace(type="response.output_text.delta", delta="O"),
            SimpleNamespace(type="response.output_text.delta", delta="K"),
            SimpleNamespace(type="response.completed", response=completed_response),
            SimpleNamespace(type="response.output_text.delta", delta="TAIL"),
        ]
    )
    adapter.client = SimpleNamespace(
        responses=SimpleNamespace(
            create=_FakeResponses(rs).create,
        ),
        chat=SimpleNamespace(completions=_FakeChatCompletions(None)),
    )

    chunks = []
    async for chunk in adapter.stream_chat(
        messages=[ChatMessage(role="user", content="hello")],
        model="gpt-5.4-xhigh",
    ):
        chunks.append(chunk)

    assert "".join(chunk.delta for chunk in chunks) == "OK"
    assert "TAIL" not in "".join(chunk.delta for chunk in chunks)
    assert chunks[-1].finish_reason == "stop"
    assert chunks[-1].total_tokens == 15
    assert rs.aclose_called is True


@pytest.mark.asyncio
async def test_stream_chat_responses_timeout_before_first_chunk_rescues_via_sync_responses() -> (
    None
):
    class _HangingResponsesStream:
        def __init__(self):
            self.aclose_called = False

        def __aiter__(self):
            return self

        async def __anext__(self):
            await asyncio.sleep(3600)
            raise StopAsyncIteration

        async def aclose(self) -> None:
            self.aclose_called = True

    adapter = OpenAIAdapter(
        api_key="test-key",
        base_url="https://api.example.com",
        provider_config={"wire_api": "responses"},
    )
    hanging_stream = _HangingResponsesStream()
    create_calls: list[dict[str, Any]] = []

    async def _create(**kwargs):
        create_calls.append(dict(kwargs))
        if kwargs.get("stream"):
            return hanging_stream
        return SimpleNamespace(
            id="resp_sync_1",
            status="completed",
            usage=SimpleNamespace(input_tokens=9, output_tokens=4, total_tokens=13),
            output_text="rescued",
            output=[_make_responses_message("rescued")],
        )

    adapter.client = SimpleNamespace(
        responses=SimpleNamespace(create=_create),
        chat=SimpleNamespace(completions=_FakeChatCompletions(None)),
    )

    chunks = []
    async for chunk in adapter.stream_chat(
        messages=[ChatMessage(role="user", content="hello")],
        model="gpt-5.4-xhigh",
        timeout_seconds=0.05,
    ):
        chunks.append(chunk)

    assert "".join(chunk.delta for chunk in chunks) == "rescued"
    assert chunks[-1].finish_reason == "stop"
    assert chunks[-1].total_tokens == 13
    assert chunks[-1].metadata["responses_response_id"] == "resp_sync_1"
    assert (
        chunks[-1].metadata["responses_stream_rescue"]
        == "sync_after_timeout_before_first_meaningful_chunk"
    )
    assert len(create_calls) == 2
    assert create_calls[0]["stream"] is True
    assert "stream" not in create_calls[1]
    assert adapter.client.chat.completions.last_kwargs is None
    assert hanging_stream.aclose_called is True


@pytest.mark.asyncio
async def test_stream_chat_responses_stream_create_timeout_rescues_via_sync() -> None:
    adapter = OpenAIAdapter(
        api_key="test-key",
        base_url="https://api.example.com",
        provider_config={"wire_api": "responses"},
    )
    create_calls: list[dict[str, Any]] = []

    async def _create(**kwargs):
        create_calls.append(dict(kwargs))
        if kwargs.get("stream"):
            raise RuntimeError("Request timed out.")
        return SimpleNamespace(
            id="resp_sync_1",
            status="completed",
            usage=SimpleNamespace(input_tokens=9, output_tokens=4, total_tokens=13),
            output_text="rescued",
            output=[_make_responses_message("rescued")],
        )

    adapter.client = SimpleNamespace(
        responses=SimpleNamespace(create=_create),
        chat=SimpleNamespace(completions=_FakeChatCompletions(None)),
    )

    chunks = []
    async for chunk in adapter.stream_chat(
        messages=[ChatMessage(role="user", content="hello")],
        model="gpt-5.4-xhigh",
        timeout_seconds=0.05,
    ):
        chunks.append(chunk)

    assert "".join(chunk.delta for chunk in chunks) == "rescued"
    assert chunks[-1].finish_reason == "stop"
    assert chunks[-1].total_tokens == 13
    assert chunks[-1].metadata["responses_response_id"] == "resp_sync_1"
    assert (
        chunks[-1].metadata["responses_stream_rescue"]
        == "sync_after_timeout_before_first_meaningful_chunk"
    )
    assert len(create_calls) == 2
    assert create_calls[0]["stream"] is True
    assert "stream" not in create_calls[1]
    assert adapter.client.chat.completions.last_kwargs is None


@pytest.mark.asyncio
async def test_stream_chat_responses_hanging_stream_times_out_with_timeout_seconds() -> (
    None
):
    class _HangingResponsesStream:
        def __init__(self):
            self.aclose_called = False

        def __aiter__(self):
            return self

        async def __anext__(self):
            await asyncio.sleep(3600)
            raise StopAsyncIteration

        async def aclose(self) -> None:
            self.aclose_called = True

    adapter = OpenAIAdapter(
        api_key="test-key",
        base_url="https://api.example.com",
        provider_config={"wire_api": "responses"},
    )
    hanging_stream = _HangingResponsesStream()
    create_calls: list[dict[str, Any]] = []

    async def _create(**kwargs):
        create_calls.append(dict(kwargs))
        if kwargs.get("stream"):
            return hanging_stream
        raise ProviderTimeoutError(
            "provider timed out",
            provider_code="openai_compatible",
            model_code="gpt-5.4",
        )

    adapter.client = SimpleNamespace(
        responses=SimpleNamespace(create=_create),
        chat=SimpleNamespace(completions=_FakeChatCompletions(None)),
    )

    with pytest.raises(ProviderTimeoutError, match="provider timed out"):
        async for _ in adapter.stream_chat(
            messages=[ChatMessage(role="user", content="hello")],
            model="gpt-5.4-xhigh",
            timeout_seconds=0.05,
        ):
            pass

    assert len(create_calls) == 2
    assert adapter.client.chat.completions.last_kwargs is None
    assert create_calls[0].get("timeout") == pytest.approx(0.05)
    assert create_calls[0]["stream"] is True
    assert create_calls[1].get("timeout") == pytest.approx(0.05)
    assert "stream" not in create_calls[1]
    assert hanging_stream.aclose_called is True


@pytest.mark.asyncio
async def test_stream_chat_public_responses_timeout_does_not_hit_chat_completions() -> (
    None
):
    class _HangingResponsesStream:
        def __init__(self):
            self.aclose_called = False

        def __aiter__(self):
            return self

        async def __anext__(self):
            await asyncio.sleep(3600)
            raise StopAsyncIteration

        async def aclose(self) -> None:
            self.aclose_called = True

    adapter = OpenAIAdapter(
        api_key="test-key",
        base_url="https://api.example.com",
        provider_config=_responses_cross_protocol_provider_config(),
    )
    hanging_stream = _HangingResponsesStream()
    create_calls: list[dict[str, Any]] = []

    async def _create(**kwargs):
        create_calls.append(dict(kwargs))
        if kwargs.get("stream"):
            return hanging_stream
        raise ProviderTimeoutError(
            "provider timed out",
            provider_code="openai_compatible",
            model_code="gpt-5.4",
        )

    adapter.client = SimpleNamespace(
        responses=SimpleNamespace(create=_create),
        chat=SimpleNamespace(completions=_FakeChatCompletions(None)),
    )

    with pytest.raises(ProviderTimeoutError, match="provider timed out"):
        async for _ in adapter.stream_chat(
            messages=[ChatMessage(role="user", content="hello")],
            model="gpt-5.4-xhigh",
            tools=[
                {
                    "type": "function",
                    "function": {"name": "crm_lookup", "parameters": {}},
                }
            ],
            tool_choice="required",
            timeout_seconds=0.05,
        ):
            pass

    assert len(create_calls) == 2
    assert adapter.client.chat.completions.last_kwargs is None
    assert create_calls[0].get("timeout") == pytest.approx(0.05)
    assert create_calls[0]["stream"] is True
    assert create_calls[1].get("timeout") == pytest.approx(0.05)
    assert "stream" not in create_calls[1]
    assert hanging_stream.aclose_called is True


@pytest.mark.asyncio
async def test_chat_protocol_responses_applies_client_retry_override() -> None:
    adapter = OpenAIAdapter(
        api_key="test-key",
        base_url="https://api.example.com",
        provider_config={"wire_api": "responses"},
    )
    client = _FakeClientWithOptions(
        None,
        SimpleNamespace(
            id="resp_1",
            status="completed",
            output_text="OK",
            output=[_make_responses_message("OK")],
            usage=SimpleNamespace(input_tokens=3, output_tokens=2, total_tokens=5),
            model_dump=lambda: {"ok": True},
        ),
    )
    adapter.client = client

    response = await adapter.execute_protocol_chat(
        wire_api="responses",
        messages=[ChatMessage(role="user", content="hello")],
        model="gpt-5.4",
        timeout_seconds=0.05,
        _runtime_client_max_retries_override=0,
        _runtime_disable_cross_protocol_fallback=True,
        _runtime_disable_sync_rescue=True,
    )

    assert response.message.content == "OK"
    assert client.with_options_calls == [{"max_retries": 0}]
    assert client.responses.last_kwargs.get("timeout") == pytest.approx(0.05)
    assert "_client_max_retries" not in client.responses.last_kwargs


@pytest.mark.asyncio
async def test_stream_protocol_responses_applies_client_retry_override() -> None:
    class _FakeResponsesStream:
        def __init__(self, events):
            self._events = events
            self.aclose_called = False

        def __aiter__(self):
            self._iter = iter(self._events)
            return self

        async def __anext__(self):
            try:
                return next(self._iter)
            except StopIteration as exc:
                raise StopAsyncIteration from exc

        async def aclose(self) -> None:
            self.aclose_called = True

    adapter = OpenAIAdapter(
        api_key="test-key",
        base_url="https://api.example.com",
        provider_config={"wire_api": "responses"},
    )
    stream = _FakeResponsesStream(
        [
            SimpleNamespace(
                type="response.completed",
                response=SimpleNamespace(
                    id="resp_1",
                    usage=SimpleNamespace(
                        input_tokens=3,
                        output_tokens=2,
                        total_tokens=5,
                    ),
                    output_text="OK",
                    output=[_make_responses_message("OK")],
                ),
            )
        ]
    )
    client = _FakeClientWithOptions(None, stream)
    adapter.client = client

    chunks = [
        chunk
        async for chunk in adapter.execute_protocol_stream(
            wire_api="responses",
            messages=[ChatMessage(role="user", content="hello")],
            model="gpt-5.4",
            timeout_seconds=0.05,
            _runtime_client_max_retries_override=0,
            _runtime_disable_cross_protocol_fallback=True,
            _runtime_disable_sync_rescue=True,
        )
    ]

    assert "".join(chunk.delta for chunk in chunks) == "OK"
    assert chunks[-1].finish_reason == "stop"
    assert client.with_options_calls == [{"max_retries": 0}]
    assert client.responses.last_kwargs.get("timeout") == pytest.approx(0.05)
    assert "_client_max_retries" not in client.responses.last_kwargs
    assert stream.aclose_called is True


@pytest.mark.asyncio
async def test_stream_chat_emits_reasoning_from_completed_response_when_no_reasoning_delta() -> (
    None
):
    class _FakeResponsesStream:
        def __init__(self, events):
            self._events = events
            self.aclose_called = False

        def __aiter__(self):
            self._iter = iter(self._events)
            return self

        async def __anext__(self):
            try:
                return next(self._iter)
            except StopIteration as exc:
                raise StopAsyncIteration from exc

        async def aclose(self) -> None:
            self.aclose_called = True

    adapter = OpenAIAdapter(
        api_key="test-key",
        base_url="https://api.example.com",
        provider_config={"wire_api": "responses"},
    )
    completed_response = SimpleNamespace(
        usage=SimpleNamespace(input_tokens=11, output_tokens=4, total_tokens=15),
        output_text="OK",
        output=[
            SimpleNamespace(
                type="reasoning",
                summary=[SimpleNamespace(text="先检查上下文。")],
            ),
            _make_responses_message("OK"),
        ],
    )
    rs = _FakeResponsesStream(
        [
            SimpleNamespace(type="response.output_text.delta", delta="O"),
            SimpleNamespace(type="response.output_text.delta", delta="K"),
            SimpleNamespace(type="response.completed", response=completed_response),
        ]
    )
    adapter.client = SimpleNamespace(
        responses=SimpleNamespace(
            create=_FakeResponses(rs).create,
        ),
        chat=SimpleNamespace(completions=_FakeChatCompletions(None)),
    )

    chunks = []
    async for chunk in adapter.stream_chat(
        messages=[ChatMessage(role="user", content="hello")],
        model="gpt-5.4-xhigh",
    ):
        chunks.append(chunk)

    reasoning = "".join(chunk.reasoning_delta for chunk in chunks)
    assert reasoning == "先检查上下文。"
    assert "".join(chunk.delta for chunk in chunks) == "OK"
    assert chunks[-1].finish_reason == "stop"
    assert rs.aclose_called is True


@pytest.mark.asyncio
async def test_convert_messages_to_responses_input_preserves_tool_roundtrip() -> None:
    adapter = OpenAIAdapter(
        api_key="test-key",
        base_url="https://api.example.com",
        provider_config={"wire_api": "responses"},
    )

    converted = await adapter._convert_messages_to_responses_input(
        [
            ChatMessage(
                role="assistant",
                content="",
                tool_calls=[
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {
                            "name": "lookup_weather",
                            "arguments": '{"city":"Shanghai"}',
                        },
                    }
                ],
            ),
            ChatMessage(role="tool", content="sunny", tool_call_id="call_1"),
        ]
    )

    assert converted == [
        {
            "type": "function_call",
            "call_id": "call_1",
            "name": "lookup_weather",
            "arguments": '{"city":"Shanghai"}',
            "status": "completed",
        },
        {
            "type": "function_call_output",
            "call_id": "call_1",
            "output": "sunny",
        },
    ]


@pytest.mark.asyncio
async def test_convert_messages_to_responses_input_keeps_item_id_separate_from_call_id() -> None:
    adapter = OpenAIAdapter(
        api_key="test-key",
        base_url="https://api.example.com",
        provider_config={"wire_api": "responses"},
    )

    converted = await adapter._convert_messages_to_responses_input(
        [
            ChatMessage(
                role="assistant",
                content="",
                tool_calls=[
                    {
                        "id": "fc_123",
                        "call_id": "call_123",
                        "type": "function",
                        "function": {
                            "name": "crm_update_record",
                            "arguments": '{"fields":{"name":"E2E-Test"}}',
                        },
                    }
                ],
            ),
            ChatMessage(role="tool", content='{"ok":true}', tool_call_id="call_123"),
        ]
    )

    assert converted == [
        {
            "type": "function_call",
            "call_id": "call_123",
            "id": "fc_123",
            "name": "crm_update_record",
            "arguments": '{"fields":{"name":"E2E-Test"}}',
            "status": "completed",
        },
        {
            "type": "function_call_output",
            "call_id": "call_123",
            "output": '{"ok":true}',
        },
    ]


@pytest.mark.asyncio
async def test_convert_messages_to_responses_input_synthesizes_missing_call_id_roundtrip() -> (
    None
):
    adapter = OpenAIAdapter(
        api_key="test-key",
        base_url="https://api.example.com",
        provider_config={"wire_api": "responses"},
    )

    converted = await adapter._convert_messages_to_responses_input(
        [
            ChatMessage(
                role="assistant",
                content="",
                tool_calls=[
                    {
                        "id": "fc_page_recovery_crm_get_record_state",
                        "type": "function",
                        "function": {
                            "name": "crm_get_record_state",
                            "arguments": "{}",
                        },
                    }
                ],
            ),
            ChatMessage(role="tool", content='{"has_active_form":true}'),
        ]
    )

    assert converted == [
        {
            "type": "function_call",
            "call_id": "call_1_1_crm_get_record_state",
            "id": "fc_page_recovery_crm_get_record_state",
            "name": "crm_get_record_state",
            "arguments": "{}",
            "status": "completed",
        },
        {
            "type": "function_call_output",
            "call_id": "call_1_1_crm_get_record_state",
            "output": '{"has_active_form":true}',
        },
    ]


@pytest.mark.asyncio
async def test_convert_messages_to_responses_input_pairs_mismatched_internal_tool_id_with_pending_call() -> (
    None
):
    adapter = OpenAIAdapter(
        api_key="test-key",
        base_url="https://api.example.com",
        provider_config={"wire_api": "responses"},
    )

    converted = await adapter._convert_messages_to_responses_input(
        [
            ChatMessage(
                role="assistant",
                content="",
                tool_calls=[
                    {
                        "id": "fc_page_recovery_crm_read_record",
                        "type": "function",
                        "function": {
                            "name": "crm_read_record",
                            "arguments": '{"locator":"main"}',
                        },
                    }
                ],
            ),
            ChatMessage(
                role="tool",
                content='{"text":"模型管理"}',
                tool_call_id="fc_page_recovery_crm_read_record",
            ),
        ]
    )

    assert converted == [
        {
            "type": "function_call",
            "call_id": "call_1_1_crm_read_record",
            "id": "fc_page_recovery_crm_read_record",
            "name": "crm_read_record",
            "arguments": '{"locator":"main"}',
            "status": "completed",
        },
        {
            "type": "function_call_output",
            "call_id": "call_1_1_crm_read_record",
            "output": '{"text":"模型管理"}',
        },
    ]


@pytest.mark.asyncio
async def test_convert_messages_to_responses_input_drops_orphan_tool_without_call_id() -> (
    None
):
    adapter = OpenAIAdapter(
        api_key="test-key",
        base_url="https://api.example.com",
        provider_config={"wire_api": "responses"},
    )

    converted = await adapter._convert_messages_to_responses_input(
        [ChatMessage(role="tool", content="orphan tool output")]
    )

    assert converted == []


@pytest.mark.asyncio
async def test_convert_messages_to_responses_input_ignores_legacy_text_mode_and_keeps_structured_tool_roundtrip() -> (
    None
):
    adapter = OpenAIAdapter(
        api_key="test-key",
        base_url="https://api.example.com",
        provider_config={
            "wire_api": "responses",
            "responses_tool_history_mode": "text",
        },
    )

    converted = await adapter._convert_messages_to_responses_input(
        [
            ChatMessage(
                role="assistant",
                content="Let me inspect the page first.",
                tool_calls=[
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {
                            "name": "crm_lookup",
                            "arguments": "{}",
                        },
                    }
                ],
            ),
            ChatMessage(
                role="tool",
                content="Page: admin.ai.providers",
                tool_call_id="call_1",
            ),
        ]
    )

    assert converted == [
        {
            "type": "function_call",
            "call_id": "call_1",
            "name": "crm_lookup",
            "arguments": "{}",
            "status": "completed",
        },
        {
            "type": "message",
            "role": "assistant",
            "content": "Let me inspect the page first.",
        },
        {
            "type": "function_call_output",
            "call_id": "call_1",
            "output": "Page: admin.ai.providers",
        },
    ]


def test_init_keeps_endpoint_style_base_url_and_does_not_infer_wire_api() -> None:
    adapter = OpenAIAdapter(
        api_key="test-key",
        base_url="https://code.respyun.com/v1/responses",
    )

    assert adapter.base_url == "https://code.respyun.com/v1/responses"
    assert adapter.wire_api == "chat_completions"


def test_build_chat_completions_v1_retry_base_url_for_root_base_url() -> None:
    adapter = OpenAIAdapter(
        api_key="test-key",
        base_url="https://codex.2api.com.cn",
    )

    assert (
        adapter._build_chat_completions_v1_retry_base_url()
        == "https://codex.2api.com.cn/v1"
    )


@pytest.mark.asyncio
async def test_build_responses_request_enables_reasoning_summary_for_gpt5() -> None:
    adapter = OpenAIAdapter(
        api_key="test-key",
        base_url="https://api.example.com",
        provider_config={"wire_api": "responses"},
    )

    request = await adapter._build_responses_request(
        messages=[ChatMessage(role="user", content="hello")],
        model="gpt-5.4",
        stream=True,
    )

    assert request["reasoning"] == {"summary": "auto"}


@pytest.mark.asyncio
async def test_build_responses_request_forwards_required_tool_choice() -> None:
    adapter = OpenAIAdapter(
        api_key="test-key",
        base_url="https://api.example.com",
        provider_config={"wire_api": "responses"},
    )

    request = await adapter._build_responses_request(
        messages=[ChatMessage(role="user", content="hello")],
        model="gpt-5.4-xhigh",
        tools=[
            {"type": "function", "function": {"name": "web_search", "parameters": {}}},
        ],
        tool_choice="required",
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
async def test_build_responses_request_keeps_runtime_web_search_when_provider_search_enabled() -> (
    None
):
    adapter = OpenAIAdapter(
        api_key="test-key",
        base_url="https://api.example.com",
        provider_config={
            "wire_api": "responses",
            "web_search": {"enabled": True},
        },
    )

    request = await adapter._build_responses_request(
        messages=[ChatMessage(role="user", content="hello")],
        model="gpt-5.4-xhigh",
        tools=[
            {"type": "function", "function": {"name": "web_search", "parameters": {}}},
        ],
        tool_choice="required",
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
async def test_build_responses_request_ignores_legacy_hosted_search_rewrite_config() -> (
    None
):
    adapter = OpenAIAdapter(
        api_key="test-key",
        base_url="https://api.example.com",
        provider_config={
            "wire_api": "responses",
            "web_search": {
                "enabled": True,
                "hosted_tool_rewrite_enabled": True,
                "prefer_hosted_tool": True,
            },
        },
    )

    request = await adapter._build_responses_request(
        messages=[ChatMessage(role="user", content="hello")],
        model="gpt-5.4-xhigh",
        tools=[
            {"type": "function", "function": {"name": "web_search", "parameters": {}}},
        ],
        tool_choice="required",
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
async def test_build_responses_request_preserves_explicit_reasoning_effort() -> None:
    adapter = OpenAIAdapter(
        api_key="test-key",
        base_url="https://api.example.com",
        provider_config={"wire_api": "responses"},
    )

    request = await adapter._build_responses_request(
        messages=[ChatMessage(role="user", content="hello")],
        model="gpt-5.4-xhigh",
        reasoning={"effort": "high"},
    )

    assert request["reasoning"] == {
        "effort": "high",
        "summary": "auto",
    }


def test_build_chat_completions_request_applies_model_config_reasoning_effort() -> None:
    adapter = OpenAIAdapter(
        api_key="test-key",
        base_url="https://api.example.com",
    )

    request = adapter._build_chat_completions_request(
        openai_messages=[{"role": "user", "content": "hello"}],
        model="gpt-5.4",
        temperature=0.7,
        max_tokens=128,
        top_p=1.0,
        tools=None,
        tool_choice=None,
        stream=False,
        model_config={
            "runtime_overrides": {
                "openai_compatible": {
                    "chat_completions": {"reasoning_effort": "xhigh"},
                }
            }
        },
    )

    assert request["model"] == "gpt-5.4"
    assert request["reasoning_effort"] == "xhigh"


@pytest.mark.asyncio
async def test_build_responses_request_applies_model_config_reasoning_effort() -> None:
    adapter = OpenAIAdapter(
        api_key="test-key",
        base_url="https://api.example.com",
        provider_config={"wire_api": "responses"},
    )

    request = await adapter._build_responses_request(
        messages=[ChatMessage(role="user", content="hello")],
        model="gpt-5.4",
        model_config={
            "runtime_overrides": {
                "openai_compatible": {
                    "responses": {"reasoning": {"effort": "xhigh"}},
                }
            }
        },
    )

    assert request["model"] == "gpt-5.4"
    assert request["reasoning"] == {
        "effort": "xhigh",
        "summary": "auto",
    }


@pytest.mark.asyncio
async def test_build_responses_request_legacy_alias_uses_base_model_and_effort() -> (
    None
):
    adapter = OpenAIAdapter(
        api_key="test-key",
        base_url="https://api.example.com",
        provider_config={"wire_api": "responses"},
    )

    request = await adapter._build_responses_request(
        messages=[ChatMessage(role="user", content="hello")],
        model="gpt-5.4-xhigh",
    )

    assert request["model"] == "gpt-5.4"
    assert request["reasoning"] == {
        "effort": "xhigh",
        "summary": "auto",
    }


def test_build_chat_completions_request_keeps_plain_model_without_reasoning_override() -> (
    None
):
    adapter = OpenAIAdapter(
        api_key="test-key",
        base_url="https://api.example.com",
    )

    request = adapter._build_chat_completions_request(
        openai_messages=[{"role": "user", "content": "hello"}],
        model="deepseek-chat",
        temperature=0.7,
        max_tokens=None,
        top_p=1.0,
        tools=None,
        tool_choice=None,
        stream=False,
    )

    assert request["model"] == "deepseek-chat"
    assert "reasoning_effort" not in request


def test_build_chat_completions_request_ignores_reasoning_effort_for_unsupported_model() -> (
    None
):
    adapter = OpenAIAdapter(
        api_key="test-key",
        base_url="https://api.example.com",
    )

    request = adapter._build_chat_completions_request(
        openai_messages=[{"role": "user", "content": "hello"}],
        model="claude-3-5-sonnet",
        temperature=0.7,
        max_tokens=128,
        top_p=1.0,
        tools=None,
        tool_choice=None,
        stream=False,
        model_config={
            "runtime_overrides": {
                "openai_compatible": {
                    "chat_completions": {"reasoning_effort": "xhigh"},
                }
            }
        },
    )

    assert request["model"] == "claude-3-5-sonnet"
    assert "reasoning_effort" not in request


def test_resolve_effective_model_request_reports_ignored_overrides_for_unsupported_model() -> (
    None
):
    effective_request = OpenAIAdapter.resolve_effective_model_request(
        model="claude-3-5-sonnet",
        model_config={
            "runtime_overrides": {
                "openai_compatible": {
                    "responses": {"reasoning": {"effort": "xhigh"}},
                }
            }
        },
        wire_api="responses",
    )

    assert effective_request["upstream_model"] == "claude-3-5-sonnet"
    assert effective_request["applied_overrides"] == []
    assert (
        "runtime_overrides.openai_compatible.responses.reasoning.effort"
        in effective_request["ignored_overrides"]
    )
    assert (
        effective_request["ignore_reasons"][
            "runtime_overrides.openai_compatible.responses.reasoning.effort"
        ]
        == "unsupported_model_family"
    )


def test_convert_responses_chat_response_extracts_reasoning_summary() -> None:
    adapter = OpenAIAdapter(
        api_key="test-key",
        base_url="https://api.example.com",
        provider_config={"wire_api": "responses"},
    )

    response_obj = SimpleNamespace(
        object="response",
        status="completed",
        usage=SimpleNamespace(input_tokens=12, output_tokens=8, total_tokens=20),
        output=[
            SimpleNamespace(
                type="reasoning",
                summary=[SimpleNamespace(text="先读取上下文，再决定是否调用工具。")],
            ),
            _make_responses_message("hello from responses"),
        ],
        output_text="hello from responses",
        model_dump=lambda: {"ok": True},
    )

    result = adapter._convert_responses_chat_response(
        response_obj,
        "gpt-5.4-xhigh",
    )

    assert result.message.content == "hello from responses"
    assert result.message.reasoning_content == "先读取上下文，再决定是否调用工具。"


def test_convert_responses_chat_response_accepts_chat_style_usage_fields() -> None:
    adapter = OpenAIAdapter(
        api_key="test-key",
        base_url="https://api.example.com",
        provider_config={"wire_api": "responses"},
    )

    response_obj = SimpleNamespace(
        object="response",
        status="completed",
        usage={
            "prompt_tokens": 21,
            "completion_tokens": 13,
            "total_tokens": 34,
        },
        output=[_make_responses_message("兼容网关也要记 token")],
        output_text="兼容网关也要记 token",
        model_dump=lambda: {"ok": True},
    )

    result = adapter._convert_responses_chat_response(
        response_obj,
        "gpt-5.4-xhigh",
    )

    assert result.input_tokens == 21
    assert result.output_tokens == 13
    assert result.total_tokens == 34


@pytest.mark.asyncio
async def test_stream_chat_responses_completed_accepts_chat_style_usage_fields() -> (
    None
):
    class _FakeResponsesStream:
        def __init__(self, events):
            self._events = events

        def __aiter__(self):
            self._iter = iter(self._events)
            return self

        async def __anext__(self):
            try:
                return next(self._iter)
            except StopIteration as exc:
                raise StopAsyncIteration from exc

        async def aclose(self) -> None:
            return None

    adapter = OpenAIAdapter(
        api_key="test-key",
        base_url="https://api.example.com",
        provider_config={"wire_api": "responses"},
    )
    completed_response = SimpleNamespace(
        usage={
            "prompt_tokens": 9,
            "completion_tokens": 6,
            "total_tokens": 15,
        },
        output_text="OK",
        output=[],
    )
    adapter.client = SimpleNamespace(
        responses=SimpleNamespace(
            create=_FakeResponses(
                _FakeResponsesStream(
                    [
                        SimpleNamespace(type="response.output_text.delta", delta="O"),
                        SimpleNamespace(type="response.output_text.delta", delta="K"),
                        SimpleNamespace(
                            type="response.completed", response=completed_response
                        ),
                    ]
                )
            ).create,
        ),
        chat=SimpleNamespace(completions=_FakeChatCompletions(None)),
    )

    chunks = []
    async for chunk in adapter.stream_chat(
        messages=[ChatMessage(role="user", content="hello")],
        model="gpt-5.4-xhigh",
    ):
        chunks.append(chunk)

    assert "".join(chunk.delta for chunk in chunks) == "OK"
    assert chunks[-1].input_tokens == 9
    assert chunks[-1].output_tokens == 6
    assert chunks[-1].total_tokens == 15
