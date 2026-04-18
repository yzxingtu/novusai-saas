from __future__ import annotations

import importlib.util
from datetime import date, datetime
from pathlib import Path
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.deps import get_current_active_admin, get_db


def _load_system_logs_module():
    module_path = (
        Path(__file__).resolve().parent.parent
        / "app"
        / "api"
        / "admin"
        / "system_logs.py"
    )
    spec = importlib.util.spec_from_file_location(
        "test_admin_system_logs_module",
        module_path,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec is not None
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _build_test_app(mock_db, system_logs_module) -> FastAPI:
    controller = system_logs_module.AdminSystemLogController
    app = FastAPI()

    @app.middleware("http")
    async def inject_permissions(request, call_next):
        request.state.user_permissions = {
            "system_log:stats",
            "system_log:categories",
            "system_log:files",
            "system_log:read",
            "system_log:download",
            "system_log:delete",
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


def _stats_payload():
    return {
        "total_files": 3,
        "total_size": 1024,
        "categories": [
            {
                "code": "app",
                "name": "Application",
                "description": "Application logs",
                "file_count": 2,
                "total_size": 900,
            }
        ],
    }


def _read_missing_file(*_args, **_kwargs):
    return None


def _read_demo_file(*_args, **_kwargs):
    return SimpleNamespace(
        filename="app.log",
        category="app",
        scope="current_file",
        lines=["line-1", "line-2"],
        items=[
            SimpleNamespace(
                file_name="app.log",
                line_number=1,
                content="line-1",
            ),
            SimpleNamespace(
                file_name="app.log",
                line_number=2,
                content="line-2",
            ),
        ],
        total_lines=2,
        total_entries=1,
        searched_files=1,
        page=1,
        page_size=100,
        has_more=False,
    )


def _category_item(**overrides):
    defaults = {
        "code": "app",
        "name": "Application",
        "description": "Application logs",
        "file_count": 2,
        "total_size": 900,
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _file_item(**overrides):
    defaults = {
        "name": "app.log",
        "category": "app",
        "size": 512,
        "modified_at": datetime(2026, 4, 11, 7, 0, 0),
        "is_current": True,
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def test_system_log_stats_route_returns_success_envelope(monkeypatch) -> None:
    from app.services.system import SystemLogService

    system_logs_module = _load_system_logs_module()
    monkeypatch.setattr(system_logs_module.AdminSystemLogController, "_instance", None)
    monkeypatch.setattr(system_logs_module.AdminSystemLogController, "_router", None)
    monkeypatch.setattr(
        SystemLogService,
        "get_log_stats",
        lambda _self: _stats_payload(),
    )

    app = _build_test_app(SimpleNamespace(), system_logs_module)

    with TestClient(app) as client:
        response = client.get("/system-logs/stats")

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 0
    assert payload["data"]["total_files"] == 3
    assert payload["data"]["categories"][0]["code"] == "app"


def test_system_log_categories_route_returns_items(monkeypatch) -> None:
    from app.services.system import SystemLogService

    system_logs_module = _load_system_logs_module()
    monkeypatch.setattr(system_logs_module.AdminSystemLogController, "_instance", None)
    monkeypatch.setattr(system_logs_module.AdminSystemLogController, "_router", None)
    monkeypatch.setattr(
        SystemLogService,
        "list_categories",
        lambda _self: [_category_item()],
    )

    app = _build_test_app(SimpleNamespace(), system_logs_module)

    with TestClient(app) as client:
        response = client.get("/system-logs/categories")

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 0
    assert payload["data"][0]["code"] == "app"
    assert payload["data"][0]["file_count"] == 2


def test_system_log_files_route_returns_items(monkeypatch) -> None:
    from app.services.system import SystemLogService

    system_logs_module = _load_system_logs_module()
    monkeypatch.setattr(system_logs_module.AdminSystemLogController, "_instance", None)
    monkeypatch.setattr(system_logs_module.AdminSystemLogController, "_router", None)
    monkeypatch.setattr(
        SystemLogService,
        "list_log_files",
        lambda _self, category=None: [_file_item(category=category or "app")],
    )

    app = _build_test_app(SimpleNamespace(), system_logs_module)

    with TestClient(app) as client:
        response = client.get("/system-logs/files?category=app")

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 0
    assert payload["data"][0]["name"] == "app.log"
    assert payload["data"][0]["category"] == "app"


def test_system_log_read_route_returns_404_when_file_missing(monkeypatch) -> None:
    from app.services.system import SystemLogService

    system_logs_module = _load_system_logs_module()
    monkeypatch.setattr(system_logs_module.AdminSystemLogController, "_instance", None)
    monkeypatch.setattr(system_logs_module.AdminSystemLogController, "_router", None)
    monkeypatch.setattr(
        SystemLogService,
        "read_log_file",
        _read_missing_file,
    )

    app = _build_test_app(SimpleNamespace(), system_logs_module)

    with TestClient(app) as client:
        response = client.get("/system-logs/files/missing.log/content")

    assert response.status_code == 404
    assert response.json()["detail"]


def test_system_log_delete_route_returns_400_for_current_file(monkeypatch) -> None:
    from app.services.system import SystemLogService

    system_logs_module = _load_system_logs_module()
    monkeypatch.setattr(system_logs_module.AdminSystemLogController, "_instance", None)
    monkeypatch.setattr(system_logs_module.AdminSystemLogController, "_router", None)
    log_dir = Path("E:/git_clone/novusai-saas-yudi/.codex-temp/pytest-temp/system-logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "app.log"
    log_file.write_text("demo", encoding="utf-8")

    monkeypatch.setattr(
        SystemLogService,
        "get_log_file_path",
        lambda _self, filename: Path(log_file) if filename == "app.log" else None,
    )
    monkeypatch.setattr(
        SystemLogService,
        "delete_log_file",
        lambda _self, _filename: False,
    )

    app = _build_test_app(SimpleNamespace(), system_logs_module)

    with TestClient(app) as client:
        response = client.delete("/system-logs/files/app.log")

    assert response.status_code == 400
    assert response.json()["detail"]


def test_system_log_read_route_returns_log_payload(monkeypatch) -> None:
    from app.services.system import SystemLogService

    system_logs_module = _load_system_logs_module()
    monkeypatch.setattr(system_logs_module.AdminSystemLogController, "_instance", None)
    monkeypatch.setattr(system_logs_module.AdminSystemLogController, "_router", None)
    monkeypatch.setattr(
        SystemLogService,
        "read_log_file",
        _read_demo_file,
    )

    app = _build_test_app(SimpleNamespace(), system_logs_module)

    with TestClient(app) as client:
        response = client.get("/system-logs/files/app.log/content?page=1&page_size=100")

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 0
    assert payload["data"]["filename"] == "app.log"
    assert payload["data"]["category"] == "app"
    assert payload["data"]["lines"] == ["line-1", "line-2"]
    assert payload["data"]["items"][0]["file_name"] == "app.log"
    assert payload["data"]["total_lines"] == 2


def test_system_log_read_route_passes_search_filters(monkeypatch) -> None:
    from app.services.system import SystemLogService

    system_logs_module = _load_system_logs_module()
    monkeypatch.setattr(system_logs_module.AdminSystemLogController, "_instance", None)
    monkeypatch.setattr(system_logs_module.AdminSystemLogController, "_router", None)

    captured: dict[str, object] = {}

    def _read_with_filters(_self, **kwargs):
        captured.update(kwargs)
        return _read_demo_file()

    monkeypatch.setattr(SystemLogService, "read_log_file", _read_with_filters)

    app = _build_test_app(SimpleNamespace(), system_logs_module)

    with TestClient(app) as client:
        response = client.get(
            "/system-logs/files/app.log/content",
            params={
                "page": 2,
                "page_size": 50,
                "reverse": "false",
                "keyword": "trace",
                "start_date": "2026-04-10",
                "end_date": "2026-04-12",
                "scope": "category",
            },
        )

    assert response.status_code == 200
    assert captured == {
        "filename": "app.log",
        "page": 2,
        "page_size": 50,
        "reverse": False,
        "keyword": "trace",
        "start_date": date(2026, 4, 10),
        "end_date": date(2026, 4, 12),
        "scope": "category",
    }


def test_system_log_read_route_rejects_invalid_date_range(monkeypatch) -> None:
    system_logs_module = _load_system_logs_module()
    monkeypatch.setattr(system_logs_module.AdminSystemLogController, "_instance", None)
    monkeypatch.setattr(system_logs_module.AdminSystemLogController, "_router", None)

    app = _build_test_app(SimpleNamespace(), system_logs_module)

    with TestClient(app) as client:
        response = client.get(
            "/system-logs/files/app.log/content",
            params={
                "start_date": "2026-04-12",
                "end_date": "2026-04-10",
            },
        )

    assert response.status_code == 400
    assert response.json()["detail"]


def test_system_log_download_route_returns_file_response(monkeypatch) -> None:
    from app.services.system import SystemLogService

    system_logs_module = _load_system_logs_module()
    monkeypatch.setattr(system_logs_module.AdminSystemLogController, "_instance", None)
    monkeypatch.setattr(system_logs_module.AdminSystemLogController, "_router", None)
    log_dir = Path("E:/git_clone/novusai-saas-yudi/.codex-temp/pytest-temp/system-logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "download.log"
    log_file.write_text("download-demo", encoding="utf-8")

    monkeypatch.setattr(
        SystemLogService,
        "get_log_file_path",
        lambda _self, filename: Path(log_file) if filename == "download.log" else None,
    )

    app = _build_test_app(SimpleNamespace(), system_logs_module)

    with TestClient(app) as client:
        response = client.get("/system-logs/files/download.log/download")

    assert response.status_code == 200
    assert "download.log" in response.headers["content-disposition"]
