"""中文: AI 测试模块分类标记。

EN: AI test module classification marker.

Test type: structural / behavioral
Scope: Existing AI tests in this module; no real-dialogue smoke acceptance is claimed.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.ai.adapters.openai_compatible.support.usage_estimation import (
    estimate_responses_stream_usage,
)
from app.ai.adapters.openai_compatible.support.usage_fields import (
    extract_usage_int,
    extract_usage_tokens,
)
from app.ai.types import ChatMessage


def test_extract_usage_int_ignores_invalid_values() -> None:
    assert extract_usage_int({"prompt_tokens": "oops"}, "prompt_tokens") is None


def test_extract_usage_tokens_supports_prompt_and_completion_fields() -> None:
    assert extract_usage_tokens({"prompt_tokens": "5", "completion_tokens": 7}) == (
        5,
        7,
        12,
    )
    assert extract_usage_tokens(
        SimpleNamespace(input_tokens=3, output_tokens=4, total_tokens=None)
    ) == (3, 4, 7)


def test_estimate_responses_stream_usage_delegates_to_usage_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    messages = [ChatMessage(role="user", content="hello")]

    def _fake_resolve_chat_usage(**kwargs):
        assert kwargs["messages"] == messages
        assert kwargs["output_text"] == "world"
        return SimpleNamespace(input_tokens=11, output_tokens=13, total_tokens=24)

    monkeypatch.setattr(
        "app.ai.adapters.openai_compatible.support.usage_estimation.resolve_chat_usage",
        _fake_resolve_chat_usage,
    )

    assert estimate_responses_stream_usage(messages, "world") == (11, 13, 24)
