from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.deps import get_current_active_admin, get_db


def _load_admin_agent_chat_module():
    module_path = (
        Path(__file__).resolve().parent.parent
        / "app"
        / "api"
        / "admin"
        / "ai_agent_chat.py"
    )
    spec = importlib.util.spec_from_file_location(
        "test_admin_agent_chat_module",
        module_path,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec is not None
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _build_test_app(mock_db, admin_module) -> FastAPI:
    app = FastAPI()

    @app.middleware("http")
    async def inject_permissions(request, call_next):
        request.state.user_permissions = {"*"}
        return await call_next(request)

    app.include_router(admin_module.AdminAgentChatController.get_router())

    async def override_db():
        yield mock_db

    async def override_admin():
        return SimpleNamespace(
            id=1,
            org_node_id=101,
            username="admin",
            is_active=True,
        )

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_active_admin] = override_admin
    return app


def _navigation_entry() -> dict[str, object]:
    return {
        "breadcrumb": ["AI", "Agents"],
        "capabilities": ["create", "edit"],
        "category": "AI",
        "description": "Manage AI agents",
        "endpoint": "/ai/agents",
        "keywords": ["agents", "assistant"],
        "page_key": "admin.ai.agents",
        "path": "/admin/ai/agents",
        "title": "Agents",
    }


class _ChatResult:
    def model_dump(self) -> dict[str, object]:
        return {
            "conversation_id": 11,
            "message": "ok",
            "tool_calls": [],
            "total_tokens": 12,
            "duration_ms": 34,
        }


def test_admin_agent_chat_route_rejects_retired_page_context(
    monkeypatch,
) -> None:
    admin_module = _load_admin_agent_chat_module()
    monkeypatch.setattr(admin_module.AdminAgentChatController, "_instance", None)
    monkeypatch.setattr(admin_module.AdminAgentChatController, "_router", None)

    handle_route = AsyncMock(
        return_value={
            "code": 0,
            "message": "success",
            "data": {
                "agent_id": 7,
                "agent_name": "Router Agent",
                "confidence": 0.91,
                "routed_by": "router",
            },
        }
    )
    monkeypatch.setattr(admin_module, "handle_route", handle_route)

    app = _build_test_app(SimpleNamespace(), admin_module)
    with TestClient(app) as client:
        response = client.post(
            "/ai/agent-chat/route",
            json={
                "message": "route me",
                "page_context": {
                    "page_key": "admin.ai.agents",
                    "page_data": {
                        "navigation_catalog": [
                            _navigation_entry(),
                            {
                                "page_key": "admin.ai.broken",
                                "title": "Broken entry without path",
                            },
                            {
                                "page_key": "   ",
                                "path": "   ",
                                "title": "   ",
                            },
                        ]
                    },
                },
            },
        )

    assert response.status_code == 422
    handle_route.assert_not_awaited()


def test_admin_agent_chat_chat_rejects_retired_page_context(monkeypatch) -> None:
    admin_module = _load_admin_agent_chat_module()
    monkeypatch.setattr(admin_module.AdminAgentChatController, "_instance", None)
    monkeypatch.setattr(admin_module.AdminAgentChatController, "_router", None)

    permission_service = SimpleNamespace(
        get_admin_permissions=AsyncMock(return_value=["*"])
    )
    chat_service = SimpleNamespace(chat=AsyncMock(return_value=_ChatResult()))

    monkeypatch.setattr(
        admin_module,
        "PermissionService",
        lambda _db: permission_service,
    )
    monkeypatch.setattr(
        admin_module,
        "AgentChatService",
        lambda _db, _tenant_id: chat_service,
    )

    app = _build_test_app(SimpleNamespace(), admin_module)
    with TestClient(app) as client:
        response = client.post(
            "/ai/agent-chat/42/chat",
            json={
                "message": "help me",
                "page_context": {
                    "page_key": "admin.ai.agents",
                    "page_data": {
                        "document_body_text": "x" * 128,
                    },
                },
            },
        )

    assert response.status_code == 422
    chat_service.chat.assert_not_awaited()
