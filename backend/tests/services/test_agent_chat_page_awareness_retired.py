"""
Test type: structural
Scope: AI dialogue page-awareness retirement request and sandbox guards.
Mock strategy: no mocks; validates public schema and sandbox guard behavior.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.ai.tools.sandbox import ToolSandbox
from app.ai.tools.types import ToolDefinition
from app.schemas.ai.agent_chat import AgentChatRequest, AgentRouteRequest


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


def test_agent_route_request_rejects_retired_page_context_fields() -> None:
    with pytest.raises(ValidationError):
        AgentRouteRequest.model_validate(
            {
                "message": "route this",
                "page_context": {"page_key": "admin.ai.agents"},
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
    ]

    for tool_name in ("ui_read_region", "get_page_context"):
        result = await sandbox.execute("call-1", tool_name, {}, definitions)

        assert result.success is False
        assert result.error_type == "page_awareness_retired"
