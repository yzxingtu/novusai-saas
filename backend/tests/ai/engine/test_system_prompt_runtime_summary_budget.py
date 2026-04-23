from __future__ import annotations

from app.ai.engine.system_prompt_runtime_summary import inject_runtime_summary
from app.ai.engine.types import ExecutionBudget, IntentPlan, ResearchContinuationContext
from app.ai.tools.types import ToolDefinition
from app.ai.types import ChatMessage
from app.ai.utils.token_estimator import estimate_tokens


def _sample_budget() -> ExecutionBudget:
    return ExecutionBudget(
        max_prompt_tokens=2000,
        max_completion_tokens=800,
        max_tool_rounds=4,
        max_elapsed_ms=20000,
        max_retry_per_intent=1,
        max_candidate_tools=8,
        max_tool_result_bytes=16000,
    )


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
    continuation = ResearchContinuationContext(
        active=True,
        family="web_research",
        origin="continuation",
        research_target_text="最新 AI 新闻",
        recent_web_queries=["latest ai news", "openai news"],
        search_query_count=2,
        fetched_url_count=0,
        research_instruction_texts=["找最新来源", "优先官方来源"],
    )
    before_tokens = estimate_tokens(messages[0].content)

    inject_runtime_summary(
        messages=messages,
        tools=tools,
        input_variables={
            "page_context": {
                "page_key": "admin.runtime.records",
                "ui_epoch": 9,
                "page_data": {
                    "search_inputs": [
                        {
                            "locator": 'input[name="title"]',
                            "label": "搜索记录标题",
                        }
                    ]
                },
            }
        },
        continuation_context=continuation,
        runtime_capability_summary={
            "selected_skill_names": ["browser", "researcher", "memory"],
            "context_line": "knowledge_base, memory, page_context",
            "knowledge_base_hint": True,
            "page_context_hint": True,
            "memory_hint": True,
        },
        intent_plan=intents,
        execution_path="normal",
        execution_budget=_sample_budget(),
    )

    delta_tokens = estimate_tokens(messages[0].content) - before_tokens

    assert delta_tokens <= 120
    assert "Budgets:" not in messages[0].content
    assert "Prefer the smallest tool sequence" not in messages[0].content
    assert "Stop after reporting completed work" not in messages[0].content
    assert "Path: normal" in messages[0].content


