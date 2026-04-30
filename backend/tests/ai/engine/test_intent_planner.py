"""
Test type: behavioral
Scope: Intent planner routing after page-awareness retirement.
Mocked dependencies: none.
"""

from app.ai.engine.intent_planner import IntentPlanner
from app.ai.engine.types import ResearchContinuationContext
from app.ai.tools.types import ToolDefinition
from app.ai.types import ChatMessage


def _tools() -> list[ToolDefinition]:
    return [
        ToolDefinition(name="web_search", description="Search the web"),
        ToolDefinition(name="fetch_url", description="Fetch a webpage"),
        ToolDefinition(name="get_current_weather", description="Current weather"),
        ToolDefinition(name="get_weather_forecast", description="Forecast"),
        ToolDefinition(name="get_current_time", description="Current time"),
        ToolDefinition(name="ui_get_snapshot", description="Retired page tool"),
        ToolDefinition(name="ui_click", description="Retired page tool"),
    ]


def _plan(
    user_text: str,
    *,
    input_variables: dict | None = None,
    messages: list[ChatMessage] | None = None,
    continuation: ResearchContinuationContext | None = None,
) -> list:
    return IntentPlanner.plan_turn(
        messages=messages or [ChatMessage(role="user", content=user_text)],
        tools=_tools(),
        input_variables=input_variables or {},
        continuation_context=continuation,
    )


def _legacy_page_context() -> dict:
    return {
        "page_key": "admin.ai.agents",
        "page_session_id": "retired-session",
        "ui_epoch": 1,
        "suggested_tools": {
            "primary": ["ui_get_snapshot", "ui_click"],
        },
    }


def test_intent_planner_suppresses_web_when_user_explicitly_disables_network() -> None:
    intents = _plan("不要联网，帮我搜一下北京天气")

    assert [intent.family for intent in intents] == ["weather"]
    assert intents[0].kind == "weather_query"
    assert intents[0].shortcircuit is True


def test_intent_planner_ignores_legacy_page_context_for_page_summary() -> None:
    intents = _plan(
        "看看本页面的内容然后总结一下",
        input_variables={"page_context": _legacy_page_context()},
    )

    assert [intent.family for intent in intents] == ["none"]
    assert intents[0].kind == "direct_reply"
    assert intents[0].requires_tools is False


def test_intent_planner_ignores_legacy_page_context_for_page_click_request() -> None:
    intents = _plan(
        "请点击当前页面上的创建按钮",
        input_variables={"page_context": _legacy_page_context()},
    )

    assert [intent.family for intent in intents] == ["none"]
    assert intents[0].kind == "direct_reply"
    assert intents[0].requires_tools is False


def test_intent_planner_keeps_weather_without_synthesizing_page_workflow() -> None:
    intents = _plan(
        "帮我查一下北京天气，然后在当前页面创建一条测试记录",
        input_variables={"page_context": _legacy_page_context()},
    )

    assert [intent.kind for intent in intents] == ["weather_query"]
    assert all(intent.family != "page_ops" for intent in intents)


def test_intent_planner_keeps_generic_search_as_web_research_inside_legacy_page_context() -> None:
    intents = _plan(
        "搜索一下今天 AI 新闻",
        input_variables={"page_context": _legacy_page_context()},
    )

    assert [intent.kind for intent in intents] == ["web_research"]
    assert intents[0].family == "web_research"


def test_intent_planner_retired_page_continuation_does_not_rehydrate_page_ops() -> None:
    continuation = ResearchContinuationContext(
        active=True,
        family="page_ops",
        origin="continuation",
        current_user_text="继续看",
        research_target_text="admin.ai.api-keys",
        recent_successful_tool_names=["ui_get_snapshot"],
        tool_families=["page_ops"],
        continuation_capable_families=["page_ops"],
        active_intent_kind="page_workflow",
    )

    intents = _plan(
        "继续看",
        input_variables={"page_context": _legacy_page_context()},
        continuation=continuation,
    )

    assert [intent.family for intent in intents] == ["none"]
    assert intents[0].kind == "direct_reply"
    assert intents[0].requires_tools is False


def test_intent_planner_returns_direct_reply_for_smalltalk_after_legacy_page_flow() -> None:
    intents = _plan(
        "你真聪明",
        input_variables={"page_context": _legacy_page_context()},
        messages=[
            ChatMessage(role="user", content="打开这个页面"),
            ChatMessage(
                role="assistant",
                content="",
                tool_calls=[
                    {"success": True, "function": {"name": "ui_click"}}
                ],
            ),
            ChatMessage(role="user", content="你真聪明"),
        ],
    )

    assert [intent.family for intent in intents] == ["none"]
    assert intents[0].kind == "direct_reply"
    assert intents[0].requires_tools is False
