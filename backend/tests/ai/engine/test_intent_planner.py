"""
Test type: behavioral
Scope: Intent planner routing with invalid runtime context guards.
Mocked dependencies: none.
"""

from app.ai.engine.intent_planner import IntentPlanner
from app.ai.engine.types import ResearchContinuationContext
from app.ai.tools.types import ToolDefinition
from app.ai.types import ChatMessage


def _tools() -> list[ToolDefinition]:
    return [
        ToolDefinition(name="get_current_weather", description="Current weather"),
        ToolDefinition(name="get_weather_forecast", description="Forecast"),
        ToolDefinition(name="get_current_time", description="Current time"),
        ToolDefinition(name="crm_lookup", description="CRM lookup"),
        ToolDefinition(name="crm_update_record", description="CRM update record"),
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


def _invalid_runtime_context() -> dict:
    return {
        "page_key": "admin.ai.agents",
        "page_session_id": "retired-session",
        "ui_epoch": 1,
        "suggested_tools": {
            "primary": ["crm_lookup", "crm_update_record"],
        },
    }


def test_intent_planner_does_not_route_plugin_weather_when_network_disabled() -> None:
    intents = _plan("不要联网，帮我搜一下北京天气")

    assert [intent.family for intent in intents] == ["none"]
    assert intents[0].kind == "direct_reply"
    assert intents[0].shortcircuit is True


def test_intent_planner_memory_save_uses_local_cached_ack() -> None:
    intents = _plan("我叫ix long  请记住")

    assert [intent.kind for intent in intents] == ["memory_save"]
    assert intents[0].shortcircuit is True
    assert intents[0].requires_tools is False
    assert intents[0].cached_result == "已记住。"


def test_intent_planner_ignores_invalid_runtime_context_for_page_summary() -> None:
    intents = _plan(
        "看看本页面的内容然后总结一下",
        input_variables={"page_context": _invalid_runtime_context()},
    )

    assert [intent.family for intent in intents] == ["none"]
    assert intents[0].kind == "direct_reply"
    assert intents[0].requires_tools is False


def test_intent_planner_ignores_invalid_runtime_context_for_page_click_request() -> (
    None
):
    intents = _plan(
        "请点击当前数据集上的创建按钮",
        input_variables={"page_context": _invalid_runtime_context()},
    )

    assert [intent.family for intent in intents] == ["none"]
    assert intents[0].kind == "direct_reply"
    assert intents[0].requires_tools is False


def test_intent_planner_does_not_synthesize_plugin_weather_or_data_workflow() -> None:
    intents = _plan(
        "帮我查一下北京天气，然后在当前数据集创建一条测试记录",
        input_variables={"page_context": _invalid_runtime_context()},
    )

    assert [intent.kind for intent in intents] == ["direct_reply"]
    assert [intent.family for intent in intents] == ["none"]


def test_intent_planner_invalid_runtime_continuation_does_not_rehydrate_data_ops() -> (
    None
):
    continuation = ResearchContinuationContext(
        active=True,
        family="data_ops",
        origin="continuation",
        current_user_text="继续看",
        research_target_text="admin.ai.api-keys",
        recent_successful_tool_names=["crm_lookup"],
        tool_families=["data_ops"],
        continuation_capable_families=["data_ops"],
        active_intent_kind="data_workflow",
    )

    intents = _plan(
        "继续看",
        input_variables={"page_context": _invalid_runtime_context()},
        continuation=continuation,
    )

    assert [intent.family for intent in intents] == ["none"]
    assert intents[0].kind == "direct_reply"
    assert intents[0].requires_tools is False


def test_intent_planner_returns_direct_reply_for_smalltalk_after_invalid_runtime_flow() -> (
    None
):
    intents = _plan(
        "你真聪明",
        input_variables={"page_context": _invalid_runtime_context()},
        messages=[
            ChatMessage(role="user", content="打开这个页面"),
            ChatMessage(
                role="assistant",
                content="",
                tool_calls=[
                    {"success": True, "function": {"name": "crm_update_record"}}
                ],
            ),
            ChatMessage(role="user", content="你真聪明"),
        ],
    )

    assert [intent.family for intent in intents] == ["none"]
    assert intents[0].kind == "direct_reply"
    assert intents[0].requires_tools is False
