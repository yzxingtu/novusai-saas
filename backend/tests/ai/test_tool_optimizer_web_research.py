from app.ai.tools.optimizer import optimize_tools
from app.ai.tools.types import ToolDefinition


def test_optimize_tools_prefers_builtin_web_research_tools() -> None:
    """
    Test type: structural
    Scope: unrelated business tools are not selected for web research.
    """
    tools = [
        ToolDefinition(name="crm_lookup", description="Read current dataset snapshot"),
        ToolDefinition(name="crm_read_record", description="Read region"),
        ToolDefinition(name="crm_list_records", description="Read table"),
        ToolDefinition(name="crm_list_actions", description="List interactables"),
        ToolDefinition(name="crm_update_record", description="Click element"),
        ToolDefinition(name="crm_open_record", description="Open CRM record"),
        ToolDefinition(name="crm_get_record_state", description="Get CRM form state"),
        ToolDefinition(name="crm_set_field", description="Set form field"),
        ToolDefinition(name="crm_update_record", description="Update CRM form"),
        ToolDefinition(name="crm_submit_record", description="Submit CRM form"),
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
    Scope: data_ops semantic-family tools are not selected for web research.
    """
    tools = [
        ToolDefinition(
            name="external_lookup",
            description="Research external public sources",
            semantic_family="web_research",
            semantic_tags=["联网搜索", "网页查询", "最新信息", "官方来源"],
        ),
        ToolDefinition(
            name="crm_read_helper",
            description="Read current dataset state",
            semantic_family="data_ops",
            semantic_tags=["数据读取", "表单状态"],
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
    assert "crm_read_helper" not in selected_names


def test_optimize_tools_prefers_semantic_web_tools_without_name_aliases() -> None:
    """
    Test type: structural
    Scope: non-web business tools stay out of semantic web-tool selection.
    """
    tools = [
        ToolDefinition(name="crm_lookup", description="Read CRM context"),
        ToolDefinition(name="crm_read_record", description="Read current area"),
        ToolDefinition(name="crm_update_record", description="Open and click"),
        ToolDefinition(
            name="public_lookup",
            description="Find external references",
            semantic_family="web_research",
            semantic_tags=["联网", "搜索", "来源", "网页"],
        ),
        ToolDefinition(
            name="source_fetcher",
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
    assert selected_names == ["public_lookup", "source_fetcher"]
