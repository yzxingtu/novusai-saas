from __future__ import annotations

import pytest

from app.ai.tools.page_runtime.executor import PageRuntimeToolExecutor
from app.ai.tools.types import ExecutionContext, ToolDefinition


class StubPageRuntimeBridge:
    def __init__(self, result: dict[str, object]) -> None:
        self.calls: list[dict[str, object]] = []
        self.result = result

    async def invoke(
        self,
        *,
        arguments: dict[str, object],
        page_session_id: str,
        tool_name: str,
        user_role: str,
    ) -> dict[str, object]:
        self.calls.append(
            {
                "arguments": arguments,
                "page_session_id": page_session_id,
                "tool_name": tool_name,
                "user_role": user_role,
            }
        )
        return self.result


@pytest.mark.asyncio
async def test_page_runtime_executor_preserves_error_detail_in_failure_summary() -> None:
    bridge = StubPageRuntimeBridge(
        {
            "success": False,
            "message": "Page runtime action 'ui_click' failed.",
            "detail": 'Unable to locate element "添加供应商".',
            "error_type": "not_found",
            "data": {
                "locator": "text:添加供应商",
            },
        }
    )
    executor = PageRuntimeToolExecutor(bridge)
    definition = ToolDefinition(name="ui_click", description="Click ui element")
    context = ExecutionContext(
        tenant_id=1,
        agent_id=2,
        user_role="tenant_admin",
        page_session_id="page-session-1",
    )

    result = await executor.execute(
        definition,
        "call-ui-click",
        {"target_locator": "text:添加供应商"},
        context,
    )

    assert result.success is False
    assert result.error_type == "not_found"
    assert result.error == (
        "Page runtime action 'ui_click' failed. Detail: "
        'Unable to locate element "添加供应商".'
    )
    assert result.summary == result.error
    assert result.summary_payload == {
        "error_detail": 'Unable to locate element "添加供应商".',
        "locator": "text:添加供应商",
    }
    assert bridge.calls == [
        {
            "arguments": {"target_locator": "text:添加供应商"},
            "page_session_id": "page-session-1",
            "tool_name": "ui_click",
            "user_role": "tenant_admin",
        }
    ]
