"""
Test type: structural
Scope: OpenAI Responses protocol conversion and stream event handling.
Mocked dependencies: provider response and stream payloads use in-memory
fixtures; these tests do not count as real-dialogue provider behavior.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator
from types import SimpleNamespace
from typing import Any

import pytest

from app.ai.adapters.openai_compatible import (
    protocol_responses_stream as responses_stream_protocol,
)
from app.ai.adapters.openai_compatible.protocol_responses import (
    execute_chat_via_responses,
)
from app.ai.adapters.openai_compatible.protocol_responses_stream import (
    execute_stream_chat_via_responses,
)
from app.ai.engine.stream_tool_call_helpers import (
    finalize_stream_tool_calls,
    merge_stream_tool_calls,
)
from app.ai.exceptions import ProviderAuthError, ProviderError, ProviderTimeoutError
from app.ai.types import ChatChunk, ChatMessage


class _FakeResponsesStream:
    def __init__(self, events: list[Any]) -> None:
        self._events = list(events)
        self.aclose_called = False

    def __aiter__(self) -> AsyncIterator[Any]:
        self._iter = iter(self._events)
        return self

    async def __anext__(self) -> Any:
        try:
            return next(self._iter)
        except StopIteration as exc:
            raise StopAsyncIteration from exc

    async def aclose(self) -> None:
        self.aclose_called = True


class _FakeAdapter:
    def __init__(self, stream: Any) -> None:
        self.client = SimpleNamespace(
            responses=SimpleNamespace(create=self._create),
        )
        self._stream = stream

    async def _create(self, **_kwargs: Any) -> Any:
        return self._stream

    def _normalize_timeout_seconds(self, timeout: Any) -> float | None:
        return float(timeout) if timeout is not None else None

    def _log_upstream_request(
        self,
        *,
        endpoint_path: str,
        model: str,
        stream: bool,
        wire_api: str | None = None,
    ) -> None:
        _ = endpoint_path, model, stream, wire_api

    async def _next_stream_event_with_timeout(
        self,
        stream: Any,
        *,
        timeout_seconds: float | None,
        model: str,
        wire_api: str,
    ) -> Any:
        _ = timeout_seconds, model, wire_api
        return await anext(stream)

    def _extract_usage_tokens(
        self,
        usage: Any,
    ) -> tuple[int | None, int | None, int | None]:
        if usage is None:
            return (None, None, None)
        if isinstance(usage, dict):
            return (
                usage.get("input_tokens"),
                usage.get("output_tokens"),
                usage.get("total_tokens"),
            )
        return (
            getattr(usage, "input_tokens", None),
            getattr(usage, "output_tokens", None),
            getattr(usage, "total_tokens", None),
        )

    async def _retrieve_responses_usage(
        self,
        response_id: str | None,
    ) -> tuple[int | None, int | None, int | None]:
        _ = response_id
        return (None, None, None)

    @staticmethod
    def _estimate_responses_stream_usage(
        messages: list[ChatMessage],
        output_text: str,
    ) -> tuple[int, int, int]:
        _ = messages, output_text
        return (11, 7, 18)

    def _extract_responses_reasoning_text(self, response: Any) -> str | None:
        _ = response
        return "final reasoning"

    def _extract_responses_text(self, response: Any) -> str:
        return getattr(response, "output_text", "") or ""


class _SlowCreateAdapter(_FakeAdapter):
    def __init__(self, stream: Any, *, delay_seconds: float = 0.05) -> None:
        super().__init__(stream)
        self._delay_seconds = delay_seconds

    async def _create(self, **_kwargs: Any) -> Any:
        await asyncio.sleep(self._delay_seconds)
        return self._stream


class _BlockingCreateAdapter(_FakeAdapter):
    def __init__(self, stream: Any, *, delay_seconds: float = 0.05) -> None:
        super().__init__(stream)
        self._delay_seconds = delay_seconds
        self.client = SimpleNamespace(
            responses=SimpleNamespace(create=self._create_blocking),
        )

    def _create_blocking(self, **_kwargs: Any) -> Any:
        time.sleep(self._delay_seconds)
        return self._stream


class _SlowEventAdapter(_FakeAdapter):
    def __init__(self, stream: Any, *, event_delay_seconds: float = 0.02) -> None:
        super().__init__(stream)
        self._event_delay_seconds = event_delay_seconds

    async def _next_stream_event_with_timeout(
        self,
        stream: Any,
        *,
        timeout_seconds: float | None,
        model: str,
        wire_api: str,
    ) -> Any:
        _ = timeout_seconds, model, wire_api
        await asyncio.sleep(self._event_delay_seconds)
        return await anext(stream)


@pytest.mark.asyncio
async def test_execute_chat_via_responses_raises_typed_timeout_from_failed_body() -> (
    None
):
    adapter = _FakeAdapter(
        SimpleNamespace(
            id="resp_failed_1",
            status="failed",
            error=SimpleNamespace(
                code="provider_timeout",
                message="provider request timed out",
                status_code=504,
            ),
            usage=None,
        )
    )

    with pytest.raises(ProviderTimeoutError, match="provider request timed out") as exc:
        await execute_chat_via_responses(
            adapter=adapter,
            messages=[ChatMessage(role="user", content="hello")],
            model="gpt-5.4",
            request_params={"model": "gpt-5.4"},
        )

    assert exc.value.error_code == "provider_timeout"
    assert exc.value.status_code == 504


@pytest.mark.asyncio
async def test_execute_chat_via_responses_bounds_create_stage_timeout() -> None:
    adapter = _SlowCreateAdapter(
        SimpleNamespace(id="resp_late_1", status="completed", output_text="late")
    )

    with pytest.raises(
        ProviderTimeoutError,
        match="timed out before returning a response",
    ) as exc:
        await execute_chat_via_responses(
            adapter=adapter,
            messages=[ChatMessage(role="user", content="hello")],
            model="gpt-5.4",
            request_params={"model": "gpt-5.4", "timeout": 0.01},
        )

    assert exc.value.error_code == "responses_create_timeout"
    assert exc.value.status_code == 504


@pytest.mark.asyncio
async def test_execute_chat_via_responses_bounds_blocking_create_stage_timeout() -> (
    None
):
    adapter = _BlockingCreateAdapter(
        SimpleNamespace(id="resp_late_blocking_1", status="completed")
    )

    with pytest.raises(
        ProviderTimeoutError,
        match="timed out before returning a response",
    ) as exc:
        await execute_chat_via_responses(
            adapter=adapter,
            messages=[ChatMessage(role="user", content="hello")],
            model="gpt-5.4",
            request_params={"model": "gpt-5.4", "timeout": 0.01},
        )

    assert exc.value.error_code == "responses_create_timeout"
    assert exc.value.status_code == 504


@pytest.mark.asyncio
async def test_execute_chat_via_responses_raises_typed_auth_from_failed_body() -> None:
    adapter = _FakeAdapter(
        SimpleNamespace(
            id="resp_failed_auth_1",
            status="failed",
            error=SimpleNamespace(
                code="insufficient_quota",
                message="provider quota is unavailable",
                status_code=403,
            ),
            usage=None,
        )
    )

    with pytest.raises(
        ProviderAuthError,
        match="provider quota is unavailable",
    ) as exc:
        await execute_chat_via_responses(
            adapter=adapter,
            messages=[ChatMessage(role="user", content="hello")],
            model="gpt-5.4",
            request_params={"model": "gpt-5.4"},
        )

    assert exc.value.error_code == "insufficient_quota"
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_execute_stream_chat_via_responses_completed_event_estimates_usage() -> (
    None
):
    stream = _FakeResponsesStream(
        [
            SimpleNamespace(
                type="response.completed",
                response=SimpleNamespace(
                    id="resp_1",
                    output_text="final answer",
                    usage=None,
                ),
            )
        ]
    )
    adapter = _FakeAdapter(stream)

    chunks: list[ChatChunk] = []
    async for chunk in execute_stream_chat_via_responses(
        adapter=adapter,
        messages=[ChatMessage(role="user", content="hello")],
        model="gpt-5.4",
        request_params={"model": "gpt-5.4"},
        aclose_stream=lambda s: s.aclose(),
    ):
        chunks.append(chunk)

    assert chunks[0].reasoning_delta == "final reasoning"
    assert chunks[1].delta == "final answer"
    assert chunks[2].finish_reason == "stop"
    assert chunks[2].input_tokens == 11
    assert chunks[2].output_tokens == 7
    assert chunks[2].total_tokens == 18
    assert (chunks[2].metadata or {}).get("usage_mode") == "estimated"
    assert (chunks[2].metadata or {}).get("responses_response_id") == "resp_1"
    assert stream.aclose_called is True


@pytest.mark.asyncio
async def test_execute_stream_chat_via_responses_bounds_create_stage_timeout() -> None:
    stream = _FakeResponsesStream([])
    adapter = _SlowCreateAdapter(stream)

    with pytest.raises(
        ProviderTimeoutError,
        match="timed out before returning a stream",
    ) as exc:
        async for _chunk in execute_stream_chat_via_responses(
            adapter=adapter,
            messages=[ChatMessage(role="user", content="hello")],
            model="gpt-5.4",
            request_params={"model": "gpt-5.4", "timeout": 0.01},
            aclose_stream=lambda s: s.aclose(),
        ):
            pass

    assert exc.value.error_code == "responses_stream_create_timeout"
    assert exc.value.status_code == 504
    assert stream.aclose_called is False


@pytest.mark.asyncio
async def test_execute_stream_chat_via_responses_bounds_blocking_create_stage_timeout() -> (
    None
):
    stream = _FakeResponsesStream([])
    adapter = _BlockingCreateAdapter(stream)

    with pytest.raises(
        ProviderTimeoutError,
        match="timed out before returning a stream",
    ) as exc:
        async for _chunk in execute_stream_chat_via_responses(
            adapter=adapter,
            messages=[ChatMessage(role="user", content="hello")],
            model="gpt-5.4",
            request_params={"model": "gpt-5.4", "timeout": 0.01},
            aclose_stream=lambda s: s.aclose(),
        ):
            pass

    assert exc.value.error_code == "responses_stream_create_timeout"
    assert exc.value.status_code == 504
    assert stream.aclose_called is False


@pytest.mark.asyncio
async def test_execute_stream_chat_via_responses_defaults_stream_create_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        responses_stream_protocol,
        "_DEFAULT_RESPONSES_STREAM_CREATE_TIMEOUT_SECONDS",
        0.01,
    )
    stream = _FakeResponsesStream([])
    adapter = _BlockingCreateAdapter(stream)

    with pytest.raises(
        ProviderTimeoutError,
        match="timed out before returning a stream",
    ) as exc:
        async for _chunk in execute_stream_chat_via_responses(
            adapter=adapter,
            messages=[ChatMessage(role="user", content="hello")],
            model="gpt-5.4",
            request_params={"model": "gpt-5.4", "stream": True},
            aclose_stream=lambda s: s.aclose(),
        ):
            pass

    assert exc.value.error_code == "responses_stream_create_timeout"
    assert exc.value.status_code == 504
    assert stream.aclose_called is False


@pytest.mark.asyncio
async def test_execute_stream_chat_via_responses_bounds_required_output_stall() -> None:
    stream = _FakeResponsesStream([SimpleNamespace(type="response.in_progress")])
    adapter = _SlowEventAdapter(stream)

    with pytest.raises(
        ProviderTimeoutError,
        match="timed out before required tool or text output",
    ) as exc:
        async for _chunk in execute_stream_chat_via_responses(
            adapter=adapter,
            messages=[ChatMessage(role="user", content="hello")],
            model="gpt-5.4",
            request_params={
                "model": "gpt-5.4",
                "stream": True,
                "timeout": 0.01,
                "tool_choice": "required",
            },
            aclose_stream=lambda s: s.aclose(),
        ):
            pass

    assert exc.value.error_code == "responses_stream_required_output_timeout"
    assert exc.value.status_code == 504
    assert stream.aclose_called is True


@pytest.mark.asyncio
async def test_execute_stream_chat_via_responses_defaults_required_output_stall_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        responses_stream_protocol,
        "_DEFAULT_RESPONSES_STREAM_CREATE_TIMEOUT_SECONDS",
        0.01,
    )
    stream = _FakeResponsesStream([SimpleNamespace(type="response.in_progress")])
    adapter = _SlowEventAdapter(stream)

    with pytest.raises(
        ProviderTimeoutError,
        match="timed out before required tool or text output",
    ) as exc:
        async for _chunk in execute_stream_chat_via_responses(
            adapter=adapter,
            messages=[ChatMessage(role="user", content="hello")],
            model="gpt-5.4",
            request_params={
                "model": "gpt-5.4",
                "stream": True,
                "tool_choice": "required",
            },
            aclose_stream=lambda s: s.aclose(),
        ):
            pass

    assert exc.value.error_code == "responses_stream_required_output_timeout"
    assert exc.value.status_code == 504
    assert stream.aclose_called is True


@pytest.mark.asyncio
async def test_execute_stream_chat_via_responses_raises_typed_auth_from_failed_event() -> (
    None
):
    stream = _FakeResponsesStream(
        [
            SimpleNamespace(
                type="response.failed",
                error=SimpleNamespace(
                    code="insufficient_quota",
                    message="provider quota is unavailable",
                    status_code=403,
                ),
            ),
        ]
    )
    adapter = _FakeAdapter(stream)

    with pytest.raises(
        ProviderAuthError,
        match="provider quota is unavailable",
    ) as exc:
        async for _chunk in execute_stream_chat_via_responses(
            adapter=adapter,
            messages=[ChatMessage(role="user", content="hello")],
            model="gpt-5.4",
            request_params={"model": "gpt-5.4"},
            aclose_stream=lambda s: s.aclose(),
        ):
            pass

    assert exc.value.error_code == "insufficient_quota"
    assert exc.value.status_code == 403
    assert stream.aclose_called is True


@pytest.mark.asyncio
async def test_execute_stream_chat_via_responses_raises_typed_timeout_from_error_event() -> (
    None
):
    stream = _FakeResponsesStream(
        [
            SimpleNamespace(
                type="response.error",
                error=SimpleNamespace(
                    code="provider_timeout",
                    message="provider error timed out",
                    status_code=504,
                ),
            ),
        ]
    )
    adapter = _FakeAdapter(stream)

    with pytest.raises(ProviderTimeoutError, match="provider error timed out"):
        async for _chunk in execute_stream_chat_via_responses(
            adapter=adapter,
            messages=[ChatMessage(role="user", content="hello")],
            model="gpt-5.4",
            request_params={"model": "gpt-5.4"},
            aclose_stream=lambda s: s.aclose(),
        ):
            pass

    assert stream.aclose_called is True


@pytest.mark.asyncio
async def test_execute_stream_chat_via_responses_rejects_retired_search_event() -> None:
    stream = _FakeResponsesStream(
        [
            SimpleNamespace(
                type="response.web_search_call.completed",
                item=SimpleNamespace(type="web_search_call", status="completed"),
            ),
        ]
    )
    adapter = _FakeAdapter(stream)

    with pytest.raises(ProviderError) as exc:
        async for _chunk in execute_stream_chat_via_responses(
            adapter=adapter,
            messages=[ChatMessage(role="user", content="hello")],
            model="gpt-5.4",
            request_params={"model": "gpt-5.4"},
            aclose_stream=lambda s: s.aclose(),
        ):
            pass

    assert exc.value.error_code == "retired_online_search_provider_event"
    assert stream.aclose_called is True


@pytest.mark.asyncio
async def test_execute_stream_chat_via_responses_emits_tool_call_from_output_item_done() -> (
    None
):
    stream = _FakeResponsesStream(
        [
            SimpleNamespace(
                type="response.output_item.done",
                output_index=0,
                item=SimpleNamespace(
                    type="function_call",
                    call_id="call_1",
                    name="crm_update_record",
                    arguments='{"target":"search"}',
                ),
            ),
            SimpleNamespace(
                type="response.completed",
                response=SimpleNamespace(
                    id="resp_1",
                    output_text="",
                    usage=SimpleNamespace(
                        input_tokens=2,
                        output_tokens=3,
                        total_tokens=5,
                    ),
                ),
            ),
        ]
    )
    adapter = _FakeAdapter(stream)

    chunks: list[ChatChunk] = []
    async for chunk in execute_stream_chat_via_responses(
        adapter=adapter,
        messages=[ChatMessage(role="user", content="hello")],
        model="gpt-5.4",
        request_params={"model": "gpt-5.4"},
        aclose_stream=lambda s: s.aclose(),
    ):
        chunks.append(chunk)

    assert chunks[0].tool_calls == [
        {
            "index": 0,
            "id": "call_1",
            "function": {
                "name": "crm_update_record",
                "arguments": '{"target":"search"}',
            },
        }
    ]
    assert chunks[-1].finish_reason == "stop"
    assert (chunks[-1].metadata or {}).get("responses_response_id") == "resp_1"
    assert stream.aclose_called is True


@pytest.mark.asyncio
async def test_execute_stream_chat_via_responses_emits_message_text_from_output_item_done() -> (
    None
):
    stream = _FakeResponsesStream(
        [
            SimpleNamespace(
                type="response.output_item.done",
                item=SimpleNamespace(
                    type="message",
                    content=[
                        SimpleNamespace(type="output_text", text="from output item")
                    ],
                ),
            ),
            SimpleNamespace(
                type="response.completed",
                response=SimpleNamespace(
                    id="resp_1",
                    output_text="",
                    usage=SimpleNamespace(
                        input_tokens=2,
                        output_tokens=3,
                        total_tokens=5,
                    ),
                ),
            ),
        ]
    )
    adapter = _FakeAdapter(stream)

    chunks: list[ChatChunk] = []
    async for chunk in execute_stream_chat_via_responses(
        adapter=adapter,
        messages=[ChatMessage(role="user", content="hello")],
        model="gpt-5.4",
        request_params={"model": "gpt-5.4"},
        aclose_stream=lambda s: s.aclose(),
    ):
        chunks.append(chunk)

    assert chunks[0].delta == "from output item"
    assert chunks[-1].finish_reason == "stop"
    assert stream.aclose_called is True


@pytest.mark.asyncio
async def test_execute_stream_chat_via_responses_deduplicates_function_call_done_variants() -> (
    None
):
    stream = _FakeResponsesStream(
        [
            SimpleNamespace(
                type="response.output_item.added",
                output_index=0,
                item=SimpleNamespace(
                    type="function_call",
                    call_id="call_1",
                    name="crm_list_actions",
                    arguments="",
                ),
            ),
            SimpleNamespace(
                type="response.function_call_arguments.delta",
                output_index=0,
                item_id="call_1",
                delta='{"surface_id":"active"}',
            ),
            SimpleNamespace(
                type="response.function_call_arguments.done",
                output_index=0,
                item_id="call_1",
                name="crm_list_actions",
                arguments='{"surface_id":"active"}',
            ),
            SimpleNamespace(
                type="response.output_item.done",
                output_index=0,
                item=SimpleNamespace(
                    type="function_call",
                    call_id="call_1",
                    name="crm_list_actions",
                    arguments='{"surface_id":"active"}',
                ),
            ),
            SimpleNamespace(
                type="response.completed",
                response=SimpleNamespace(
                    id="resp_1",
                    output_text="",
                    usage=SimpleNamespace(
                        input_tokens=2,
                        output_tokens=3,
                        total_tokens=5,
                    ),
                ),
            ),
        ]
    )
    adapter = _FakeAdapter(stream)

    chunks: list[ChatChunk] = []
    async for chunk in execute_stream_chat_via_responses(
        adapter=adapter,
        messages=[ChatMessage(role="user", content="hello")],
        model="gpt-5.4",
        request_params={"model": "gpt-5.4"},
        aclose_stream=lambda s: s.aclose(),
    ):
        chunks.append(chunk)

    merged: list[dict[str, Any]] = []
    for chunk in chunks:
        if chunk.tool_calls:
            merged = merge_stream_tool_calls(merged, chunk.tool_calls)

    finalized = finalize_stream_tool_calls(merged)
    assert finalized == [
        {
            "id": "call_1",
            "type": "function",
            "function": {
                "name": "crm_list_actions",
                "arguments": '{"surface_id":"active"}',
            },
        }
    ]
    assert chunks[-1].finish_reason == "stop"
    assert stream.aclose_called is True
