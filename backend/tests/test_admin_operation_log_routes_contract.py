from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.admin.operation_logs import AdminOperationLogController
from app.core.deps import get_current_active_admin, get_db
from app.repositories.system.operation_log_repository import OperationLogRepository
from tests.services.conftest import make_scalar_result


def _build_test_app(mock_db) -> FastAPI:
    app = FastAPI()

    @app.middleware("http")
    async def inject_permissions(request, call_next):
        request.state.user_permissions = {"operation_log:detail"}
        return await call_next(request)

    app.include_router(AdminOperationLogController.get_router())

    async def override_db():
        yield mock_db

    async def override_admin():
        return SimpleNamespace(id=1, is_active=True, is_super=True)

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_active_admin] = override_admin
    return app


def test_get_log_route_keeps_operation_log_facade_chain(monkeypatch) -> None:
    from app.services.system.operation_log_service import OperationLogService

    monkeypatch.setattr(AdminOperationLogController, "_instance", None)
    monkeypatch.setattr(AdminOperationLogController, "_router", None)

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

    app = _build_test_app(mock_db)

    with TestClient(app) as client:
        response = client.get("/operation-logs/7")

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 0
    assert payload["data"]["id"] == 7
    assert payload["data"]["path"] == "/admin/tenants"
    assert payload["data"]["method"] == "GET"
    serialize_log.assert_awaited_once_with(log_record)
