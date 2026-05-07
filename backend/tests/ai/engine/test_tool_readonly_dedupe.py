"""
Test type: structural
Scope: same-turn readonly tool result deduplication in ToolCallProcessor.
Mock strategy: sandbox execution is mocked because this file verifies processor
cache behavior, not individual tool executors.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.ai.engine.tool_processor import ToolCallProcessor
from app.ai.tools.types import ToolDefinition, ToolResult


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
