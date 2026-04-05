from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.api.admin.plugins import AdminPluginController, PluginDependencyActionBody
from app.core.deps import get_current_active_admin, get_db


def _build_test_app(db: AsyncMock) -> FastAPI:
    app = FastAPI()
    app.include_router(AdminPluginController.get_router())

    async def override_db():
        yield db

    async def override_admin():
        return SimpleNamespace(id=1, is_active=True)

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_active_admin] = override_admin
    return app


def test_plugin_dependency_action_body_forbids_force_flag() -> None:
    with pytest.raises(ValidationError):
        PluginDependencyActionBody.model_validate({"python": True, "force": True})


def test_uninstall_plugin_dependencies_rejects_legacy_force_field(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(AdminPluginController, "_instance", None)
    monkeypatch.setattr(AdminPluginController, "_router", None)

    service = SimpleNamespace(uninstall_plugin_dependencies=AsyncMock())
    monkeypatch.setattr(
        AdminPluginController,
        "get_service",
        lambda self, db: service,
    )

    db = AsyncMock()
    app = _build_test_app(db)

    with TestClient(app) as client:
        response = client.post(
            "/plugins/1/dependencies/uninstall",
            json={"python": True, "force": True},
        )

    assert response.status_code == 422
    service.uninstall_plugin_dependencies.assert_not_awaited()


def test_uninstall_plugin_dependencies_response_omits_forced_field(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(AdminPluginController, "_instance", None)
    monkeypatch.setattr(AdminPluginController, "_router", None)

    result = {
        "plugin_id": 1,
        "plugin_name": "demo-plugin",
        "python": {"declared": [], "attempted": True},
        "plugins": [],
    }
    service = SimpleNamespace(
        uninstall_plugin_dependencies=AsyncMock(return_value=result),
    )
    monkeypatch.setattr(
        AdminPluginController,
        "get_service",
        lambda self, db: service,
    )

    db = AsyncMock()
    app = _build_test_app(db)

    with TestClient(app) as client:
        response = client.post(
            "/plugins/1/dependencies/uninstall",
            json={"python": True},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 0
    assert payload["data"] == result
    assert "forced" not in payload["data"]
    service.uninstall_plugin_dependencies.assert_awaited_once_with(
        1,
        uninstall_python=True,
    )


def test_ai_services_package_no_longer_exports_table_policy_services() -> None:
    import app.services.ai as ai_services

    assert not hasattr(ai_services, "AITablePolicyService")
    assert not hasattr(ai_services, "AITablePolicyOverrideService")
