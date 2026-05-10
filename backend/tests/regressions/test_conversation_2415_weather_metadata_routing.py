"""Test type: behavioral.

Regression for: conversation 2415.
Original symptom: "凤凰县七天的天气" selected the weather skill tools but kept a
direct_reply all-shortcircuit plan, so capability injection was bypassed and the
turn depended on a plain provider answer instead of a tool-use contract.

中文: 这个回归锚定真实会话 2415。天气能力来自已授权技能包的工具元数据，
不是主 runtime 里写死的天气插件名或工具名。
EN: This regression anchors the real conversation 2415. Weather capability
comes from authorized skill tool metadata, not hardcoded plugin/tool names in
the main runtime.

Real dependencies: plan_execution_tools, metadata matching, intent flags, and
tool policy projection.
Mocked dependencies: none.
"""

from types import SimpleNamespace

from app.ai.engine.prepare_execution_tool_helpers import plan_execution_tools
from app.ai.engine.types import ExecutionRequest, IntentPlan
from app.ai.tools.types import ToolDefinition


def test_conversation_2415_weather_query_promotes_metadata_tool_intent() -> None:
    """Test type: behavioral. A metadata-matched skill query must not remain all-shortcircuit direct_reply."""

    request = ExecutionRequest(agent_id=59, tenant_id=0, messages=[])
    messages = [SimpleNamespace(role="user", content="凤凰县七天的天气")]
    tools = [
        ToolDefinition(
            name="get_current_weather",
            description=(
                "Get real-time current weather for a city, county, district, "
                "region, or scenic area."
            ),
            semantic_family="weather",
            semantic_tags=["天气查询", "当前天气", "实时天气", "weather"],
        ),
        ToolDefinition(
            name="get_weather_forecast",
            description=(
                "Get multi-day weather forecast for a city, county, district, "
                "region, or scenic area. Supports 1-7 days forecast."
            ),
            semantic_family="weather",
            semantic_tags=["天气预报", "未来天气", "weather forecast", "forecast"],
        ),
    ]
    diagnostics = {
        "intent_plan": [
            IntentPlan(
                intent_id="intent-1",
                kind="direct_reply",
                family="none",
                order=1,
                user_visible_label="direct_reply",
                source_text="凤凰县七天的天气",
                requires_tools=False,
                shortcircuit=True,
            ).to_dict()
        ]
    }

    plan = plan_execution_tools(
        agent_id=59,
        conversation_id=2415,
        request=request,
        messages=messages,  # type: ignore[arg-type]
        tools=list(tools),
        all_tools=list(tools),
        diagnostics=diagnostics,
    )

    intent = plan.intent_plan[0]
    assert intent.kind == "weather_query"
    assert intent.family == "weather"
    assert intent.requires_tools is True
    assert intent.shortcircuit is False
    assert intent.status == "pending"
    assert intent.metadata["routing_source"] == "tool_metadata"
    assert plan.intent_flags["all_shortcircuit"] is False
    assert plan.execution_path == "normal"
    assert plan.tool_use_policy.family == "weather"
    assert plan.tool_use_policy.mode == "required"
    assert plan.tool_use_policy.retry_on_contract_breach is True
    assert plan.tool_use_policy.allowed_tool_names == [
        "get_current_weather",
        "get_weather_forecast",
    ]
    assert plan.tool_planner is not None
    assert plan.tool_planner["intent"] == "weather_query"
    assert plan.tool_planner["intent_plan"][0]["shortcircuit"] is False
