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
