from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.deps import get_current_active_admin, get_db
from app.repositories.system.operation_log_repository import OperationLogRepository
from tests.services.conftest import make_scalar_result


def _load_operation_logs_module():
    module_path = (
        Path(__file__).resolve().parent.parent
        / "app"
        / "api"
        / "admin"
        / "operation_logs.py"
    )
    spec = importlib.util.spec_from_file_location(
        "test_admin_operation_logs_module",
        module_path,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec is not None
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _build_test_app(mock_db, operation_logs_module) -> FastAPI:
    controller = operation_logs_module.AdminOperationLogController
    app = FastAPI()

    @app.middleware("http")
    async def inject_permissions(request, call_next):
        request.state.user_permissions = {"operation_log:detail", "operation_log:list"}
        return await call_next(request)

    app.include_router(controller.get_router())

    async def override_db():
        yield mock_db

    async def override_admin():
        return SimpleNamespace(id=1, is_active=True, is_super=True)

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_active_admin] = override_admin
    return app


def test_get_log_route_keeps_operation_log_facade_chain(monkeypatch) -> None:
    from app.services.system.operation_log_service import OperationLogService

    operation_logs_module = _load_operation_logs_module()
    monkeypatch.setattr(
        operation_logs_module.AdminOperationLogController,
        "_instance",
        None,
    )
    monkeypatch.setattr(
        operation_logs_module.AdminOperationLogController,
        "_router",
        None,
    )

    log_record = SimpleNamespace(id=7, path="/admin/tenants", method="GET")
    mock_db = AsyncMock()
    mock_db.execute.return_value = make_scalar_result(log_record)

    def fake_init(self, db) -> None:
        self.db = db
        self.repo = OperationLogRepository(db)

    serialize_log = AsyncMock(
        return_value={
            "id": 7,
            "path": "/admin/tenants",
            "method": "GET",
        }
    )

    monkeypatch.setattr(OperationLogService, "__init__", fake_init)
    monkeypatch.setattr(OperationLogService, "serialize_log", serialize_log)

    app = _build_test_app(mock_db, operation_logs_module)

    with TestClient(app) as client:
        response = client.get("/operation-logs/7")

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 0
    assert payload["data"]["id"] == 7
    assert payload["data"]["path"] == "/admin/tenants"
    assert payload["data"]["method"] == "GET"
    serialize_log.assert_awaited_once_with(log_record)


def test_list_logs_route_returns_paginated_envelope(monkeypatch) -> None:
    from app.services.system.operation_log_service import OperationLogService

    operation_logs_module = _load_operation_logs_module()
    monkeypatch.setattr(
        operation_logs_module.AdminOperationLogController,
        "_instance",
        None,
    )
    monkeypatch.setattr(
        operation_logs_module.AdminOperationLogController,
        "_router",
        None,
    )

    def fake_init(self, db) -> None:
        self.db = db
        self.repo = OperationLogRepository(db)

    query_admin_logs = AsyncMock(
        return_value=([SimpleNamespace(id=9, path="/admin/plugins", method="GET")], 1)
    )
    serialize_logs = AsyncMock(
        return_value=[{"id": 9, "path": "/admin/plugins", "method": "GET"}]
    )

    monkeypatch.setattr(OperationLogService, "__init__", fake_init)
    monkeypatch.setattr(
        OperationLogService,
        "query_admin_logs_by_permission",
        query_admin_logs,
    )
    monkeypatch.setattr(OperationLogService, "serialize_logs", serialize_logs)

    app = _build_test_app(AsyncMock(), operation_logs_module)

    with TestClient(app) as client:
        response = client.get("/operation-logs?page[number]=1&page[size]=20")

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 0
    assert payload["data"]["items"][0]["id"] == 9
    assert payload["data"]["total"] == 1
    assert payload["data"]["page"] == 1
    assert payload["data"]["page_size"] == 20


def test_list_operators_route_returns_paged_payload(monkeypatch) -> None:
    from app.services.system.operation_log_service import OperationLogService

    operation_logs_module = _load_operation_logs_module()
    monkeypatch.setattr(
        operation_logs_module.AdminOperationLogController,
        "_instance",
        None,
    )
    monkeypatch.setattr(
        operation_logs_module.AdminOperationLogController,
        "_router",
        None,
    )

    def fake_init(self, db) -> None:
        self.db = db
        self.repo = OperationLogRepository(db)

    get_admin_operators_select = AsyncMock(
        return_value=(
            [
                {
                    "label": "Alice",
                    "value": "alice",
                    "extra": {"user_id": 7},
                    "disabled": False,
                }
            ],
            1,
        )
    )

    monkeypatch.setattr(OperationLogService, "__init__", fake_init)
    monkeypatch.setattr(
        OperationLogService,
        "get_admin_operators_select",
        get_admin_operators_select,
    )

    app = _build_test_app(AsyncMock(), operation_logs_module)

    with TestClient(app) as client:
        response = client.get(
            "/operation-logs/operators?page=1&page_size=10&search=ali"
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 0
    assert payload["data"]["total"] == 1
    assert payload["data"]["items"][0]["label"] == "Alice"
    assert payload["data"]["page"] == 1
    assert payload["data"]["page_size"] == 10
    get_admin_operators_select.assert_awaited_once_with(
        search="ali",
        page=1,
        page_size=10,
    )


def test_list_operators_route_defaults_to_paged_payload(monkeypatch) -> None:
    from app.services.system.operation_log_service import OperationLogService

    operation_logs_module = _load_operation_logs_module()
    monkeypatch.setattr(
        operation_logs_module.AdminOperationLogController,
        "_instance",
        None,
    )
    monkeypatch.setattr(
        operation_logs_module.AdminOperationLogController,
        "_router",
        None,
    )

    def fake_init(self, db) -> None:
        self.db = db
        self.repo = OperationLogRepository(db)

    get_admin_operators_select = AsyncMock(
        return_value=(
            [
                {
                    "label": "Alice",
                    "value": "alice",
                    "extra": {"user_id": 7},
                    "disabled": False,
                }
            ],
            1,
        )
    )
    get_admin_operators = AsyncMock()

    monkeypatch.setattr(OperationLogService, "__init__", fake_init)
    monkeypatch.setattr(
        OperationLogService,
        "get_admin_operators_select",
        get_admin_operators_select,
    )
    monkeypatch.setattr(
        OperationLogService,
        "get_admin_operators",
        get_admin_operators,
    )

    app = _build_test_app(AsyncMock(), operation_logs_module)

    with TestClient(app) as client:
        response = client.get("/operation-logs/operators")

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 0
    assert payload["data"] == {
        "items": [
            {
                "label": "Alice",
                "value": "alice",
                "extra": {"user_id": 7},
                "disabled": False,
            }
        ],
        "total": 1,
        "page": 1,
        "page_size": 10,
    }
    get_admin_operators_select.assert_awaited_once_with(
        search=None,
        page=1,
        page_size=10,
    )
    get_admin_operators.assert_not_awaited()


def test_export_logs_route_uses_serialized_labels(monkeypatch) -> None:
    from app.services.system.operation_log_service import OperationLogService

    operation_logs_module = _load_operation_logs_module()
    monkeypatch.setattr(
        operation_logs_module.AdminOperationLogController,
        "_instance",
        None,
    )
    monkeypatch.setattr(
        operation_logs_module.AdminOperationLogController,
        "_router",
        None,
    )

    def fake_init(self, db) -> None:
        self.db = db
        self.repo = OperationLogRepository(db)

    query_admin_logs = AsyncMock(
        return_value=(
            [SimpleNamespace(id=11, path="/api/public/attachments/26/image")],
            1,
        )
    )
    serialize_logs = AsyncMock(
        return_value=[
            {
                "id": 11,
                "display_name": "管理员",
                "username": "admin",
                "module": "attachment",
                "module_label": "附件",
                "action": "query",
                "action_label": "查询",
                "ip": "127.0.0.1",
                "response_code": 0,
                "created_at": "2026-04-15T15:17:50+00:00",
            }
        ]
    )

    monkeypatch.setattr(OperationLogService, "__init__", fake_init)
    monkeypatch.setattr(
        OperationLogService,
        "query_admin_logs_by_permission",
        query_admin_logs,
    )
    monkeypatch.setattr(OperationLogService, "serialize_logs", serialize_logs)

    app = _build_test_app(AsyncMock(), operation_logs_module)

    with TestClient(app) as client:
        response = client.get("/operation-logs/export")

    assert response.status_code == 200
    assert "text/csv" in response.headers["content-type"]
    content = response.content.decode("utf-8-sig")
    assert "附件" in content
    assert "查询" in content
    assert "attachment" not in content
