import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.ai.engine.base import BaseEngine
from app.ai.engine.types import ExecutionRequest, ExecutionResult
from app.ai.tools.types import ToolDefinition, ToolResult
from app.ai.types import ChatMessage, ChatResponse


class _DummyEngine(BaseEngine):
    async def execute(self, _agent, _request) -> ExecutionResult:  # noqa: ANN001
        return ExecutionResult(success=True)


@pytest.mark.asyncio
async def test_tool_call_loop_injects_internal_screenshot_attachment_for_next_llm_round() -> (
    None
):
    screenshot_attachment = {
        "type": "image",
        "url": "/uploads/chat/screenshot-1.jpg",
        "name": "screenshot-1.jpg",
        "mime_type": "image/jpeg",
    }
    sandbox = MagicMock()
    sandbox.execute = AsyncMock(
        return_value=ToolResult(
            tool_call_id="tc-shot",
            name="ui_get_snapshot",
            success=True,
            output="ok",
            attachments=[screenshot_attachment],
        )
    )

    engine = _DummyEngine(
        db=MagicMock(),
        gateway=MagicMock(),
        sandbox=sandbox,
    )

    llm_messages_seen: list[ChatMessage] = []
    llm_call_count = 0
    initial_total_tokens = 3
    initial_output_tokens = 1
    followup_total_tokens = 9
    followup_output_tokens = 4

    async def _fake_call_llm(**kwargs):  # noqa: ANN003
        nonlocal llm_call_count
        llm_call_count += 1
        llm_messages_seen[:] = list(kwargs["messages"])
        return ChatResponse(
            message=ChatMessage(role="assistant", content="Visual analysis completed."),
            total_tokens=followup_total_tokens,
            output_tokens=followup_output_tokens,
        )

    engine._call_llm = AsyncMock(side_effect=_fake_call_llm)  # type: ignore[method-assign]

    request = ExecutionRequest(
        agent_id=1,
        tenant_id=1,
        conversation_id=99,
        messages=[ChatMessage(role="user", content="请看一下这个页面布局")],
    )
    messages = [
        ChatMessage(role="system", content="system"),
        ChatMessage(role="user", content="请看一下这个页面布局"),
    ]
    response = ChatResponse(
        message=ChatMessage(role="assistant", content=""),
        total_tokens=initial_total_tokens,
        output_tokens=initial_output_tokens,
        tool_calls=[
            {
                "id": "tc-shot",
                "type": "function",
                "function": {
                    "name": "ui_get_snapshot",
                    "arguments": '{"mode":"full"}',
                },
            },
        ],
    )

    final_response, tool_results, total_tokens, _completion_tokens = await engine._handle_tool_calls(
        agent=SimpleNamespace(id=1),
        messages=messages,
        response=response,
        tools=[ToolDefinition(name="ui_get_snapshot", description="snapshot")],
        all_tools=[ToolDefinition(name="ui_get_snapshot", description="snapshot")],
        request=request,
    )

    assert final_response is not None
    assert final_response.message.content == "Visual analysis completed."
    assert total_tokens == (
        initial_total_tokens + llm_call_count * followup_total_tokens
    )
    assert len(tool_results) == 1
    assert tool_results[0].attachments == [screenshot_attachment]
    assert _completion_tokens == (
        initial_output_tokens + llm_call_count * followup_output_tokens
    )

    internal_user = llm_messages_seen[-1]
    assert internal_user.role == "user"
    assert internal_user.internal_only is True
    assert internal_user.attachments == [screenshot_attachment]
    assert internal_user.content == ""


@pytest.mark.asyncio
async def test_tool_call_loop_executes_tool_after_pending_consent_is_approved() -> None:
    sandbox = MagicMock()
    sandbox.execute = AsyncMock(
        return_value=ToolResult(
            tool_call_id="tc-weather",
            name="get_current_weather",
            success=True,
            output='{"city":"北京","temperature":25}',
        )
    )

    engine = _DummyEngine(
        db=MagicMock(),
        gateway=MagicMock(),
        sandbox=sandbox,
    )

    llm_messages_seen: list[ChatMessage] = []
    llm_call_count = 0
    initial_total_tokens = 3
    initial_output_tokens = 2
    followup_total_tokens = 7
    followup_output_tokens = 5

    async def _fake_call_llm(**kwargs):  # noqa: ANN003
        nonlocal llm_call_count
        llm_call_count += 1
        llm_messages_seen[:] = list(kwargs["messages"])
        return ChatResponse(
            message=ChatMessage(role="assistant", content="北京当前 25C，晴。"),
            total_tokens=followup_total_tokens,
            output_tokens=followup_output_tokens,
        )

    engine._call_llm = AsyncMock(side_effect=_fake_call_llm)  # type: ignore[method-assign]

    request = ExecutionRequest(
        agent_id=1,
        tenant_id=1,
        conversation_id=584,
        messages=[ChatMessage(role="user", content="今天北京天气怎么样？")],
        interaction_updates=[
            {
                "kind": "pending_consent",
                "tool_name": "get_current_weather",
                "rejected": False,
            }
        ],
    )
    messages = [
        ChatMessage(role="user", content="今天北京天气怎么样？"),
    ]
    response = ChatResponse(
        message=ChatMessage(role="assistant", content=""),
        total_tokens=initial_total_tokens,
        output_tokens=initial_output_tokens,
        tool_calls=[
            {
                "id": "tc-weather",
                "type": "function",
                "function": {
                    "name": "get_current_weather",
                    "arguments": '{"city":"北京"}',
                },
            },
        ],
    )

    final_response, tool_results, total_tokens, _completion_tokens = await engine._handle_tool_calls(
        agent=SimpleNamespace(id=1),
        messages=messages,
        response=response,
        tools=[ToolDefinition(name="get_current_weather", description="weather")],
        all_tools=[ToolDefinition(name="get_current_weather", description="weather")],
        request=request,
        tool_consent_modes={"get_current_weather": "ask"},
    )

    assert final_response is not None
    assert final_response.message.content == "北京当前 25C，晴。"
    assert total_tokens == (
        initial_total_tokens + llm_call_count * followup_total_tokens
    )
    assert len(tool_results) == 1
    assert tool_results[0].name == "get_current_weather"
    sandbox.execute.assert_awaited_once()
    assert llm_messages_seen[-1].role == "tool"
    assert _completion_tokens == (
        initial_output_tokens + llm_call_count * followup_output_tokens
    )
    assert "25" in (llm_messages_seen[-1].content or "")


@pytest.mark.asyncio
async def test_tool_call_loop_runs_parallel_safe_web_search_batch_concurrently() -> None:
    class _TrackingSandbox:
        def __init__(self) -> None:
            self.active_calls = 0
            self.max_parallel = 0

        async def execute(
            self,
            tool_call_id: str,
            name: str,
            arguments: dict,
            definitions: list[ToolDefinition],
            conversation_id: int,
        ) -> ToolResult:
            _ = definitions, conversation_id
            self.active_calls += 1
            self.max_parallel = max(self.max_parallel, self.active_calls)
            await asyncio.sleep(0.02)
            self.active_calls -= 1
            return ToolResult(
                tool_call_id=tool_call_id,
                name=name,
                success=True,
                output=f'{{"query":"{arguments.get("query", "")}"}}',
            )

    sandbox = _TrackingSandbox()
    engine = _DummyEngine(
        db=MagicMock(),
        gateway=MagicMock(),
        sandbox=sandbox,
    )
    request = ExecutionRequest(
        agent_id=1,
        tenant_id=1,
        conversation_id=321,
        messages=[ChatMessage(role="user", content="查两条新闻")],
    )
    messages = [ChatMessage(role="user", content="查两条新闻")]
    response = ChatResponse(
        message=ChatMessage(role="assistant", content=""),
        total_tokens=5,
        output_tokens=5,
        tool_calls=[
            {
                "id": "tc-search-1",
                "type": "function",
                "function": {
                    "name": "web_search",
                    "arguments": '{"query":"AI latest news"}',
                },
            },
            {
                "id": "tc-search-2",
                "type": "function",
                "function": {
                    "name": "web_search",
                    "arguments": '{"query":"OpenAI latest news"}',
                },
            },
        ],
    )

    final_response, tool_results, _total_tokens, _completion_tokens = (
        await engine._handle_tool_calls(
            agent=SimpleNamespace(id=1),
            messages=messages,
            response=response,
            tools=[ToolDefinition(name="web_search", description="search")],
            all_tools=[ToolDefinition(name="web_search", description="search")],
            request=request,
            skip_final_call=True,
        )
    )

    assert final_response is None
    assert len(tool_results) == 2
    assert [result.tool_call_id for result in tool_results] == [
        "tc-search-1",
        "tc-search-2",
    ]
    assert sandbox.max_parallel >= 2
