"""Test type: behavioral
Scope: ToolSandbox runtime context propagation and executor ownership guards.
Real dependencies: ToolSandbox executor selection and ExecutionContext assembly.
Mocked dependencies: plugin registry lookup only, never tool execution result.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

import pytest

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
        definitions=[
            ToolDefinition(name="capture_runtime_info", description="capture")
        ],
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
        definitions=[
            ToolDefinition(name="capture_runtime_info", description="capture")
        ],
    )

    assert result.success is True
    assert capture.last_context is not None
    assert capture.last_context.runtime_provider_id is None
    assert capture.last_context.runtime_provider_name is None
    assert capture.last_context.runtime_model_id is None
    assert capture.last_context.runtime_model_name is None
    assert capture.last_context.runtime_model_code is None


def test_tool_sandbox_does_not_wire_invalid_runtime_executors() -> None:
    """
    Test type: structural
    Scope: ToolSandbox executor registry does not expose invalid runtime tools.
    """
    sandbox = ToolSandbox(
        tenant_id=100,
        agent_id=200,
        config=SandboxConfig(),
    )

    for tool_name in {
        "ui_get_snapshot",
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
        assert tool_name not in sandbox._named_executors


@pytest.mark.asyncio
async def test_tool_sandbox_rejects_invalid_runtime_tools_even_if_defined() -> None:
    """
    Test type: structural
    Scope: invalid runtime tools cannot be resurrected by supplied definitions.
    """
    sandbox = ToolSandbox(
        tenant_id=100,
        agent_id=200,
        config=SandboxConfig(),
    )
    sandbox._named_executors["ui_get_snapshot"] = _CaptureExecutor()

    result = await sandbox.execute(
        tool_call_id="tc-invalid-runtime",
        name="ui_get_snapshot",
        arguments={},
        definitions=[ToolDefinition(name="ui_get_snapshot", description="snapshot")],
    )

    assert result.success is False
    assert result.error_type == "invalid_runtime_tool"


@pytest.mark.asyncio
async def test_tool_sandbox_plugin_tool_missing_executor_does_not_use_generic_fallback(
    monkeypatch,
) -> None:
    sandbox = ToolSandbox(
        tenant_id=100,
        agent_id=200,
        config=SandboxConfig(),
    )
    capture = _CaptureExecutor()
    sandbox._named_executors["plugin_tool"] = capture
    registry_stub = SimpleNamespace(get_plugin_executor=lambda *_args: None)
    monkeypatch.setattr(
        "app.plugins.registry.ExtensionRegistry.get_instance",
        lambda: registry_stub,
    )

    result = await sandbox.execute(
        tool_call_id="tc-plugin-missing-executor",
        name="plugin_tool",
        arguments={},
        definitions=[
            ToolDefinition(
                name="plugin_tool",
                description="plugin-owned tool",
                source_plugin="weather-widget",
            )
        ],
    )

    assert result.success is False
    assert result.error_type == "plugin_executor_unavailable"
    assert "plugin:weather-widget" in result.error
    assert capture.last_context is None
