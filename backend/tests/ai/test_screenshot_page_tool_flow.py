from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.ai.engine.base import BaseEngine
from app.ai.engine.types import ExecutionRequest, ExecutionResult
from app.ai.tools.page_tool_expander import expand_page_tools
from app.ai.tools.types import ToolDefinition, ToolResult
from app.ai.types import ChatMessage, ChatResponse


class _DummyEngine(BaseEngine):
    async def execute(self, _agent, _request) -> ExecutionResult:  # noqa: ANN001
        return ExecutionResult(success=True)


def test_expand_page_tools_includes_capture_screenshot() -> None:
    base_tools = [
        ToolDefinition(name="invoke_page_operation", description="invoke"),
    ]
    input_vars = {
        "page_context": {
            "page_key": "admin.dashboard",
            "page_data": {
                "available_operations": [
                    {
                        "name": "capture_screenshot",
                        "label": "Capture Screenshot",
                        "readonly": True,
                    },
                ],
            },
        },
    }

    expanded = expand_page_tools(base_tools, input_vars)

    assert [tool.name for tool in expanded] == [
        "invoke_page_operation",
        "pageop_capture_screenshot",
    ]


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
            name="invoke_page_operation",
            success=True,
            output="Screenshot captured.",
            attachments=[screenshot_attachment],
            llm_follow_up_message=(
                "Analyze the attached current-page screenshot together with the existing page context."
            ),
        )
    )

    engine = _DummyEngine(
        db=MagicMock(),
        gateway=MagicMock(),
        sandbox=sandbox,
    )

    llm_messages_seen: list[ChatMessage] = []

    async def _fake_call_llm(**kwargs):  # noqa: ANN003
        llm_messages_seen[:] = list(kwargs["messages"])
        return ChatResponse(
            message=ChatMessage(role="assistant", content="Visual analysis completed."),
            total_tokens=9,
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
        total_tokens=3,
        tool_calls=[
            {
                "id": "tc-shot",
                "type": "function",
                "function": {
                    "name": "invoke_page_operation",
                    "arguments": (
                        '{"page_key":"admin.dashboard","operation_name":"capture_screenshot"}'
                    ),
                },
            },
        ],
    )

    final_response, tool_results, total_tokens = await engine._handle_tool_calls(
        agent=SimpleNamespace(id=1),
        messages=messages,
        response=response,
        tools=[ToolDefinition(name="invoke_page_operation", description="invoke")],
        request=request,
    )

    assert final_response is not None
    assert final_response.message.content == "Visual analysis completed."
    assert total_tokens == 12
    assert len(tool_results) == 1
    assert tool_results[0].attachments == [screenshot_attachment]

    internal_user = llm_messages_seen[-1]
    assert internal_user.role == "user"
    assert internal_user.internal_only is True
    assert internal_user.attachments == [screenshot_attachment]
    assert "screenshot" in internal_user.content.lower()
