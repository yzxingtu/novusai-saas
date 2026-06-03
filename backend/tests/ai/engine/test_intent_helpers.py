"""
Test type: behavioral
Scope: intent signal helper behavior after page-operation retirement.
Mocked dependencies: none.
"""

from app.ai.engine.intent_clause_helpers import _split_clauses
from app.ai.engine.intent_signal_helpers import (
    _first_position,
    _last_user_text,
)
from app.ai.types import ChatMessage


def test_last_user_text_picks_latest_and_handles_empty() -> None:
    messages = [
        ChatMessage(role="user", content=" first "),
        ChatMessage(role="assistant", content="ok"),
        ChatMessage(role="user", content=" final "),
    ]

    assert _last_user_text(messages) == "final"
    assert (
        _last_user_text(
            [
                ChatMessage(role="system", content="sys"),
                ChatMessage(role="assistant", content="assistant"),
            ]
        )
        == ""
    )


def test_first_position_picks_earliest_and_handles_missing() -> None:
    text = "alpha then beta then gamma"

    assert _first_position(text, ("gamma", "then")) == text.find("then")
    assert _first_position(text, ("delta",)) == -1


def test_split_clauses_splits_and_falls_back() -> None:
    text = "帮我查天气，然后再查新闻"

    clauses = _split_clauses(text)
    expected_start = text.index("，然后") + len("，然后")

    assert clauses == [(0, "帮我查天气"), (expected_start, "再查新闻")]

    single = "Just a single request."
    assert _split_clauses(single) == [(0, "Just a single request.")]
