"""
Test type: behavioral
Scope: runtime summary prompt-budget guardrails for live-turn capability hints.
Mocked dependencies: none.
"""

from __future__ import annotations

from app.ai.engine.system_prompt_runtime_summary import inject_runtime_summary
from app.ai.engine.types import IntentPlan
from app.ai.tools.types import ToolDefinition
from app.ai.types import ChatMessage
from app.ai.utils.token_estimator import estimate_tokens


def test_inject_runtime_summary_stays_within_prompt_budget_when_runtime_state_is_busy() -> None:
    messages = [ChatMessage(role="system", content="SYS")]
    tools = [
        ToolDefinition(name="web_search"),
        ToolDefinition(name="fetch_url"),
        ToolDefinition(name="ui_click"),
        ToolDefinition(name="ui_read_table"),
        ToolDefinition(name="ui_list_interactables"),
    ]
    intents = [
        IntentPlan(
            intent_id="intent-1",
            kind="page_search",
            family="page_ops",
            order=1,
            user_visible_label="page_search",
            source_text="搜索当前页面中的记录",
        )
    ]
    before_tokens = estimate_tokens(messages[0].content)

    inject_runtime_summary(
        messages=messages,
        tools=tools,
        runtime_capability_summary={
            "selected_skill_names": ["browser", "researcher", "memory"],
            "selection_semantics": "turn_selected_subset",
            "selection_live": True,
            "live_turn_bound": True,
        },
        intent_plan=intents,
        execution_path="normal",
    )

    delta_tokens = estimate_tokens(messages[0].content) - before_tokens

    assert delta_tokens <= 120
    assert "Budgets:" not in messages[0].content
    assert "Prefer the smallest tool sequence" not in messages[0].content
    assert "Stop after reporting completed work" not in messages[0].content
    assert "runtime.path=normal" in messages[0].content


def test_inject_runtime_summary_skips_inventory_selected_skills_in_prompt_budget() -> None:
    messages = [ChatMessage(role="system", content="SYS")]
    tools = [ToolDefinition(name="web_search"), ToolDefinition(name="fetch_url")]
    before_tokens = estimate_tokens(messages[0].content)

    inject_runtime_summary(
        messages=messages,
        tools=tools,
        runtime_capability_summary={
            "selected_skill_names": ["browser", "researcher", "memory"],
            "selection_semantics": "capability_reporting_inventory",
            "selection_live": False,
            "live_turn_bound": False,
        },
        execution_path="normal",
    )

    delta_tokens = estimate_tokens(messages[0].content) - before_tokens

    assert delta_tokens <= 120
    assert "runtime.path=normal" in messages[0].content
    assert "runtime.selected_skills=" not in messages[0].content

