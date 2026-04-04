from app.ai.engine.base import BaseEngine
from app.ai.tools.types import ToolDefinition, ToolResult
from app.ai.types import ChatMessage


def _page_tools() -> list[ToolDefinition]:
    return [
        ToolDefinition(name="get_page_context"),
        ToolDefinition(name="pageop_list_available_menus"),
        ToolDefinition(name="pageop_navigate_menu"),
        ToolDefinition(name="invoke_page_operation"),
    ]


def test_build_page_no_progress_recovery_for_navigation_request() -> None:
    hint, preferred_tool_names, diagnostics = BaseEngine._build_page_no_progress_recovery(  # noqa: SLF001
        messages=[ChatMessage(role="user", content="帮我新增 AI 助手")],
        tool_calls=[
            {
                "id": "call_1",
                "type": "function",
                "function": {"name": "get_page_context", "arguments": "{}"},
            }
        ],
        tool_results=[
            ToolResult(
                tool_call_id="call_1",
                name="get_page_context",
                success=True,
                output=(
                    "Page context was already returned earlier in this turn. "
                    "Reuse the previous get_page_context result unless the page actually changed."
                ),
            )
        ],
        tools=_page_tools(),
        input_variables={
            "page_context": {
                "page_key": "admin.dashboard",
                "page_data": {
                    "available_operations": [
                        {"name": "navigate_menu"},
                        {"name": "list_available_menus"},
                    ],
                    "available_menus": [
                        {
                            "title": "智能体管理",
                            "page_key": "admin.ai.agents",
                            "path": "/admin/ai/agents",
                            "description": "创建、编辑和管理 AI 智能体",
                            "keywords": ["智能体", "agent", "AI助手", "assistant"],
                            "capabilities": ["create_agent", "edit_agent"],
                            "category": "ai",
                        }
                    ],
                },
            }
        },
    )

    assert hint is not None
    assert "Do NOT call get_page_context again" in hint
    assert preferred_tool_names == [
        "pageop_list_available_menus",
        "pageop_navigate_menu",
        "invoke_page_operation",
    ]
    assert diagnostics["reason"] == "repeated_get_page_context"
    assert diagnostics["current_page_key"] == "admin.dashboard"


def test_build_page_no_progress_recovery_skips_non_navigation_turn() -> None:
    hint, preferred_tool_names, diagnostics = BaseEngine._build_page_no_progress_recovery(  # noqa: SLF001
        messages=[ChatMessage(role="user", content="读一下当前页面有什么")],
        tool_calls=[
            {
                "id": "call_1",
                "type": "function",
                "function": {"name": "get_page_context", "arguments": "{}"},
            }
        ],
        tool_results=[
            ToolResult(
                tool_call_id="call_1",
                name="get_page_context",
                success=True,
                output="Page: admin.dashboard",
            )
        ],
        tools=_page_tools(),
        input_variables={
            "page_context": {
                "page_key": "admin.dashboard",
                "page_data": {
                    "available_operations": [{"name": "navigate_menu"}],
                    "available_menus": [
                        {
                            "title": "智能体管理",
                            "page_key": "admin.ai.agents",
                            "path": "/admin/ai/agents",
                        }
                    ],
                },
            }
        },
    )

    assert hint is None
    assert preferred_tool_names == []
    assert diagnostics == {}
