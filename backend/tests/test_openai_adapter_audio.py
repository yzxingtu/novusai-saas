"""Tests for OpenAI adapter native audio (input_audio) conversion. / 测试

Covers:
- Audio attachment with HTTP URL: mock returns wav/mp3 bytes → content contains input_audio with correct format.
- Audio attachment with data URL → input_audio block.
- Failure path (fetch fails or no URL): content is text hint [Audio: ...].
- supports_audio=False: always text hint.
- url is null or url key missing: fallback to text hint."""

from __future__ import annotations

import base64
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.ai.adapters.openai_adapter import SUPPORTS_NATIVE_AUDIO, OpenAIAdapter
from app.ai.types import ChatMessage


@pytest.fixture
def adapter() -> OpenAIAdapter:
    return OpenAIAdapter(api_key="test-key", base_url="https://api.example.com")


def _make_audio_message(
    url: str,
    mime_type: str = "audio/wav",
    name: str = "test.wav",
) -> ChatMessage:
    return ChatMessage(
        role="user",
        content="",
        attachments=[
            {"type": "audio", "url": url, "mime_type": mime_type, "name": name},
        ],
    )


@pytest.mark.asyncio
async def test_convert_messages_audio_http_url_yields_input_audio(
    adapter: OpenAIAdapter,
) -> None:
    """When supports_audio and SUPPORTS_NATIVE_AUDIO, HTTP URL returning bytes → input_audio block. / 获取/返回"""
    wav_bytes = b"fake-wav-bytes"
    mock_response = MagicMock()
    mock_response.content = wav_bytes
    mock_response.headers = {"content-length": str(len(wav_bytes))}
    mock_response.raise_for_status = MagicMock()

    async def fake_get(_url: str):
        return mock_response

    mock_client = MagicMock()
    mock_client.get = AsyncMock(side_effect=fake_get)
    mock_cm = AsyncMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_client)
    mock_cm.__aexit__ = AsyncMock(return_value=None)
    with pytest.MonkeyPatch.context() as m:
        m.setattr(
            "app.ai.adapters.openai_compatible.support.multimodal_attachment_runtime.httpx.AsyncClient",
            lambda *_args, **_kwargs: mock_cm,
        )
        messages = [
            _make_audio_message("https://example.com/audio.wav", mime_type="audio/wav")
        ]
        result = await adapter._convert_messages(
            messages,
            supports_vision=True,
            supports_audio=True,
            supports_video=False,
        )
    assert len(result) == 1
    content = result[0]["content"]
    assert isinstance(content, list)
    # One text (empty user content) + one input_audio
    parts = [p for p in content if p.get("type") == "input_audio"]
    assert len(parts) == 1
    assert parts[0]["input_audio"]["format"] == "wav"
    assert isinstance(parts[0]["input_audio"]["data"], str)
    assert base64.b64decode(parts[0]["input_audio"]["data"]) == wav_bytes


@pytest.mark.asyncio
async def test_convert_messages_audio_http_url_mp3_format(
    adapter: OpenAIAdapter,
) -> None:
    """HTTP URL with audio/mpeg → format mp3 in input_audio. / 说明"""
    mp3_bytes = b"fake-mp3"
    mock_response = MagicMock()
    mock_response.content = mp3_bytes
    mock_response.headers = {"content-length": str(len(mp3_bytes))}
    mock_response.raise_for_status = MagicMock()

    async def fake_get(_url: str):
        return mock_response

    mock_client = MagicMock()
    mock_client.get = AsyncMock(side_effect=fake_get)
    mock_cm = AsyncMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_client)
    mock_cm.__aexit__ = AsyncMock(return_value=None)
    with pytest.MonkeyPatch.context() as m:
        m.setattr(
            "app.ai.adapters.openai_compatible.support.multimodal_attachment_runtime.httpx.AsyncClient",
            lambda *_args, **_kwargs: mock_cm,
        )
        messages = [
            _make_audio_message("https://example.com/a.mp3", mime_type="audio/mpeg")
        ]
        result = await adapter._convert_messages(
            messages,
            supports_vision=True,
            supports_audio=True,
            supports_video=False,
        )
    parts = [p for p in result[0]["content"] if p.get("type") == "input_audio"]
    assert len(parts) == 1
    assert parts[0]["input_audio"]["format"] == "mp3"


@pytest.mark.asyncio
async def test_convert_messages_audio_data_url_yields_input_audio(
    adapter: OpenAIAdapter,
) -> None:
    """Data URL (data:audio/...;base64,...) → input_audio without HTTP. / 说明"""
    raw = b"small-audio"
    b64 = base64.b64encode(raw).decode("ascii")
    data_url = f"data:audio/wav;base64,{b64}"
    messages = [_make_audio_message(data_url, mime_type="audio/wav")]
    result = await adapter._convert_messages(
        messages,
        supports_vision=True,
        supports_audio=True,
        supports_video=False,
    )
    parts = [p for p in result[0]["content"] if p.get("type") == "input_audio"]
    assert len(parts) == 1
    assert base64.b64decode(parts[0]["input_audio"]["data"]) == raw
    assert parts[0]["input_audio"]["format"] == "wav"


@pytest.mark.asyncio
async def test_convert_messages_audio_fetch_failure_fallback_to_text(
    adapter: OpenAIAdapter,
) -> None:
    """When _fetch_audio_bytes fails (e.g. HTTP error), fallback to text hint. / 说明"""

    async def fake_get(_url: str):
        raise Exception("network error")

    mock_client = MagicMock()
    mock_client.get = AsyncMock(side_effect=fake_get)
    mock_cm = AsyncMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_client)
    mock_cm.__aexit__ = AsyncMock(return_value=None)
    with pytest.MonkeyPatch.context() as m:
        m.setattr(
            "app.ai.adapters.openai_compatible.support.multimodal_attachment_runtime.httpx.AsyncClient",
            lambda *_args, **_kwargs: mock_cm,
        )
        messages = [_make_audio_message("https://example.com/bad.wav")]
        result = await adapter._convert_messages(
            messages,
            supports_vision=True,
            supports_audio=True,
            supports_video=False,
        )
    content = result[0]["content"]
    text_parts = [
        p for p in content if p.get("type") == "text" and "[Audio:" in p.get("text", "")
    ]
    assert len(text_parts) == 1
    input_audio_parts = [p for p in content if p.get("type") == "input_audio"]
    assert len(input_audio_parts) == 0


@pytest.mark.asyncio
async def test_convert_messages_audio_no_url_fallback_to_text(
    adapter: OpenAIAdapter,
) -> None:
    """Audio attachment with empty URL → text hint. / 说明"""
    msg = ChatMessage(
        role="user",
        content="",
        attachments=[
            {"type": "audio", "url": "", "mime_type": "audio/wav", "name": "x.wav"}
        ],
    )
    result = await adapter._convert_messages(
        [msg],
        supports_vision=True,
        supports_audio=True,
        supports_video=False,
    )
    content = result[0]["content"]
    text_parts = [
        p for p in content if p.get("type") == "text" and "[Audio:" in p.get("text", "")
    ]
    assert len(text_parts) == 1
    assert "x.wav" in text_parts[0]["text"] or "uploaded audio" in text_parts[0]["text"]


@pytest.mark.asyncio
async def test_convert_messages_audio_url_null_fallback_to_text(
    adapter: OpenAIAdapter,
) -> None:
    """Audio attachment with url=null → text hint (no HTTP fetch). / 说明"""
    msg = ChatMessage(
        role="user",
        content="",
        attachments=[
            {"type": "audio", "url": None, "mime_type": "audio/wav", "name": "a.wav"}
        ],
    )
    result = await adapter._convert_messages(
        [msg],
        supports_vision=True,
        supports_audio=True,
        supports_video=False,
    )
    content = result[0]["content"]
    text_parts = [
        p for p in content if p.get("type") == "text" and "[Audio:" in p.get("text", "")
    ]
    assert len(text_parts) == 1
    input_audio_parts = [p for p in content if p.get("type") == "input_audio"]
    assert len(input_audio_parts) == 0


@pytest.mark.asyncio
async def test_convert_messages_audio_url_key_missing_fallback_to_text(
    adapter: OpenAIAdapter,
) -> None:
    """Audio attachment without 'url' key → text hint (att.get('url', '') yields ''). / 获取/返回"""
    msg = ChatMessage(
        role="user",
        content="",
        attachments=[{"type": "audio", "mime_type": "audio/wav", "name": "b.wav"}],
    )
    result = await adapter._convert_messages(
        [msg],
        supports_vision=True,
        supports_audio=True,
        supports_video=False,
    )
    content = result[0]["content"]
    text_parts = [
        p for p in content if p.get("type") == "text" and "[Audio:" in p.get("text", "")
    ]
    assert len(text_parts) == 1
    input_audio_parts = [p for p in content if p.get("type") == "input_audio"]
    assert len(input_audio_parts) == 0


@pytest.mark.asyncio
async def test_convert_messages_audio_supports_audio_false_yields_text(
    adapter: OpenAIAdapter,
) -> None:
    """When supports_audio=False, always text hint even if URL would work. / 说明"""
    wav_bytes = b"tiny"
    mock_response = MagicMock()
    mock_response.content = wav_bytes
    mock_response.headers = {"content-length": "4"}
    mock_response.raise_for_status = MagicMock()

    async def fake_get(_url: str):
        return mock_response

    mock_client = MagicMock()
    mock_client.get = AsyncMock(side_effect=fake_get)
    mock_cm = AsyncMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_client)
    mock_cm.__aexit__ = AsyncMock(return_value=None)
    with pytest.MonkeyPatch.context() as m:
        m.setattr(
            "app.ai.adapters.openai_compatible.support.multimodal_attachment_runtime.httpx.AsyncClient",
            lambda *_args, **_kwargs: mock_cm,
        )
        messages = [_make_audio_message("https://example.com/x.wav")]
        result = await adapter._convert_messages(
            messages,
            supports_vision=True,
            supports_audio=False,
            supports_video=False,
        )
    content = result[0]["content"]
    input_audio_parts = [p for p in content if p.get("type") == "input_audio"]
    assert len(input_audio_parts) == 0
    text_parts = [
        p for p in content if p.get("type") == "text" and "[Audio:" in p.get("text", "")
    ]
    assert len(text_parts) == 1


@pytest.mark.asyncio
async def test_convert_messages_audio_uses_payload_helper(
    adapter: OpenAIAdapter,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Audio conversion should delegate to the shared payload helper. / 说明"""
    called: dict[str, object] = {}

    async def _fake_fetch_audio_bytes(_url: str) -> bytes | None:
        return b"payload-bytes"

    def _fake_build_input_audio_part(
        audio_bytes: bytes,
        mime_type: str | None,
        *,
        audio_mime_to_openai_format: dict[str, str] | None = None,
    ) -> dict[str, object]:
        called["audio_bytes"] = audio_bytes
        called["mime_type"] = mime_type
        called["mapping"] = dict(audio_mime_to_openai_format or {})
        return {"type": "input_audio", "input_audio": {"data": "YWJj", "format": "wav"}}

    monkeypatch.setattr(
        adapter, "_fetch_audio_bytes", AsyncMock(side_effect=_fake_fetch_audio_bytes)
    )
    monkeypatch.setattr(
        "app.ai.adapters.openai_compatible.support.chat_multimodal_messages.build_input_audio_part",
        _fake_build_input_audio_part,
    )

    messages = [
        _make_audio_message("https://example.com/audio.wav", mime_type="audio/wav")
    ]
    result = await adapter._convert_messages(
        messages,
        supports_vision=True,
        supports_audio=True,
        supports_video=False,
    )

    parts = [p for p in result[0]["content"] if p.get("type") == "input_audio"]
    assert len(parts) == 1
    assert parts[0]["input_audio"]["format"] == "wav"
    assert called["audio_bytes"] == b"payload-bytes"
    assert called["mime_type"] == "audio/wav"


def test_supports_native_audio_constant() -> None:
    """SUPPORTS_NATIVE_AUDIO is True so native audio can be used when enabled. / 说明"""
    assert SUPPORTS_NATIVE_AUDIO is True
