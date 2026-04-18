from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from app.ai.tools.executors.ui_snapshot_executor import UISnapshotExecutor
from app.ai.tools.page_runtime.executor import PageRuntimeToolExecutor
from app.ai.tools.sandbox import SandboxConfig, ToolSandbox
from app.ai.tools.types import ToolDefinition, ToolResult


@dataclass
class _CaptureExecutor:
    last_context: Any = None

    async def validate(self, definition, arguments) -> bool:  # noqa: ANN001
        _ = (definition, arguments)
        return True

    async def execute(  # noqa: ANN001
        self,
        definition,
        tool_call_id,
        arguments,
        context=None,
    ) -> ToolResult:
        _ = arguments
        self.last_context = context
        return ToolResult(
            tool_call_id=tool_call_id,
            name=definition.name,
            success=True,
            output="ok",
        )


@pytest.mark.asyncio
async def test_tool_sandbox_passes_runtime_model_info_into_execution_context() -> None:
    sandbox = ToolSandbox(
        tenant_id=100,
        agent_id=200,
        config=SandboxConfig(),
        user_id=300,
    )
    capture = _CaptureExecutor()
    sandbox._named_executors["capture_runtime_info"] = capture
    sandbox.set_runtime_model_info(
        {
            "provider_id": 11,
            "provider_name": "Provider Eleven",
            "model_id": 22,
            "model_name": "Model Twenty Two",
            "model_code": "gpt-x",
        }
    )

    result = await sandbox.execute(
        tool_call_id="tc-runtime",
        name="capture_runtime_info",
        arguments={},
        definitions=[ToolDefinition(name="capture_runtime_info", description="capture")],
    )

    assert result.success is True
    assert capture.last_context is not None
    assert capture.last_context.runtime_provider_id == 11
    assert capture.last_context.runtime_provider_name == "Provider Eleven"
    assert capture.last_context.runtime_model_id == 22
    assert capture.last_context.runtime_model_name == "Model Twenty Two"
    assert capture.last_context.runtime_model_code == "gpt-x"


@pytest.mark.asyncio
async def test_tool_sandbox_runtime_model_info_is_optional() -> None:
    sandbox = ToolSandbox(
        tenant_id=100,
        agent_id=200,
        config=SandboxConfig(),
    )
    capture = _CaptureExecutor()
    sandbox._named_executors["capture_runtime_info"] = capture
    sandbox.set_runtime_model_info(None)

    result = await sandbox.execute(
        tool_call_id="tc-runtime-none",
        name="capture_runtime_info",
        arguments={},
        definitions=[ToolDefinition(name="capture_runtime_info", description="capture")],
    )

    assert result.success is True
    assert capture.last_context is not None
    assert capture.last_context.runtime_provider_id is None
    assert capture.last_context.runtime_provider_name is None
    assert capture.last_context.runtime_model_id is None
    assert capture.last_context.runtime_model_name is None
    assert capture.last_context.runtime_model_code is None


def test_tool_sandbox_wires_live_page_runtime_executor_for_page_tools() -> None:
    sandbox = ToolSandbox(
        tenant_id=100,
        agent_id=200,
        config=SandboxConfig(),
    )

    page_runtime_executor = sandbox._named_executors["ui_read_page"]

    assert isinstance(page_runtime_executor, PageRuntimeToolExecutor)
    for tool_name in {
        "ui_read_surface",
        "ui_read_region",
        "ui_read_table",
        "ui_list_interactables",
        "ui_click",
        "ui_open_surface",
        "ui_get_form_state",
        "ui_set_field",
        "ui_fill_form",
        "ui_submit_form",
    }:
        assert sandbox._named_executors[tool_name] is page_runtime_executor

    assert isinstance(sandbox._named_executors["ui_get_snapshot"], UISnapshotExecutor)
