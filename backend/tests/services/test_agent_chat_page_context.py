"""Agent chat thin page context tests / AgentChat 薄页面上下文测试。"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import ValidationError

from app.ai.tools.executors.ui_snapshot_executor import UISnapshotExecutor
from app.ai.tools.semantic_defaults import page_context_available_ui_tools
from app.ai.tools.types import ExecutionContext, ToolDefinition
from app.exceptions import ValidationException
from app.schemas.ai.agent_chat import (
    AgentChatRequest,
    AgentRouteRequest,
    NavigationCatalogEntry,
    PageContext,
)


def _navigation_entry() -> dict[str, object]:
    return {
        "title": "Agents",
        "path": "/admin/ai/agents",
        "page_key": "admin.ai.agents",
        "description": "Manage AI agents",
        "category": "AI",
        "endpoint": "/ai/agents",
        "keywords": ["agents", "assistant"],
        "capabilities": ["create", "edit"],
        "breadcrumb": ["AI", "Agents"],
    }


def test_page_context_accepts_thin_runtime_fields() -> None:
    page_context = PageContext.model_validate(
        {
            "page_key": "tenant.ai.agents",
            "locale": "zh-CN",
            "page_session_id": "session-1",
            "ui_epoch": 3,
            "surface_stack": [
                {"surface_id": "page-root", "kind": "page", "title": "Agents"},
            ],
            "active_form_summary": {
                "form_session_id": "form-1",
                "entity_name": "Agent",
                "mode": "create",
                "stage": "ready_to_submit",
                "can_submit": True,
            },
            "suggested_tools": {
                "primary": ["ui_get_snapshot", "ui_fill_form", "ui_submit_form"],
                "secondary": ["ui_get_form_state"],
            },
            "page_data": {
                "locale": "en-US",
                "entity_description": " Agent workspace ",
                "navigation_catalog": [_navigation_entry(), _navigation_entry()],
                "navigation_context": {
                    "breadcrumb": ["AI", "Agents", "Agents"],
                    "endpoint": "/ai/agents",
                    "page_key": "admin.ai.agents",
                    "path": "/admin/ai/agents",
                },
            },
        }
    )

    dumped = page_context.model_dump(exclude_none=True)
    assert dumped["page_key"] == "tenant.ai.agents"
    assert dumped["locale"] == "zh-CN"
    assert dumped["page_session_id"] == "session-1"
    assert dumped["ui_epoch"] == 3
    assert dumped["surface_stack"][0]["surface_id"] == "page-root"
    assert dumped["active_form_summary"]["form_session_id"] == "form-1"
    assert dumped["suggested_tools"]["primary"][0] == "ui_get_snapshot"
    assert dumped["page_data"]["locale"] == "en-US"
    assert dumped["page_data"]["entity_description"] == "Agent workspace"
    assert dumped["page_data"]["navigation_catalog"] == [_navigation_entry()]
    assert dumped["page_data"]["navigation_context"]["breadcrumb"] == ["AI", "Agents"]


def test_page_context_normalize_returns_none_for_invalid_payload() -> None:
    assert PageContext.normalize({"page_title": "missing page_key"}) is None


def test_page_context_normalize_variables_prefers_explicit_page_context() -> None:
    normalized = PageContext.normalize_variables(
        {"foo": "bar"},
        {
            "page_key": "tenant.ai.agents",
            "ui_epoch": 5,
            "page_data": {
                "navigation_catalog": [_navigation_entry()],
            },
            "suggested_tools": {"primary": ["ui_get_snapshot"]},
        },
    )
    assert normalized == {
        "foo": "bar",
        "page_context": {
            "page_key": "tenant.ai.agents",
            "ui_epoch": 5,
            "page_data": {
                "navigation_catalog": [_navigation_entry()],
            },
            "surface_stack": [],
            "suggested_tools": {"primary": ["ui_get_snapshot"], "secondary": []},
        },
    }


def test_agent_chat_request_accepts_thin_page_context_shape() -> None:
    request = AgentChatRequest.model_validate(
        {
            "message": "help me",
            "page_context": {
                "locale": "zh-CN",
                "page_key": "tenant.ai.agents",
                "page_session_id": "sess-88",
                "page_data": {
                    "navigation_catalog": [_navigation_entry()],
                    "navigation_context": {
                        "breadcrumb": ["AI", "Agents"],
                        "endpoint": "/ai/agents",
                        "page_key": "admin.ai.agents",
                        "path": "/admin/ai/agents",
                    },
                },
                "ui_epoch": 2,
            },
        }
    )
    assert request.page_context is not None
    assert request.page_context.locale == "zh-CN"
    assert request.page_context.page_key == "tenant.ai.agents"
    assert request.page_context.page_session_id == "sess-88"
    assert request.page_context.page_data is not None
    assert request.page_context.page_data.navigation_catalog[0].page_key == "admin.ai.agents"


def test_agent_route_request_accepts_thin_page_context_shape() -> None:
    request = AgentRouteRequest.model_validate(
        {
            "message": "route me",
            "page_context": {
                "page_key": "admin.ai.agents",
                "ui_epoch": 8,
                "suggested_tools": {"primary": ["ui_get_snapshot", "ui_click"]},
            },
        }
    )
    assert request.page_context is not None
    assert request.page_context.page_key == "admin.ai.agents"
    assert request.page_context.ui_epoch == 8


def test_agent_chat_request_filters_invalid_navigation_catalog_entries() -> None:
    request = AgentChatRequest.model_validate(
        {
            "message": "help me",
            "page_context": {
                "page_key": "tenant.ai.agents",
                "page_data": {
                    "navigation_catalog": [
                        _navigation_entry(),
                        {
                            "page_key": "admin.ai.broken",
                            "title": "Broken Entry",
                        },
                        {
                            "page_key": "   ",
                            "path": "   ",
                            "title": "   ",
                        },
                    ],
                },
            },
        }
    )

    assert request.page_context is not None
    assert request.page_context.page_data is not None
    assert request.page_context.page_data.navigation_catalog == [
        NavigationCatalogEntry.model_validate(_navigation_entry())
    ]


def test_navigation_catalog_entry_rejects_blank_required_values() -> None:
    with pytest.raises(ValidationError):
        NavigationCatalogEntry.model_validate(
            {
                "title": "   ",
                "path": "   ",
                "page_key": "   ",
            }
        )


def test_page_context_rejects_blank_page_key() -> None:
    with pytest.raises(ValidationError):
        PageContext.model_validate({"page_key": "   "})


def test_agent_chat_request_rejects_unknown_page_data_fields() -> None:
    with pytest.raises(ValidationError):
        AgentChatRequest.model_validate(
            {
                "message": "help me",
                "page_context": {
                    "page_key": "tenant.ai.agents",
                    "page_data": {
                        "document_body_text": "x" * 32,
                    },
                },
            }
        )


@pytest.mark.asyncio
async def test_validate_page_context_size_accepts_payload_within_runtime_limit() -> None:
    from app.services.ai.page_context_limits import validate_page_context_size

    page_context = {
        "page_key": "tenant.ai.agents",
        "ui_epoch": 1,
        "suggested_tools": {"primary": ["ui_get_snapshot", "ui_click"]},
    }

    with patch(
        "app.services.ai.page_context_limits.get_ui_runtime_payload_max_bytes",
        new=AsyncMock(return_value=1024),
    ):
        await validate_page_context_size(MagicMock(), page_context)


@pytest.mark.asyncio
async def test_validate_page_context_size_rejects_payload_over_runtime_limit() -> None:
    from app.services.ai.page_context_limits import validate_page_context_size

    page_context = {
        "page_key": "tenant.ai.agents",
        "page_title": "Agent Management",
        "surface_stack": [
            {"surface_id": "page-root", "kind": "page", "title": "Agents"},
            {"surface_id": "drawer-create", "kind": "drawer", "title": "Create Agent"},
        ],
        "active_form_summary": {
            "form_session_id": "form-1",
            "entity_name": "Agent",
            "mode": "create",
            "stage": "ready_to_submit",
            "remaining_required_fields": [],
            "can_submit": True,
            "submit_policy": "confirm",
        },
        "suggested_tools": {
            "primary": ["ui_get_snapshot", "ui_fill_form", "ui_submit_form"],
            "secondary": ["ui_get_form_state"],
        },
    }

    with patch(
        "app.services.ai.page_context_limits.get_ui_runtime_payload_max_bytes",
        new=AsyncMock(return_value=32),
    ), pytest.raises(ValidationException) as exc_info:
        await validate_page_context_size(MagicMock(), page_context)

    assert "32" in str(exc_info.value)


def test_page_context_available_ui_tools_infers_base_tools_from_thin_context() -> None:
    tools = page_context_available_ui_tools(
        {
            "page_key": "tenant.ai.agents",
            "ui_epoch": 9,
        }
    )
    assert "ui_get_snapshot" in tools
    assert "ui_read_region" in tools
    assert "ui_read_table" in tools
    assert "ui_click" in tools


def test_page_context_available_ui_tools_infers_form_tools_when_active_form_exists() -> None:
    tools = page_context_available_ui_tools(
        {
            "page_key": "tenant.ai.agents",
            "active_form_session_id": "form-1",
            "active_form_summary": {
                "form_session_id": "form-1",
                "stage": "ready_to_submit",
                "can_submit": True,
            },
        }
    )
    assert "ui_get_form_state" in tools
    assert "ui_fill_form" in tools
    assert "ui_submit_form" in tools


def test_page_context_available_ui_tools_ignores_suggested_submit_hint_without_form() -> (
    None
):
    tools = page_context_available_ui_tools(
        {
            "page_key": "tenant.ai.agents",
            "ui_epoch": 9,
            "suggested_tools": {
                "primary": ["ui_submit_form", "ui_fill_form"],
                "secondary": ["ui_get_form_state"],
            },
        }
    )

    assert "ui_get_snapshot" in tools
    assert "ui_click" in tools
    assert "ui_fill_form" not in tools
    assert "ui_get_form_state" not in tools
    assert "ui_submit_form" not in tools


def test_page_context_available_ui_tools_filters_available_names_by_runtime_state() -> None:
    tools = page_context_available_ui_tools(
        {
            "page_key": "tenant.ai.agents",
            "ui_epoch": 9,
            "suggested_tools": {
                "primary": ["ui_submit_form", "ui_fill_form"],
            },
        },
        available_tool_names={"ui_get_snapshot", "ui_click", "ui_submit_form"},
    )

    assert tools == ["ui_get_snapshot", "ui_click"]


@pytest.mark.asyncio
async def test_ui_snapshot_executor_requires_page_session_id() -> None:
    executor = UISnapshotExecutor()
    result = await executor.execute(
        ToolDefinition(name="ui_get_snapshot", description="Get UI snapshot"),
        "call-1",
        {"mode": "compact"},
        ExecutionContext(tenant_id=1, agent_id=2, variables={}),
    )

    assert result.success is False
    assert result.error_type == "session_not_found"


@pytest.mark.asyncio
async def test_ui_snapshot_executor_uses_cached_snapshot_when_bridge_unavailable() -> None:
    executor = UISnapshotExecutor()
    cached_snapshot = {
        "ui_epoch": 2,
        "nodes": [
            {
                "id": "node-1",
                "kind": "button",
                "locator": "save-button",
                "text": "Save",
                "interactable": True,
            }
        ],
        "surface_stack": [{"surface_id": "root", "kind": "page", "title": "Agents"}],
        "suggested_tools": {"primary": ["ui_get_snapshot", "ui_read_region"]},
    }
    context = ExecutionContext(
        tenant_id=1,
        agent_id=2,
        page_session_id="sess-1",
        variables={"ui_snapshot": cached_snapshot},
    )

    with patch(
        "app.ai.tools.executors.ui_snapshot_executor._request_ui_snapshot",
        new=AsyncMock(return_value=None),
    ):
        result = await executor.execute(
            ToolDefinition(name="ui_get_snapshot", description="Get UI snapshot"),
            "call-2",
            {"mode": "compact"},
            context,
        )

    assert result.success is True
    payload = json.loads(result.output)
    assert payload["ui_epoch"] == 2
    assert payload["nodes"][0]["kind"] == "button"
    assert payload["interactables_count"] >= 1


@pytest.mark.asyncio
async def test_ui_snapshot_executor_prefers_bridge_payload_when_available() -> None:
    executor = UISnapshotExecutor()
    context = ExecutionContext(
        tenant_id=1,
        agent_id=2,
        page_session_id="sess-99",
        variables={},
    )
    bridge_payload = {
        "success": True,
        "snapshot": {
            "ui_epoch": 6,
            "nodes": [
                {
                    "node_id": "node-a",
                    "kind": "input",
                    "locator": "name",
                    "summary": "Agent Name",
                    "interactable": True,
                }
            ],
            "surface_stack": [{"surface_id": "root", "kind": "page"}],
            "suggested_tools": {"primary": ["ui_get_snapshot"]},
        },
    }

    with patch(
        "app.ai.tools.executors.ui_snapshot_executor._request_ui_snapshot",
        new=AsyncMock(return_value=bridge_payload),
    ):
        result = await executor.execute(
            ToolDefinition(name="ui_get_snapshot", description="Get UI snapshot"),
            "call-3",
            {"mode": "full"},
            context,
        )

    assert result.success is True
    payload = json.loads(result.output)
    assert payload["ui_epoch"] == 6
    assert payload["mode"] == "full"
    assert payload["nodes"][0]["node_id"] == "node-a"
