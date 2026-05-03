"""
Test type: structural / behavioral
Scope: OpenAI adapter support mixins keep public helper seams available and
handle usage backfill/provider diagnostics without depending on live providers.
Mocked dependencies: OpenAI SDK clients and support helper callables are local
fakes; adapter glue and usage-support decision logic execute real code.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest

from app.ai.adapters.openai_adapter import SUPPORTS_NATIVE_AUDIO, OpenAIAdapter
from app.ai.types import ChatMessage, ChatResponse


def _make_adapter(*, base_url: str = "https://api.example.com") -> OpenAIAdapter:
    return OpenAIAdapter(
        api_key="test-key",
        base_url=base_url,
    )


@pytest.mark.asyncio
async def test_embedding_maps_vectors_and_usage() -> None:
    adapter = _make_adapter()
    adapter.client = SimpleNamespace(
        embeddings=SimpleNamespace(
            create=AsyncMock(
                return_value=SimpleNamespace(
                    data=[
                        SimpleNamespace(embedding=[0.1, 0.2]),
                        SimpleNamespace(embedding=[0.3, 0.4]),
                    ],
                    usage=SimpleNamespace(prompt_tokens=6, total_tokens=6),
                )
            )
        )
    )

    response = await adapter.embedding(
        ["hello", "world"],
        model="text-embedding-3-small",
    )

    assert response.embeddings == [[0.1, 0.2], [0.3, 0.4]]
    assert response.input_tokens == 6
    assert response.total_tokens == 6
    assert response.model == "text-embedding-3-small"


@pytest.mark.asyncio
async def test_list_models_preserves_ids_and_owners() -> None:
    adapter = _make_adapter()
    adapter.client = SimpleNamespace(
        models=SimpleNamespace(
            list=AsyncMock(
                return_value=SimpleNamespace(
                    data=[
                        SimpleNamespace(id="gpt-5.4", owned_by="openai"),
                        SimpleNamespace(id="deepseek-chat", owned_by=None),
                    ]
                )
            )
        )
    )

    models = await adapter.list_models()

    assert models == [
        {"id": "gpt-5.4", "owned_by": "openai"},
        {"id": "deepseek-chat", "owned_by": None},
    ]


@pytest.mark.asyncio
async def test_generate_image_preserves_urls_base64_and_revised_prompt() -> None:
    adapter = _make_adapter()
    adapter.client = SimpleNamespace(
        images=SimpleNamespace(
            generate=AsyncMock(
                return_value=SimpleNamespace(
                    data=[
                        SimpleNamespace(
                            url="https://example.com/image.png",
                            b64_json=None,
                            revised_prompt=None,
                        ),
                        SimpleNamespace(
                            url=None,
                            b64_json="YmFzZTY0",
                            revised_prompt="Refined prompt",
                        ),
                    ]
                )
            )
        )
    )

    response = await adapter.generate_image(
        prompt="draw a tree",
        model="dall-e-3",
        style="natural",
    )

    assert [image.url for image in response.images] == [
        "https://example.com/image.png",
        "YmFzZTY0",
    ]
    assert [image.is_base64 for image in response.images] == [False, True]
    assert response.revised_prompt == "Refined prompt"
    assert response.model == "dall-e-3"
    assert adapter.client.images.generate.await_args.kwargs["style"] == "natural"


def test_upstream_helpers_and_public_exports_remain_available() -> None:
    adapter = _make_adapter(base_url="https://codex.2api.com.cn")

    assert adapter._build_endpoint_url("chat/completions") == (
        "https://codex.2api.com.cn/chat/completions"
    )
    assert (
        adapter._build_chat_completions_v1_retry_base_url()
        == "https://codex.2api.com.cn/v1"
    )
    assert adapter.get_supported_features() == {
        "chat": True,
        "streaming": True,
        "function_calling": True,
        "vision": True,
        "embedding": True,
        "image_generation": True,
    }
    assert SUPPORTS_NATIVE_AUDIO is True


@pytest.mark.asyncio
async def test_usage_runtime_delegates_responses_usage_retrieve(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = _make_adapter()
    adapter.client = SimpleNamespace(responses=SimpleNamespace(retrieve=AsyncMock()))
    captured: dict[str, object] = {}

    async def _fake_retrieve_responses_usage(
        *,
        client,
        response_id: str | None,
        extract_usage_tokens,
    ) -> tuple[int | None, int | None, int | None]:
        captured["client"] = client
        captured["response_id"] = response_id
        captured["usage"] = extract_usage_tokens(
            {"prompt_tokens": 5, "completion_tokens": 7, "total_tokens": 12}
        )
        return (5, 7, 12)

    monkeypatch.setattr(
        "app.ai.adapters.openai_compatible.support.usage_runtime.retrieve_responses_usage",
        _fake_retrieve_responses_usage,
    )

    usage = await adapter._retrieve_responses_usage("resp_123")

    assert usage == (5, 7, 12)
    assert captured["client"] is adapter.client
    assert captured["response_id"] == "resp_123"
    assert captured["usage"] == (5, 7, 12)


@pytest.mark.asyncio
async def test_responses_usage_retrieve_nested_404_body_is_debug_not_warning(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.ai.adapters.openai_compatible.support import usage_support

    class _NestedBodyNotFoundError(Exception):
        def __init__(self) -> None:
            super().__init__("page not found")
            self.body = {"error": {"message": "page not found", "code": 404}}
            self.response = SimpleNamespace(text="page not found")

    debug_calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = []
    warning_calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = []
    monkeypatch.setattr(
        usage_support,
        "logger",
        SimpleNamespace(
            debug=lambda *args, **kwargs: debug_calls.append((args, kwargs)),
            warning=lambda *args, **kwargs: warning_calls.append((args, kwargs)),
        ),
    )
    client = SimpleNamespace(
        responses=SimpleNamespace(
            retrieve=AsyncMock(side_effect=_NestedBodyNotFoundError()),
        ),
    )

    result = await usage_support.retrieve_responses_usage(
        client=client,
        response_id="resp_missing",
        extract_usage_tokens=lambda _usage: (1, 2, 3),
    )

    assert result == (None, None, None)
    assert warning_calls == []
    assert len(debug_calls) == 1


def test_usage_runtime_delegates_terminal_stream_chunk_builder(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = _make_adapter()

    def _fake_build_terminal_stream_chunk(response: ChatResponse):
        assert response.message.content == "done"
        return SimpleNamespace(delta="ok", finish_reason="stop")

    monkeypatch.setattr(
        "app.ai.adapters.openai_compatible.support.usage_runtime.build_terminal_stream_chunk",
        _fake_build_terminal_stream_chunk,
    )

    chunk = adapter._chat_response_to_stream_chunk(
        ChatResponse(
            message=ChatMessage(role="assistant", content="done"),
            total_tokens=9,
        )
    )

    assert chunk.delta == "ok"
    assert chunk.finish_reason == "stop"


@pytest.mark.asyncio
async def test_multimodal_support_delegates_message_conversion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = _make_adapter()
    seen: dict[str, object] = {}

    async def _fake_convert_chat_messages_for_adapter(
        *,
        adapter,
        messages,
        supports_vision: bool = True,
        supports_audio: bool = False,
        supports_video: bool = False,
    ):
        seen["adapter"] = adapter
        seen["messages"] = messages
        seen["supports"] = (supports_vision, supports_audio, supports_video)
        return [{"role": "user", "content": "converted"}]

    monkeypatch.setattr(
        "app.ai.adapters.openai_compatible.support.multimodal_support.convert_chat_messages_for_adapter",
        _fake_convert_chat_messages_for_adapter,
    )

    converted = await adapter._convert_messages(
        [ChatMessage(role="user", content="hello")],
        supports_vision=False,
        supports_audio=True,
        supports_video=False,
    )

    assert converted == [{"role": "user", "content": "converted"}]
    assert seen["adapter"] is adapter
    assert seen["supports"] == (False, True, False)


@pytest.mark.asyncio
async def test_multimodal_support_delegates_responses_input_conversion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = _make_adapter()
    seen: dict[str, object] = {}

    async def _fake_convert_messages_to_responses_input_for_adapter(
        *,
        adapter,
        messages,
        supports_vision: bool = True,
        supports_audio: bool = False,
        supports_video: bool = False,
    ):
        seen["adapter"] = adapter
        seen["messages"] = messages
        seen["supports"] = (supports_vision, supports_audio, supports_video)
        return [{"type": "message", "role": "user", "content": "responses"}]

    monkeypatch.setattr(
        "app.ai.adapters.openai_compatible.support.multimodal_support.convert_messages_to_responses_input_for_adapter",
        _fake_convert_messages_to_responses_input_for_adapter,
    )

    converted = await adapter._convert_messages_to_responses_input(
        [ChatMessage(role="user", content="hello")],
        supports_vision=True,
        supports_audio=True,
        supports_video=False,
    )

    assert converted == [{"type": "message", "role": "user", "content": "responses"}]
    assert seen["adapter"] is adapter
    assert seen["supports"] == (True, True, False)


@pytest.mark.asyncio
async def test_multimodal_support_delegates_audio_fetch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = _make_adapter()

    async def _fake_fetch_audio_bytes_for_adapter(url: str) -> bytes | None:
        assert url == "https://example.com/audio.mp3"
        return b"audio-bytes"

    monkeypatch.setattr(
        "app.ai.adapters.openai_compatible.support.multimodal_support.fetch_audio_bytes_for_adapter",
        _fake_fetch_audio_bytes_for_adapter,
    )

    payload = await adapter._fetch_audio_bytes("https://example.com/audio.mp3")

    assert payload == b"audio-bytes"


@pytest.mark.asyncio
async def test_multimodal_support_delegates_image_resolution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = _make_adapter()
    adapter.config["internal_tenant_id"] = 42
    seen: dict[str, object] = {}

    async def _fake_resolve_image_url_for_adapter(
        *,
        config,
        att_url: str,
        att_mime: str,
        attachment_id: object = None,
    ) -> str | None:
        seen["config"] = config
        seen["att_url"] = att_url
        seen["att_mime"] = att_mime
        seen["attachment_id"] = attachment_id
        return "https://cdn.example.com/image.png"

    monkeypatch.setattr(
        "app.ai.adapters.openai_compatible.support.multimodal_support.resolve_image_url_for_adapter",
        _fake_resolve_image_url_for_adapter,
    )

    resolved = await adapter._resolve_image_url_for_llm(
        "https://example.com/file.png",
        "image/png",
        attachment_id="att-1",
    )

    assert resolved == "https://cdn.example.com/image.png"
    assert seen["config"] is adapter.config
    assert seen["att_url"] == "https://example.com/file.png"
    assert seen["att_mime"] == "image/png"
    assert seen["attachment_id"] == "att-1"
