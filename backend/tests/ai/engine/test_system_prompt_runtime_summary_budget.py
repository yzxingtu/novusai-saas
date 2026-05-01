"""
Test type: behavioral
Scope: runtime summary prompt-budget guardrails for live-turn capability hints.
Mocked dependencies: none.
"""

from __future__ import annotations

from app.ai.engine.system_prompt_runtime_summary import inject_runtime_summary
from app.ai.tools.types import ToolDefinition
from app.ai.types import ChatMessage
from app.ai.utils.token_estimator import estimate_tokens


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

