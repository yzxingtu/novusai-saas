from app.ai.tools.optimizer import optimize_tools
from app.ai.tools.types import ToolDefinition


def test_optimize_tools_prefers_web_research_over_pageops_and_data_tools() -> None:
    tools = [
        ToolDefinition(name="get_page_context", description="Read page context"),
        ToolDefinition(name="invoke_page_operation", description="Operate page"),
        ToolDefinition(name="pageop_capture_screenshot", description="Capture screenshot"),
        ToolDefinition(name="pageop_refresh_list", description="Refresh list"),
        ToolDefinition(name="pageop_search", description="Search current page"),
        ToolDefinition(name="pageop_clear_search", description="Clear page search"),
        ToolDefinition(name="pageop_read_visible_rows", description="Read visible rows"),
        ToolDefinition(name="pageop_next_page", description="Next page"),
        ToolDefinition(name="pageop_prev_page", description="Previous page"),
        ToolDefinition(name="pageop_go_to_page", description="Go to page"),
        ToolDefinition(name="data_query", description="Query platform data"),
        ToolDefinition(name="data_create", description="Create platform record"),
        ToolDefinition(name="data_update", description="Update platform record"),
        ToolDefinition(name="data_delete", description="Delete platform record"),
        ToolDefinition(name="web_search", description="Search the web"),
        ToolDefinition(name="fetch_url", description="Fetch a webpage"),
    ]

    result = optimize_tools(
        tools,
        "联网查询一下 小猫为什么 爱吃鱼",
        preferred_family="web_research",
    )

    selected_names = [tool.name for tool in result.tools]
    assert "web_search" in selected_names
    assert "fetch_url" in selected_names
    assert "get_page_context" in selected_names
    assert "invoke_page_operation" in selected_names
    assert "data_query" not in selected_names
    pageop_names = [name for name in selected_names if name.startswith("pageop_")]
    assert len(pageop_names) < 8


def test_optimize_tools_uses_semantic_metadata_for_custom_web_research_tools() -> None:
    tools = [
        ToolDefinition(
            name="external_lookup",
            description="Research external public sources",
            semantic_family="web_research",
            semantic_tags=["联网搜索", "网页查询", "最新信息", "官方来源"],
        ),
        ToolDefinition(
            name="tenant_records",
            description="Read tenant records",
            semantic_family="data_ops",
            semantic_tags=["数据查询", "数据库操作", "记录管理"],
        ),
        ToolDefinition(
            name="page_read_helper",
            description="Read current page state",
            semantic_family="page_ops",
            semantic_tags=["页面操作", "读取页面", "表单状态"],
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
    assert "tenant_records" not in selected_names


def test_optimize_tools_prefers_semantic_web_tools_without_name_aliases() -> None:
    tools = [
        ToolDefinition(name="get_page_context", description="Read page context"),
        ToolDefinition(name="invoke_page_operation", description="Operate page"),
        ToolDefinition(name="pageop_refresh_list", description="Refresh list"),
        ToolDefinition(name="pageop_search", description="Search current page"),
        ToolDefinition(name="data_query", description="Query platform data"),
        ToolDefinition(name="data_update", description="Update platform record"),
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
    assert "public_lookup" in selected_names
    assert "page_fetcher" in selected_names
    assert "data_query" not in selected_names
