from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.ai.adapters.openai_compatible.support.native_web_search_request_builder import (
    build_native_web_search_request,
)
from app.ai.adapters.openai_compatible.support.native_web_search_result_builder import (
    build_native_web_search_items_result,
)
from app.ai.adapters.openai_compatible.support.native_web_search_stream_runtime import (
    consume_native_web_search_stream,
)


class _FakeAsyncStream:
    def __init__(self, events):
        self._events = list(events)
        self.closed = False

    def __aiter__(self):
        self._iter = iter(self._events)
        return self

    async def __anext__(self):
        try:
            return next(self._iter)
        except StopIteration as exc:
            raise StopAsyncIteration from exc

    async def aclose(self) -> None:
        self.closed = True


class _AdapterStub:
    def _extract_responses_text(self, response) -> str:
        return getattr(response, "output_text", "") or ""


def test_build_native_web_search_request_switches_include_and_stream_flags() -> None:
    request = build_native_web_search_request(
        model="gpt-5.4",
        query="hello",
        instructions="PROMPT",
        timeout_seconds=20,
        stream=False,
        include_sources=True,
    )
    stream_request = build_native_web_search_request(
        model="gpt-5.4",
        query="hello",
        instructions="PROMPT",
        timeout_seconds=20,
        stream=True,
        include_sources=True,
    )

    assert request["include"] == ["web_search_call.action.sources"]
    assert "stream" not in request
    assert stream_request["stream"] is True
    assert "include" not in stream_request


@pytest.mark.asyncio
async def test_consume_native_web_search_stream_collects_text_usage_and_call_marker() -> (
    None
):
    stream = _FakeAsyncStream(
        [
            SimpleNamespace(type="response.web_search_call.in_progress"),
            SimpleNamespace(type="response.output_text.delta", delta="https://example.com"),
            SimpleNamespace(
                type="response.completed",
                response=SimpleNamespace(
                    usage=SimpleNamespace(input_tokens=5, output_tokens=7, total_tokens=12)
                ),
            ),
        ]
    )

    capture = await consume_native_web_search_stream(
        adapter=_AdapterStub(),
        stream=stream,
        provider_label="openai",
        model="gpt-5.4",
        aclose_stream=lambda value: value.aclose(),
    )

    assert capture is not None
    assert capture.saw_web_search_call is True
    assert capture.final_text == "https://example.com"
    assert capture.response_usage.input_tokens == 5
    assert stream.closed is True


def test_build_native_web_search_items_result_reports_parse_error_without_items() -> None:
    run = build_native_web_search_items_result(
        provider_label="openai",
        backend_key="native:openai:gpt-5.4",
        items=[],
        saw_unverifiable_url=True,
        no_results_reason="no results",
        parse_error_reason="bad urls",
        input_tokens=1,
        output_tokens=2,
        total_tokens=3,
    )

    assert run.status == "parse_error"
    assert run.failure_reason == "bad urls"
    assert run.total_tokens == 3
