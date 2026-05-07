from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.ai.adapters.openai_compatible import usage_parser as compat_usage_parser
from app.ai.adapters.openai_compatible.support import usage_estimation, usage_fields
from app.ai.adapters.openai_compatible.support import (
    usage_parser as support_usage_parser,
)
from app.ai.adapters.openai_compatible.usage_parser import (
    estimate_responses_stream_usage,
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


def test_compat_usage_parser_matches_support_exports() -> None:
    assert (
        compat_usage_parser.extract_usage_int is support_usage_parser.extract_usage_int
    )
    assert (
        compat_usage_parser.extract_usage_tokens
        is support_usage_parser.extract_usage_tokens
    )
    assert (
        compat_usage_parser.estimate_responses_stream_usage
        is support_usage_parser.estimate_responses_stream_usage
    )
    assert compat_usage_parser.extract_usage_int is usage_fields.extract_usage_int
    assert compat_usage_parser.extract_usage_tokens is usage_fields.extract_usage_tokens
    assert (
        compat_usage_parser.estimate_responses_stream_usage
        is usage_estimation.estimate_responses_stream_usage
    )
