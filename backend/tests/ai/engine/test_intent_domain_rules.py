"""
Test type: behavioral
Scope: deterministic intent-domain classification and tool-family selection.
Mocked dependencies: none; assertions exercise real IntentDomainRules logic.
"""

from types import SimpleNamespace

from app.ai.engine.intent_domain_rules import IntentDomainRules
from app.ai.tools.types import ToolDefinition


def _tools_weather_time() -> list[ToolDefinition]:
    return [
        ToolDefinition(name="get_current_weather", description="Current weather"),
        ToolDefinition(name="get_weather_forecast", description="Forecast"),
        ToolDefinition(name="get_current_time", description="Current time"),
    ]


def _detect(
    text: str,
    *,
    tools: list[ToolDefinition] | None = None,
    capability_bundle: object | None = None,
    continuation_context: object | None = None,
) -> list:
    return IntentDomainRules.detect_domain_signals(
        clause=text,
        offset=0,
        tools=tools or [],
        input_variables={},
        capability_bundle=capability_bundle,
        continuation_context=continuation_context,
    )


def test_intent_domain_rules_detects_memory_save_and_recall() -> None:
    recall = _detect("你还记得我吗")
    assert len(recall) == 1
    assert recall[0].kind == "memory_recall"
    assert recall[0].requires_tools is False
    assert recall[0].shortcircuit is True

    save = _detect("请记住这个")
    assert len(save) == 1
    assert save[0].kind == "memory_save"
    assert save[0].requires_tools is False
    assert save[0].shortcircuit is True

    long_term_save = _detect("我叫大致坡，请把这个信息存入长期记忆")
    assert len(long_term_save) == 1
    assert long_term_save[0].kind == "memory_save"
    assert long_term_save[0].shortcircuit is True


def test_intent_domain_rules_suppresses_for_no_tool_or_capability() -> None:
    no_tool = _detect("不要使用任何工具，帮我查天气", tools=_tools_weather_time())
    assert no_tool == []

    capability = _detect("你有哪些能力，能不能调用工具", tools=_tools_weather_time())
    assert capability == []

    memory_save = _detect(
        "不要使用任何工具，但请记住这个偏好", tools=_tools_weather_time()
    )
    assert len(memory_save) == 1
    assert memory_save[0].kind == "memory_save"
    assert memory_save[0].requires_tools is False


def test_intent_domain_rules_leaves_plugin_weather_to_metadata_and_detects_time() -> (
    None
):
    signals = _detect("北京天气，现在几点", tools=_tools_weather_time())
    assert [signal.kind for signal in signals] == ["time_query"]
    assert [signal.family for signal in signals] == ["time_ops"]
    assert all(signal.shortcircuit for signal in signals)
    assert [signal.metadata.get("routing_mode") for signal in signals] == [
        "deterministic_shortcircuit",
    ]


def test_intent_domain_rules_detects_time_query_for_city_time_tool_directive() -> None:
    signals = _detect(
        "必须使用 get_current_time 工具获取当前上海时间，只回答 HH:MM；若没有实际调用工具就回答 NO_TOOL。",
        tools=_tools_weather_time(),
    )

    assert [signal.kind for signal in signals] == ["time_query"]
    assert signals[0].shortcircuit is True


def test_intent_domain_rules_detects_knowledge_query_when_kb_bound() -> None:
    kb_bundle = SimpleNamespace(context_sources=[{"kind": "knowledge_base"}])

    knowledge = _detect("向量数据库是什么", capability_bundle=kb_bundle)
    assert len(knowledge) == 1
    assert knowledge[0].kind == "knowledge_query"
    assert knowledge[0].requires_tools is False
    assert knowledge[0].metadata.get("routing_mode") == "structured_semantic"

    intro = _detect("介绍一下退货政策", capability_bundle=kb_bundle)
    assert len(intro) == 1
    assert intro[0].kind == "knowledge_query"

    memory_first = _detect("记住这个：向量数据库是什么", capability_bundle=kb_bundle)
    assert len(memory_first) == 1
    assert memory_first[0].kind in {"memory_save", "memory_recall"}
