from unittest.mock import AsyncMock

import pytest

from app.ai.tools.executors.ui_action_executor import UIActionExecutor
from app.ai.tools.types import ExecutionContext, ToolDefinition


@pytest.fixture()
def executor() -> UIActionExecutor:
    return UIActionExecutor()


@pytest.fixture()
def click_definition() -> ToolDefinition:
    return ToolDefinition(name="ui_click", description="Click ui element")


@pytest.fixture()
def open_surface_definition() -> ToolDefinition:
    return ToolDefinition(name="ui_open_surface", description="Open ui surface")


@pytest.mark.asyncio
async def test_ui_click_success_returns_diff(
    executor: UIActionExecutor,
    click_definition: ToolDefinition,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.sio import page_session as page_session_module

    invoke_mock = AsyncMock(
        return_value={
            "success": True,
            "message": "Clicked create button",
            "diff": {
                "changed": True,
                "ui_epoch": 3,
                "surfaces_added": [{"kind": "drawer", "surface_id": "drawer:create"}],
                "surfaces_removed": [],
                "page_key_changed": False,
                "active_surface_id": "drawer:create",
            },
        }
    )
    monkeypatch.setattr(page_session_module, "invoke_ui_action", invoke_mock, raising=False)

    context = ExecutionContext(
        tenant_id=1,
        agent_id=2,
        user_role="tenant_admin",
        page_session_id="ps-click",
    )
    result = await executor.execute(
        click_definition,
        "call-ui-click",
        {"target_locator": "testid:create"},
        context,
    )

    assert result.success is True
    assert "ui_click" in result.output
    assert "ui_epoch" in result.output
    invoke_mock.assert_awaited_once()
    _, kwargs = invoke_mock.await_args
    assert kwargs["page_session_id"] == "ps-click"
    assert kwargs["action_type"] == "ui_click"
    assert kwargs["payload"]["target_locator"] == "testid:create"


@pytest.mark.asyncio
async def test_ui_click_missing_locator_returns_invalid_input(
    executor: UIActionExecutor,
    click_definition: ToolDefinition,
) -> None:
    context = ExecutionContext(
        tenant_id=1,
        agent_id=2,
        page_session_id="ps-click",
    )

    result = await executor.execute(
        click_definition,
        "call-ui-click-invalid",
        {},
        context,
    )

    assert result.success is False
    assert result.error_type == "invalid_input"
    assert "target_locator" in result.error


@pytest.mark.asyncio
async def test_ui_action_without_session_returns_session_not_found(
    executor: UIActionExecutor,
    click_definition: ToolDefinition,
) -> None:
    context = ExecutionContext(tenant_id=1, agent_id=2)
    result = await executor.execute(
        click_definition,
        "call-ui-click-no-session",
        {"target_locator": "testid:create"},
        context,
    )
    assert result.success is False
    assert result.error_type == "session_not_found"


@pytest.mark.asyncio
async def test_ui_open_surface_failure_propagates_error_type(
    executor: UIActionExecutor,
    open_surface_definition: ToolDefinition,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.sio import page_session as page_session_module

    invoke_mock = AsyncMock(
        return_value={
            "success": False,
            "message": "No new modal found",
            "error_type": "surface_not_opened",
            "diff": {
                "changed": False,
                "ui_epoch": 2,
                "surfaces_added": [],
                "surfaces_removed": [],
                "page_key_changed": False,
                "active_surface_id": "page:admin.ai.agents",
            },
        }
    )
    monkeypatch.setattr(page_session_module, "invoke_ui_action", invoke_mock, raising=False)

    context = ExecutionContext(
        tenant_id=1,
        agent_id=2,
        user_role="platform_admin",
        page_session_id="ps-open",
    )
    result = await executor.execute(
        open_surface_definition,
        "call-ui-open-failed",
        {"target_locator": "text:Open modal"},
        context,
    )

    assert result.success is False
    assert result.error_type == "surface_not_opened"
    assert "No new modal found" in result.error


@pytest.mark.asyncio
async def test_ui_click_failure_appends_error_detail_to_summary_payload(
    executor: UIActionExecutor,
    click_definition: ToolDefinition,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.sio import page_session as page_session_module

    invoke_mock = AsyncMock(
        return_value={
            "success": False,
            "message": "UI action execution failed.",
            "error": "Target not found",
            "error_detail": 'Unable to locate element "添加供应商".',
            "error_type": "not_found",
            "diff": {
                "changed": False,
                "ui_epoch": 2,
                "surfaces_added": [],
                "surfaces_removed": [],
                "page_key_changed": False,
                "active_surface_id": "page:admin.ai.agents",
            },
        }
    )
    monkeypatch.setattr(page_session_module, "invoke_ui_action", invoke_mock, raising=False)

    context = ExecutionContext(
        tenant_id=1,
        agent_id=2,
        user_role="tenant_admin",
        page_session_id="ps-click-detail",
    )
    result = await executor.execute(
        click_definition,
        "call-ui-click-detail",
        {"target_locator": "text:添加供应商"},
        context,
    )

    assert result.success is False
    assert result.error_type == "not_found"
    assert result.error == 'Target not found (Unable to locate element "添加供应商".)'
    assert result.summary_payload == {
        "diff": {
            "changed": False,
            "ui_epoch": 2,
            "surfaces_added": [],
            "surfaces_removed": [],
            "page_key_changed": False,
            "active_surface_id": "page:admin.ai.agents",
        },
        "error_detail": 'Unable to locate element "添加供应商".',
    }
