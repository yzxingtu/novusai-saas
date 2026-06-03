"""
Test type: behavioral
Scope: OpenAI-compatible client factory SDK retry ownership.
Mock strategy: patch AsyncOpenAI constructor only; runtime defaults stay real.
"""

from __future__ import annotations

from app.ai.adapters.openai_compatible.client_factory import build_openai_client


def test_build_openai_client_defaults_to_zero_sdk_retries(monkeypatch) -> None:
    captured_kwargs: list[dict[str, object]] = []

    class _FakeAsyncOpenAI:
        def __init__(self, **kwargs):
            captured_kwargs.append(dict(kwargs))

    monkeypatch.setattr(
        "app.ai.adapters.openai_compatible.client_factory.AsyncOpenAI",
        _FakeAsyncOpenAI,
    )

    build_openai_client(
        api_key="test-key",
        base_url="https://api.example.com/v1",
    )

    assert captured_kwargs == [
        {
            "api_key": "test-key",
            "base_url": "https://api.example.com/v1",
            "max_retries": 0,
        }
    ]
