from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.ai.adapters.openai_adapter import OpenAIAdapter
from app.ai.exceptions import ProviderError
from app.ai.runtime.query_engine import ConversationQueryEngine
from app.ai.types import ChatMessage


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
    assert result.metadata["protocol_path"] == "responses"
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
async def test_chat_retries_chat_completions_with_v1_when_root_endpoint_returns_html() -> None:
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
        chat_response=SimpleNamespace(error={"message": "invalid", "type": "invalid_request_error"}),
        responses_response=SimpleNamespace(output_text="should not be used"),
    )
    with pytest.raises(ProviderError, match="AI 请求失败"):
        await adapter.chat(
            messages=[ChatMessage(role="user", content="hello")],
            model="gpt-4",
        )


@pytest.mark.asyncio
async def test_chat_forwards_required_tool_choice_and_subset_tools_to_chat_completions() -> None:
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
    adapter = OpenAIAdapter(api_key="test-key", base_url="https://api.example.com")
    response_obj = SimpleNamespace(
        object="response",
        status="completed",
        usage=SimpleNamespace(input_tokens=10, output_tokens=5, total_tokens=15),
        output=[_make_responses_message("forced responses")],
        output_text="forced responses",
        model_dump=lambda: {"ok": True},
    )
    responses_create = AsyncMock(return_value=response_obj)
    completions_create = AsyncMock(return_value=_make_chat_completion_response("chat path"))
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
async def test_chat_falls_back_to_chat_completions_when_responses_tool_call_returns_5xx() -> None:
    adapter = OpenAIAdapter(
        api_key="test-key",
        base_url="https://api.example.com",
        provider_config={"wire_api": "responses"},
    )
    completions = _FakeChatCompletions(_make_chat_completion_response("fallback ok"))
    adapter.client = SimpleNamespace(
        responses=SimpleNamespace(
            create=AsyncMock(side_effect=_FakeStatusError(502, "Upstream request failed")),
        ),
        chat=SimpleNamespace(completions=completions),
    )

    result = await adapter.chat(
        messages=[ChatMessage(role="user", content="hello")],
        model="gpt-5.4-xhigh",
        tools=[{"type": "function", "function": {"name": "get_page_context", "parameters": {}}}],
        tool_choice="required",
    )

    assert result.message.content == "fallback ok"
    assert result.metadata["protocol_path"] == "chat_completions"
    assert completions.last_kwargs is not None
    assert completions.last_kwargs["tool_choice"] == "required"


@pytest.mark.asyncio
async def test_chat_does_not_fallback_to_chat_completions_on_responses_4xx() -> None:
    adapter = OpenAIAdapter(
        api_key="test-key",
        base_url="https://api.example.com",
        provider_config={"wire_api": "responses"},
    )
    completions = _FakeChatCompletions(_make_chat_completion_response("fallback ok"))
    adapter.client = SimpleNamespace(
        responses=SimpleNamespace(
            create=AsyncMock(side_effect=_FakeStatusError(400, "invalid request")),
        ),
        chat=SimpleNamespace(completions=completions),
    )

    with pytest.raises(ProviderError, match="AI 请求失败"):
        await adapter.chat(
            messages=[ChatMessage(role="user", content="hello")],
            model="gpt-5.4-xhigh",
            tools=[{"type": "function", "function": {"name": "get_page_context", "parameters": {}}}],
            tool_choice="required",
        )

    assert completions.last_kwargs is None


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
async def test_stream_chat_falls_back_to_chat_completions_when_responses_tool_call_returns_5xx() -> None:
    adapter = OpenAIAdapter(
        api_key="test-key",
        base_url="https://api.example.com",
        provider_config={"wire_api": "responses"},
    )
    stream = _FakeChatStream(
        [
            _fake_chat_completion_chunk("hi", None),
            _fake_chat_completion_chunk("", "stop"),
        ]
    )
    adapter.client = SimpleNamespace(
        responses=SimpleNamespace(
            create=AsyncMock(side_effect=_FakeStatusError(502, "Upstream request failed")),
        ),
        chat=SimpleNamespace(completions=SimpleNamespace(create=AsyncMock(return_value=stream))),
    )

    chunks = []
    async for chunk in adapter.stream_chat(
        messages=[ChatMessage(role="user", content="hello")],
        model="gpt-5.4-xhigh",
        tools=[{"type": "function", "function": {"name": "get_page_context", "parameters": {}}}],
        tool_choice="required",
    ):
        chunks.append(chunk)

    assert "".join(chunk.delta for chunk in chunks) == "hi"
    assert chunks[-1].finish_reason == "stop"
    assert stream.aclose_called is True


@pytest.mark.asyncio
async def test_stream_chat_responses_fallback_empty_chat_stream_rescues_with_sync_chat() -> None:
    adapter = OpenAIAdapter(
        api_key="test-key",
        base_url="https://api.example.com",
        provider_config={"wire_api": "responses"},
    )
    empty_stream = _FakeChatStream([])
    chat_create = AsyncMock(
        side_effect=[empty_stream, _make_chat_completion_response("sync rescue ok")],
    )
    adapter.client = SimpleNamespace(
        responses=SimpleNamespace(
            create=AsyncMock(side_effect=_FakeStatusError(502, "Upstream request failed")),
        ),
        chat=SimpleNamespace(completions=SimpleNamespace(create=chat_create)),
    )

    chunks = []
    async for chunk in adapter.stream_chat(
        messages=[ChatMessage(role="user", content="hello")],
        model="gpt-5.4-xhigh",
        tools=[{"type": "function", "function": {"name": "get_page_context", "parameters": {}}}],
        tool_choice="required",
    ):
        chunks.append(chunk)

    assert "".join(chunk.delta for chunk in chunks) == "sync rescue ok"
    assert chunks[-1].finish_reason == "stop"
    assert chat_create.await_count == 2
    assert empty_stream.aclose_called is True


@pytest.mark.asyncio
async def test_stream_chat_responses_fallback_failed_chat_stream_rescues_with_sync_chat() -> None:
    class _FailImmediatelyChatStream:
        def __aiter__(self):
            return self

        async def __anext__(self):
            raise RuntimeError("broken chat stream")

        async def aclose(self) -> None:
            return None

    adapter = OpenAIAdapter(
        api_key="test-key",
        base_url="https://api.example.com",
        provider_config={"wire_api": "responses"},
    )
    chat_create = AsyncMock(
        side_effect=[_FailImmediatelyChatStream(), _make_chat_completion_response("sync rescue after error")],
    )
    adapter.client = SimpleNamespace(
        responses=SimpleNamespace(
            create=AsyncMock(side_effect=_FakeStatusError(502, "Upstream request failed")),
        ),
        chat=SimpleNamespace(completions=SimpleNamespace(create=chat_create)),
    )

    chunks = []
    async for chunk in adapter.stream_chat(
        messages=[ChatMessage(role="user", content="hello")],
        model="gpt-5.4-xhigh",
        tools=[{"type": "function", "function": {"name": "get_page_context", "parameters": {}}}],
        tool_choice="required",
    ):
        chunks.append(chunk)

    assert "".join(chunk.delta for chunk in chunks) == "sync rescue after error"
    assert chunks[-1].finish_reason == "stop"
    assert chat_create.await_count == 2


@pytest.mark.asyncio
async def test_stream_chat_responses_fallback_empty_chat_stream_rescues_with_sync_raw_text() -> None:
    adapter = OpenAIAdapter(
        api_key="test-key",
        base_url="https://api.example.com",
        provider_config={"wire_api": "responses"},
    )
    empty_stream = _FakeChatStream([])
    chat_create = AsyncMock(side_effect=[empty_stream, "sync raw text rescue"])
    adapter.client = SimpleNamespace(
        responses=SimpleNamespace(
            create=AsyncMock(side_effect=_FakeStatusError(502, "Upstream request failed")),
        ),
        chat=SimpleNamespace(completions=SimpleNamespace(create=chat_create)),
    )

    chunks = []
    async for chunk in adapter.stream_chat(
        messages=[ChatMessage(role="user", content="hello")],
        model="gpt-5.4-xhigh",
        tools=[{"type": "function", "function": {"name": "get_page_context", "parameters": {}}}],
        tool_choice="required",
    ):
        chunks.append(chunk)

    assert "".join(chunk.delta for chunk in chunks) == "sync raw text rescue"
    assert chunks[-1].finish_reason == "stop"
    assert chunks[-1].metadata["response_shape"] == "raw_text"
    assert chat_create.await_count == 2
    assert empty_stream.aclose_called is True


@pytest.mark.asyncio
async def test_stream_chat_responses_fallback_sync_chat_retries_v1_when_root_returns_html() -> None:
    adapter = OpenAIAdapter(
        api_key="test-key",
        base_url="https://codex.2api.com.cn",
        provider_config={"wire_api": "responses"},
    )
    empty_stream = _FakeChatStream([])
    primary_chat_create = AsyncMock(
        side_effect=[empty_stream, "<!doctype html><html></html>"],
    )
    retry_completions = _FakeChatCompletions(
        _make_chat_completion_response("v1 stream rescue ok"),
    )
    adapter._chat_completions_v1_retry_client = SimpleNamespace(
        chat=SimpleNamespace(completions=retry_completions),
    )
    adapter._chat_completions_v1_retry_base_url = "https://codex.2api.com.cn/v1"
    adapter.client = SimpleNamespace(
        responses=SimpleNamespace(
            create=AsyncMock(side_effect=_FakeStatusError(502, "Upstream request failed")),
        ),
        chat=SimpleNamespace(completions=SimpleNamespace(create=primary_chat_create)),
    )

    chunks = []
    async for chunk in adapter.stream_chat(
        messages=[ChatMessage(role="user", content="hello")],
        model="gpt-5.4-xhigh",
        tools=[{"type": "function", "function": {"name": "get_page_context", "parameters": {}}}],
        tool_choice="required",
    ):
        chunks.append(chunk)

    assert "".join(chunk.delta for chunk in chunks) == "v1 stream rescue ok"
    assert chunks[-1].finish_reason == "stop"
    assert primary_chat_create.await_count == 2
    assert retry_completions.last_kwargs is not None
    assert empty_stream.aclose_called is True


@pytest.mark.asyncio
async def test_stream_chat_runtime_disable_cross_protocol_fallback_keeps_responses_error() -> None:
    adapter = OpenAIAdapter(
        api_key="test-key",
        base_url="https://api.example.com",
        provider_config={"wire_api": "responses"},
    )
    stream = _FakeChatStream(
        [
            _fake_chat_completion_chunk("hi", None),
            _fake_chat_completion_chunk("", "stop"),
        ]
    )
    chat_create = AsyncMock(return_value=stream)
    responses_create = AsyncMock(side_effect=_FakeStatusError(502, "Upstream request failed"))
    adapter.client = SimpleNamespace(
        responses=SimpleNamespace(create=responses_create),
        chat=SimpleNamespace(completions=SimpleNamespace(create=chat_create)),
    )

    with pytest.raises(ProviderError, match="AI 请求失败"):
        async for _ in adapter.stream_chat(
            messages=[ChatMessage(role="user", content="hello")],
            model="gpt-5.4-xhigh",
            tools=[{"type": "function", "function": {"name": "get_page_context", "parameters": {}}}],
            tool_choice="required",
            _runtime_disable_cross_protocol_fallback=True,
        ):
            pass

    assert chat_create.await_count == 0


@pytest.mark.asyncio
async def test_stream_chat_responses_error_after_meaningful_chunk_does_not_fallback() -> None:
    class _FailAfterFirstResponsesStream:
        def __init__(self) -> None:
            self._step = 0
            self.aclose_called = False

        def __aiter__(self):
            return self

        async def __anext__(self):
            if self._step == 0:
                self._step += 1
                return SimpleNamespace(type="response.output_text.delta", delta="partial")
            raise _FakeStatusError(502, "stream interrupted")

        async def aclose(self) -> None:
            self.aclose_called = True

    adapter = OpenAIAdapter(
        api_key="test-key",
        base_url="https://api.example.com",
        provider_config={"wire_api": "responses"},
    )
    stream = _FailAfterFirstResponsesStream()
    chat_create = AsyncMock(
        return_value=_FakeChatStream(
            [
                _fake_chat_completion_chunk("fallback", None),
                _fake_chat_completion_chunk("", "stop"),
            ]
        ),
    )
    adapter.client = SimpleNamespace(
        responses=SimpleNamespace(create=AsyncMock(return_value=stream)),
        chat=SimpleNamespace(completions=SimpleNamespace(create=chat_create)),
    )

    with pytest.raises(ProviderError, match="AI 请求失败"):
        async for _ in adapter.stream_chat(
            messages=[ChatMessage(role="user", content="hello")],
            model="gpt-5.4-xhigh",
            tools=[{"type": "function", "function": {"name": "get_page_context", "parameters": {}}}],
            tool_choice="required",
        ):
            pass

    assert chat_create.await_count == 0
    assert stream.aclose_called is True


class _RuntimeFakeAdapter:
    def __init__(self, *, wire_api: str = "responses"):
        self.wire_api = wire_api
        self.stream_calls: list[dict] = []
        self.chat_calls: list[dict] = []
        self._stream_behaviors: dict[str, list] = {"responses": [], "chat_completions": []}
        self._chat_behaviors: dict[str, object] = {"responses": None, "chat_completions": None}

    def set_stream(self, protocol: str, chunks: list) -> None:
        self._stream_behaviors[protocol] = list(chunks)

    def set_chat(self, protocol: str, response: object) -> None:
        self._chat_behaviors[protocol] = response

    async def stream_chat(self, **kwargs):
        forced = kwargs.get("_runtime_force_wire_api") or self.wire_api
        protocol = "responses" if str(forced).startswith("responses") else "chat_completions"
        self.stream_calls.append({"protocol": protocol, **kwargs})
        for chunk in list(self._stream_behaviors.get(protocol, [])):
            yield chunk

    async def chat(self, **kwargs):
        forced = kwargs.get("_runtime_force_wire_api") or self.wire_api
        protocol = "responses" if str(forced).startswith("responses") else "chat_completions"
        self.chat_calls.append({"protocol": protocol, **kwargs})
        result = self._chat_behaviors.get(protocol)
        if isinstance(result, Exception):
            raise result
        return result


@pytest.mark.asyncio
async def test_runtime_query_engine_required_empty_without_tool_calls_fails() -> None:
    adapter = _RuntimeFakeAdapter(wire_api="chat_completions")
    adapter.set_stream(
        "chat_completions",
        [SimpleNamespace(delta="", tool_calls=None, metadata={}, input_tokens=None, output_tokens=None, total_tokens=None)],
    )
    query_engine = ConversationQueryEngine(adapter=adapter, strict_contract=True)

    with pytest.raises(RuntimeError, match="required_tool_round_empty_no_tool_calls"):
        await query_engine.run_stream_turn(
            messages=[ChatMessage(role="user", content="请调用工具")],
            model="gpt-5.4-xhigh",
            temperature=0.7,
            max_tokens=None,
            top_p=1.0,
            tools=[{"type": "function", "function": {"name": "web_search", "parameters": {}}}],
            tool_choice="required",
            supports_vision=True,
            supports_audio=False,
            supports_video=False,
        )


@pytest.mark.asyncio
async def test_runtime_query_engine_stream_empty_after_fallback_sync_rescue_success() -> None:
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
        tools=[{"type": "function", "function": {"name": "web_search", "parameters": {}}}],
        tool_choice="required",
        supports_vision=True,
        supports_audio=False,
        supports_video=False,
    )

    assert len(chunks) == 1
    assert chunks[0].delta == "rescued reply"
    assert query_engine.turn_record.termination_reason == "protocol_fallback"
    assert query_engine.turn_record.metadata["sync_rescue"] is True
    assert [call["protocol"] for call in adapter.stream_calls] == ["responses", "chat_completions"]
    assert [call["protocol"] for call in adapter.chat_calls] == ["chat_completions"]


@pytest.mark.asyncio
async def test_runtime_query_engine_chat_turn_records_protocol_fallback_history() -> None:
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
        tools=[{"type": "function", "function": {"name": "web_search", "parameters": {}}}],
        tool_choice="auto",
        supports_vision=True,
        supports_audio=False,
        supports_video=False,
    )

    assert response.message.content == "fallback chat result"
    assert query_engine.turn_record.termination_reason == "protocol_fallback"
    assert len(query_engine.turn_record.fallback_history) == 1
    assert query_engine.turn_record.fallback_history[0].from_protocol == "responses"
    assert query_engine.turn_record.fallback_history[0].to_protocol == "chat_completions"
    assert query_engine.turn_record.fallback_history[0].reason == "exception:RuntimeError"
    assert response.metadata["runtime_turn_record"] is query_engine.turn_record
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
async def test_stream_chat_responses_output_text_done_retrieves_usage_when_event_omits_it() -> None:
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
    rs = _FakeResponsesStream([
        SimpleNamespace(type="response.created", response=created_response),
        SimpleNamespace(type="response.output_text.delta", delta="A"),
        SimpleNamespace(type="response.output_text.done", text="", usage=None),
    ])
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
async def test_stream_chat_responses_output_text_done_estimates_usage_when_retrieve_unavailable() -> None:
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
        SimpleNamespace(
            type="response.created",
            response=SimpleNamespace(id="resp_404"),
        ),
        SimpleNamespace(type="response.output_text.delta", delta="你好"),
        SimpleNamespace(type="response.output_text.done", text="", usage=None),
    ])
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


@pytest.mark.asyncio
async def test_convert_messages_to_responses_input_can_textualize_tool_roundtrip() -> None:
    adapter = OpenAIAdapter(
        api_key="test-key",
        base_url="https://api.example.com",
        provider_config={
            "wire_api": "responses",
            "responses_tool_history_mode": "text",
        },
    )

    converted = await adapter._convert_messages_to_responses_input([
        ChatMessage(
            role="assistant",
            content="我先看看页面。",
            tool_calls=[{
                "id": "call_1",
                "type": "function",
                "function": {
                    "name": "get_page_context",
                    "arguments": "{}",
                },
            }],
        ),
        ChatMessage(
            role="tool",
            content="Page: admin.ai.providers",
            tool_call_id="call_1",
        ),
    ])

    assert converted == [
        {
            "type": "message",
            "role": "assistant",
            "content": "我先看看页面。",
        },
        {
            "type": "message",
            "role": "assistant",
            "content": "Context returned by previously executed tool get_page_context:\nPage: admin.ai.providers",
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
    assert request["tools"][0]["name"] == "web_search"


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
async def test_build_responses_request_legacy_alias_uses_base_model_and_effort() -> None:
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


def test_build_chat_completions_request_keeps_plain_model_without_reasoning_override() -> None:
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


def test_build_chat_completions_request_ignores_reasoning_effort_for_unsupported_model() -> None:
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


def test_resolve_effective_model_request_reports_ignored_overrides_for_unsupported_model() -> None:
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
async def test_stream_chat_responses_completed_accepts_chat_style_usage_fields() -> None:
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
                _FakeResponsesStream([
                    SimpleNamespace(type="response.output_text.delta", delta="O"),
                    SimpleNamespace(type="response.output_text.delta", delta="K"),
                    SimpleNamespace(type="response.completed", response=completed_response),
                ])
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
