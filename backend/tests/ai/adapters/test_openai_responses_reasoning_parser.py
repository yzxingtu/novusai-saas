"""中文: AI 测试模块分类标记。

EN: AI test module classification marker.

Test type: structural / behavioral
Scope: Existing AI tests in this module; no real-dialogue smoke acceptance is claimed.
"""

from __future__ import annotations

from types import SimpleNamespace

from app.ai.adapters.openai_compatible.support.responses_reasoning_parser import (
    extract_responses_reasoning_text,
)


def test_extract_responses_reasoning_text_supports_dict_payload() -> None:
    response = {
        "output": [
            {
                "type": "reasoning",
                "content": [
                    {"text": "first thought"},
                    {"summary_text": "second thought"},
                ],
            }
        ]
    }

    assert (
        extract_responses_reasoning_text(response) == "first thought\n\nsecond thought"
    )


def test_extract_responses_reasoning_text_falls_back_to_message_reasoning_blocks() -> (
    None
):
    response = SimpleNamespace(
        output=[
            SimpleNamespace(
                type="message",
                content=[
                    SimpleNamespace(type="reasoning", text="hidden reasoning"),
                    SimpleNamespace(type="output_text", text="answer"),
                ],
            )
        ]
    )

    assert extract_responses_reasoning_text(response) == "hidden reasoning"


def test_extract_responses_reasoning_text_returns_none_when_missing() -> None:
    response = SimpleNamespace(
        output=[
            SimpleNamespace(
                type="message",
                content=[SimpleNamespace(type="output_text", text="normal content")],
            )
        ]
    )

    assert extract_responses_reasoning_text(response) is None
