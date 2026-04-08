from types import SimpleNamespace

from app.ai.engine.intent_planner import IntentPlanner
from app.ai.engine.path_selector import PathSelector
from app.ai.engine.types import ResearchContinuationContext
from app.ai.tools.types import ToolDefinition
from app.ai.types import ChatMessage


def _tools() -> list[ToolDefinition]:
    return [
        ToolDefinition(name="web_search", description="Search the web"),
        ToolDefinition(name="fetch_url", description="Fetch a webpage"),
        ToolDefinition(name="get_page_context", description="Read current page"),
        ToolDefinition(name="invoke_page_operation", description="Operate page"),
    ]


def _tools_with_weather() -> list[ToolDefinition]:
    return [
        *_tools(),
        ToolDefinition(name="get_current_weather", description="Current weather"),
        ToolDefinition(name="get_weather_forecast", description="Forecast"),
        ToolDefinition(name="get_current_time", description="Current time"),
    ]


def _plan(
    user_text: str,
    *,
    tools: list[ToolDefinition] | None = None,
    input_variables: dict | None = None,
    messages: list[ChatMessage] | None = None,
    continuation: ResearchContinuationContext | None = None,
    capability_bundle: object | None = None,
) -> list:
    return IntentPlanner.plan_turn(
        messages=messages or [ChatMessage(role="user", content=user_text)],
        tools=tools or _tools_with_weather(),
        input_variables=input_variables or {},
        continuation_context=continuation,
        capability_bundle=capability_bundle,
    )


def _page_continuation_context(
    *,
    current_user_text: str,
    active_intent_kind: str = "page_summary",
) -> ResearchContinuationContext:
    return ResearchContinuationContext(
        active=True,
        family="page_ops",
        origin="continuation",
        current_user_text=current_user_text,
        research_target_text="admin.ai.api-keys",
        recent_successful_tool_names=["get_page_context"],
        tool_families=["page_ops"],
        page_context_attached=True,
        continuation_capable_families=["page_ops"],
        active_intent_kind=active_intent_kind,
    )


def _kb_capability_bundle() -> SimpleNamespace:
    return SimpleNamespace(context_sources=[{"kind": "knowledge_base"}])


def test_intent_planner_suppresses_web_when_user_explicitly_disables_network() -> None:
    intents = _plan("不要联网，帮我搜一下北京天气")

    assert [intent.family for intent in intents] == ["weather"]
    assert intents[0].kind == "weather_query"
    assert intents[0].shortcircuit is True


def test_intent_planner_returns_direct_reply_for_smalltalk_after_page_flow() -> None:
    intents = _plan(
        "你真聪明",
        tools=_tools(),
        input_variables={"page_context": {"page_key": "admin.ai.api-keys"}},
        messages=[
            ChatMessage(role="user", content="打开这个页面"),
            ChatMessage(
                role="assistant",
                content="",
                tool_calls=[
                    {"success": True, "function": {"name": "invoke_page_operation"}}
                ],
            ),
            ChatMessage(role="user", content="你真聪明"),
        ],
    )

    assert len(intents) == 1
    assert intents[0].family == "none"
    assert intents[0].kind == "direct_reply"
    assert intents[0].requires_tools is False
    assert intents[0].shortcircuit is True


def test_intent_planner_returns_direct_reply_for_health_phrase_after_web_flow() -> None:
    intents = _plan(
        "我肚子疼",
        tools=_tools(),
        continuation=ResearchContinuationContext(
            active=True,
            family="web_research",
            current_user_text="我肚子疼",
            research_target_text="乌克兰局势",
            recent_successful_tool_names=["web_search"],
            recent_web_queries=["乌克兰局势"],
            search_query_count=1,
            fetched_url_count=0,
        ),
        messages=[
            ChatMessage(role="user", content="联网查一下最近乌克兰的局势"),
            ChatMessage(
                role="assistant",
                content="",
                tool_calls=[{"success": True, "function": {"name": "web_search"}}],
            ),
            ChatMessage(role="user", content="我肚子疼"),
        ],
    )

    assert len(intents) == 1
    assert intents[0].family == "none"
    assert intents[0].kind == "direct_reply"
    assert intents[0].requires_tools is False
    assert intents[0].shortcircuit is True


def test_intent_planner_detects_page_summary_when_page_context_is_present() -> None:
    intents = _plan(
        "看看本页面的内容然后总结一下",
        tools=_tools(),
        input_variables={"page_context": {"page_key": "admin.ai.api-keys"}},
    )

    assert [intent.family for intent in intents] == ["page_ops"]
    assert intents[0].kind == "page_summary"
    assert intents[0].shortcircuit is True


def test_intent_planner_detects_page_continuation_summary_for_continue_look() -> None:
    intents = _plan(
        "继续看",
        tools=_tools(),
        input_variables={"page_context": {"page_key": "admin.ai.api-keys"}},
        continuation=_page_continuation_context(current_user_text="继续看"),
    )

    assert [intent.family for intent in intents] == ["page_ops"]
    assert intents[0].kind == "page_summary"
    assert intents[0].continuation is True


def test_intent_planner_detects_page_continuation_screenshot_request() -> None:
    intents = _plan(
        "截个图看",
        tools=_tools(),
        input_variables={
            "page_context": {
                "page_key": "admin.ai.api-keys",
                "page_data": {
                    "available_operations": [{"name": "capture_screenshot"}],
                },
            }
        },
        continuation=_page_continuation_context(current_user_text="截个图看"),
    )

    assert [intent.family for intent in intents] == ["page_ops"]
    assert intents[0].kind == "page_screenshot"
    assert intents[0].continuation is True


def test_intent_planner_detects_page_screenshot_request() -> None:
    intents = _plan(
        "帮我把当前页面截图发出来",
        tools=_tools(),
        input_variables={"page_context": {"page_key": "admin.ai.api-keys"}},
    )

    assert [intent.kind for intent in intents] == ["page_screenshot"]


def test_intent_planner_detects_editor_write_request() -> None:
    intents = _plan(
        "帮我修改当前编辑器标题并追加一段总结",
        tools=_tools(),
        input_variables={"page_context": {"page_key": "admin.ai.knowledge-bases"}},
    )

    assert [intent.kind for intent in intents] == ["page_editor_write"]


def test_intent_planner_detects_page_pagination_request() -> None:
    intents = _plan(
        "把列表翻到下一页",
        tools=_tools(),
        input_variables={"page_context": {"page_key": "admin.ai.logs"}},
    )

    assert [intent.kind for intent in intents] == ["page_pagination"]


def test_intent_planner_detects_page_row_detail_request() -> None:
    intents = _plan(
        "查看这条记录的详情",
        tools=_tools(),
        input_variables={"page_context": {"page_key": "admin.ai.logs"}},
    )

    assert [intent.kind for intent in intents] == ["page_row_detail"]


def test_intent_planner_prefers_page_search_over_web_search_inside_page_context() -> (
    None
):
    intents = _plan(
        "请帮我搜索记录并清空筛选条件",
        tools=_tools(),
        input_variables={"page_context": {"page_key": "admin.ai.logs"}},
    )

    assert [intent.kind for intent in intents] == ["page_search"]


def test_intent_planner_keeps_generic_search_as_web_research_inside_page_context() -> (
    None
):
    intents = _plan(
        "帮我搜索一下2026年中国新能源汽车销量排行",
        tools=_tools(),
        input_variables={"page_context": {"page_key": "admin.ai.logs"}},
    )

    assert [intent.kind for intent in intents] == ["web_research"]


def test_intent_planner_splits_shunbian_and_duile_mixed_prompt() -> None:
    intents = _plan(
        "帮我查一下北京天气，顺便搜索一下今天的热点新闻，对了这个页面上有什么",
        tools=_tools_with_weather(),
        input_variables={"page_context": {"page_key": "admin.ai.agents"}},
    )

    assert [intent.kind for intent in intents] == [
        "weather_query",
        "web_research",
        "page_summary",
    ]


def test_intent_planner_detects_time_and_weather_as_two_intents() -> None:
    intents = _plan("帮我看一下北京天气，再告诉我今天星期几和现在几点")

    assert [intent.kind for intent in intents] == ["weather_query", "time_query"]
    assert [intent.shortcircuit for intent in intents] == [True, True]
    assert PathSelector.select(intents) == "fast"


def test_intent_planner_marks_weather_without_city_for_clarification() -> None:
    intents = _plan("现在几点了？今天天气怎么样？")

    assert [intent.kind for intent in intents] == ["time_query", "weather_query"]
    assert intents[1].allow_text_response is True
    assert intents[1].metadata.get("missing_args") == ["city"]


def test_intent_planner_detects_news_queries_as_web_research() -> None:
    intents = _plan("查今天新闻，给我 3 条来源", tools=_tools())

    assert [intent.kind for intent in intents] == ["web_research"]


def test_intent_planner_detects_definition_query_as_knowledge_when_bound_kb_present() -> (
    None
):
    intents = _plan(
        "NovusAI 是什么？",
        tools=_tools(),
        capability_bundle=_kb_capability_bundle(),
    )

    assert [intent.kind for intent in intents] == ["knowledge_query"]
    assert intents[0].shortcircuit is False


def test_intent_planner_keeps_pronoun_only_definition_as_direct_reply_even_with_bound_kb() -> (
    None
):
    intents = _plan(
        "这是什么？",
        tools=_tools(),
        capability_bundle=_kb_capability_bundle(),
    )

    assert [intent.kind for intent in intents] == ["direct_reply"]
    assert intents[0].shortcircuit is True


def test_intent_planner_marks_time_query_as_shortcircuit() -> None:
    intents = _plan("current time")

    assert [intent.kind for intent in intents] == ["time_query"]
    assert intents[0].shortcircuit is True


def test_intent_planner_ignores_page_phrasing_without_page_context() -> None:
    intents = _plan(
        "看看本页面的内容然后总结一下",
        tools=_tools(),
    )

    assert len(intents) == 1
    assert intents[0].family == "none"
    assert intents[0].kind == "direct_reply"
    assert intents[0].shortcircuit is True
