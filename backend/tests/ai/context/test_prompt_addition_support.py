"""
Test type: behavioral
Scope: context prompt-addition helper output without invoking LLM/provider calls.
Mock strategy: only clocks are monkeypatched; helper logic and prompt rendering run real.
"""

from datetime import datetime, timezone
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import app.ai.context.prompt_addition_support as support
from app.ai.types import ChatMessage


def _freeze_clock(
    monkeypatch,
    *,
    local_dt: datetime,
    utc_dt: datetime,
) -> None:
    class FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):  # type: ignore[override]
            if tz is None:
                return local_dt
            return local_dt.astimezone(tz)

    monkeypatch.setattr(support, "datetime", FixedDatetime)
    monkeypatch.setattr(support, "utc_now", lambda: utc_dt)


def test_build_memory_recall_block_formats_entries() -> None:
    records = [
        SimpleNamespace(memory_type="user_profile", summary="likes cats"),
        SimpleNamespace(memory_type="", content="Met at the conference"),
    ]

    block = support.build_memory_recall_block(records)

    assert block.splitlines()[0] == "[LONG-TERM MEMORY RECALL]"
    assert "- User Profile: likes cats" in block
    assert "- Memory: Met at the conference" in block


def test_build_profile_snapshot_block_compacts_sections() -> None:
    snapshot = {
        "profile": {
            "preferences": ["uses python", "prefers pytest", "extra"],
            "facts": ["based in NYC"],
        }
    }

    block = support.build_profile_snapshot_block(snapshot)

    assert block.splitlines()[0] == "[PROFILE SNAPSHOT]"
    assert "- Preferences: uses python; prefers pytest" in block
    assert "- Facts: based in NYC" in block
    assert "extra" not in block


def test_build_web_research_date_anchor_when_tools(monkeypatch) -> None:
    local_dt = datetime(2026, 2, 3, 4, 5, 6, tzinfo=ZoneInfo("Asia/Shanghai"))
    utc_dt = datetime(2026, 2, 2, 20, 5, 6, tzinfo=timezone.utc)
    _freeze_clock(monkeypatch, local_dt=local_dt, utc_dt=utc_dt)

    messages = [ChatMessage(role="user", content="What's new today?")]
    skill_result = SimpleNamespace(tools=[SimpleNamespace(name="web_search")])

    anchor = support.build_web_research_date_anchor(
        messages, skill_result=skill_result
    )

    assert "[RUNTIME CLOCK]" in anchor
    assert "2026-02-03 04:05:06" in anchor
    assert "Asia/Shanghai" in anchor
    assert "2026-02-02" in anchor
    assert "2026" in anchor


def test_build_web_research_date_anchor_continues_follow_up() -> None:
    messages = [
        ChatMessage(
            role="assistant",
            content="",
            tool_calls=[
                {
                    "id": "c1",
                    "type": "function",
                    "function": {"name": "web_search"},
                    "success": True,
                }
            ],
        ),
        ChatMessage(role="user", content="ok"),
    ]

    anchor = support.build_web_research_date_anchor(messages, skill_result=None)

    assert "[RUNTIME CLOCK]" in anchor


def test_build_web_research_date_anchor_requires_signal() -> None:
    messages = [
        ChatMessage(role="user", content="Tell me about the roadmap"),
    ]
    skill_result = SimpleNamespace(tools=[SimpleNamespace(name="summarize")])

    anchor = support.build_web_research_date_anchor(
        messages, skill_result=skill_result
    )

    assert anchor == ""


def test_build_visible_locale_hint_uses_explicit_request_locale() -> None:
    request = SimpleNamespace(
        messages=[],
        input_variables={"locale": "zh-CN"},
    )
    visible_hint = support.build_visible_output_locale_hint(request)

    assert "zh_CN" in visible_hint
    assert "中文(Chinese)" in visible_hint
    assert "English" not in visible_hint


def test_build_visible_locale_hint_prefers_user_message_language() -> None:
    request = SimpleNamespace(
        messages=[ChatMessage(role="user", content="你好")],
        input_variables={},
    )
    visible_hint = support.build_visible_output_locale_hint(request)

    assert "zh_CN" in visible_hint
    assert "中文(Chinese)" in visible_hint
