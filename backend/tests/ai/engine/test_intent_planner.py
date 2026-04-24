"""
Test type: behavioral
Scope: Intent planner page-workflow routing and domain suppression behavior.
Mocked dependencies: none.
"""

from types import SimpleNamespace

from app.ai.engine.intent_planner import IntentPlanner
from app.ai.engine.types import ResearchContinuationContext
from app.ai.tools.types import ToolDefinition
from app.ai.types import ChatMessage


def _tools() -> list[ToolDefinition]:
    return [
        ToolDefinition(name="web_search", description="Search the web"),
        ToolDefinition(name="fetch_url", description="Fetch a webpage"),
        ToolDefinition(name="ui_get_snapshot", description="Read current page"),
        ToolDefinition(name="ui_read_region", description="Read page region"),
        ToolDefinition(name="ui_click", description="Click UI element"),
        ToolDefinition(name="ui_fill_form", description="Fill form fields"),
        ToolDefinition(name="ui_submit_form", description="Submit form"),
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
    active_intent_kind: str = "page_workflow",
) -> ResearchContinuationContext:
    return ResearchContinuationContext(
        active=True,
        family="page_ops",
        origin="continuation",
        current_user_text=current_user_text,
        research_target_text="admin.ai.api-keys",
        recent_successful_tool_names=["ui_get_snapshot"],
        tool_families=["page_ops"],
        page_context_attached=True,
        continuation_capable_families=["page_ops"],
        active_intent_kind=active_intent_kind,
    )


def _runtime_page_context(page_key: str, **extra) -> dict:
    page_context = {
        "page_key": page_key,
        "page_session_id": f"{page_key}-session",
        "ui_epoch": 1,
        "suggested_tools": {
            "primary": [
                "ui_get_snapshot",
                "ui_read_region",
                "ui_read_table",
                "ui_list_interactables",
                "ui_click",
                "ui_open_surface",
                "ui_get_form_state",
                "ui_fill_form",
                "ui_submit_form",
            ]
        },
    }
    page_context.update(extra)
    return page_context


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
        input_variables={"page_context": _runtime_page_context("admin.ai.api-keys")},
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
        input_variables={"page_context": _runtime_page_context("admin.ai.api-keys")},
    )

    assert [intent.family for intent in intents] == ["page_ops"]
    assert intents[0].kind == "page_workflow"
    assert intents[0].shortcircuit is True
    assert intents[0].metadata.get("page_workflow_kind") == "page_workflow"
    assert intents[0].metadata.get("page_workflow_goal") == "page_summary"
    assert intents[0].metadata.get("routing_mode") == "deterministic_shortcircuit"
    assert intents[0].metadata.get("routing_provenance") == "page_reference_fallback"


def test_intent_planner_routes_click_preface_without_catalog_to_navigation() -> (
    None
):
    intents = _plan(
        "请点击页面上的“查看 AI 使用分析”，然后告诉我当前进入了什么页面。",
        tools=_tools(),
        input_variables={"page_context": _runtime_page_context("admin.dashboard")},
    )

    assert [intent.kind for intent in intents] == ["page_workflow"]
    assert intents[0].metadata.get("page_workflow_goal") == "navigation"
    assert intents[0].metadata.get("routing_provenance") == "page_action_guard"


def test_intent_planner_routes_page_aware_click_clause_to_navigation() -> None:
    intents = _plan(
        "这个页面 click 一下 Add Supplier ➕",
        tools=_tools(),
        input_variables={"page_context": _runtime_page_context("admin.ai.providers")},
    )

    assert [intent.kind for intent in intents] == ["page_workflow"]
    assert intents[0].metadata.get("page_workflow_goal") == "navigation"
    assert intents[0].metadata.get("routing_provenance") == "page_action_guard"
    assert intents[0].shortcircuit is False


def test_intent_planner_keeps_weather_then_page_navigation_for_mixed_page_action() -> (
    None
):
    intents = _plan(
        "查下上海天气 and click the Add Supplier button on this page",
        tools=_tools_with_weather(),
        input_variables={"page_context": _runtime_page_context("admin.ai.providers")},
    )

    assert [intent.kind for intent in intents] == ["weather_query", "page_workflow"]
    assert intents[0].family == "weather"
    assert intents[1].metadata.get("page_workflow_goal") == "navigation"
    assert intents[1].metadata.get("routing_provenance") == "page_action_guard"


def test_intent_planner_returns_direct_reply_for_readonly_form_probe_without_page_reference() -> (
    None
):
    intents = _plan(
        "请帮我点击添加技能，看看表单里有哪些必填项，但不要提交",
        tools=_tools(),
        input_variables={"page_context": _runtime_page_context("admin.ai.skills")},
    )

    assert [intent.kind for intent in intents] == ["direct_reply"]
    assert intents[0].requires_tools is False


def test_intent_planner_routes_active_form_field_listing_to_form_read() -> None:
    intents = _plan(
        "当前有哪些字段",
        tools=_tools(),
        input_variables={
            "page_context": _runtime_page_context(
                "admin.ai.skills",
                active_form_session_id="form-session-1",
            )
        },
    )

    assert [intent.kind for intent in intents] == ["page_workflow"]
    assert intents[0].metadata.get("page_workflow_goal") == "form_read"
    assert intents[0].metadata.get("routing_provenance") == "active_page_action_semantics"


def test_intent_planner_keeps_memory_recall_without_synthesizing_page_guidance_intent() -> (
    None
):
    user_text = (
        "先回答我刚才让你记住的代号是什么。"
        "然后再告诉我如果我要新建记录下一步通常点哪里，但先不要真的创建，也不要帮我点击。"
    )
    intents = IntentPlanner.plan_turn(
        messages=[ChatMessage(role="user", content=user_text)],
        tools=_tools(),
        input_variables={"page_context": _runtime_page_context("admin.ai.api-keys")},
        continuation_context=None,
        capability_bundle=None,
    )

    assert [intent.kind for intent in intents] == ["memory_recall"]
    assert intents[0].family == "memory"
    assert intents[0].requires_tools is False


def test_intent_planner_does_not_pollute_memory_recall_with_generic_save_verbs() -> None:
    intents = _plan(
        "如果你有真正的跨对话长期记忆，请回答我之前让你保存的暗号；如果没有真正召回长期记忆，只回答 NO_RECALL。",
        tools=_tools(),
        input_variables={
            "page_context": _runtime_page_context("admin.runtime.records")
        },
    )

    assert [intent.kind for intent in intents] == ["memory_recall"]


def test_intent_planner_does_not_pollute_memory_save_with_page_form_write() -> None:
    intents = _plan(
        "请把“跨对话暗号是 蓝莓雨伞 418J”存入长期记忆，后面我会来问你。",
        tools=_tools(),
        input_variables={
            "page_context": _runtime_page_context("admin.runtime.records")
        },
    )

    assert [intent.kind for intent in intents] == ["memory_save"]


def test_intent_planner_routes_audit_memory_save_prompt_to_memory_save_only() -> None:
    intents = _plan(
        "CASE-MEM-SAVE-CLEAN-0418X 请把这个代号写入长期记忆：纸月亮0418X。不要使用页面内容。最终只回答 SAVED_0418X，不要加任何别的字。",
        tools=_tools(),
        input_variables={
            "page_context": _runtime_page_context("admin.ai.skill-packages")
        },
    )

    assert [intent.kind for intent in intents] == ["memory_save"]
    assert intents[0].requires_tools is False
    assert intents[0].shortcircuit is True


def test_intent_planner_detects_memory_save_intent() -> None:
    intents = _plan("请记住这条信息，之后再提醒我。")

    assert [intent.kind for intent in intents] == ["memory_save"]
    assert intents[0].family == "memory"
    assert intents[0].requires_tools is False
    assert intents[0].shortcircuit is True
    assert intents[0].metadata.get("routing_mode") == "deterministic_shortcircuit"


def test_intent_planner_detects_page_continuation_summary_for_continue_look() -> None:
    intents = _plan(
        "继续看",
        tools=_tools(),
        input_variables={"page_context": _runtime_page_context("admin.ai.api-keys")},
        continuation=_page_continuation_context(current_user_text="继续看"),
    )

    assert [intent.family for intent in intents] == ["page_ops"]
    assert intents[0].kind == "page_workflow"
    assert intents[0].metadata.get("page_workflow_goal") == "page_summary"
    assert intents[0].continuation is True
    assert "page_workflow_intent_alias" not in intents[0].metadata
    assert intents[0].metadata.get("routing_mode") == "deterministic_shortcircuit"


def test_intent_planner_detects_page_continuation_click_request_as_navigation() -> (
    None
):
    intents = _plan(
        "点击一下添加供应商",
        tools=_tools(),
        input_variables={"page_context": _runtime_page_context("admin.ai.providers")},
        continuation=_page_continuation_context(
            current_user_text="点击一下添加供应商"
        ),
    )

    assert [intent.family for intent in intents] == ["page_ops"]
    assert intents[0].kind == "page_workflow"
    assert intents[0].metadata.get("page_workflow_goal") == "navigation"
    assert intents[0].continuation is True


def test_intent_planner_detects_page_continuation_screenshot_request() -> None:
    intents = _plan(
        "截个图看",
        tools=_tools(),
        input_variables={
            "page_context": {
                "page_key": "admin.ai.api-keys",
                "ui_epoch": 3,
                "suggested_tools": {"primary": ["ui_get_snapshot"]},
            }
        },
        continuation=_page_continuation_context(current_user_text="截个图看"),
    )

    assert [intent.family for intent in intents] == ["page_ops"]
    assert intents[0].kind == "page_workflow"
    assert intents[0].metadata.get("page_workflow_goal") == "page_screenshot"
    assert intents[0].continuation is True


def test_intent_planner_routes_direct_page_screenshot_request_to_page_screenshot_goal() -> (
    None
):
    intents = _plan(
        "帮我把当前页面截图发出来",
        tools=_tools(),
        input_variables={"page_context": _runtime_page_context("admin.ai.api-keys")},
    )

    assert [intent.kind for intent in intents] == ["page_workflow"]
    assert intents[0].metadata.get("page_workflow_goal") == "page_screenshot"
    assert intents[0].metadata.get("routing_provenance") == "page_workflow_semantic_profile"
    assert intents[0].shortcircuit is True


def test_intent_planner_routes_editor_write_request_into_page_workflow() -> (
    None
):
    intents = _plan(
        "帮我修改当前编辑器标题并追加一段总结",
        tools=_tools(),
        input_variables={
            "page_context": _runtime_page_context("admin.ai.knowledge-bases")
        },
    )

    assert [intent.kind for intent in intents] == ["page_workflow"]
    assert intents[0].metadata.get("page_workflow_goal") == "form_write"
    assert intents[0].metadata.get("routing_provenance") == "active_page_action_semantics"


def test_intent_planner_keeps_capability_self_report_prompt_as_direct_reply() -> None:
    intents = _plan(
        "先简单介绍一下你自己，并说明你是否能查询天气、调用技能和执行页面操作。",
        tools=_tools_with_weather(),
        input_variables={"page_context": _runtime_page_context("admin.dashboard")},
    )

    assert [intent.kind for intent in intents] == ["direct_reply"]
    assert intents[0].requires_tools is False


def test_intent_planner_respects_explicit_no_tool_instruction_for_long_writing() -> None:
    intents = _plan(
        "请只用中文写一篇至少2500字的长文，分成标题、正文和结尾三个部分，不要调用任何工具。",
        tools=_tools_with_weather(),
        input_variables={"page_context": _runtime_page_context("admin.dashboard")},
    )

    assert [intent.kind for intent in intents] == ["direct_reply"]
    assert intents[0].requires_tools is False


def test_intent_planner_routes_pagination_request_on_active_page_without_reference() -> (
    None
):
    intents = _plan(
        "把列表翻到下一页",
        tools=_tools(),
        input_variables={"page_context": _runtime_page_context("admin.ai.logs")},
    )

    assert [intent.kind for intent in intents] == ["page_workflow"]
    assert intents[0].metadata.get("page_workflow_goal") == "pagination"
    assert intents[0].metadata.get("routing_provenance") == "active_page_action_semantics"


def test_intent_planner_routes_colloquial_here_question_to_page_summary_with_page_context() -> (
    None
):
    intents = _plan(
        "这里都有啥？",
        tools=_tools(),
        input_variables={"page_context": _runtime_page_context("admin.ai.agents")},
    )

    assert [intent.kind for intent in intents] == ["page_workflow"]
    assert intents[0].metadata.get("page_workflow_goal") == "page_summary"
    assert intents[0].metadata.get("routing_provenance") == "page_reference_fallback"


def test_intent_planner_routes_record_detail_phrase_to_row_detail() -> None:
    intents = _plan(
        "查看这条记录的详情",
        tools=_tools(),
        input_variables={"page_context": _runtime_page_context("admin.ai.logs")},
    )

    assert [intent.kind for intent in intents] == ["page_workflow"]
    assert intents[0].metadata.get("page_workflow_goal") == "row_detail"
    assert intents[0].metadata.get("routing_provenance") == "page_workflow_semantic_profile"


def test_intent_planner_detects_cross_page_navigation_from_menu_semantics() -> None:
    intents = _plan(
        "添加供应商",
        tools=_tools(),
        input_variables={
            "page_context": {
                **_runtime_page_context("admin.runtime.records"),
                "page_data": {
                    "navigation_catalog": [
                        {
                            "title": "供应商管理",
                            "path": "/admin/suppliers",
                            "page_key": "admin.suppliers",
                            "description": "管理供应商并新增供应商",
                            "keywords": ["供应商", "添加供应商"],
                        }
                    ]
                },
            }
        },
    )

    assert [intent.kind for intent in intents] == ["page_workflow"]
    assert intents[0].metadata.get("page_workflow_goal") == "navigation"


def test_intent_planner_routes_generic_record_creation_request_to_form_write() -> None:
    intents = _plan(
        "请帮我新增一条记录",
        tools=_tools(),
        input_variables={"page_context": _runtime_page_context("admin.ai.skills")},
    )

    assert [intent.kind for intent in intents] == ["page_workflow"]
    assert intents[0].metadata.get("page_workflow_goal") == "form_write"
    assert intents[0].metadata.get("routing_provenance") == "active_page_action_semantics"


def test_intent_planner_returns_direct_reply_for_add_vendor_click_request_without_catalog() -> (
    None
):
    intents = _plan(
        "帮我点击一下添加供应商 添加一个测试的供应商",
        tools=_tools(),
        input_variables={"page_context": _runtime_page_context("admin.ai.providers")},
    )

    assert [intent.kind for intent in intents] == ["direct_reply"]
    assert intents[0].requires_tools is False


def test_intent_planner_uses_summary_fallback_for_skill_binding_request_with_page_reference() -> (
    None
):
    intents = _plan(
        "帮我给这个页面的智能体绑定几个技能测试一下",
        tools=_tools(),
        input_variables={
            "page_context": _runtime_page_context("admin.ai.agent.detail")
        },
    )

    assert [intent.kind for intent in intents] == ["page_workflow"]
    assert intents[0].metadata.get("page_workflow_goal") == "page_summary"
    assert intents[0].metadata.get("routing_provenance") == "page_reference_fallback"


def test_intent_planner_routes_implicit_record_search_to_page_workflow() -> (
    None
):
    intents = _plan(
        "请帮我搜索记录并清空筛选条件",
        tools=_tools(),
        input_variables={"page_context": _runtime_page_context("admin.ai.logs")},
    )

    assert [intent.kind for intent in intents] == ["page_workflow"]
    assert intents[0].metadata.get("page_workflow_goal") == "search"
    assert intents[0].metadata.get("routing_provenance") == "active_page_action_semantics"


def test_intent_planner_routes_weather_keyword_record_search_to_page_workflow() -> (
    None
):
    intents = _plan(
        "帮我搜索一下包含'天气'的记录",
        tools=_tools(),
        input_variables={"page_context": _runtime_page_context("admin.ai.logs")},
    )

    assert [intent.kind for intent in intents] == ["page_workflow"]
    assert intents[0].metadata.get("page_workflow_goal") == "search"
    assert intents[0].metadata.get("routing_provenance") == "active_page_action_semantics"


def test_intent_planner_routes_table_summary_request_to_canonical_goal() -> None:
    intents = _plan(
        "列出这个表格前5条标题和时间",
        tools=_tools(),
        input_variables={"page_context": _runtime_page_context("admin.ai.logs")},
    )

    assert [intent.kind for intent in intents] == ["page_workflow"]
    assert intents[0].metadata.get("page_workflow_goal") == "table_summary"
    assert intents[0].metadata.get("routing_provenance") == "page_workflow_semantic_profile"


def test_intent_planner_keeps_generic_search_as_web_research_inside_page_context() -> (
    None
):
    intents = _plan(
        "帮我搜索一下2026年中国新能源汽车销量排行",
        tools=_tools(),
        input_variables={"page_context": _runtime_page_context("admin.ai.logs")},
    )

    assert [intent.kind for intent in intents] == ["web_research"]


def test_intent_planner_prefers_web_research_for_explicit_url_inside_page_context() -> (
    None
):
    intents = _plan(
        "请打开 https://docs.python.org/3/whatsnew/3.13.html 并概括重点，要求基于实际抓取内容回答",
        tools=_tools(),
        input_variables={"page_context": _runtime_page_context("admin.ai.logs")},
    )

    assert [intent.kind for intent in intents] == ["web_research"]


def test_intent_planner_keeps_fetch_url_only_request_out_of_page_intents() -> None:
    intents = _plan(
        "必须只使用 fetch_url 抓取 https://example.com ，不要联网搜索，也不要参考当前页面；只回答 标题：...；摘要：...；若没实际调用 fetch_url 就回答 NO_FETCH。",
        tools=_tools(),
        input_variables={"page_context": _runtime_page_context("admin.ai.logs")},
    )

    assert [intent.kind for intent in intents] == ["web_research"]
    assert intents[0].metadata["explicit_url"] == "https://example.com"
    assert intents[0].metadata["fetch_only"] is True


def test_intent_planner_splits_shunbian_and_duile_mixed_prompt() -> None:
    intents = _plan(
        "帮我查一下北京天气，顺便搜索一下今天的热点新闻，对了这个页面上有什么",
        tools=_tools_with_weather(),
        input_variables={"page_context": _runtime_page_context("admin.ai.agents")},
    )

    assert [intent.kind for intent in intents] == [
        "weather_query",
        "web_research",
        "page_workflow",
    ]
    assert intents[2].metadata.get("page_workflow_goal") == "page_summary"


def test_intent_planner_detects_time_and_weather_as_two_intents() -> None:
    intents = _plan("帮我看一下北京天气，再告诉我今天星期几和现在几点")

    assert [intent.kind for intent in intents] == ["weather_query", "time_query"]


def test_intent_planner_detects_time_tool_directive_for_city_clock() -> None:
    intents = _plan(
        "必须使用 get_current_time 工具获取当前上海时间，只回答 HH:MM；若没有实际调用工具就回答 NO_TOOL。",
        tools=[ToolDefinition(name="get_current_time", description="Current time")],
    )

    assert [intent.kind for intent in intents] == ["time_query"]
    assert intents[0].shortcircuit is True


def test_intent_planner_detects_now_is_time_phrase_variant() -> None:
    intents = _plan(
        "现在是几点",
        tools=[ToolDefinition(name="get_current_time", description="Current time")],
    )

    assert [intent.kind for intent in intents] == ["time_query"]


def test_intent_planner_falls_back_to_web_research_for_weather_when_only_web_tools_exist() -> (
    None
):
    intents = _plan("帮我查一下上海天气", tools=_tools())

    assert [intent.kind for intent in intents] == ["web_research"]
    assert intents[0].family == "web_research"


def test_intent_planner_does_not_duplicate_weather_web_lookup_into_two_web_intents() -> (
    None
):
    intents = _plan("今天怀化天气怎么样 联网查查", tools=_tools())

    assert [intent.kind for intent in intents] == ["web_research"]
    assert intents[0].family == "web_research"
    assert intents[0].user_visible_label == "weather_web_research"


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


def test_intent_planner_does_not_default_to_kb_when_bound_kb_present() -> None:
    intents = _plan(
        "你好",
        tools=_tools(),
        capability_bundle=_kb_capability_bundle(),
    )

    assert [intent.kind for intent in intents] == ["direct_reply"]
    assert intents[0].shortcircuit is True


def test_intent_planner_keeps_definition_like_kb_query_when_web_signal_exists() -> None:
    intents = _plan(
        "联网查一下 NovusAI 是什么",
        tools=_tools(),
        capability_bundle=_kb_capability_bundle(),
    )

    assert [intent.kind for intent in intents] == ["web_research", "knowledge_query"]


def test_intent_planner_keeps_definition_like_intro_as_kb_query_when_bound_kb_present() -> None:
    intents = _plan(
        "介绍一下退货政策",
        tools=_tools(),
        capability_bundle=_kb_capability_bundle(),
    )

    assert [intent.kind for intent in intents] == ["knowledge_query"]
    assert intents[0].requires_tools is False
    assert intents[0].shortcircuit is False


def test_intent_planner_keeps_formal_kb_summary_prompt_out_of_web_research() -> None:
    intents = _plan(
        "如果你的知识库里有关于 NovusAI SaaS 的资料，请概括一下它的三个端口和主要用途",
        tools=_tools(),
        capability_bundle=_kb_capability_bundle(),
    )

    assert [intent.kind for intent in intents] == ["knowledge_query"]
    assert intents[0].family == "none"


def test_intent_planner_keeps_generic_kb_search_prefix_out_of_web_research() -> None:
    intents = _plan(
        "搜索一下知识库里的退货政策，并概括关键规则",
        tools=_tools(),
        capability_bundle=_kb_capability_bundle(),
    )

    assert [intent.kind for intent in intents] == ["knowledge_query"]
    assert intents[0].family == "none"


def test_intent_planner_routes_explicit_current_page_create_request_to_write_goal() -> (
    None
):
    intents = _plan(
        "帮我查一下北京天气，然后在当前页面创建一条测试记录，名称叫 Consent-Recovery-E2E",
        tools=_tools_with_weather(),
        input_variables={"page_context": _runtime_page_context("admin.runtime.records")},
    )

    assert [intent.kind for intent in intents] == ["weather_query", "page_workflow"]
    assert intents[0].family == "weather"
    assert intents[1].metadata.get("page_workflow_goal") == "form_write"
    assert intents[1].metadata.get("routing_provenance") == "page_reference_write_semantics"
    assert intents[1].shortcircuit is False


def test_intent_planner_detects_code_mixed_page_summary_with_weather() -> None:
    intents = _plan(
        "hey 猫娘！帮我check一下今天的weather🌤️ btw这个page上有啥东西？😊",
        tools=_tools_with_weather(),
        input_variables={"page_context": _runtime_page_context("admin.ai.agents")},
    )

    assert [intent.kind for intent in intents] == ["weather_query", "page_workflow"]
    assert intents[0].allow_text_response is True
    assert intents[1].metadata.get("page_workflow_goal") == "page_summary"
    assert intents[1].metadata.get("routing_provenance") == "page_reference_fallback"


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


