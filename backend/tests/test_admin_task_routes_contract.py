from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.deps import get_current_active_admin, get_db


def _load_tasks_module():
    module_path = (
        Path(__file__).resolve().parent.parent / "app" / "api" / "admin" / "tasks.py"
    )
    spec = importlib.util.spec_from_file_location(
        "test_admin_tasks_module",
        module_path,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec is not None
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _build_test_app(mock_db, tasks_module) -> FastAPI:
    controller = tasks_module.AdminTaskController
    app = FastAPI()

    @app.middleware("http")
    async def inject_permissions(request, call_next):
        request.state.user_permissions = {
            "task_log:list",
            "task_log:stats",
            "task_log:active",
            "task_log:detail",
            "task_log:retry",
            "task_log:cancel",
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


def test_task_list_route_returns_paginated_payload(monkeypatch) -> None:
    tasks_module = _load_tasks_module()
    monkeypatch.setattr(tasks_module.AdminTaskController, "_instance", None)
    monkeypatch.setattr(tasks_module.AdminTaskController, "_router", None)

    task_run = SimpleNamespace(id=9)
    service = SimpleNamespace(
        query_list_by_view=AsyncMock(return_value=([task_run], 1)),
    )
    relation_resolver = SimpleNamespace(
        build_maps=AsyncMock(
            return_value=(
                {3: {"name": "nightly-cleanup", "scope": "admin_only"}},
                {7: "Tenant A"},
            )
        ),
        serialize_task_run=Mock(
            return_value={
                "id": 9,
                "task_id": "task-9",
                "task_name": "nightly-cleanup",
            }
        ),
    )

    monkeypatch.setattr(
        tasks_module.AdminTaskController,
        "get_service",
        _return(service),
    )
    monkeypatch.setattr(
        tasks_module,
        "TaskLogRelationService",
        _return(relation_resolver),
    )

    app = _build_test_app(SimpleNamespace(), tasks_module)

    with TestClient(app) as client:
        response = client.get("/tasks?view=execution&page[number]=2&page[size]=50")

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 0
    assert payload["data"]["items"] == [
        {
            "id": 9,
            "task_id": "task-9",
            "task_name": "nightly-cleanup",
        }
    ]
    assert payload["data"]["total"] == 1
    assert payload["data"]["page"] == 2
    assert payload["data"]["page_size"] == 50

    awaited = service.query_list_by_view.await_args
    assert awaited.kwargs == {"view": "execution"}
    assert awaited.args[0].page == 2
    assert awaited.args[0].size == 50
    relation_resolver.build_maps.assert_awaited_once_with([task_run])
    relation_resolver.serialize_task_run.assert_called_once()


def test_retry_task_route_reuses_original_queue_when_body_omitted(monkeypatch) -> None:
    tasks_module = _load_tasks_module()
    monkeypatch.setattr(tasks_module.AdminTaskController, "_instance", None)
    monkeypatch.setattr(tasks_module.AdminTaskController, "_router", None)

    task_log = SimpleNamespace(
        id=7,
        handler_path_snapshot="app.tasks.system.nightly_cleanup",
        args_summary={"args": [1, 2], "kwargs": {"tenant_id": 9}},
        queue="scheduled",
    )
    service = SimpleNamespace(get_by_id=AsyncMock(return_value=task_log))
    relation_resolver = SimpleNamespace(
        unpack_args_kwargs=Mock(return_value=([1, 2], {"tenant_id": 9}))
    )
    retry_task = Mock(return_value="retry-task-77")

    monkeypatch.setattr(
        tasks_module.AdminTaskController,
        "get_service",
        _return(service),
    )
    monkeypatch.setattr(
        tasks_module,
        "TaskLogRelationService",
        _return(relation_resolver),
    )
    monkeypatch.setattr(tasks_module.TaskManagerService, "retry_task", retry_task)

    app = _build_test_app(SimpleNamespace(), tasks_module)

    with TestClient(app) as client:
        response = client.post("/tasks/7/retry")

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 0
    assert payload["data"] == {"new_task_id": "retry-task-77"}
    service.get_by_id.assert_awaited_once_with(7)
    relation_resolver.unpack_args_kwargs.assert_called_once_with(task_log.args_summary)
    retry_task.assert_called_once_with(
        task_name="app.tasks.system.nightly_cleanup",
        args=[1, 2],
        kwargs={"tenant_id": 9},
        queue="scheduled",
    )


def test_active_tasks_route_wraps_manager_payload(monkeypatch) -> None:
    tasks_module = _load_tasks_module()
    monkeypatch.setattr(tasks_module.AdminTaskController, "_instance", None)
    monkeypatch.setattr(tasks_module.AdminTaskController, "_router", None)

    active_tasks = Mock(
        return_value=[
            {
                "task_id": "task-1",
                "task_name": "nightly-cleanup",
                "worker": "worker-a",
                "started_at": 1712799900.0,
            }
        ]
    )
    monkeypatch.setattr(tasks_module.TaskManagerService, "get_active_tasks", active_tasks)

    app = _build_test_app(SimpleNamespace(), tasks_module)

    with TestClient(app) as client:
        response = client.get("/tasks/active")

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 0
    assert payload["data"] == [
        {
            "task_id": "task-1",
            "task_name": "nightly-cleanup",
            "worker": "worker-a",
            "started_at": 1712799900.0,
        }
    ]
    active_tasks.assert_called_once_with()
