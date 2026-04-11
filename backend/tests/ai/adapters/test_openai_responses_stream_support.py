from __future__ import annotations

from collections.abc import AsyncIterator
from types import SimpleNamespace
from typing import Any

import pytest

from app.ai.adapters.openai_compatible.protocol_responses_stream import (
    execute_stream_chat_via_responses,
)
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
    def __init__(self, stream: _FakeResponsesStream) -> None:
        self.client = SimpleNamespace(
            responses=SimpleNamespace(create=self._create),
        )
        self._stream = stream

    async def _create(self, **_kwargs: Any) -> _FakeResponsesStream:
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


@pytest.mark.asyncio
async def test_execute_stream_chat_via_responses_emits_progress_before_text() -> None:
    stream = _FakeResponsesStream(
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
    adapter = _FakeAdapter(stream)

    chunks: list[ChatChunk] = []
    async for chunk in execute_stream_chat_via_responses(
        adapter=adapter,
        messages=[ChatMessage(role="user", content="hello")],
        model="gpt-5.4",
        request_params={"model": "gpt-5.4", "timeout": 20.0},
        aclose_stream=lambda s: s.aclose(),
    ):
        chunks.append(chunk)

    assert (chunks[0].metadata or {}).get("web_search_in_progress") is True
    assert chunks[1].delta == "A"
    assert chunks[-1].finish_reason == "stop"
    assert chunks[-1].total_tokens == 5
    assert (chunks[-1].metadata or {}).get("usage_mode") == "actual"
    assert stream.aclose_called is True


@pytest.mark.asyncio
async def test_execute_stream_chat_via_responses_completed_event_estimates_usage() -> None:
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
    assert stream.aclose_called is True
