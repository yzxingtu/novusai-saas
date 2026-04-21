from __future__ import annotations

import pytest

from app.ai.tools.page_runtime.live_bridge import SocketIOPageRuntimeBridge


@pytest.mark.asyncio
async def test_live_bridge_reads_ui_snapshot_with_canonical_contract(
    monkeypatch,
) -> None:
    async def _request_ui_snapshot(**kwargs):
        assert kwargs["mode"] == "full"
        assert kwargs["surface_id"] == "drawer:agent"
        assert kwargs["page_session_id"] == "ps-1"
        return {
            "success": True,
            "snapshot": {
                "ui_epoch": 7,
                "active_surface_id": "drawer:agent",
                "surface_stack": [
                    {
                        "surface_id": "drawer:agent",
                        "kind": "drawer",
                        "title": "Agent Drawer",
                    }
                ],
                "nodes": [
                    {
                        "node_id": "node-1",
                        "kind": "button",
                        "locator": "button.save",
                        "interactable": True,
                        "summary": "Save",
                    }
                ],
            },
        }

    monkeypatch.setattr(
        "app.sio.page_session.request_ui_snapshot",
        _request_ui_snapshot,
    )

    bridge = SocketIOPageRuntimeBridge()
    result = await bridge.invoke(
        arguments={"mode": "full", "surface_id": "drawer:agent"},
        page_session_id="ps-1",
        tool_name="ui_get_snapshot",
        user_role="tenant_admin",
    )

    assert result["success"] is True
    assert result["data"]["mode"] == "full"
    assert result["data"]["ui_epoch"] == 7
    assert result["data"]["active_surface_id"] == "drawer:agent"
    assert result["data"]["nodes"][0]["locator"] == "button.save"
