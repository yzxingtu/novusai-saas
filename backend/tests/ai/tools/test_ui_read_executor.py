from __future__ import annotations

import json

import pytest

from app.ai.tools.executors.ui_read_executor import UIReadExecutor
from app.ai.tools.types import ExecutionContext, ToolDefinition
from app.schemas.ai.agent_chat import PAGE_CONTEXT_KEY


@pytest.mark.asyncio
async def test_ui_read_region_normalizes_shape(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _fake_request_ui_read(**_: object) -> dict[str, object]:
        return {
            "success": True,
            "data": {
                "items": [
                    {"label": "Name", "value": "Agent A"},
                    {"label": "Model", "value": "gpt"},
                ],
                "surface_id": "drawer-1",
                "text": "x" * 4500,
                "title": "Details",
            },
        }

    monkeypatch.setattr(
        "app.ai.tools.executors.ui_read_executor._request_ui_read",
        _fake_request_ui_read,
    )

    executor = UIReadExecutor()
    context = ExecutionContext(
        tenant_id=1,
        agent_id=1,
        page_session_id="session-1",
        variables={PAGE_CONTEXT_KEY: {"page_key": "admin.ai.agents"}},
    )
    definition = ToolDefinition(name="ui_read_region", description="read region")

    result = await executor.execute(
        definition=definition,
        tool_call_id="tc-ui-read-region",
        arguments={"region_locator": "profile-panel"},
        context=context,
    )

    assert result.success is True
    payload = json.loads(result.output)
    assert payload["region_locator"] == "profile-panel"
    assert payload["surface_id"] == "drawer-1"
    assert payload["title"] == "Details"
    assert payload["text"].endswith("...")
    assert len(payload["items"]) == 2
    assert payload["size_bytes"] > 0


@pytest.mark.asyncio
async def test_ui_read_table_normalizes_pagination(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _fake_request_ui_read(**_: object) -> dict[str, object]:
        rows = [{"id": index, "name": f"row-{index}"} for index in range(150)]
        return {
            "success": True,
            "data": {
                "columns": ["id", "name"],
                "rows": rows,
                "total_rows": 150,
            },
        }

    monkeypatch.setattr(
        "app.ai.tools.executors.ui_read_executor._request_ui_read",
        _fake_request_ui_read,
    )

    executor = UIReadExecutor()
    context = ExecutionContext(
        tenant_id=1,
        agent_id=1,
        page_session_id="session-1",
    )
    definition = ToolDefinition(name="ui_read_table", description="read table")

    result = await executor.execute(
        definition=definition,
        tool_call_id="tc-ui-read-table",
        arguments={"page": 2, "page_size": 200, "table_locator": "table-agents"},
        context=context,
    )

    assert result.success is True
    payload = json.loads(result.output)
    assert payload["table_locator"] == "table-agents"
    assert payload["page"] == 2
    assert payload["page_size"] == 100
    assert len(payload["rows"]) == 100
    assert payload["has_more"] is False


@pytest.mark.asyncio
async def test_ui_list_interactables_filters_surface(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _fake_request_ui_read(**_: object) -> dict[str, object]:
        return {
            "success": True,
            "items": [
                {
                    "enabled": True,
                    "kind": "button",
                    "label": "Save",
                    "locator": "btn-save",
                    "surface_id": "drawer-1",
                },
                {
                    "enabled": True,
                    "kind": "button",
                    "label": "Delete",
                    "locator": "btn-delete",
                    "surface_id": "drawer-2",
                },
            ],
        }

    monkeypatch.setattr(
        "app.ai.tools.executors.ui_read_executor._request_ui_read",
        _fake_request_ui_read,
    )

    executor = UIReadExecutor()
    context = ExecutionContext(
        tenant_id=1,
        agent_id=1,
        page_session_id="session-1",
    )
    definition = ToolDefinition(
        name="ui_list_interactables",
        description="list interactables",
    )

    result = await executor.execute(
        definition=definition,
        tool_call_id="tc-ui-list-interactables",
        arguments={"surface_id": "drawer-1"},
        context=context,
    )

    assert result.success is True
    payload = json.loads(result.output)
    assert payload["surface_id"] == "drawer-1"
    assert payload["count"] == 1
    assert payload["items"][0]["locator"] == "btn-save"


@pytest.mark.asyncio
async def test_ui_read_executor_reports_bridge_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _fake_request_ui_read(**_: object) -> dict[str, object]:
        return {
            "success": False,
            "error_type": "target_not_found",
            "error": "region missing",
        }

    monkeypatch.setattr(
        "app.ai.tools.executors.ui_read_executor._request_ui_read",
        _fake_request_ui_read,
    )

    executor = UIReadExecutor()
    definition = ToolDefinition(name="ui_read_region", description="read region")
    context = ExecutionContext(tenant_id=1, agent_id=1, page_session_id="session-1")

    result = await executor.execute(
        definition=definition,
        tool_call_id="tc-ui-read-error",
        arguments={"region_locator": "missing-region"},
        context=context,
    )

    assert result.success is False
    assert result.error_type == "target_not_found"


@pytest.mark.asyncio
async def test_ui_read_executor_validate_inputs() -> None:
    executor = UIReadExecutor()
    region_def = ToolDefinition(name="ui_read_region", description="read region")
    table_def = ToolDefinition(name="ui_read_table", description="read table")
    list_def = ToolDefinition(
        name="ui_list_interactables",
        description="list interactables",
    )

    assert await executor.validate(region_def, {"region_locator": "summary"}) is True
    assert await executor.validate(region_def, {"region_locator": 1}) is False
    assert (
        await executor.validate(table_def, {"table_locator": "table", "page": 1})
        is True
    )
    assert (
        await executor.validate(table_def, {"table_locator": "table", "page": "1"})
        is False
    )
    assert await executor.validate(list_def, {"surface_id": "drawer-1"}) is True
    assert await executor.validate(list_def, {"surface_id": 1}) is False
