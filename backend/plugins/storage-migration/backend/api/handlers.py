"""Storage Migration Plugin API Handlers.

All handlers receive ``(request, ctx)``.
The plugin needs cross-table access (plugin tables + attachments), so it
uses the raw AsyncSession exposed by PluginContext.
"""

from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse

ALLOWED_TASK_STATUSES = {
    "pending",
    "running",
    "paused",
    "completed",
    "failed",
    "cancelled",
    "rolling_back",
}
ALLOWED_LOG_STATUSES = {"pending", "success", "failed", "skipped"}


def _bad_request(message: str, code: int = 4001) -> JSONResponse:
    return JSONResponse(status_code=400, content={"code": code, "message": message})


def _unprocessable(message: str, code: int = 4220) -> JSONResponse:
    return JSONResponse(status_code=422, content={"code": code, "message": message})


def _get_raw_db(ctx: object):
    """Extract raw AsyncSession from PluginContext."""
    return ctx._db  # type: ignore[attr-defined]


def _get_user_id(ctx: object) -> int:
    """Extract current user ID via PluginContext public API."""
    uid = ctx.get_current_user_id()  # type: ignore[attr-defined]
    return uid or 0


def _safe_int(value: object, default: int) -> int:
    """Safely parse an integer value, returning default on failure."""
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


def _normalize_scope(raw_scope: object) -> str:
    scope = str(raw_scope or "all").strip()
    if not scope or scope == "all":
        return "all"
    if not scope.startswith("tenant:"):
        raise ValueError("scope must be 'all' or 'tenant:{id}'")

    tenant_part = scope.split(":", 1)[1].strip()
    tenant_id = int(tenant_part)
    if tenant_id <= 0:
        raise ValueError("tenant scope id must be a positive integer")
    return f"tenant:{tenant_id}"


def _normalize_task_status(raw_status: object) -> str | None:
    status = str(raw_status or "").strip()
    if not status or status == "all":
        return None
    if status not in ALLOWED_TASK_STATUSES:
        raise ValueError("invalid task status filter")
    return status


def _normalize_log_status(raw_status: object) -> str | None:
    status = str(raw_status or "").strip()
    if not status or status == "all":
        return None
    if status not in ALLOWED_LOG_STATUSES:
        raise ValueError("invalid log status filter")
    return status


async def get_impact_analysis(request: Request, ctx: object) -> JSONResponse:
    """GET /admin/plugins/storage-migration/api/impact-analysis."""
    from ..services.migration_service import MigrationImpactAnalyzer

    source_driver = request.query_params.get("source_driver", "").strip()
    target_driver = request.query_params.get("target_driver", "").strip()

    if not source_driver or not target_driver:
        return _bad_request("source_driver and target_driver are required")

    try:
        scope = _normalize_scope(request.query_params.get("scope", "all"))
    except ValueError as exc:
        return _bad_request(str(exc))

    db = _get_raw_db(ctx)
    analyzer = MigrationImpactAnalyzer(db)

    try:
        result = await analyzer.analyze(source_driver, target_driver, scope)
    except ValueError as exc:
        return _bad_request(str(exc))

    return result


async def create_migration_task(request: Request, ctx: object) -> JSONResponse:
    """POST /admin/plugins/storage-migration/api/tasks."""
    from ..services.migration_service import StorageMigrationService

    try:
        body = await request.json()
    except Exception:
        return _bad_request("Invalid JSON body")

    source_driver = str(body.get("source_driver") or "").strip()
    target_driver = str(body.get("target_driver") or "").strip()
    concurrency = _safe_int(body.get("concurrency"), 5)

    if not source_driver or not target_driver:
        return _bad_request("source_driver and target_driver are required")
    if concurrency < 1 or concurrency > 20:
        return _bad_request("concurrency must be between 1 and 20")

    try:
        scope = _normalize_scope(body.get("scope", "all"))
    except ValueError as exc:
        return _bad_request(str(exc))

    db = _get_raw_db(ctx)
    service = StorageMigrationService(db)
    user_id = _get_user_id(ctx)

    result = await service.create_task(
        source_driver=source_driver,
        target_driver=target_driver,
        scope=scope,
        concurrency=concurrency,
        created_by=user_id,
    )

    if "error" in result:
        return _unprocessable(result["error"])

    start_result = await service.start_task(result["task_id"])
    if "error" in start_result:
        return _unprocessable(start_result["error"])

    result["status"] = start_result.get("status", "pending")
    return result


async def list_migration_tasks(request: Request, ctx: object) -> JSONResponse:
    """GET /admin/plugins/storage-migration/api/tasks."""
    from ..services.migration_service import StorageMigrationService

    page = _safe_int(
        request.query_params.get("page[number]") or request.query_params.get("page"),
        1,
    )
    page_size = _safe_int(
        request.query_params.get("page[size]") or request.query_params.get("page_size"),
        20,
    )
    page = max(page, 1)
    page_size = min(max(page_size, 1), 100)

    try:
        status_filter = _normalize_task_status(request.query_params.get("status"))
    except ValueError as exc:
        return _bad_request(str(exc))

    db = _get_raw_db(ctx)
    service = StorageMigrationService(db)
    result = await service.list_tasks(
        page=page,
        page_size=page_size,
        status_filter=status_filter,
    )
    return result


async def get_migration_task(request: Request, ctx: object) -> JSONResponse:
    """GET /admin/plugins/storage-migration/api/tasks/{task_id}."""
    from ..services.migration_service import StorageMigrationService

    task_id = _safe_int(request.path_params.get("task_id"), 0)
    if not task_id:
        return _bad_request("task_id is required")

    try:
        log_status = _normalize_log_status(request.query_params.get("log_status"))
    except ValueError as exc:
        return _bad_request(str(exc))

    log_page = _safe_int(
        request.query_params.get("log_page[number]") or request.query_params.get("log_page"),
        1,
    )
    log_page_size = _safe_int(
        request.query_params.get("log_page[size]") or request.query_params.get("log_page_size"),
        50,
    )
    log_page = max(log_page, 1)
    log_page_size = min(max(log_page_size, 1), 200)

    db = _get_raw_db(ctx)
    service = StorageMigrationService(db)

    task = await service.get_task(task_id)
    if not task:
        return JSONResponse(
            status_code=404,
            content={"code": 4040, "message": "Task not found"},
        )

    logs = await service.get_task_logs(
        task_id,
        status_filter=log_status,
        page=log_page,
        page_size=log_page_size,
    )
    task["logs"] = logs
    return task


async def pause_migration_task(request: Request, ctx: object) -> JSONResponse:
    """POST /admin/plugins/storage-migration/api/tasks/{task_id}/pause."""
    from ..services.migration_service import StorageMigrationService

    task_id = _safe_int(request.path_params.get("task_id"), 0)
    if not task_id:
        return _bad_request("task_id is required")

    db = _get_raw_db(ctx)
    service = StorageMigrationService(db)
    result = await service.pause_task(task_id)
    if "error" in result:
        return _unprocessable(result["error"])
    return result


async def resume_migration_task(request: Request, ctx: object) -> JSONResponse:
    """POST /admin/plugins/storage-migration/api/tasks/{task_id}/resume."""
    from ..services.migration_service import StorageMigrationService

    task_id = _safe_int(request.path_params.get("task_id"), 0)
    if not task_id:
        return _bad_request("task_id is required")

    db = _get_raw_db(ctx)
    service = StorageMigrationService(db)
    result = await service.resume_task(task_id)
    if "error" in result:
        return _unprocessable(result["error"])
    return result


async def cancel_migration_task(request: Request, ctx: object) -> JSONResponse:
    """POST /admin/plugins/storage-migration/api/tasks/{task_id}/cancel."""
    from ..services.migration_service import StorageMigrationService

    task_id = _safe_int(request.path_params.get("task_id"), 0)
    if not task_id:
        return _bad_request("task_id is required")

    db = _get_raw_db(ctx)
    service = StorageMigrationService(db)
    result = await service.cancel_task(task_id)
    if "error" in result:
        return _unprocessable(result["error"])
    return result


async def retry_failed_files(request: Request, ctx: object) -> JSONResponse:
    """POST /admin/plugins/storage-migration/api/tasks/{task_id}/retry-failed."""
    from ..services.migration_service import StorageMigrationService

    task_id = _safe_int(request.path_params.get("task_id"), 0)
    if not task_id:
        return _bad_request("task_id is required")

    db = _get_raw_db(ctx)
    service = StorageMigrationService(db)
    result = await service.retry_failed(task_id)
    if "error" in result:
        return _unprocessable(result["error"])
    return result


async def rollback_migration_task(request: Request, ctx: object) -> JSONResponse:
    """POST /admin/plugins/storage-migration/api/tasks/{task_id}/rollback."""
    from ..services.migration_service import StorageMigrationService

    task_id = _safe_int(request.path_params.get("task_id"), 0)
    if not task_id:
        return _bad_request("task_id is required")

    db = _get_raw_db(ctx)
    service = StorageMigrationService(db)
    result = await service.rollback_task(task_id)
    if "error" in result:
        return _unprocessable(result["error"])
    return result


async def cleanup_source_files(request: Request, ctx: object) -> JSONResponse:
    """DELETE /admin/plugins/storage-migration/api/tasks/{task_id}/source-files."""
    from ..services.migration_service import StorageMigrationService

    task_id = _safe_int(request.path_params.get("task_id"), 0)
    if not task_id:
        return _bad_request("task_id is required")

    db = _get_raw_db(ctx)
    service = StorageMigrationService(db)
    result = await service.cleanup_source_files(task_id)
    if "error" in result:
        return _unprocessable(result["error"])
    return result
