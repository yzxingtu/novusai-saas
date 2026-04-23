from __future__ import annotations

import json

import pytest

from app.ai.tools.executors.ui_snapshot_executor import UISnapshotExecutor
from app.ai.tools.types import ExecutionContext, ToolDefinition
from app.schemas.ai.agent_chat import PAGE_CONTEXT_KEY, PageContext


@pytest.mark.asyncio
async def test_ui_snapshot_executor_compact_normalizes_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _fake_request_ui_snapshot(**_: object) -> dict[str, object]:
        return {
            "success": True,
            "snapshot": {
                "active_form_session_id": "form-1",
                "active_form_summary": {
                    "can_submit": False,
                    "entity_name": "Agent",
                    "form_session_id": "form-1",
                    "mode": "edit",
                    "remaining_required_fields": ["name", "model", "name"],
                    "stage": "ready",
                    "submit_policy": "confirm",
                },
                "active_surface_id": "drawer-1",
                "nodes": [
                    {
                        "content": "x" * 600,
                        "interactable": True,
                        "kind": "button",
                        "locator": "btn-save",
                        "node_id": "btn-save",
                        "text": "Save",
                    },
                    {
                        "content": "y" * 600,
                        "kind": "text",
                        "locator": "summary-1",
                        "node_id": "summary-1",
                        "text": "Some summary",
                    },
                ],
                "surface_stack": [
                    {"kind": "page", "surface_id": "page-1", "title": "Agents"},
                    {"kind": "drawer", "surface_id": "drawer-1", "title": "Edit"},
                ],
                "ui_epoch": 9,
            },
        }

    monkeypatch.setattr(
        "app.ai.tools.executors.ui_snapshot_executor._request_ui_snapshot",
        _fake_request_ui_snapshot,
    )

    executor = UISnapshotExecutor()
    context = ExecutionContext(
        tenant_id=1,
        agent_id=1,
        page_session_id="session-1",
        variables={PAGE_CONTEXT_KEY: {"page_key": "admin.ai.agents"}},
    )
    definition = ToolDefinition(name="ui_get_snapshot", description="snapshot")

    result = await executor.execute(
        definition=definition,
        tool_call_id="tc-ui-snapshot",
        arguments={"mode": "compact"},
        context=context,
    )

    assert result.success is True
    payload = json.loads(result.output)
    assert payload["mode"] == "compact"
    assert payload["ui_epoch"] == 9
    assert payload["active_form_session_id"] == "form-1"
    assert payload["surface_stack"][0]["surface_id"] == "page-1"
    assert payload["interactables_count"] >= 1
    assert payload["size_bytes"] <= 10 * 1024
    assert "suggested_tools" not in payload
    assert all(
        "content" not in node or node["content"] is None for node in payload["nodes"]
    )


@pytest.mark.asyncio
async def test_ui_snapshot_executor_reports_bridge_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _fake_request_ui_snapshot(**_: object) -> dict[str, object]:
        return {
            "success": False,
            "error_type": "snapshot_timeout",
            "error": "timeout",
        }

    monkeypatch.setattr(
        "app.ai.tools.executors.ui_snapshot_executor._request_ui_snapshot",
        _fake_request_ui_snapshot,
    )

    executor = UISnapshotExecutor()
    context = ExecutionContext(
        tenant_id=1,
        agent_id=1,
        page_session_id="session-1",
    )
    definition = ToolDefinition(name="ui_get_snapshot", description="snapshot")

    result = await executor.execute(
        definition=definition,
        tool_call_id="tc-ui-snapshot-failed",
        arguments={"mode": "full"},
        context=context,
    )

    assert result.success is False
    assert result.error_type == "snapshot_timeout"
    assert "timeout" in result.error


@pytest.mark.asyncio
async def test_ui_snapshot_executor_requires_page_session_id() -> None:
    executor = UISnapshotExecutor()
    definition = ToolDefinition(name="ui_get_snapshot", description="snapshot")
    context = ExecutionContext(
        tenant_id=1,
        agent_id=1,
        variables={PAGE_CONTEXT_KEY: {"page_key": "admin.ai.agents"}},
    )

    result = await executor.execute(
        definition=definition,
        tool_call_id="tc-ui-snapshot-no-session",
        arguments={"mode": "compact"},
        context=context,
    )

    assert result.success is False
    assert result.error_type == "session_not_found"


@pytest.mark.asyncio
async def test_ui_snapshot_executor_validate_mode() -> None:
    executor = UISnapshotExecutor()
    definition = ToolDefinition(name="ui_get_snapshot", description="snapshot")

    assert await executor.validate(definition, {"mode": "compact"}) is True
    assert await executor.validate(definition, {"mode": "full"}) is True
    assert await executor.validate(definition, {"mode": "invalid"}) is False
    assert (
        await executor.validate(definition, {"mode": "compact", "surface_id": 1})
        is False
    )


def test_page_context_normalize_keeps_thin_schema_only() -> None:
    normalized = PageContext.normalize(
        {
            "page_key": "  admin.ai.agents  ",
            "page_title": " Agent List ",
            "page_session_id": " session-1 ",
            "ui_epoch": 5,
            "active_surface_id": "drawer-1",
            "surface_stack": [
                {"surface_id": "page-1", "kind": "page", "title": "Agents"},
                {"surface_id": "page-1", "kind": "page", "title": "Duplicated"},
                {"surface_id": "drawer-1", "kind": "drawer", "title": "Edit"},
            ],
            "active_form_summary": {
                "form_session_id": "form-1",
                "entity_name": "Agent",
                "remaining_required_fields": ["name", "name", "model"],
            },
            "unknown_payload": {"any": "value"},
            "unknown_list": [{"item": "value"}],
        }
    )

    assert normalized is not None
    assert set(normalized) == {
        "page_key",
        "page_title",
        "page_session_id",
        "ui_epoch",
        "active_surface_id",
        "active_form_session_id",
        "surface_stack",
        "active_form_summary",
    }
    assert normalized["page_key"] == "admin.ai.agents"
    assert normalized["page_title"] == "Agent List"
    assert normalized["surface_stack"] == [
        {"surface_id": "page-1", "kind": "page", "title": "Agents"},
        {"surface_id": "drawer-1", "kind": "drawer", "title": "Edit"},
    ]
    assert normalized["active_form_summary"]["remaining_required_fields"] == [
        "name",
        "model",
    ]
    assert "unknown_payload" not in normalized
    assert "unknown_list" not in normalized


def test_page_context_normalize_variables_drops_invalid_context() -> None:
    normalized_variables = PageContext.normalize_variables(
        variables={
            "x": 1,
            PAGE_CONTEXT_KEY: {"page_title": "missing key"},
        }
    )
    assert normalized_variables == {"x": 1}
