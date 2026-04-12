from app.ai.engine.intent_planner import IntentPlanner
from app.ai.tools.types import ToolDefinition
from app.ai.types import ChatMessage


def test_intent_planner_facade_returns_direct_reply_for_simple_turn() -> None:
    result = IntentPlanner.plan_turn(
        messages=[ChatMessage(role="user", content="你好呀")],
        tools=[ToolDefinition(name="web_search")],
        input_variables={},
        continuation_context=None,
        capability_bundle=None,
    )

    assert len(result) == 1
    assert result[0].kind == "direct_reply"
    assert result[0].family == "none"
    assert result[0].requires_tools is False
    assert result[0].shortcircuit is True
