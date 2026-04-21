from __future__ import annotations

import asyncio

import pytest
import socketio

from app.core.i18n import set_locale
from app.sio.page_session import (
    PageSessionMixin,
    get_active_session_id,
    invoke_ui_action,
    request_ui_list_interactables,
    request_ui_read_region,
    request_ui_read_table,
    request_ui_snapshot,
)


@pytest.fixture(autouse=True)
def _set_test_locale() -> None:
    set_locale("en")


class DummyPageSessionNamespace(PageSessionMixin, socketio.AsyncNamespace):
    def __init__(self) -> None:
        super().__init__("/tenant")
        self.emitted_events: list[tuple[str, dict[str, object], str | None]] = []
        self.joined_rooms: list[tuple[str, str]] = []

    async def enter_room(self, sid: str, room: str) -> None:  # type: ignore[override]
        self.joined_rooms.append((sid, room))

    async def emit(  # type: ignore[override]
        self,
        event: str,
        data: dict[str, object],
        to: str | None = None,
        **_: object,
    ) -> None:
        self.emitted_events.append((event, data, to))

    async def get_socket_session_with_fallback(
        self,
        sid: str,
    ) -> dict[str, object] | None:
        _ = sid
        return None


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


@pytest.mark.asyncio
async def test_invoke_ui_action_drops_page_key_from_live_action_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    async def _fake_dispatch(**kwargs: object) -> dict[str, object]:
        captured.update(kwargs)
        return {"success": True, "message": "ok"}

    monkeypatch.setattr(
        "app.sio.page_session._dispatch_page_session_request",
        _fake_dispatch,
    )

    result = await invoke_ui_action(
        page_session_id="session-1",
        action_type="ui_click",
        payload={
            "page_key": "legacy.page",
            "target_locator": "testid:create",
        },
    )

    assert result["success"] is True
    assert captured["event_name"] == "ui_action_invoke"
    assert captured["page_session_id"] == "session-1"
    payload = captured["payload"]
    assert isinstance(payload, dict)
    assert payload["action_type"] == "ui_click"
    assert payload["target_locator"] == "testid:create"
    assert "page_key" not in payload


@pytest.mark.asyncio
async def test_page_session_join_ack_uses_page_session_id_only() -> None:
    namespace = DummyPageSessionNamespace()

    await namespace.on_page_session_join(
        "sid-1",
        {
            "page_key": "legacy.page",
            "page_session_id": "page-session-1",
        },
    )

    assert namespace.joined_rooms == [("sid-1", "page_session:page-session-1")]
    assert len(namespace.emitted_events) == 1
    event_name, payload, sid = namespace.emitted_events[0]
    assert event_name == "page_session_joined"
    assert sid == "sid-1"
    assert payload["page_session_id"] == "page-session-1"
    assert "page_key" not in payload
    assert isinstance(payload.get("trace_id"), str)


def test_get_active_session_id_no_longer_recovers_from_page_key_fallback() -> None:
    assert get_active_session_id(7, "tenant.dashboard") is None
    from app.sio import page_session as page_session_module

    assert not hasattr(page_session_module, "_active_sessions")
    assert not hasattr(page_session_module, "_sid_active_sessions")
