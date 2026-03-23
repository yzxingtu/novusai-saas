from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.ai.adapters.openai_adapter import OpenAIAdapter
from app.ai.exceptions import ProviderError
from app.ai.types import ChatMessage


class _FakeChatCompletions:
    def __init__(self, response):
        self.response = response

    async def create(self, **kwargs):
        return self.response


class _FakeResponses:
    def __init__(self, response):
        self.response = response

    async def create(self, **kwargs):
        return self.response


class _FakeClient:
    def __init__(self, chat_response, responses_response):
        self.chat = SimpleNamespace(completions=_FakeChatCompletions(chat_response))
        self.responses = _FakeResponses(responses_response)


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


@pytest.mark.asyncio
async def test_chat_falls_back_to_responses_when_chat_payload_has_no_choices() -> None:
    adapter = OpenAIAdapter(api_key="test-key", base_url="https://api.example.com")
    response_obj = SimpleNamespace(
        object="response",
        status="completed",
        usage=SimpleNamespace(input_tokens=12, output_tokens=8, total_tokens=20),
        output=[
            _make_responses_message("hello from responses"),
            _make_responses_function_call("lookup_weather", '{"city":"Shanghai"}', "call_1"),
        ],
        output_text="hello from responses",
        model_dump=lambda: {"ok": True},
    )
    # Misrouted: chat.completions returns a Responses-shaped body (no choices) / 误走路由：chat 返回 Responses 形响应
    adapter.client = _FakeClient(chat_response=response_obj, responses_response=response_obj)

    result = await adapter.chat(
        messages=[ChatMessage(role="user", content="hello")],
        model="gpt-5.4-xhigh",
    )

    assert result.message.content == "hello from responses"
    assert result.total_tokens == 20
    assert result.tool_calls == [{
        "id": "call_1",
        "type": "function",
        "function": {
            "name": "lookup_weather",
            "arguments": '{"city":"Shanghai"}',
        },
    }]


@pytest.mark.asyncio
async def test_chat_does_not_fallback_when_payload_is_plain_html() -> None:
    """HTML or non-Responses garbage must not trigger responses.create / 非 Responses 结构不二次请求。"""
    adapter = OpenAIAdapter(api_key="test-key", base_url="https://api.example.com")
    adapter.client = _FakeClient(
        chat_response="<!doctype html><html></html>",
        responses_response=SimpleNamespace(output_text="should not be used"),
    )
    with pytest.raises(ProviderError, match="choices"):
        await adapter.chat(
            messages=[ChatMessage(role="user", content="hello")],
            model="gpt-4",
        )


@pytest.mark.asyncio
async def test_chat_does_not_fallback_on_error_payload_without_choices() -> None:
    adapter = OpenAIAdapter(api_key="test-key", base_url="https://api.example.com")
    adapter.client = _FakeClient(
        chat_response=SimpleNamespace(error={"message": "invalid", "type": "invalid_request_error"}),
        responses_response=SimpleNamespace(output_text="should not be used"),
    )
    with pytest.raises(ProviderError, match="choices"):
        await adapter.chat(
            messages=[ChatMessage(role="user", content="hello")],
            model="gpt-4",
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


@pytest.mark.asyncio
async def test_stream_chat_chat_completions_breaks_on_finish_reason_and_acloses() -> None:
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
        chat=SimpleNamespace(completions=SimpleNamespace(create=AsyncMock(return_value=stream))),
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
    rs = _FakeResponsesStream([
        SimpleNamespace(type="response.output_text.delta", delta="A"),
        SimpleNamespace(
            type="response.output_text.done",
            text="",
            usage=SimpleNamespace(input_tokens=2, output_tokens=3, total_tokens=5),
        ),
    ])
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
                _FakeResponsesStream([
                    SimpleNamespace(type="response.output_text.done", text="Body", usage=None),
                ])
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
    rs = _FakeResponsesStream([
        SimpleNamespace(type="response.output_text.delta", delta="O"),
        SimpleNamespace(type="response.output_text.delta", delta="K"),
        SimpleNamespace(type="response.completed", response=completed_response),
        SimpleNamespace(type="response.output_text.delta", delta="TAIL"),
    ])
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
async def test_stream_chat_emits_reasoning_from_completed_response_when_no_reasoning_delta() -> None:
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
    rs = _FakeResponsesStream([
        SimpleNamespace(type="response.output_text.delta", delta="O"),
        SimpleNamespace(type="response.output_text.delta", delta="K"),
        SimpleNamespace(type="response.completed", response=completed_response),
    ])
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

    converted = await adapter._convert_messages_to_responses_input([
        ChatMessage(
            role="assistant",
            content="",
            tool_calls=[{
                "id": "call_1",
                "type": "function",
                "function": {
                    "name": "lookup_weather",
                    "arguments": '{"city":"Shanghai"}',
                },
            }],
        ),
        ChatMessage(role="tool", content="sunny", tool_call_id="call_1"),
    ])

    assert converted == [
        {
            "type": "function_call",
            "call_id": "call_1",
            "id": "call_1",
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

def test_init_keeps_endpoint_style_base_url_and_does_not_infer_wire_api() -> None:
    adapter = OpenAIAdapter(
        api_key="test-key",
        base_url="https://code.respyun.com/v1/responses",
    )

    assert adapter.base_url == "https://code.respyun.com/v1/responses"
    assert adapter.wire_api == "chat_completions"


@pytest.mark.asyncio
async def test_build_responses_request_enables_reasoning_summary_for_gpt5() -> None:
    adapter = OpenAIAdapter(
        api_key="test-key",
        base_url="https://api.example.com",
        provider_config={"wire_api": "responses"},
    )

    request = await adapter._build_responses_request(
        messages=[ChatMessage(role="user", content="hello")],
        model="gpt-5.4-xhigh",
        stream=True,
    )

    assert request["reasoning"] == {"summary": "auto"}


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
