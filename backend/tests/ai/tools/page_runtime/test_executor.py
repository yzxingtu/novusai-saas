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


@pytest.mark.asyncio
async def test_page_runtime_executor_appends_specific_error_from_error_field() -> None:
    bridge = StubPageRuntimeBridge(
        {
            "success": False,
            "message": "Action execution failed.",
            "error": "Target not found: 添加供应商",
            "error_type": "not_found",
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
        "Action execution failed. Detail: Target not found: 添加供应商"
    )
    assert result.summary == result.error
    assert result.summary_payload is not None
    assert result.summary_payload["error_detail"] == "Target not found: 添加供应商"
    assert result.summary_payload["error"] == "Target not found: 添加供应商"
    assert result.summary_payload["message"] == "Action execution failed."
    assert result.summary_payload["error_type"] == "not_found"


@pytest.mark.asyncio
async def test_page_runtime_executor_forwards_page_context_and_page_key_to_bridge() -> None:
    bridge = StubPageRuntimeBridge(
        {
            "success": True,
            "message": "Page runtime action completed.",
            "data": {"opened_surface_id": "surface:modal"},
        }
    )
    executor = PageRuntimeToolExecutor(bridge)
    definition = ToolDefinition(
        name="ui_open_surface",
        description="Open ui surface",
    )
    context = ExecutionContext(
        tenant_id=1,
        agent_id=2,
        user_role="tenant_admin",
        page_session_id="page-session-1",
        variables={
            "page_context": {
                "page_key": "admin.suppliers",
                "ui_epoch": 7,
            }
        },
    )

    result = await executor.execute(
        definition,
        "call-ui-open",
        {"target_locator": "text:添加供应商"},
        context,
    )

    assert result.success is True
    assert bridge.calls == [
        {
            "arguments": {
                "_page_context": {
                    "page_key": "admin.suppliers",
                    "ui_epoch": 7,
                },
                "page_key": "admin.suppliers",
                "target_locator": "text:添加供应商",
            },
            "page_session_id": "page-session-1",
            "tool_name": "ui_open_surface",
            "user_role": "tenant_admin",
        }
    ]
