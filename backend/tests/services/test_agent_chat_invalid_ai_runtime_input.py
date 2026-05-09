"""
Test type: structural
Scope: AI dialogue request and sandbox guards reject invalid runtime input.
Mock strategy: no mocks; validates public schema and sandbox guard behavior.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.ai.engine.system_prompt_rendering import build_system_message
from app.ai.engine.types import ExecutionRequest
from app.ai.tools.sandbox import ToolSandbox
from app.ai.tools.types import ToolDefinition, to_openai_tools
from app.ai.types import ChatMessage
from app.schemas.ai.agent_chat import AgentChatRequest, AgentRouteRequest
from app.schemas.ai.batch_run import BatchRunCreate
from app.schemas.ai.gateway import ChatRequest

RETIRED_ONLINE_SEARCH_TOOL_NAMES = (
    "web_search",
    "fetch_url",
    "web_research",
    "online_search",
    "hosted_web_search",
    "native_web_search",
    "SearchProvider",
    "联网搜索",
)


def test_agent_chat_request_rejects_invalid_runtime_fields() -> None:
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
        "active_surface",
        "current_dom",
        "has_page_intent",
        "page_intent_kind",
        "last_page_key",
        "last_page_op",
        "ui_click",
        "UI_CLICK",
        "Page_Runtime",
        "ui_custom_action",
        "pageop_click",
        "PageOp_Click",
        "replace_content",
        "web_search",
        "fetch_url",
        "online_search",
        "web_research",
        "SearchProvider",
        "search_provider",
        "hosted_web_search",
        "native_web_search_supported",
        "联网搜索",
    ],
)
def test_agent_chat_request_rejects_invalid_runtime_variables(
    key: str,
) -> None:
    with pytest.raises(ValidationError):
        AgentChatRequest.model_validate(
            {
                "message": "hello",
                "variables": {key: "invalid"},
            }
        )


@pytest.mark.parametrize(
    "variables",
    [
        {"intent_plan": [{"kind": "tool", "family": "page_ops"}]},
        {"tool_planner": {"semantic_family": "page_ops"}},
        {"selected": "ui_get_snapshot"},
        {"capability": "page_awareness"},
    ],
)
def test_agent_chat_request_rejects_invalid_runtime_values(
    variables: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        AgentChatRequest.model_validate(
            {
                "message": "hello",
                "variables": variables,
            }
        )


@pytest.mark.parametrize(
    "selected_skill_name",
    [
        "天气组件",
        "report_query",
        "page_awareness",
        "页面感知交互",
        "ui-click",
        "pageop-click",
        "web_search",
        "fetch_url",
        "web_research",
        "online_search",
        "public_search",
        "baidu_public_search",
        "baidu_search",
        "SearchProvider",
        "search_provider",
        "联网搜索",
        "网页搜索",
        "在线搜索",
        "公开搜索",
        "百度公开搜索",
    ],
)
def test_agent_chat_request_rejects_client_selected_skill_names(
    selected_skill_name: str,
) -> None:
    with pytest.raises(ValidationError):
        AgentChatRequest.model_validate(
            {
                "message": "hello",
                "selected_skill_names": [selected_skill_name],
            }
        )


def test_execution_request_rejects_direct_invalid_runtime_selection() -> None:
    with pytest.raises(ValueError):
        ExecutionRequest(
            agent_id=1,
            tenant_id=1,
            messages=[ChatMessage(role="user", content="hello")],
            selected_skill_names=["page_awareness"],
        )

    with pytest.raises(ValueError):
        ExecutionRequest(
            agent_id=1,
            tenant_id=1,
            messages=[ChatMessage(role="user", content="hello")],
            trust_policy_ref={"allowed_tool_names": ["ui-click"]},
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
def test_batch_run_items_reject_invalid_runtime_variables(key: str) -> None:
    with pytest.raises(ValidationError):
        BatchRunCreate.model_validate({"items": [{"name": "row", key: "invalid"}]})


def test_batch_run_nested_variables_reject_invalid_runtime_variables() -> None:
    with pytest.raises(ValidationError):
        BatchRunCreate.model_validate(
            {"items": [{"name": "row", "variables": {"page_runtime": "invalid"}}]}
        )


def test_system_prompt_rendering_rejects_direct_invalid_variable_bypass() -> None:
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


def test_tool_sandbox_constructor_rejects_invalid_runtime_variables() -> None:
    with pytest.raises(ValueError):
        ToolSandbox(
            tenant_id=1,
            agent_id=1,
            input_variables={"last_page_key": "admin.ai.health"},
        )


def test_agent_route_request_rejects_invalid_runtime_fields() -> None:
    with pytest.raises(ValidationError):
        AgentRouteRequest.model_validate(
            {
                "message": "route this",
                "page_context": {"page_key": "admin.ai.agents"},
            }
        )


def test_direct_gateway_chat_request_rejects_invalid_runtime_fields() -> None:
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


def test_direct_gateway_rejects_invalid_runtime_tool_definitions() -> None:
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
                            "description": "invalid runtime tool",
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
                            "description": "invalid runtime tool",
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


@pytest.mark.parametrize("tool_name", RETIRED_ONLINE_SEARCH_TOOL_NAMES)
def test_direct_gateway_rejects_retired_online_search_tool_definitions(
    tool_name: str,
) -> None:
    with pytest.raises(ValidationError):
        ChatRequest.model_validate(
            {
                "model_code": "openai/gpt-test",
                "messages": [{"role": "user", "content": "hello"}],
                "tools": [
                    {
                        "type": "function",
                        "function": {
                            "name": tool_name,
                            "description": "retired online-search tool",
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
                                "id": "call-retired",
                                "type": "function",
                                "function": {"name": tool_name},
                            }
                        ],
                    }
                ],
            }
        )


@pytest.mark.asyncio
async def test_tool_sandbox_rejects_invalid_runtime_tools() -> None:
    sandbox = ToolSandbox(
        tenant_id=1,
        agent_id=1,
    )
    definitions = [
        ToolDefinition(name="ui_read_region", description="invalid"),
        ToolDefinition(name="get_page_context", description="invalid"),
        ToolDefinition(
            name="custom_editor_bridge",
            description="invalid by semantic family",
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
        assert result.error_type == "invalid_runtime_tool"


def test_openai_tool_schema_filters_invalid_runtime_tools() -> None:
    tools = to_openai_tools(
        [
            ToolDefinition(name="crm_lookup", description="valid"),
            ToolDefinition(name="ui-click", description="invalid alias"),
            ToolDefinition(
                name="custom_bridge",
                description="invalid family",
                semantic_family="page_ops",
            ),
            ToolDefinition(
                name="crm_public_lookup",
                description="invalid retired skill owner",
                source_skill_name="联网搜索",
                source_package_name="百度公开搜索",
                source_plugin="baidu_public_search",
            ),
        ]
    )

    assert [tool["function"]["name"] for tool in tools] == ["crm_lookup"]


@pytest.mark.parametrize("tool_name", RETIRED_ONLINE_SEARCH_TOOL_NAMES)
def test_openai_tool_schema_rejects_retired_online_search_tool_names(
    tool_name: str,
) -> None:
    with pytest.raises(ValueError):
        ToolDefinition(name=tool_name, description="retired search").to_openai_schema()


def test_openai_tools_filter_retired_online_search_tool_names() -> None:
    tools = to_openai_tools(
        [
            ToolDefinition(name="crm_lookup", description="valid"),
            *[
                ToolDefinition(name=tool_name, description="retired search")
                for tool_name in RETIRED_ONLINE_SEARCH_TOOL_NAMES
            ],
        ]
    )

    assert [tool["function"]["name"] for tool in tools] == ["crm_lookup"]
