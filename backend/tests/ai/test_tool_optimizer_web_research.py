from app.ai.tools.optimizer import optimize_tools
from app.ai.tools.types import ToolDefinition


def test_optimize_tools_filters_retired_page_tools_from_web_research() -> None:
    """
    Test type: structural
    Scope: retired page tools cannot survive optimizer selection.
    """
    tools = [
        ToolDefinition(name="ui_get_snapshot", description="Read current page snapshot"),
        ToolDefinition(name="ui_read_region", description="Read region"),
        ToolDefinition(name="ui_read_table", description="Read table"),
        ToolDefinition(name="ui_list_interactables", description="List interactables"),
        ToolDefinition(name="ui_click", description="Click element"),
        ToolDefinition(name="ui_open_surface", description="Open target surface"),
        ToolDefinition(name="ui_get_form_state", description="Get form state"),
        ToolDefinition(name="ui_set_field", description="Set form field"),
        ToolDefinition(name="ui_fill_form", description="Fill form"),
        ToolDefinition(name="ui_submit_form", description="Submit form"),
        ToolDefinition(name="web_search", description="Search the web"),
        ToolDefinition(name="fetch_url", description="Fetch a webpage"),
    ]

    result = optimize_tools(
        tools,
        "联网查询一下 小猫为什么 爱吃鱼",
        preferred_family="web_research",
    )

    selected_names = [tool.name for tool in result.tools]
    assert selected_names == ["web_search", "fetch_url"]


def test_optimize_tools_uses_semantic_metadata_for_custom_web_research_tools() -> None:
    """
    Test type: structural
    Scope: page_ops semantic-family tools are not selected for web research.
    """
    tools = [
        ToolDefinition(
            name="external_lookup",
            description="Research external public sources",
            semantic_family="web_research",
            semantic_tags=["联网搜索", "网页查询", "最新信息", "官方来源"],
        ),
        ToolDefinition(
            name="page_read_helper",
            description="Read current page state",
            semantic_family="page_ops",
            semantic_tags=["页面操作", "读取页面", "表单状态"],
        ),
        ToolDefinition(
            name="generic_helper",
            description="General internal helper",
            semantic_family="general",
            semantic_tags=["内部", "辅助"],
        ),
    ]

    result = optimize_tools(
        tools,
        "请联网搜索最新公开来源，帮我查一下小猫为什么爱吃鱼",
        preferred_family="web_research",
        max_after_optimization=2,
    )

    selected_names = [tool.name for tool in result.tools]
    assert "external_lookup" in selected_names
    assert "page_read_helper" not in selected_names


def test_optimize_tools_prefers_semantic_web_tools_without_name_aliases() -> None:
    """
    Test type: structural
    Scope: retired page tool names are filtered before semantic web-tool selection.
    """
    tools = [
        ToolDefinition(name="ui_get_snapshot", description="Read page context"),
        ToolDefinition(name="ui_read_region", description="Read current area"),
        ToolDefinition(name="ui_click", description="Open and click"),
        ToolDefinition(
            name="public_lookup",
            description="Find external references",
            semantic_family="web_research",
            semantic_tags=["联网", "搜索", "来源", "网页"],
        ),
        ToolDefinition(
            name="page_fetcher",
            description="Read cited sources",
            semantic_family="web_research",
            semantic_tags=["网页", "链接", "来源"],
        ),
    ]

    result = optimize_tools(
        tools,
        "联网查询一下 小猫为什么 爱吃鱼",
        preferred_family="web_research",
        max_without_optimization=4,
        max_after_optimization=6,
    )

    selected_names = [tool.name for tool in result.tools]
    assert selected_names == ["public_lookup", "page_fetcher"]
