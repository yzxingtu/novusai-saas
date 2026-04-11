from __future__ import annotations

import asyncio

import pytest

from app.core.i18n import set_locale
from app.sio.page_session import (
    request_ui_list_interactables,
    request_ui_read_region,
    request_ui_read_table,
    request_ui_snapshot,
)


@pytest.fixture(autouse=True)
def _set_test_locale() -> None:
    set_locale("en")


@pytest.mark.asyncio
async def test_request_ui_snapshot_timeout_is_localized(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _fake_dispatch(**_: object) -> dict[str, object]:
        raise asyncio.TimeoutError

    monkeypatch.setattr(
        "app.sio.page_session._dispatch_page_session_request",
        _fake_dispatch,
    )

    result = await request_ui_snapshot(page_session_id="session-1")

    assert result["success"] is False
    assert result["error_type"] == "timeout"
    assert result["message"] == "UI snapshot request timed out."


@pytest.mark.asyncio
async def test_request_ui_read_region_failure_is_localized(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _fake_dispatch(**_: object) -> dict[str, object]:
        raise RuntimeError("boom")

    monkeypatch.setattr(
        "app.sio.page_session._dispatch_page_session_request",
        _fake_dispatch,
    )

    result = await request_ui_read_region(
        page_session_id="session-1",
        region_locator="profile-panel",
    )

    assert result["success"] is False
    assert result["error_type"] == "internal_error"
    assert result["message"] == "UI region read request failed."


@pytest.mark.asyncio
async def test_request_ui_read_table_timeout_is_localized(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _fake_dispatch(**_: object) -> dict[str, object]:
        raise asyncio.TimeoutError

    monkeypatch.setattr(
        "app.sio.page_session._dispatch_page_session_request",
        _fake_dispatch,
    )

    result = await request_ui_read_table(
        page_session_id="session-1",
        table_locator="table-agents",
    )

    assert result["success"] is False
    assert result["error_type"] == "timeout"
    assert result["message"] == "UI table read request timed out."


@pytest.mark.asyncio
async def test_request_ui_list_interactables_failure_is_localized(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _fake_dispatch(**_: object) -> dict[str, object]:
        raise RuntimeError("boom")

    monkeypatch.setattr(
        "app.sio.page_session._dispatch_page_session_request",
        _fake_dispatch,
    )

    result = await request_ui_list_interactables(page_session_id="session-1")

    assert result["success"] is False
    assert result["error_type"] == "internal_error"
    assert result["message"] == "Interactables request failed."
