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


def test_tool_router_does_not_reactivate_retired_data_workflow_tools() -> None:
    decision = ToolRouter.route(
        intents=[_intent("data_workflow", "data_ops")],
        tools=[
            ToolDefinition(name="crm_lookup"),
            ToolDefinition(name="crm_read_record"),
            ToolDefinition(name="pageop_click"),
        ],
        budget=_budget(),
        input_variables={"page_context": {"page_key": "admin.ai.logs"}},
        user_text="帮我读取当前数据集",
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
            ToolDefinition(name="crm_lookup"),
        ],
        budget=_budget(),
        input_variables={"page_context": {"page_key": "admin.ai.logs"}},
        user_text="请抓取 https://example.com",
    )

    assert decision.candidate_tool_names() == ["fetch_url"]
    assert decision.intent_allowed_tools["intent-web_research"] == ["fetch_url"]
    assert decision.intent_preferred_tools["intent-web_research"] == ["fetch_url"]


def test_tool_router_generic_web_research_uses_builtin_pipeline() -> None:
    intent = _intent("web_research", "web_research")

    decision = ToolRouter.route(
        intents=[intent],
        tools=[
            ToolDefinition(name="web_search"),
            ToolDefinition(name="fetch_url"),
            ToolDefinition(name="crm_lookup"),
        ],
        budget=_budget(),
        input_variables={},
        user_text="联网查一下今天的开源模型发布",
    )

    assert decision.candidate_tool_names() == ["web_search", "fetch_url"]
    assert decision.intent_allowed_tools["intent-web_research"] == [
        "web_search",
        "fetch_url",
    ]
    assert decision.intent_preferred_tools["intent-web_research"] == [
        "web_search",
        "fetch_url",
    ]
    assert "native_search_preferred" not in intent.metadata
    assert "fallback_tool_names" not in intent.metadata


def test_tool_router_web_search_about_tools_uses_builtin_pipeline() -> None:
    intent = _intent("web_research", "web_research")

    decision = ToolRouter.route(
        intents=[intent],
        tools=[
            ToolDefinition(name="web_search"),
            ToolDefinition(name="fetch_url"),
            ToolDefinition(name="crm_lookup"),
        ],
        budget=_budget(),
        input_variables={},
        user_text="联网搜索最新 AI 工具发布，给我三个来源",
    )

    assert decision.candidate_tool_names() == ["web_search", "fetch_url"]
    assert decision.intent_allowed_tools["intent-web_research"] == [
        "web_search",
        "fetch_url",
    ]
    assert "native_search_preferred" not in intent.metadata


def test_tool_router_search_tool_as_research_subject_uses_builtin_pipeline() -> None:
    intent = _intent("web_research", "web_research")

    decision = ToolRouter.route(
        intents=[intent],
        tools=[
            ToolDefinition(name="web_search"),
            ToolDefinition(name="fetch_url"),
        ],
        budget=_budget(),
        input_variables={},
        user_text="搜索工具有哪些好用？请联网对比最新资料",
    )

    assert decision.candidate_tool_names() == ["web_search", "fetch_url"]
    assert "native_search_preferred" not in intent.metadata


def test_tool_router_search_tool_howto_subject_uses_builtin_pipeline() -> None:
    intent = _intent("web_research", "web_research")

    decision = ToolRouter.route(
        intents=[intent],
        tools=[
            ToolDefinition(name="web_search"),
            ToolDefinition(name="fetch_url"),
        ],
        budget=_budget(),
        input_variables={},
        user_text="联网搜索如何使用搜索工具的最新资料",
    )

    assert decision.candidate_tool_names() == ["web_search", "fetch_url"]
    assert decision.intent_allowed_tools["intent-web_research"] == [
        "web_search",
        "fetch_url",
    ]
    assert "native_search_preferred" not in intent.metadata


def test_tool_router_use_web_search_phrase_uses_builtin_pipeline() -> None:
    intent = _intent("web_research", "web_research")

    decision = ToolRouter.route(
        intents=[intent],
        tools=[
            ToolDefinition(name="web_search"),
            ToolDefinition(name="fetch_url"),
        ],
        budget=_budget(),
        input_variables={},
        user_text="请使用联网搜索查今天的开源模型发布",
    )

    assert decision.candidate_tool_names() == ["web_search", "fetch_url"]
    assert decision.intent_allowed_tools["intent-web_research"] == [
        "web_search",
        "fetch_url",
    ]
    assert "native_search_preferred" not in intent.metadata
    assert "fallback_tool_names" not in intent.metadata


def test_tool_router_explicit_builtin_search_request_uses_web_tools() -> None:
    intent = _intent("web_research", "web_research")

    decision = ToolRouter.route(
        intents=[intent],
        tools=[
            ToolDefinition(name="web_search"),
            ToolDefinition(name="fetch_url"),
            ToolDefinition(name="crm_lookup"),
        ],
        budget=_budget(),
        input_variables={},
        user_text="请调用 web_search 工具搜索今天的开源模型发布",
    )

    assert decision.candidate_tool_names() == ["web_search", "fetch_url"]
    assert decision.intent_allowed_tools["intent-web_research"] == [
        "web_search",
        "fetch_url",
    ]
    assert "native_search_preferred" not in intent.metadata


def test_tool_router_explicit_search_skill_request_uses_web_tools() -> None:
    intent = _intent("web_research", "web_research")

    decision = ToolRouter.route(
        intents=[intent],
        tools=[
            ToolDefinition(name="web_search"),
            ToolDefinition(name="fetch_url"),
            ToolDefinition(name="crm_lookup"),
        ],
        budget=_budget(),
        input_variables={},
        user_text="请使用联网搜索技能查今天的开源模型发布",
    )

    assert decision.candidate_tool_names() == ["web_search", "fetch_url"]
    assert decision.intent_allowed_tools["intent-web_research"] == [
        "web_search",
        "fetch_url",
    ]
    assert "native_search_preferred" not in intent.metadata
