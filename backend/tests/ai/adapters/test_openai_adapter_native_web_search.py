"""
Test type: behavioral
Scope: OpenAI-compatible native web search live-path request handling.
Mock strategy: fake client transport only; native-web-search orchestration stays real.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.ai.adapters.openai_adapter import OpenAIAdapter
from app.ai.web_search.types import (
    STATUS_PARSE_ERROR,
    STATUS_SUCCESS,
    STATUS_UNSUPPORTED,
)


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


class _FakeAsyncStream:
    def __init__(self, events: list[SimpleNamespace]):
        self._events = list(events)

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


class _FakeResponsesClient:
    def __init__(self, create_impl):
        self.responses = SimpleNamespace(create=create_impl)
        self.with_options_calls: list[dict[str, object]] = []

    def with_options(self, **kwargs):
        self.with_options_calls.append(dict(kwargs))
        return self


def _make_adapter() -> OpenAIAdapter:
    return OpenAIAdapter(
        api_key="test-key",
        base_url="https://api.example.com",
        provider_config={"wire_api": "responses"},
    )


def test_supports_native_web_search_requires_responses_and_supported_model_family() -> None:
    adapter = _make_adapter()

    assert adapter.supports_native_web_search("gpt-5.4") is True
    assert adapter.supports_native_web_search("deepseek-chat") is False

    chat_adapter = OpenAIAdapter(
        api_key="test-key",
        base_url="https://api.example.com",
        provider_config={"wire_api": "chat_completions"},
    )
    assert chat_adapter.supports_native_web_search("gpt-5.4") is False


@pytest.mark.asyncio
async def test_native_web_search_normalizes_url_citations_and_sources() -> None:
    adapter = _make_adapter()
    response = SimpleNamespace(
        status="completed",
        output=[
            SimpleNamespace(
                type="message",
                content=[
                    SimpleNamespace(
                        type="output_text",
                        text="Example Source says something useful. Backup source also exists.",
                        annotations=[
                            SimpleNamespace(
                                type="url_citation",
                                title="Example Source",
                                url="https://example.com/article",
                                start_index=0,
                                end_index=14,
                            ),
                            SimpleNamespace(
                                type="url_citation",
                                title="Bad Source",
                                url="javascript:alert(1)",
                                start_index=0,
                                end_index=10,
                            ),
                        ],
                    )
                ],
            ),
            SimpleNamespace(
                type="web_search_call",
                action=SimpleNamespace(
                    sources=[
                        SimpleNamespace(url="https://backup.example.com/page"),
                        SimpleNamespace(url="file:///tmp/nope"),
                    ]
                ),
            ),
        ],
    )
    create = AsyncMock(return_value=response)
    adapter.client = SimpleNamespace(responses=SimpleNamespace(create=create))

    run = await adapter.native_web_search(
        query="OpenAI",
        max_results=5,
        locale="en",
        timeout_seconds=20,
        model="gpt-5.4",
        provider_label="openai",
        backend_key="native:openai:gpt-5.4",
    )

    assert run.status == STATUS_SUCCESS
    assert len(run.items) == 2
    assert run.items[0].title == "Example Source"
    assert run.items[0].url == "https://example.com/article"
    assert run.items[0].provider == "openai"
    assert run.items[1].url == "https://backup.example.com/page"
    assert create.await_args.kwargs["tool_choice"] == "required"
    assert create.await_args.kwargs["include"] == ["web_search_call.action.sources"]
    assert create.await_args.kwargs["tools"][0]["type"] == "web_search"


@pytest.mark.asyncio
async def test_native_web_search_applies_zero_sdk_retries_to_non_stream_request() -> (
    None
):
    adapter = _make_adapter()
    response = SimpleNamespace(
        status="completed",
        output=[
            SimpleNamespace(
                type="message",
                content=[
                    SimpleNamespace(
                        type="output_text",
                        text="Example Source",
                        annotations=[
                            SimpleNamespace(
                                type="url_citation",
                                title="Example Source",
                                url="https://example.com/article",
                                start_index=0,
                                end_index=14,
                            )
                        ],
                    )
                ],
            )
        ],
    )
    create = AsyncMock(return_value=response)
    client = _FakeResponsesClient(create)
    adapter.client = client

    run = await adapter.native_web_search(
        query="OpenAI",
        max_results=5,
        locale="en",
        timeout_seconds=20,
        model="gpt-5.4",
        provider_label="openai",
        backend_key="native:openai:gpt-5.4",
    )

    assert run.status == STATUS_SUCCESS
    assert client.with_options_calls == [{"max_retries": 0}]
    assert create.await_count == 1


@pytest.mark.asyncio
async def test_native_web_search_returns_parse_error_when_only_unverifiable_urls_exist() -> None:
    adapter = _make_adapter()
    response = SimpleNamespace(
        status="completed",
        output=[
            SimpleNamespace(
                type="message",
                content=[
                    SimpleNamespace(
                        type="output_text",
                        text="Bad source only.",
                        annotations=[
                            SimpleNamespace(
                                type="url_citation",
                                title="Bad Source",
                                url="javascript:alert(1)",
                                start_index=0,
                                end_index=10,
                            )
                        ],
                    )
                ],
            )
        ],
    )
    adapter.client = SimpleNamespace(
        responses=SimpleNamespace(create=AsyncMock(return_value=response))
    )

    run = await adapter.native_web_search(
        query="OpenAI",
        max_results=5,
        locale="en",
        timeout_seconds=20,
        model="gpt-5.4",
        provider_label="openai",
        backend_key="native:openai:gpt-5.4",
    )

    assert run.status == STATUS_PARSE_ERROR
    assert run.failure_reason == "native web search returned no verifiable absolute URLs"


@pytest.mark.asyncio
async def test_native_web_search_marks_zero_request_responses_as_unsupported() -> None:
    adapter = _make_adapter()
    response = SimpleNamespace(
        status="completed",
        output=[],
        tool_usage=SimpleNamespace(web_search=SimpleNamespace(num_requests=0)),
        usage=SimpleNamespace(input_tokens=12, output_tokens=3, total_tokens=15),
    )
    adapter.client = SimpleNamespace(
        responses=SimpleNamespace(create=AsyncMock(return_value=response))
    )

    run = await adapter.native_web_search(
        query="OpenAI",
        max_results=5,
        locale="en",
        timeout_seconds=20,
        model="gpt-5.4",
        provider_label="openai",
        backend_key="native:openai:gpt-5.4",
    )

    assert run.status == STATUS_UNSUPPORTED
    assert (
        run.failure_reason
        == "provider responses runtime accepted native web search request but did not execute hosted web_search"
    )


@pytest.mark.asyncio
async def test_native_web_search_renders_prompt_contract_and_attempts_stream_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = _make_adapter()
    empty_response = SimpleNamespace(
        status="completed",
        output=[],
        tool_usage=SimpleNamespace(web_search=SimpleNamespace(num_requests=0)),
        usage=SimpleNamespace(input_tokens=12, output_tokens=3, total_tokens=15),
    )
    stream = _FakeAsyncStream(
        [
            SimpleNamespace(type="response.web_search_call.in_progress"),
            SimpleNamespace(
                type="response.output_text.delta",
                delta="https://example.com/ai-story",
            ),
            SimpleNamespace(
                type="response.completed",
                response=SimpleNamespace(
                    usage=SimpleNamespace(
                        input_tokens=20,
                        output_tokens=10,
                        total_tokens=30,
                    )
                ),
            ),
        ]
    )
    calls: list[dict] = []

    async def _create(*args, **kwargs):
        _ = args
        calls.append(kwargs)
        if kwargs.get("stream"):
            return stream
        return empty_response

    render_calls: list[tuple[str, str | None]] = []

    def _fake_render(contract_name: str, *, locale: str | None = None, **kwargs):
        _ = kwargs
        render_calls.append((contract_name, locale))
        return "PROMPT"

    monkeypatch.setattr(
        "app.ai.adapters.openai_compatible.support.native_web_search_support.render_prompt_contract",
        _fake_render,
    )
    client = _FakeResponsesClient(_create)
    adapter.client = client

    run = await adapter.native_web_search(
        query="OpenAI",
        max_results=5,
        locale="zh-CN",
        timeout_seconds=20,
        model="gpt-5.4",
        provider_label="openai",
        backend_key="native:openai:gpt-5.4",
    )

    assert run.status == STATUS_SUCCESS
    assert render_calls == [("hosted_web_search_candidate_instructions", "zh-CN")]
    assert len(calls) == 2
    assert client.with_options_calls == [{"max_retries": 0}, {"max_retries": 0}]
    assert calls[0].get("stream") is not True
    assert calls[0]["instructions"] == "PROMPT"
    assert calls[1]["stream"] is True
    assert calls[1]["instructions"] == "PROMPT"


@pytest.mark.asyncio
async def test_native_web_search_uses_stream_fallback_when_non_stream_returns_empty_completed_body() -> None:
    adapter = _make_adapter()
    empty_response = SimpleNamespace(
        status="completed",
        output=[],
        tool_usage=SimpleNamespace(web_search=SimpleNamespace(num_requests=0)),
        usage=SimpleNamespace(input_tokens=12, output_tokens=3, total_tokens=15),
    )
    stream = _FakeAsyncStream(
        [
            SimpleNamespace(type="response.web_search_call.in_progress"),
            SimpleNamespace(type="response.web_search_call.completed"),
            SimpleNamespace(
                type="response.output_text.delta",
                delta=(
                    "Source: https://example.com/ai-story "
                    "Backup: https://backup.example.com/report"
                ),
            ),
            SimpleNamespace(
                type="response.completed",
                response=SimpleNamespace(
                    usage=SimpleNamespace(
                        input_tokens=20,
                        output_tokens=10,
                        total_tokens=30,
                    )
                ),
            ),
        ]
    )

    async def _create(*args, **kwargs):
        if kwargs.get("stream"):
            return stream
        return empty_response

    adapter.client = SimpleNamespace(responses=SimpleNamespace(create=_create))

    run = await adapter.native_web_search(
        query="OpenAI",
        max_results=5,
        locale="en",
        timeout_seconds=20,
        model="gpt-5.4",
        provider_label="openai",
        backend_key="native:openai:gpt-5.4",
    )

    assert run.status == STATUS_SUCCESS
    assert [item.url for item in run.items] == [
        "https://example.com/ai-story",
        "https://backup.example.com/report",
    ]
    assert run.input_tokens == 20
    assert run.output_tokens == 10
    assert run.total_tokens == 30


@pytest.mark.asyncio
async def test_native_web_search_maps_400_errors_to_unsupported() -> None:
    adapter = _make_adapter()
    adapter.client = SimpleNamespace(
        responses=SimpleNamespace(
            create=AsyncMock(
                side_effect=_FakeStatusError(400, "web_search tool unsupported")
            )
        )
    )

    run = await adapter.native_web_search(
        query="OpenAI",
        max_results=5,
        locale="en",
        timeout_seconds=20,
        model="gpt-5.4",
        provider_label="openai",
        backend_key="native:openai:gpt-5.4",
    )

    assert run.status == STATUS_UNSUPPORTED
