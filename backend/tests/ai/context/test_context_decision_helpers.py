"""中文: AI 测试模块分类标记。

EN: AI test module classification marker.

Test type: structural / behavioral
Scope: Existing AI tests in this module; no real-dialogue smoke acceptance is claimed.
"""

from app.ai.context.decision_helpers import (
    extract_last_user_text,
    looks_like_generic_follow_up,
)
from app.ai.types import ChatMessage


def test_extract_last_user_text_skips_empty_messages() -> None:
    messages = [
        ChatMessage(role="assistant", content="hello"),
        ChatMessage(role="user", content=" "),
        ChatMessage(role="user", content=" final "),
    ]

    assert extract_last_user_text(messages) == "final"


def test_looks_like_generic_follow_up_flags_short_requests() -> None:
    assert looks_like_generic_follow_up("ok")


def test_looks_like_generic_follow_up_rejects_questions_and_longer_prompts() -> None:
    assert not looks_like_generic_follow_up("ok?")
    assert not looks_like_generic_follow_up("please summarize the report for today now")
