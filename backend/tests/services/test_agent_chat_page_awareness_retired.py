"""
Test type: structural
Scope: AI dialogue page-awareness retirement request and sandbox guards.
Mock strategy: no mocks; validates public schema and sandbox guard behavior.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.ai.engine.system_prompt_rendering import build_system_message
from app.ai.tools.sandbox import ToolSandbox
from app.ai.tools.types import ToolDefinition
from app.schemas.ai.agent_chat import AgentChatRequest, AgentRouteRequest
from app.schemas.ai.batch_run import BatchRunCreate
from app.schemas.ai.gateway import ChatRequest


def test_agent_chat_request_rejects_retired_page_context_fields() -> None:
    with pytest.raises(ValidationError):
        AgentChatRequest.model_validate(
            {
                "message": "hello",
                "page_context": {"page_key": "tenant.ai.agents"},
            }
        )

    with pytest.raises(ValidationError):
        AgentChatRequest.model_validate(
            {
                "message": "hello",
                "page_session_id": "session-1",
            }
        )

    with pytest.raises(ValidationError):
        AgentChatRequest.model_validate(
            {
                "message": "hello",
                "variables": {"page_session": {"id": "session-1"}},
            }
        )


@pytest.mark.parametrize(
    "key",
    [
        "page_runtime",
        "last_page_key",
        "last_page_op",
        "ui_click",
        "UI_CLICK",
        "Page_Runtime",
        "ui_custom_action",
        "pageop_click",
        "PageOp_Click",
        "replace_content",
    ],
)
def test_agent_chat_request_rejects_retired_page_runtime_variables(
    key: str,
) -> None:
    with pytest.raises(ValidationError):
        AgentChatRequest.model_validate(
            {
                "message": "hello",
                "variables": {key: "retired"},
            }
        )


@pytest.mark.parametrize(
    "key",
    [
        "page_runtime",
        "last_page_key",
        "last_page_op",
        "ui_fill_form",
        "pageop_submit",
        "get_editor_html",
        "replace_content",
    ],
)
def test_batch_run_items_reject_retired_page_runtime_variables(key: str) -> None:
    with pytest.raises(ValidationError):
        BatchRunCreate.model_validate({"items": [{"name": "row", key: "retired"}]})


def test_batch_run_nested_variables_reject_retired_page_runtime_variables() -> None:
    with pytest.raises(ValidationError):
        BatchRunCreate.model_validate(
            {"items": [{"name": "row", "variables": {"page_runtime": "retired"}}]}
        )


def test_system_prompt_rendering_rejects_direct_retired_variable_bypass() -> None:
    agent = SimpleNamespace(
        id=1,
        name="Assistant",
        system_prompt="Use {{ page_runtime }}",
    )

    with pytest.raises(ValueError):
        build_system_message(
            agent=agent,  # type: ignore[arg-type]
            input_variables={"page_runtime": {"route": "admin.ai.health"}},
        )


def test_tool_sandbox_constructor_rejects_retired_page_variables() -> None:
    with pytest.raises(ValueError):
        ToolSandbox(
            tenant_id=1,
            agent_id=1,
            input_variables={"last_page_key": "admin.ai.health"},
        )


def test_agent_route_request_rejects_retired_page_context_fields() -> None:
    with pytest.raises(ValidationError):
        AgentRouteRequest.model_validate(
            {
                "message": "route this",
                "page_context": {"page_key": "admin.ai.agents"},
            }
        )


def test_direct_gateway_chat_request_rejects_retired_page_context_fields() -> None:
    with pytest.raises(ValidationError):
        ChatRequest.model_validate(
            {
                "model_code": "openai/gpt-test",
                "messages": [{"role": "user", "content": "hello"}],
                "page_context": {"page_key": "admin.ai.agents"},
            }
        )

    with pytest.raises(ValidationError):
        ChatRequest.model_validate(
            {
                "model_code": "openai/gpt-test",
                "messages": [
                    {
                        "role": "user",
                        "content": "hello",
                        "page_session_id": "session-1",
                    }
                ],
            }
        )


def test_direct_gateway_rejects_retired_page_tool_definitions() -> None:
    with pytest.raises(ValidationError):
        ChatRequest.model_validate(
            {
                "model_code": "openai/gpt-test",
                "messages": [{"role": "user", "content": "hello"}],
                "tools": [
                    {
                        "type": "function",
                        "function": {
                            "name": "ui_get_snapshot",
                            "description": "retired",
                        },
                    }
                ],
            }
        )

    with pytest.raises(ValidationError):
        ChatRequest.model_validate(
            {
                "model_code": "openai/gpt-test",
                "messages": [{"role": "user", "content": "hello"}],
                "tools": [
                    {
                        "type": "function",
                        "function": {
                            "name": "append_content",
                            "description": "retired editor runtime",
                        },
                    }
                ],
            }
        )

    with pytest.raises(ValidationError):
        ChatRequest.model_validate(
            {
                "model_code": "openai/gpt-test",
                "messages": [
                    {
                        "role": "assistant",
                        "content": "",
                        "tool_calls": [
                            {
                                "id": "call-1",
                                "type": "function",
                                "function": {"name": "pageop_click"},
                            }
                        ],
                    }
                ],
            }
        )


@pytest.mark.asyncio
async def test_tool_sandbox_rejects_retired_page_tools() -> None:
    sandbox = ToolSandbox(
        tenant_id=1,
        agent_id=1,
    )
    definitions = [
        ToolDefinition(name="ui_read_region", description="retired"),
        ToolDefinition(name="get_page_context", description="retired"),
        ToolDefinition(
            name="custom_editor_bridge",
            description="retired by semantic family",
            semantic_family="page_ops",
        ),
    ]

    for tool_name in (
        "ui_read_region",
        "get_page_context",
        "custom_editor_bridge",
    ):
        result = await sandbox.execute("call-1", tool_name, {}, definitions)

        assert result.success is False
        assert result.error_type == "page_awareness_retired"
