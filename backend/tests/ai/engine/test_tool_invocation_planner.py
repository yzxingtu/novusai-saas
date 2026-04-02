from app.ai.engine.tool_invocation_planner import ToolInvocationPlanner
from app.ai.engine.types import ResearchContinuationContext
from app.ai.runtime.types import ContextSource
from app.ai.tools.semantic_defaults import tool_family_from_name
from app.ai.tools.types import ToolDefinition
from app.ai.types import ChatMessage


def _tools() -> list[ToolDefinition]:
    return [
        ToolDefinition(name="web_search", description="Search the web"),
        ToolDefinition(name="fetch_url", description="Fetch a webpage"),
        ToolDefinition(name="get_page_context", description="Read current page"),
        ToolDefinition(name="invoke_page_operation", description="Operate page"),
        ToolDefinition(name="data_query", description="Query data"),
    ]


def test_planner_returns_no_tool_for_compliment_after_page_ops() -> None:
    plan = ToolInvocationPlanner.plan(
        messages=[
            ChatMessage(role="user", content="打开这个页面"),
            ChatMessage(
                role="assistant",
                content="",
                tool_calls=[
                    {
                        "success": True,
                        "function": {"name": "invoke_page_operation"},
                    }
                ],
            ),
            ChatMessage(role="user", content="你真聪明"),
        ],
        tools=_tools(),
        input_variables={
            "page_context": {"page_key": "admin.ai.api-keys"},
        },
        continuation_context=None,
    )

    assert plan.family == "none"
    assert plan.allow_no_tool is True
    assert plan.reason == "smalltalk_or_support_no_tool"


def test_planner_returns_no_tool_for_health_after_web_research() -> None:
    plan = ToolInvocationPlanner.plan(
        messages=[
            ChatMessage(role="user", content="联网查一下最近乌克兰的局势"),
            ChatMessage(
                role="assistant",
                content="",
                tool_calls=[
                    {
                        "success": True,
                        "function": {"name": "web_search"},
                    }
                ],
            ),
            ChatMessage(role="user", content="我肚子疼"),
        ],
        tools=_tools(),
        input_variables={},
        continuation_context=ResearchContinuationContext(
            active=True,
            family="web_research",
            current_user_text="我肚子疼",
            research_target_text="乌克兰局势",
            recent_successful_tool_names=["web_search"],
            recent_web_queries=["乌克兰局势"],
            search_query_count=1,
            fetched_url_count=0,
        ),
    )

    assert plan.family == "none"
    assert plan.allow_no_tool is True
    assert plan.reason == "smalltalk_or_support_no_tool"


def test_planner_selects_page_ops_for_page_question() -> None:
    plan = ToolInvocationPlanner.plan(
        messages=[ChatMessage(role="user", content="你能看到这个页面的内容吗？")],
        tools=_tools(),
        input_variables={
            "page_context": {"page_key": "admin.ai.api-keys"},
        },
        continuation_context=None,
    )

    assert plan.family == "page_ops"
    assert plan.allow_no_tool is False
    assert plan.reason == "explicit_page_request"

def test_planner_selects_page_ops_for_local_page_phrases_with_context() -> None:
    plan = ToolInvocationPlanner.plan(
        messages=[
            ChatMessage(role="user", content="看看本页面的内容然后总结一下"),
        ],
        tools=_tools(),
        input_variables={
            "page_context": {"page_key": "admin.ai.api-keys"},
        },
        continuation_context=None,
    )

    assert plan.family == "page_ops"
    assert plan.allow_no_tool is False
    assert plan.reason == "explicit_page_request"


def test_planner_selects_page_ops_for_page_capability_request_with_context() -> None:
    plan = ToolInvocationPlanner.plan(
        messages=[
            ChatMessage(
                role="user",
                content="通过页面感知能力添加一个测试的智能体 具体里面的内容你来决定",
            ),
        ],
        tools=_tools(),
        input_variables={
            "page_context": {"page_key": "admin.ai.agents"},
        },
        continuation_context=None,
    )

    assert plan.family == "page_ops"
    assert plan.allow_no_tool is False
    assert plan.reason == "explicit_page_request"

def test_planner_ignores_local_page_phrases_without_context() -> None:
    plan = ToolInvocationPlanner.plan(
        messages=[
            ChatMessage(role="user", content="看看本页面的内容然后总结一下"),
        ],
        tools=_tools(),
        input_variables={},
        continuation_context=None,
    )

    assert plan.family == "none"
    assert plan.reason == "default_no_tool"


def test_planner_detects_page_context_from_shared_schema_key() -> None:
    assert ToolInvocationPlanner._has_page_context(  # noqa: SLF001
        {
            "page_context": {"page_key": "admin.ai.api-keys"},
        }
    )


def test_list_page_operations_uses_shared_page_context_key() -> None:
    assert (
        tool_family_from_name(
            "list_page_operations",
            {"page_context": {"page_key": "admin.ai.api-keys"}},
        )
        == "page_ops"
    )


def test_planner_selects_web_research_for_explicit_research_turn() -> None:
    plan = ToolInvocationPlanner.plan(
        messages=[ChatMessage(role="user", content="联网查一下最近乌克兰的局势")],
        tools=_tools(),
        input_variables={},
        continuation_context=None,
    )

    assert plan.family == "web_research"
    assert plan.allow_no_tool is False
    assert plan.reason == "explicit_web_request"


def test_planner_allows_web_research_continuation_for_result_anchor() -> None:
    plan = ToolInvocationPlanner.plan(
        messages=[
            ChatMessage(role="user", content="联网查一下最近乌克兰的局势"),
            ChatMessage(
                role="assistant",
                content="",
                tool_calls=[
                    {"success": True, "function": {"name": "web_search"}}
                ],
            ),
            ChatMessage(role="tool", content="Search results"),
            ChatMessage(role="user", content="刚才那个链接讲了什么？"),
        ],
        tools=_tools(),
        input_variables={},
        continuation_context=ResearchContinuationContext(
            active=True,
            family="web_research",
            current_user_text="刚才那个链接讲了什么？",
            research_target_text="乌克兰局势",
            recent_successful_tool_names=["web_search"],
            recent_web_queries=["乌克兰局势"],
            search_query_count=1,
            fetched_url_count=0,
        ),
    )

    assert plan.family == "web_research"
    assert plan.allow_family_continuation is True
    assert plan.reason == "anchored_or_unfinished_web_continuation"


def test_planner_keeps_explicit_web_request_even_with_health_phrase() -> None:
    plan = ToolInvocationPlanner.plan(
        messages=[
            ChatMessage(role="user", content="我肚子疼，顺便联网查一下最近流感新闻"),
        ],
        tools=_tools(),
        input_variables={},
        continuation_context=None,
    )

    assert plan.family == "web_research"
    assert plan.allow_no_tool is False
    assert plan.reason == "explicit_web_request"


def test_planner_prefers_page_ops_when_pending_page_confirmation_unresolved() -> None:
    plan = ToolInvocationPlanner.plan(
        messages=[
            ChatMessage(role="user", content="打开这个页面"),
            ChatMessage(
                role="assistant",
                content="",
                metadata={
                    "pending_confirmation": {
                        "action": "page_operation",
                        "resolved": False,
                    }
                },
                tool_calls=[
                    {
                        "success": True,
                        "function": {"name": "invoke_page_operation"},
                    }
                ],
            ),
            ChatMessage(role="user", content="继续这个页面"),
        ],
        tools=_tools(),
        input_variables={
            "page_context": {"page_key": "admin.ai.api-keys"},
        },
        continuation_context=None,
    )

    assert plan.family == "page_ops"
    assert plan.allow_no_tool is False
    assert plan.allow_family_continuation is True
    assert plan.reason == "anchored_or_pending_page_continuation"

def test_planner_routes_explicit_weather_query_to_weather_family() -> None:
    weather_tools = [
        ToolDefinition(name="get_current_weather", description="Get current weather"),
        ToolDefinition(name="get_weather_forecast", description="Get weather forecast"),
    ]
    plan = ToolInvocationPlanner.plan(
        messages=[ChatMessage(role="user", content="今天北京天气怎么样")],
        tools=weather_tools,
        input_variables={},
        continuation_context=None,
    )

    assert plan.family == "weather"
    assert plan.reason == "explicit_weather_request"


def test_planner_requires_weather_tools_for_weather_phrases() -> None:
    plan = ToolInvocationPlanner.plan(
        messages=[ChatMessage(role="user", content="现在北京气温多少")],
        tools=_tools(),
        input_variables={},
        continuation_context=None,
    )

    assert plan.family == "none"
    assert plan.reason == "default_no_tool"


def test_planner_does_not_mistake_mood_questions_for_weather() -> None:
    weather_tools = [
        ToolDefinition(name="get_current_weather", description="Get current weather"),
    ]
    plan = ToolInvocationPlanner.plan(
        messages=[ChatMessage(role="user", content="今天心情怎么样")],
        tools=weather_tools,
        input_variables={},
        continuation_context=None,
    )

    assert plan.family == "none"
    assert plan.reason == "default_no_tool"


def test_planner_keeps_explicit_weather_even_with_health_phrase() -> None:
    weather_tools = [
        ToolDefinition(name="get_current_weather", description="Get current weather"),
        ToolDefinition(name="get_weather_forecast", description="Get weather forecast"),
    ]
    plan = ToolInvocationPlanner.plan(
        messages=[ChatMessage(role="user", content="我头疼，今天北京天气怎么样")],
        tools=weather_tools,
        input_variables={},
        continuation_context=None,
    )

    assert plan.family == "weather"
    assert plan.reason == "explicit_weather_request"


def test_explicit_requested_families_preserves_user_order_for_page_then_weather() -> None:
    tools = [
        ToolDefinition(name="get_page_context", description="Read current page"),
        ToolDefinition(name="invoke_page_operation", description="Operate page"),
        ToolDefinition(name="get_current_weather", description="Get current weather"),
        ToolDefinition(name="get_weather_forecast", description="Get weather forecast"),
    ]
    families = ToolInvocationPlanner.explicit_requested_families(
        messages=[ChatMessage(role="user", content="先看看本页面，再查北京天气")],
        tools=tools,
        input_variables={"page_context": {"page_key": "admin.ai.api-keys"}},
    )

    assert families == ["page_ops", "weather"]


def test_explicit_requested_families_preserves_user_order_for_weather_then_page() -> None:
    tools = [
        ToolDefinition(name="get_page_context", description="Read current page"),
        ToolDefinition(name="invoke_page_operation", description="Operate page"),
        ToolDefinition(name="get_current_weather", description="Get current weather"),
        ToolDefinition(name="get_weather_forecast", description="Get weather forecast"),
    ]
    families = ToolInvocationPlanner.explicit_requested_families(
        messages=[ChatMessage(role="user", content="先查北京天气，再看看本页面")],
        tools=tools,
        input_variables={"page_context": {"page_key": "admin.ai.api-keys"}},
    )

    assert families == ["weather", "page_ops"]


def test_explicit_requested_families_does_not_add_data_ops_for_web_query_verb_only() -> None:
    tools = [
        ToolDefinition(name="web_search", description="Search the web"),
        ToolDefinition(name="fetch_url", description="Fetch URL"),
        ToolDefinition(name="data_query", description="Query data"),
    ]
    families = ToolInvocationPlanner.explicit_requested_families(
        messages=[ChatMessage(role="user", content="联网查询一下 小猫为什么爱吃鱼")],
        tools=tools,
        input_variables={},
    )

    assert families == ["web_research"]


def test_planner_prefers_data_ops_for_recent_data_request_with_bound_kb() -> None:
    capability_bundle = type(
        "Bundle",
        (),
        {
            "context_sources": [
                ContextSource(kind="knowledge_base", name="kb", active=True),
            ]
        },
    )()

    plan = ToolInvocationPlanner.plan(
        messages=[
            ChatMessage(
                role="user",
                content="请统计最近7天创建的终端用户数量，再根据已绑定知识库概括产品主要功能",
            ),
        ],
        tools=_tools(),
        input_variables={},
        continuation_context=None,
        capability_bundle=capability_bundle,
    )

    assert plan.family == "data_ops"
    assert plan.reason == "data_time_range_with_kb"


def test_planner_respects_no_web_for_data_plus_kb_requests() -> None:
    capability_bundle = type(
        "Bundle",
        (),
        {
            "context_sources": [
                ContextSource(kind="knowledge_base", name="kb", active=True),
            ]
        },
    )()

    plan = ToolInvocationPlanner.plan(
        messages=[
            ChatMessage(
                role="user",
                content="不要联网。请统计最近7天创建的终端用户数量，再只根据已绑定知识库概括产品主要功能",
            ),
        ],
        tools=_tools(),
        input_variables={},
        continuation_context=None,
        capability_bundle=capability_bundle,
    )

    assert plan.family == "data_ops"
    assert plan.reason == "no_web_explicit_data"


def test_planner_does_not_treat_recent_as_web_without_explicit_web_signal() -> None:
    plan = ToolInvocationPlanner.plan(
        messages=[ChatMessage(role="user", content="请统计最近7天创建的用户有多少")],
        tools=_tools(),
        input_variables={},
        continuation_context=None,
    )

    assert plan.family == "data_ops"
    assert plan.reason == "explicit_data_request"
