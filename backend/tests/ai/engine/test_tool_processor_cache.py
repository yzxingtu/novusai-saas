import pytest
from typing import Any

from app.ai.engine.execution_state_machine import (
    ExecutionStateMachine,
    reset_current_execution_state_machine,
    set_current_execution_state_machine,
)
from app.ai.engine.tool_processor import ToolCallProcessor
from app.ai.tools.types import ToolResult


class _FakeSandbox:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def execute(
        self,
        tool_call_id: str,
        name: str,
        arguments: dict[str, Any],
        definitions=None,
        conversation_id: int | None = None,
    ) -> ToolResult:
        self.calls.append((name, dict(arguments)))
        return ToolResult(
            tool_call_id=tool_call_id,
            name=name,
            success=True,
            output=f"{name}-result",
        )


@pytest.mark.asyncio
async def test_web_search_hits_turn_cache_once() -> None:
    state = ExecutionStateMachine(
        intent_plan=[],
        budget=None,
        execution_path="fast",
    )
    token = set_current_execution_state_machine(state)
    try:
        sandbox = _FakeSandbox()
        processor = ToolCallProcessor(
            sandbox=sandbox,
            tools=[],
            all_tools=[],
        )
        await processor.execute_tool("tc1", "web_search", {"query": "rain"}, 1)
        await processor.execute_tool("tc2", "web_search", {"query": "rain"}, 1)

        assert len(sandbox.calls) == 1
        assert state.dedupe_hit
        payload = state.build_diagnostics_payload()
        cache_info = payload["cache_hits"]
        assert cache_info["dedupe_hit"] is True
        assert cache_info["cache_hit_kind"] is not None
        assert "search_query" in cache_info["cache_hit_kind"]
        assert cache_info["page_context_cache_hit"] is False
    finally:
        reset_current_execution_state_machine(token)


@pytest.mark.asyncio
async def test_page_context_cache_marker_set_on_hit() -> None:
    state = ExecutionStateMachine(
        intent_plan=[],
        budget=None,
        execution_path="fast",
    )
    token = set_current_execution_state_machine(state)
    try:
        sandbox = _FakeSandbox()
        processor = ToolCallProcessor(
            sandbox=sandbox,
            tools=[],
            all_tools=[],
        )
        args = {"page_key": "admin.users"}
        await processor.execute_tool("tc1", "get_page_context", args, 2)
        await processor.execute_tool("tc2", "get_page_context", args, 2)

        assert len(sandbox.calls) == 1
        payload = state.build_diagnostics_payload()
        cache_info = payload["cache_hits"]
        assert cache_info["page_context_cache_hit"] is True
        assert "page_context" in cache_info["cache_hit_kind"]
    finally:
        reset_current_execution_state_machine(token)
