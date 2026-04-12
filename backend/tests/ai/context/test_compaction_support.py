from unittest.mock import AsyncMock

import pytest

from app.ai.context.compaction_support import (
    build_compact_summary,
    coerce_result_messages,
    compact_messages_if_needed,
    compaction_split_index,
    inject_system_prompt_additions,
    messages_token_estimate,
)
from app.ai.types import ChatMessage
from app.ai.utils.token_estimator import estimate_tokens


def test_messages_token_estimate_sums_message_content() -> None:
    messages = [
        ChatMessage(role="user", content="abcd"),
        ChatMessage(role="assistant", content="你好"),
    ]

    expected = estimate_tokens("abcd") + estimate_tokens("你好")
    assert messages_token_estimate(messages) == expected


def test_coerce_result_messages_normalizes_dicts_and_skips_invalid() -> None:
    raw_messages = [
        ChatMessage(role="user", content="hello"),
        {
            "content": "hi",
            "metadata": {"source": "test"},
            "attachments": [{"id": 1}],
        },
        "bad",
        {"role": "user", "content": None},
    ]

    result = coerce_result_messages(raw_messages)

    assert len(result) == 3
    assert result[0].role == "user"
    assert result[1].role == "assistant"
    assert result[1].content == "hi"
    assert result[1].metadata == {"source": "test"}
    assert result[1].attachments == [{"id": 1}]
    assert result[2].role == "user"
    assert result[2].content == ""


def test_inject_system_prompt_additions_merges_into_system_message() -> None:
    messages = [
        ChatMessage(role="system", content="Base  "),
        ChatMessage(role="user", content="hello"),
    ]

    injected = inject_system_prompt_additions(messages, [" First ", "", "Second"])

    assert injected is messages
    assert messages[0].content == "Base\n\nFirst\n\nSecond"


def test_compaction_split_index_keeps_last_assistants() -> None:
    messages = [
        ChatMessage(role="system", content="sys"),
        ChatMessage(role="user", content="u1"),
        ChatMessage(role="assistant", content="a1"),
        ChatMessage(role="user", content="u2"),
        ChatMessage(role="assistant", content="a2"),
        ChatMessage(role="user", content="u3"),
        ChatMessage(role="assistant", content="a3"),
    ]

    assert compaction_split_index(messages, keep_last_assistants=2) == 4


def test_compaction_split_index_caps_at_unresolved_tool_state() -> None:
    messages = [
        ChatMessage(role="system", content="sys"),
        ChatMessage(role="user", content="u1"),
        ChatMessage(role="assistant", content="a1"),
        ChatMessage(role="tool", content='{"requires_confirmation": true}'),
        ChatMessage(role="assistant", content="a2"),
        ChatMessage(role="user", content="u2"),
        ChatMessage(role="assistant", content="a3"),
    ]

    assert compaction_split_index(messages, keep_last_assistants=1) == 3


def test_build_compact_summary_uses_reasoning_content_and_truncates() -> None:
    long_content = "word " * 80
    messages = [
        ChatMessage(role="assistant", content="", reasoning_content=long_content),
    ]

    summary = build_compact_summary(messages, max_chars=1600)

    assert summary.startswith("- Assistant:")
    assert summary.endswith("...")
    assert len(summary) <= 220


def test_build_compact_summary_honors_remaining_budget() -> None:
    long_content = "x" * 800
    messages = [
        ChatMessage(role="user", content=long_content),
        ChatMessage(role="assistant", content=long_content),
    ]

    summary = build_compact_summary(messages, max_chars=10)

    assert len(summary.splitlines()) == 1


@pytest.mark.asyncio
async def test_compact_messages_if_needed_persists_summary_when_threshold_exceeded() -> (
    None
):
    messages = [
        ChatMessage(role="system", content="system"),
        ChatMessage(role="user", content="第一轮用户消息，需要被压缩。"),
        ChatMessage(role="assistant", content="第一轮助手回复，也足够长。"),
        ChatMessage(role="user", content="第二轮继续追问。"),
        ChatMessage(role="assistant", content="最近一轮助手回复。"),
    ]
    persist_snapshot = AsyncMock()

    await compact_messages_if_needed(
        context_config={
            "compact_threshold_tokens": 10,
            "compact_keep_last_assistants": 1,
            "compact_max_summary_chars": 300,
        },
        messages=messages,
        persist_snapshot=persist_snapshot,
    )

    persist_snapshot.assert_awaited_once()
    kwargs = persist_snapshot.await_args.kwargs
    assert kwargs["source_message_count"] == 3
    assert kwargs["source_token_estimate"] > 0
    assert kwargs["summary"].startswith("- User:")
