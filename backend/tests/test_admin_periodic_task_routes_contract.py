"""中文: 管理端周期任务路由契约测试。

EN: Admin periodic task route contract tests.

Test type: structural / behavioral
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.deps import get_current_active_admin, get_db


def _load_periodic_tasks_module():
    module_path = (
        Path(__file__).resolve().parent.parent
        / "app"
        / "api"
        / "admin"
        / "periodic_tasks.py"
    )
    spec = importlib.util.spec_from_file_location(
        "test_admin_periodic_tasks_module",
        module_path,
    )
    module = importlib.util.module_from_spec(spec)
    if spec is None or spec.loader is None:
        raise RuntimeError(
            "Failed to load periodic tasks module for route contract tests"
        )
    spec.loader.exec_module(module)
    return module


def _build_test_app(mock_db, periodic_tasks_module) -> FastAPI:
    controller = periodic_tasks_module.AdminPeriodicTaskController
    app = FastAPI()

    @app.middleware("http")
    async def inject_permissions(request, call_next):
        request.state.user_permissions = {
            "periodic_task:list",
            "periodic_task:detail",
            "periodic_task:create",
            "periodic_task:update",
            "periodic_task:delete",
            "periodic_task:toggle",
            "periodic_task:trigger",
            "periodic_task:bindings",
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


def test_list_periodic_tasks_route_returns_paginated_payload(monkeypatch) -> None:
    periodic_tasks_module = _load_periodic_tasks_module()
    monkeypatch.setattr(
        periodic_tasks_module.AdminPeriodicTaskController, "_instance", None
    )
    monkeypatch.setattr(
        periodic_tasks_module.AdminPeriodicTaskController, "_router", None
    )

    definition = SimpleNamespace(id=4)
    service = SimpleNamespace(query_list=AsyncMock(return_value=([definition], 1)))
    binding_service = SimpleNamespace(
        get_definition_binding_summary=AsyncMock(
            return_value={
                4: {
                    "assigned_tenant_ids": [7],
                    "assigned_tenant_names": ["Tenant A"],
                    "active_binding_count": 1,
                    "binding_summary": "Tenant A",
                }
            }
        )
    )
    plugin_state_service = SimpleNamespace(
        resolve_enabled_map=AsyncMock(return_value={"demo-plugin": False})
    )
    presenter = SimpleNamespace(
        collect_plugin_names=Mock(return_value=["demo-plugin"]),
        patch_missing_next_run=Mock(),
        serialize_definition=Mock(
            return_value={
                "id": 4,
                "name": "nightly-cleanup",
                "binding_count": 1,
                "plugin_enabled": False,
            }
        ),
    )

    monkeypatch.setattr(
        periodic_tasks_module.AdminPeriodicTaskController,
        "get_service",
        _return(service),
    )
    monkeypatch.setattr(
        periodic_tasks_module,
        "TaskBindingService",
        _return(binding_service),
    )
    monkeypatch.setattr(
        periodic_tasks_module,
        "PeriodicTaskPluginStateService",
        _return(plugin_state_service),
    )
    monkeypatch.setattr(
        periodic_tasks_module.AdminPeriodicTaskController,
        "_presentation",
        presenter,
    )

    app = _build_test_app(SimpleNamespace(), periodic_tasks_module)

    with TestClient(app) as client:
        response = client.get("/periodic-tasks?page[number]=3&page[size]=15")

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 0
    assert payload["data"]["items"] == [
        {
            "id": 4,
            "name": "nightly-cleanup",
            "binding_count": 1,
            "plugin_enabled": False,
        }
    ]
    assert payload["data"]["total"] == 1
    assert payload["data"]["page"] == 3
    assert payload["data"]["page_size"] == 15

    awaited = service.query_list.await_args
    assert awaited.args[0].page == 3
    assert awaited.args[0].size == 15
    presenter.collect_plugin_names.assert_called_once_with([definition])
    plugin_state_service.resolve_enabled_map.assert_awaited_once_with(
        plugin_names=["demo-plugin"]
    )
    binding_service.get_definition_binding_summary.assert_awaited_once_with([4])
    presenter.patch_missing_next_run.assert_called_once()


def test_create_periodic_task_route_maps_request_fields_and_syncs_bindings(
    monkeypatch,
) -> None:
    periodic_tasks_module = _load_periodic_tasks_module()
    monkeypatch.setattr(
        periodic_tasks_module.AdminPeriodicTaskController, "_instance", None
    )
    monkeypatch.setattr(
        periodic_tasks_module.AdminPeriodicTaskController, "_router", None
    )

    created_definition = SimpleNamespace(id=12)
    hydrated_definition = SimpleNamespace(id=12)
    service = SimpleNamespace(
        create=AsyncMock(return_value=created_definition),
        get_by_id=AsyncMock(return_value=hydrated_definition),
    )
    binding_service = SimpleNamespace(
        resolve_target_tenant_ids=AsyncMock(return_value=[3, 4]),
        sync_definition_bindings=AsyncMock(),
        get_definition_binding_summary=AsyncMock(
            return_value={
                12: {
                    "assigned_tenant_ids": [3, 4],
                    "assigned_tenant_names": ["Tenant A", "Tenant B"],
                    "active_binding_count": 2,
                    "binding_summary": "2 tenants",
                }
            }
        ),
    )
    presenter = SimpleNamespace(
        serialize_definition=Mock(
            return_value={
                "id": 12,
                "scope": "selected_tenants",
                "assigned_tenant_ids": [3, 4],
                "binding_count": 2,
            }
        )
    )

    monkeypatch.setattr(
        periodic_tasks_module.AdminPeriodicTaskController,
        "get_service",
        _return(service),
    )
    monkeypatch.setattr(
        periodic_tasks_module,
        "TaskBindingService",
        _return(binding_service),
    )
    monkeypatch.setattr(
        periodic_tasks_module.AdminPeriodicTaskController,
        "_presentation",
        presenter,
    )

    app = _build_test_app(SimpleNamespace(), periodic_tasks_module)

    with TestClient(app) as client:
        response = client.post(
            "/periodic-tasks",
            json={
                "name": "nightly-cleanup",
                "task_path": "app.tasks.system.nightly_cleanup",
                "schedule_type": "interval",
                "interval_seconds": 600,
                "args": {"batch": 3},
                "kwargs": {"dry_run": True},
                "description": "Nightly cleanup",
                "scope": "selected_tenants",
                "tenant_ids": [3, 4],
                "owner_tenant_id": 99,
                "is_active": False,
                "max_retries": 2,
                "retry_delay": 120,
                "timeout": 1800,
                "notify_on_failure": True,
                "notify_emails": "ops@example.com",
                "default_priority": 7,
                "required_feature_codes": ["storage_billing_enabled"],
                "required_plugin_names": ["storage-billing"],
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 0
    assert payload["data"] == {
        "id": 12,
        "scope": "selected_tenants",
        "assigned_tenant_ids": [3, 4],
        "binding_count": 2,
    }

    service.create.assert_awaited_once_with(
        {
            "name": "nightly-cleanup",
            "handler_path": "app.tasks.system.nightly_cleanup",
            "default_schedule_type": "interval",
            "default_cron_expression": None,
            "default_interval_seconds": 600,
            "default_args": {"batch": 3},
            "default_kwargs": {"dry_run": True},
            "description": "Nightly cleanup",
            "scope": "selected_tenants",
            "owner_tenant_id": 99,
            "is_enabled": False,
            "max_retries": 2,
            "retry_delay": 120,
            "timeout": 1800,
            "notify_on_failure": True,
            "notify_emails": "ops@example.com",
            "default_queue": "scheduled",
            "default_priority": 7,
            "required_feature_codes": ["storage_billing_enabled"],
            "required_plugin_names": ["storage-billing"],
            "definition_type": "system",
        }
    )
    binding_service.resolve_target_tenant_ids.assert_awaited_once_with(
        "selected_tenants",
        [3, 4],
    )
    binding_service.sync_definition_bindings.assert_awaited_once_with(
        12,
        [3, 4],
        target_scope="selected_tenants",
        binding_payloads=[],
    )


def test_sync_bindings_route_preserves_explicit_scope_when_request_omits_scope(
    monkeypatch,
) -> None:
    periodic_tasks_module = _load_periodic_tasks_module()
    monkeypatch.setattr(
        periodic_tasks_module.AdminPeriodicTaskController, "_instance", None
    )
    monkeypatch.setattr(
        periodic_tasks_module.AdminPeriodicTaskController, "_router", None
    )

    service = SimpleNamespace(
        get_by_id=AsyncMock(
            return_value=SimpleNamespace(id=18, scope="selected_tenants")
        )
    )
    binding_service = SimpleNamespace(
        resolve_target_tenant_ids=AsyncMock(return_value=[8, 9]),
        sync_definition_bindings=AsyncMock(
            return_value={"scope": "selected_tenants", "assigned_tenant_ids": [8, 9]}
        ),
    )
    presenter = SimpleNamespace(
        resolve_binding_target_scope=Mock(return_value="selected_tenants")
    )
    mock_db = SimpleNamespace(commit=AsyncMock())

    monkeypatch.setattr(
        periodic_tasks_module.AdminPeriodicTaskController,
        "get_service",
        _return(service),
    )
    monkeypatch.setattr(
        periodic_tasks_module,
        "TaskBindingService",
        _return(binding_service),
    )
    monkeypatch.setattr(
        periodic_tasks_module.AdminPeriodicTaskController,
        "_presentation",
        presenter,
    )

    app = _build_test_app(mock_db, periodic_tasks_module)

    with TestClient(app) as client:
        response = client.put(
            "/periodic-tasks/18/bindings",
            json={"tenant_ids": [8, 9]},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 0
    assert payload["data"] == {
        "scope": "selected_tenants",
        "assigned_tenant_ids": [8, 9],
    }
    service.get_by_id.assert_awaited_once_with(18)
    presenter.resolve_binding_target_scope.assert_called_once_with(
        current_scope="selected_tenants",
        requested_scope=None,
        tenant_ids=[8, 9],
    )
    binding_service.resolve_target_tenant_ids.assert_awaited_once_with(
        "selected_tenants",
        [8, 9],
    )
    binding_service.sync_definition_bindings.assert_awaited_once_with(
        18,
        [8, 9],
        target_scope="selected_tenants",
        binding_payloads=[],
    )
    mock_db.commit.assert_awaited_once_with()


def test_update_periodic_task_route_maps_entitlement_fields(monkeypatch) -> None:
    periodic_tasks_module = _load_periodic_tasks_module()
    monkeypatch.setattr(
        periodic_tasks_module.AdminPeriodicTaskController, "_instance", None
    )
    monkeypatch.setattr(
        periodic_tasks_module.AdminPeriodicTaskController, "_router", None
    )

    task = SimpleNamespace(id=18, scope="admin_only")
    service = SimpleNamespace(
        get_by_id=AsyncMock(return_value=task),
        update=AsyncMock(return_value=task),
    )
    binding_service = SimpleNamespace(
        get_definition_binding_summary=AsyncMock(return_value={18: {}}),
    )
    plugin_state_service = SimpleNamespace(
        resolve_enabled_map=AsyncMock(return_value={})
    )
    presenter = SimpleNamespace(
        collect_plugin_names=Mock(return_value=[]),
        serialize_definition=Mock(return_value={"id": 18}),
    )

    monkeypatch.setattr(
        periodic_tasks_module.AdminPeriodicTaskController,
        "get_service",
        _return(service),
    )
    monkeypatch.setattr(
        periodic_tasks_module,
        "TaskBindingService",
        _return(binding_service),
    )
    monkeypatch.setattr(
        periodic_tasks_module,
        "PeriodicTaskPluginStateService",
        _return(plugin_state_service),
    )
    monkeypatch.setattr(
        periodic_tasks_module.AdminPeriodicTaskController,
        "_presentation",
        presenter,
    )

    app = _build_test_app(SimpleNamespace(), periodic_tasks_module)

    with TestClient(app) as client:
        response = client.put(
            "/periodic-tasks/18",
            json={
                "required_feature_codes": ["storage_billing_enabled"],
                "required_plugin_names": ["storage-billing"],
            },
        )

    assert response.status_code == 200
    assert response.json()["data"] == {"id": 18}
    service.update.assert_awaited_once_with(
        18,
        {
            "required_feature_codes": ["storage_billing_enabled"],
            "required_plugin_names": ["storage-billing"],
        },
    )


def test_trigger_periodic_task_route_returns_full_dispatch_payload(monkeypatch) -> None:
    periodic_tasks_module = _load_periodic_tasks_module()
    monkeypatch.setattr(
        periodic_tasks_module.AdminPeriodicTaskController, "_instance", None
    )
    monkeypatch.setattr(
        periodic_tasks_module.AdminPeriodicTaskController, "_router", None
    )

    dispatch_payload = {
        "triggered_task_id": "binding-task-1",
        "dispatched_task_ids": ["binding-task-1", "binding-task-2"],
        "dispatched_count": 2,
    }
    service = SimpleNamespace(trigger_now=AsyncMock(return_value=dispatch_payload))

    monkeypatch.setattr(
        periodic_tasks_module.AdminPeriodicTaskController,
        "get_service",
        _return(service),
    )

    app = _build_test_app(SimpleNamespace(), periodic_tasks_module)

    with TestClient(app) as client:
        response = client.post("/periodic-tasks/18/trigger")

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 0
    assert payload["data"] == dispatch_payload
    service.trigger_now.assert_awaited_once_with(18)
