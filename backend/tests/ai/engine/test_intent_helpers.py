from types import SimpleNamespace

from app.ai.engine.intent_clause_helpers import _split_clauses
from app.ai.engine.intent_signal_helpers import (
    _continuation_families,
    _first_position,
    _has_page_context,
    _last_user_text,
    _page_operation_names,
    _tool_families,
)
from app.ai.tools.types import ToolDefinition
from app.ai.types import ChatMessage


def test_last_user_text_picks_latest_and_handles_empty() -> None:
    messages = [
        ChatMessage(role="user", content=" first "),
        ChatMessage(role="assistant", content="ok"),
        ChatMessage(role="user", content=" final "),
    ]

    assert _last_user_text(messages) == "final"
    assert _last_user_text(
        [
            ChatMessage(role="system", content="sys"),
            ChatMessage(role="assistant", content="assistant"),
        ]
    ) == ""


def test_page_context_helpers_resolve_context_and_page_tools() -> None:
    input_variables = {"page_context": {"page_key": "admin.ai.logs"}}

    assert _has_page_context(input_variables) is True
    assert _has_page_context({"page_context": "nope"}) is False
    assert _has_page_context(None) is False

    names = _page_operation_names(input_variables)
    assert "ui_get_snapshot" in names
    assert _page_operation_names(None) == set()


def test_tool_families_includes_page_ops_and_filters_none() -> None:
    tools = [
        ToolDefinition(name="web_search", description="Search the web"),
        ToolDefinition(name="get_current_time", description="Current time"),
        ToolDefinition(name="", description=""),
    ]

    families = _tool_families(tools, {"page_context": {"page_key": "admin.ai.logs"}})

    assert "web_research" in families
    assert "time_ops" in families
    assert "page_ops" in families
    assert "none" not in families


def test_continuation_families_merges_sources() -> None:
    context = SimpleNamespace(
        continuation_capable_families=["page_ops", ""],
        family="web_research",
        tool_families=["weather", "page_ops", ""],
    )

    assert _continuation_families(context) == {"page_ops", "web_research", "weather"}
    assert _continuation_families(None) == set()


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
