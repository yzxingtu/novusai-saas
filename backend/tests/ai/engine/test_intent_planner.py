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
    ]


def _plan(
    user_text: str,
    *,
    tools: list[ToolDefinition] | None = None,
    input_variables: dict | None = None,
    messages: list[ChatMessage] | None = None,
    continuation: ResearchContinuationContext | None = None,
) -> list:
    return IntentPlanner.plan_turn(
        messages=messages or [ChatMessage(role="user", content=user_text)],
        tools=tools or _tools_with_weather(),
        input_variables=input_variables or {},
        continuation_context=continuation,
        capability_bundle=None,
    )


def test_intent_planner_suppresses_web_when_user_explicitly_disables_network() -> None:
    intents = _plan("不要联网，帮我搜一下北京天气")

    assert [intent.family for intent in intents] == ["weather"]
    assert intents[0].kind == "weather_query"


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
                tool_calls=[
                    {"success": True, "function": {"name": "web_search"}}
                ],
            ),
            ChatMessage(role="user", content="我肚子疼"),
        ],
    )

    assert len(intents) == 1
    assert intents[0].family == "none"
    assert intents[0].kind == "direct_reply"
    assert intents[0].requires_tools is False


def test_intent_planner_detects_page_read_when_page_context_is_present() -> None:
    intents = _plan(
        "看看本页面的内容然后总结一下",
        tools=_tools(),
        input_variables={"page_context": {"page_key": "admin.ai.api-keys"}},
    )

    assert [intent.family for intent in intents] == ["page_ops"]
    assert intents[0].kind == "page_read"


def test_intent_planner_ignores_page_phrasing_without_page_context() -> None:
    intents = _plan(
        "看看本页面的内容然后总结一下",
        tools=_tools(),
    )

    assert len(intents) == 1
    assert intents[0].family == "none"
    assert intents[0].kind == "direct_reply"


def test_intent_planner_marks_multi_intent_turn_as_deep_path() -> None:
    user_text = "请帮我查一下今天北京的天气，然后联网查一下长沙去北京的高铁票，再帮我阅读一下本页面都有什么内容"
    intents = _plan(
        user_text,
        tools=_tools_with_weather(),
        input_variables={"page_context": {"page_key": "admin.ai.api-keys"}},
    )

    assert [intent.family for intent in intents] == [
        "weather",
        "web_research",
        "page_ops",
    ]
    assert PathSelector.select(intents) == "deep"


def test_intent_planner_is_deterministic_for_same_multi_intent_input() -> None:
    user_text = "请帮我查一下今天北京的天气，然后联网查一下长沙去北京的高铁票，再帮我阅读一下本页面都有什么内容"

    families_runs = []
    paths = []
    for _ in range(3):
        intents = _plan(
            user_text,
            tools=_tools_with_weather(),
            input_variables={"page_context": {"page_key": "admin.ai.api-keys"}},
        )
        families_runs.append([intent.family for intent in intents])
        paths.append(PathSelector.select(intents))

    assert families_runs == [
        ["weather", "web_research", "page_ops"],
        ["weather", "web_research", "page_ops"],
        ["weather", "web_research", "page_ops"],
    ]
    assert paths == ["deep", "deep", "deep"]
