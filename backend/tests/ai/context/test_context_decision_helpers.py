from app.ai.context.decision_helpers import (
    extract_last_user_text,
    extract_recent_successful_tool_names,
    looks_like_generic_follow_up,
)
from app.ai.types import ChatMessage


def test_extract_recent_successful_tool_names_orders_latest_first() -> None:
    messages = [
        ChatMessage(role="user", content="hi"),
        ChatMessage(
            role="assistant",
            content="",
            tool_calls=[
                {
                    "id": "c1",
                    "type": "function",
                    "function": {"name": "web_search"},
                    "success": True,
                },
                {
                    "id": "c2",
                    "type": "function",
                    "function": {"name": "fetch_url"},
                    "success": True,
                },
            ],
        ),
        ChatMessage(
            role="assistant",
            content="",
            tool_calls=[
                {
                    "id": "c3",
                    "type": "function",
                    "function": {"name": "web_search"},
                    "success": True,
                },
                {
                    "id": "c4",
                    "type": "function",
                    "function": {"name": "summarize"},
                    "success": False,
                },
            ],
        ),
    ]

    assert extract_recent_successful_tool_names(messages) == [
        "web_search",
        "fetch_url",
    ]


def test_extract_recent_successful_tool_names_honors_limit() -> None:
    messages = [
        ChatMessage(
            role="assistant",
            content="",
            tool_calls=[
                {
                    "id": "c1",
                    "type": "function",
                    "function": {"name": "fetch_url"},
                    "success": True,
                },
                {
                    "id": "c2",
                    "type": "function",
                    "function": {"name": "web_search"},
                    "success": True,
                },
            ],
        )
    ]

    assert extract_recent_successful_tool_names(messages, limit=1) == ["web_search"]


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
    assert not looks_like_generic_follow_up(
        "please summarize the report for today now"
    )
