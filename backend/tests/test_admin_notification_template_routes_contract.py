from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.deps import get_current_active_admin, get_db
from app.schemas.common.query import FilterOp


def _load_notification_templates_module():
    module_path = (
        Path(__file__).resolve().parent.parent
        / "app"
        / "api"
        / "admin"
        / "notification_templates.py"
    )
    spec = importlib.util.spec_from_file_location(
        "test_admin_notification_templates_module",
        module_path,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec is not None
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _build_test_app(mock_db, module) -> FastAPI:
    controller = module.AdminNotificationTemplateController
    app = FastAPI()

    @app.middleware("http")
    async def inject_permissions(request, call_next):
        request.state.user_permissions = {
            "notification_template:list",
            "notification_template:update",
            "notification_template:test",
        }
        return await call_next(request)

    app.include_router(controller.get_router())

    async def override_db():
        yield mock_db

    async def override_admin():
        return SimpleNamespace(id=1, is_active=True, is_super=True)

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_active_admin] = override_admin
    return app


def _return(value):
    return lambda *_args, **_kwargs: value


def _make_template(**overrides):
    defaults = {
        "id": 9,
        "code": "task.failed",
        "category": "task",
        "title_template": "Task failed",
        "body_template": None,
        "channels": ["inbox"],
        "priority": "high",
        "scope": "tenant",
        "source": "plugin",
        "plugin_name": "scheduler",
        "is_enabled": True,
        "is_system": False,
        "tenant_id": None,
        "override_of": None,
        "locked_fields": [],
        "created_at": "2026-05-01T00:00:00Z",
        "updated_at": "2026-05-02T00:00:00Z",
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def test_list_notification_templates_route_returns_tenant_and_override_metadata(
    monkeypatch,
) -> None:
    module = _load_notification_templates_module()
    monkeypatch.setattr(module.AdminNotificationTemplateController, "_instance", None)
    monkeypatch.setattr(module.AdminNotificationTemplateController, "_router", None)

    template = SimpleNamespace(
        id=9,
        code="task.failed",
        category="task",
        title_template="Task failed",
        body_template=None,
        channels=["inbox"],
        priority="high",
        scope="tenant",
        source="plugin",
        plugin_name="scheduler",
        is_enabled=True,
        is_system=False,
        tenant_id=22,
        override_of=4,
        locked_fields=["title_template"],
        created_at="2026-05-01T00:00:00Z",
        updated_at="2026-05-02T00:00:00Z",
    )
    repo = SimpleNamespace(
        query_list=AsyncMock(return_value=([template], 1)),
        get_tenant_name_map=AsyncMock(return_value={22: "Tenant A"}),
        resolve_effective_template=AsyncMock(
            return_value=SimpleNamespace(
                title_template="Effective title",
                body_template="Effective body",
                channels=["email"],
                priority="urgent",
            )
        ),
    )

    monkeypatch.setattr(module, "NotificationTemplateRepository", _return(repo))

    app = _build_test_app(SimpleNamespace(), module)

    with TestClient(app) as client:
        response = client.get(
            "/notification-templates",
            params={
                "filter[is_override][eq]": "true",
                "page[number]": "2",
                "page[size]": "5",
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 0
    assert payload["data"]["total"] == 1
    assert payload["data"]["page"] == 2
    assert payload["data"]["page_size"] == 5
    assert payload["data"]["items"] == [
        {
            "id": 9,
            "code": "task.failed",
            "category": "task",
            "title_template": "Task failed",
            "body_template": None,
            "channels": ["inbox"],
            "priority": "high",
            "scope": "tenant",
            "source": "plugin",
            "plugin_name": "scheduler",
            "is_enabled": True,
            "is_system": False,
            "tenant_id": 22,
            "tenant_name": "Tenant A",
            "override_of": 4,
            "is_override": True,
            "locked_fields": ["title_template"],
            "effective_preview": {
                "title_template": "Effective title",
                "body_template": "Effective body",
                "channels": ["email"],
                "priority": "urgent",
            },
            "created_at": "2026-05-01T00:00:00Z",
            "updated_at": "2026-05-02T00:00:00Z",
        }
    ]

    awaited = repo.query_list.await_args
    assert awaited.args[0].page == 2
    assert awaited.args[0].size == 5
    assert any(
        rule.field == "is_override" and rule.op == FilterOp.eq and rule.value == "true"
        for rule in awaited.args[0].filters
    )
    repo.get_tenant_name_map.assert_awaited_once_with({22})
    repo.resolve_effective_template.assert_awaited_once_with("task.failed", 22)


def test_update_notification_template_accepts_canonical_is_enabled_only(
    monkeypatch,
) -> None:
    module = _load_notification_templates_module()
    monkeypatch.setattr(module.AdminNotificationTemplateController, "_instance", None)
    monkeypatch.setattr(module.AdminNotificationTemplateController, "_router", None)

    template = _make_template(is_enabled=True)
    repo = SimpleNamespace(
        get_by_id=AsyncMock(return_value=template),
        get_tenant_name_map=AsyncMock(return_value={}),
        resolve_effective_template=AsyncMock(return_value=None),
    )
    monkeypatch.setattr(module, "NotificationTemplateRepository", _return(repo))
    mock_db = SimpleNamespace(commit=AsyncMock(), refresh=AsyncMock())
    app = _build_test_app(mock_db, module)

    with TestClient(app) as client:
        response = client.put(
            "/notification-templates/9",
            json={"is_enabled": False},
        )

    assert response.status_code == 200
    assert template.is_enabled is False
    payload = response.json()["data"]
    assert payload["is_enabled"] is False
    assert "enabled" not in payload
    mock_db.commit.assert_awaited_once()
    mock_db.refresh.assert_awaited_once_with(template)


def test_update_notification_template_rejects_enabled_alias(monkeypatch) -> None:
    module = _load_notification_templates_module()
    monkeypatch.setattr(module.AdminNotificationTemplateController, "_instance", None)
    monkeypatch.setattr(module.AdminNotificationTemplateController, "_router", None)

    repo = SimpleNamespace(get_by_id=AsyncMock())
    monkeypatch.setattr(module, "NotificationTemplateRepository", _return(repo))
    mock_db = SimpleNamespace(commit=AsyncMock(), refresh=AsyncMock())
    app = _build_test_app(mock_db, module)

    with TestClient(app) as client:
        response = client.put(
            "/notification-templates/9",
            json={"enabled": False},
        )

    assert response.status_code == 422
    assert "enabled" in response.text
    repo.get_by_id.assert_not_awaited()
    mock_db.commit.assert_not_awaited()
