"""
Test type: behavioral
Scope: ToolRouter live routing after AI page-awareness retirement.
Mock strategy: no mocks; verifies deterministic routing decisions.
"""

from app.ai.engine.tool_router import ToolRouter
from app.ai.engine.types import ExecutionBudget, IntentPlan
from app.ai.tools.types import ToolDefinition


def _budget(max_candidate_tools: int = 8) -> ExecutionBudget:
    return ExecutionBudget(
        max_prompt_tokens=8000,
        max_completion_tokens=2000,
        max_tool_rounds=3,
        max_elapsed_ms=60000,
        max_retry_per_intent=1,
        max_candidate_tools=max_candidate_tools,
        max_tool_result_bytes=40000,
        finalization_grace_ms=15000,
    )


def _intent(kind: str, family: str, *, metadata: dict | None = None) -> IntentPlan:
    return IntentPlan(
        intent_id=f"intent-{kind}",
        kind=kind,
        family=family,
        order=1,
        user_visible_label=kind,
        source_text=kind,
        metadata=dict(metadata or {}),
    )


def test_tool_router_does_not_reactivate_retired_page_workflow_tools() -> None:
    decision = ToolRouter.route(
        intents=[_intent("page_workflow", "page_ops")],
        tools=[
            ToolDefinition(name="ui_get_snapshot"),
            ToolDefinition(name="ui_read_region"),
            ToolDefinition(name="pageop_click"),
        ],
        budget=_budget(),
        input_variables={"page_context": {"page_key": "admin.ai.logs"}},
        user_text="帮我读取当前页面",
    )

    assert decision.candidate_tool_names() == []
    assert decision.intent_allowed_tools == {}
    assert decision.intent_preferred_tools == {}


def test_tool_router_web_fetch_ignores_stale_page_context() -> None:
    decision = ToolRouter.route(
        intents=[
            _intent(
                "web_research",
                "web_research",
                metadata={
                    "explicit_url": "https://example.com",
                    "fetch_only": True,
                    "prefer_fetch_url": True,
                },
            )
        ],
        tools=[
            ToolDefinition(name="web_search"),
            ToolDefinition(name="fetch_url"),
            ToolDefinition(name="ui_get_snapshot"),
        ],
        budget=_budget(),
        input_variables={"page_context": {"page_key": "admin.ai.logs"}},
        user_text="请抓取 https://example.com",
    )

    assert decision.candidate_tool_names() == ["fetch_url"]
    assert decision.intent_allowed_tools["intent-web_research"] == ["fetch_url"]
    assert decision.intent_preferred_tools["intent-web_research"] == ["fetch_url"]
