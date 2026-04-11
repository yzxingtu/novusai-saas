"""Tests for same-turn readonly tool result deduplication in ToolCallProcessor."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.ai.engine.tool_processor import ToolCallProcessor
from app.ai.tools.types import ToolDefinition, ToolResult
from app.schemas.ai.agent_chat import PAGE_CONTEXT_KEY


@pytest.mark.asyncio
async def test_dedupes_identical_get_current_weather_same_turn() -> None:
    sandbox = MagicMock()
    sandbox.execute = AsyncMock(
        return_value=ToolResult(
            tool_call_id="first",
            name="get_current_weather",
            success=True,
            output="晴",
        )
    )
    proc = ToolCallProcessor(
        sandbox=sandbox,
        tools=[ToolDefinition(name="get_current_weather", description="x")],
    )
    r1, _ms1 = await proc.execute_tool(
        "tc-1", "get_current_weather", {"city": "北京"}, 1
    )
    r2, ms2 = await proc.execute_tool(
        "tc-2", "get_current_weather", {"city": "北京"}, 1
    )

    assert sandbox.execute.call_count == 1
    assert ms2 == 0
    assert r2.tool_call_id == "tc-2"
    assert r1.output == r2.output


@pytest.mark.asyncio
async def test_ui_write_tools_are_never_deduped() -> None:
    sandbox = MagicMock()
    sandbox.execute = AsyncMock(
        return_value=ToolResult(
            tool_call_id="x",
            name="ui_click",
            success=True,
            output="ok",
        )
    )
    sandbox.input_variables = {PAGE_CONTEXT_KEY: {"page_key": "p1"}}
    proc = ToolCallProcessor(
        sandbox=sandbox,
        tools=[
            ToolDefinition(name="ui_click", description="x"),
            ToolDefinition(name="ui_fill_form", description="x"),
            ToolDefinition(name="ui_submit_form", description="x"),
        ],
    )
    await proc.execute_tool("1", "ui_click", {"target_locator": "btn-save"}, 1)
    await proc.execute_tool("2", "ui_click", {"target_locator": "btn-save"}, 1)
    await proc.execute_tool("3", "ui_fill_form", {"fields": [{"name": "n", "value": "v"}]}, 1)
    await proc.execute_tool("4", "ui_fill_form", {"fields": [{"name": "n", "value": "v"}]}, 1)
    await proc.execute_tool("5", "ui_submit_form", {"form_session_id": "form-1"}, 1)
    await proc.execute_tool("6", "ui_submit_form", {"form_session_id": "form-1"}, 1)

    assert sandbox.execute.call_count == 6


@pytest.mark.asyncio
async def test_ui_navigation_tools_never_deduped_same_turn() -> None:
    """Navigation changes UI state; same args must still execute."""
    sandbox = MagicMock()
    sandbox.execute = AsyncMock(
        return_value=ToolResult(
            tool_call_id="x",
            name="ui_open_surface",
            success=True,
            output="ok",
        )
    )
    sandbox.input_variables = {PAGE_CONTEXT_KEY: {"page_key": "p1"}}
    sandbox._page_session_id = "s1"
    sandbox._page_readonly_cache_epoch = 0
    proc = ToolCallProcessor(
        sandbox=sandbox,
        tools=[
            ToolDefinition(name="ui_open_surface", description="x"),
            ToolDefinition(name="ui_click", description="x"),
        ],
    )
    await proc.execute_tool("1", "ui_open_surface", {"surface_id": "drawer-1"}, 1)
    await proc.execute_tool("2", "ui_open_surface", {"surface_id": "drawer-1"}, 1)
    await proc.execute_tool("3", "ui_click", {"target_locator": "menu-agents"}, 1)
    await proc.execute_tool("4", "ui_click", {"target_locator": "menu-agents"}, 1)

    assert sandbox.execute.call_count == 4


