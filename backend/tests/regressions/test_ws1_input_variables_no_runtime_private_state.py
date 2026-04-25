"""
Test type: behavioral
Regression for: BUG-2026-04-26-003
Original symptom: page session identity and UI executor fallback cache could
still round-trip through input_variables, so page-aware tools kept working off
the generic variable bag instead of explicit/private carriers.
Scope: ui snapshot/read fallback behavior for WS1-PKG-01 envelope ownership.
Real dependencies: UISnapshotExecutor and UIReadExecutor run their real
normalization and fallback logic.
Mocked dependencies: page-session bridge requests are mocked to return no live
payload so the tests exercise the local owner fallback rules without using
self-fulfilling success stubs.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from app.ai.tools.executors.ui_read_executor import UIReadExecutor
from app.ai.tools.executors.ui_snapshot_executor import UISnapshotExecutor
from app.ai.tools.types import ExecutionContext, ToolDefinition


def _snapshot_cache_payload() -> dict[str, Any]:
    return {
        "active_surface_id": "surface:page:1",
        "nodes": [
            {
                "node_id": "save",
                "kind": "button",
                "locator": "text:Save",
                "text": "Save",
                "interactable": True,
            }
        ],
        "surface_stack": [{"surface_id": "surface:page:1", "kind": "page"}],
        "ui_epoch": 9,
    }


def _region_cache_payload() -> dict[str, Any]:
    return {
        "surface_id": "drawer-1",
        "title": "Details",
        "text": "Agent A",
        "items": [{"label": "Name", "value": "Agent A"}],
        "truncated": False,
    }


@pytest.mark.asyncio
async def test_ui_snapshot_executor_rejects_variable_bag_page_transport(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _missing_snapshot(**_: object) -> None:
        return None

    monkeypatch.setattr(
        "app.ai.tools.executors.ui_snapshot_executor._request_ui_snapshot",
        _missing_snapshot,
    )

    executor = UISnapshotExecutor()
    definition = ToolDefinition(name="ui_get_snapshot", description="snapshot")
    context = ExecutionContext(
        tenant_id=1,
        agent_id=1,
        variables={
            "page_context": {
                "page_key": "admin.ai.agents",
                "page_session_id": "bag-session",
            },
            "ui_snapshot": _snapshot_cache_payload(),
        },
    )

    result = await executor.execute(
        definition=definition,
        tool_call_id="tc-ui-snapshot-bag-private-state",
        arguments={"mode": "compact"},
        context=context,
    )

    assert result.success is False
    assert result.error_type == "session_not_found"


@pytest.mark.asyncio
async def test_ui_snapshot_executor_uses_explicit_page_context_and_private_cache(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _missing_snapshot(**_: object) -> None:
        return None

    monkeypatch.setattr(
        "app.ai.tools.executors.ui_snapshot_executor._request_ui_snapshot",
        _missing_snapshot,
    )

    executor = UISnapshotExecutor()
    definition = ToolDefinition(name="ui_get_snapshot", description="snapshot")
    context = ExecutionContext(
        tenant_id=1,
        agent_id=1,
    )
    context.page_context = {
        "page_key": "admin.ai.agents",
        "page_session_id": "private-page-context-session",
    }
    context.executor_cache = {
        "ui_snapshot": _snapshot_cache_payload(),
    }

    result = await executor.execute(
        definition=definition,
        tool_call_id="tc-ui-snapshot-private-carriers",
        arguments={"mode": "compact"},
        context=context,
    )

    assert result.success is True
    payload = json.loads(result.output)
    assert payload["active_surface_id"] == "surface:page:1"
    assert payload["surface_stack"] == [
        {"surface_id": "surface:page:1", "kind": "page", "title": None}
    ]
    assert payload["nodes"][0]["node_id"] == "save"
    assert payload["nodes"][0]["interactable"] is True


@pytest.mark.asyncio
async def test_ui_read_executor_rejects_variable_bag_read_cache(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _missing_read(**_: object) -> None:
        return None

    monkeypatch.setattr(
        "app.ai.tools.executors.ui_read_executor._request_ui_read",
        _missing_read,
    )

    executor = UIReadExecutor()
    definition = ToolDefinition(name="ui_read_region", description="read region")
    context = ExecutionContext(
        tenant_id=1,
        agent_id=1,
        page_session_id="private-session",
        variables={
            "ui_regions": {
                "details-panel": _region_cache_payload(),
            }
        },
    )

    result = await executor.execute(
        definition=definition,
        tool_call_id="tc-ui-read-region-bag-private-cache",
        arguments={"region_locator": "details-panel"},
        context=context,
    )

    assert result.success is False
    assert result.error_type == "read_unavailable"


@pytest.mark.asyncio
async def test_ui_read_executor_uses_private_executor_cache(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _missing_read(**_: object) -> None:
        return None

    monkeypatch.setattr(
        "app.ai.tools.executors.ui_read_executor._request_ui_read",
        _missing_read,
    )

    executor = UIReadExecutor()
    definition = ToolDefinition(name="ui_read_region", description="read region")
    context = ExecutionContext(
        tenant_id=1,
        agent_id=1,
        page_session_id="private-session",
    )
    context.executor_cache = {
        "ui_regions": {
            "details-panel": _region_cache_payload(),
        }
    }

    result = await executor.execute(
        definition=definition,
        tool_call_id="tc-ui-read-region-private-cache",
        arguments={"region_locator": "details-panel"},
        context=context,
    )

    assert result.success is True
    payload = json.loads(result.output)
    assert payload["region_locator"] == "details-panel"
    assert payload["title"] == "Details"
    assert payload["items"] == [{"label": "Name", "value": "Agent A"}]
