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
async def test_get_page_context_not_deduped_when_page_key_changes() -> None:
    sandbox = MagicMock()
    sandbox.execute = AsyncMock(
        side_effect=[
            ToolResult(
                tool_call_id="a",
                name="get_page_context",
                success=True,
                output="page-a",
            ),
            ToolResult(
                tool_call_id="b",
                name="get_page_context",
                success=True,
                output="page-b",
            ),
        ]
    )
    sandbox.input_variables = {
        PAGE_CONTEXT_KEY: {"page_key": "admin.a"},
        "page_session_id": "s1",
    }
    sandbox._page_session_id = "s1"
    proc = ToolCallProcessor(
        sandbox=sandbox,
        tools=[ToolDefinition(name="get_page_context", description="x")],
    )
    await proc.execute_tool("1", "get_page_context", {}, 1)
    sandbox.input_variables[PAGE_CONTEXT_KEY] = {"page_key": "admin.b"}
    await proc.execute_tool("2", "get_page_context", {}, 1)

    assert sandbox.execute.call_count == 2


@pytest.mark.asyncio
async def test_pageop_mutation_tools_are_never_deduped() -> None:
    sandbox = MagicMock()
    sandbox.execute = AsyncMock(
        return_value=ToolResult(
            tool_call_id="x",
            name="pageop_create_record",
            success=True,
            output="ok",
        )
    )
    sandbox.input_variables = {PAGE_CONTEXT_KEY: {"page_key": "p1"}}
    proc = ToolCallProcessor(
        sandbox=sandbox,
        tools=[ToolDefinition(name="pageop_create_record", description="x")],
    )
    await proc.execute_tool("1", "pageop_create_record", {}, 1)
    await proc.execute_tool("2", "pageop_create_record", {}, 1)

    assert sandbox.execute.call_count == 2


@pytest.mark.asyncio
async def test_next_page_and_prev_page_never_deduped_same_turn() -> None:
    """Paging changes view state; same empty args must run twice (not readonly cache)."""
    sandbox = MagicMock()
    sandbox.execute = AsyncMock(
        return_value=ToolResult(
            tool_call_id="x",
            name="pageop_next_page",
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
            ToolDefinition(name="pageop_next_page", description="x"),
            ToolDefinition(name="pageop_prev_page", description="x"),
        ],
    )
    await proc.execute_tool("1", "pageop_next_page", {}, 1)
    await proc.execute_tool("2", "pageop_next_page", {}, 1)
    await proc.execute_tool("3", "pageop_prev_page", {}, 1)
    await proc.execute_tool("4", "pageop_prev_page", {}, 1)

    assert sandbox.execute.call_count == 4


@pytest.mark.asyncio
async def test_same_page_state_change_invalidates_get_page_context_cache() -> None:
    """After a state-changing page op, readonly snapshot cache must not reuse pre-change results."""
    sandbox = MagicMock()
    seq = {"i": 0}

    async def execute_side_effect(**kwargs: object) -> ToolResult:
        seq["i"] += 1
        n = seq["i"]
        name = kwargs.get("name") or ""
        return ToolResult(
            tool_call_id=str(kwargs.get("tool_call_id", "")),
            name=str(name),
            success=True,
            output=f"snapshot-{n}",
        )

    sandbox.execute = AsyncMock(side_effect=execute_side_effect)
    sandbox.input_variables = {PAGE_CONTEXT_KEY: {"page_key": "p1"}}
    sandbox._page_session_id = "s1"
    sandbox._page_readonly_cache_epoch = 0

    tools = [
        ToolDefinition(name="get_page_context", description="x"),
        ToolDefinition(name="pageop_next_page", description="x"),
    ]
    proc = ToolCallProcessor(sandbox=sandbox, tools=tools, all_tools=tools)

    r1, _ = await proc.execute_tool("1", "get_page_context", {}, 1)
    r2, _ = await proc.execute_tool("2", "get_page_context", {}, 1)
    assert r1.output == r2.output
    assert sandbox.execute.call_count == 1

    await proc.execute_tool("3", "pageop_next_page", {}, 1)
    assert sandbox._page_readonly_cache_epoch == 1

    r3, _ = await proc.execute_tool("4", "get_page_context", {}, 1)
    assert sandbox.execute.call_count == 3
    assert r3.output != r1.output
