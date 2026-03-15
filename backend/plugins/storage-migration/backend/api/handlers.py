"""Storage Migration Plugin API Handlers / 接口/处理器

All handlers receive (request, ctx) or (request, db, ctx).
For cross-table queries (attachments), we use ctx._db (raw AsyncSession).
This is acceptable for admin_only first-party plugins."""

from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse


def _get_raw_db(ctx: object):
    """Extract raw AsyncSession from PluginContext. / 插件

    Migration plugin needs cross-table access (attachments + plugin tables).
    The raw session is used instead of PluginDbProxy which restricts to px_* tables."""
    return ctx._db  # type: ignore[attr-defined]


def _get_user_id(ctx: object) -> int:
    """Extract current user ID via PluginContext public API. / 接口/处理器"""
    uid = ctx.get_current_user_id()  # type: ignore[attr-defined]
    return uid or 0


def _safe_int(value: object, default: int) -> int:
    """Safely parse an integer value, returning default on failure. / 获取/返回"""
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


# ── Impact Analysis ────────────────────────────────────────────


async def get_impact_analysis(request: Request, ctx: object) -> JSONResponse:
    """GET /admin/plugins/storage-migration/api/impact-analysis / 接口/路由 — Query params: source_driver, target_driver, scope (optional)."""
    from ..services.migration_service import MigrationImpactAnalyzer

    source_driver = request.query_params.get("source_driver", "")
    target_driver = request.query_params.get("target_driver", "")

    if not source_driver or not target_driver:
        return JSONResponse(
            status_code=400,
            content={"code": 4001, "message": "source_driver and target_driver are required"},
        )

    scope = request.query_params.get("scope", "all")
    db = _get_raw_db(ctx)
    analyzer = MigrationImpactAnalyzer(db)
    result = await analyzer.analyze(source_driver, target_driver, scope)
    return result


# ── Task CRUD ──────────────────────────────────────────────────


async def create_migration_task(request: Request, ctx: object) -> JSONResponse:
    """POST /admin/plugins/storage-migration/api/tasks / 接口/路由 — Body: source_driver, target_driver, scope?, concurrency?."""
    from ..services.migration_service import StorageMigrationService

    try:
        body = await request.json()
    except Exception:
        return JSONResponse(
            status_code=400,
            content={"code": 4001, "message": "Invalid JSON body"},
        )

    source_driver = body.get("source_driver", "")
    target_driver = body.get("target_driver", "")
    scope = body.get("scope", "all")
    concurrency = _safe_int(body.get("concurrency"), 5)

    if not source_driver or not target_driver:
        return JSONResponse(
            status_code=400,
            content={"code": 4001, "message": "source_driver and target_driver are required"},
        )

    if concurrency < 1 or concurrency > 20:
        return JSONResponse(
            status_code=400,
            content={"code": 4001, "message": "concurrency must be between 1 and 20"},
        )

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
        return JSONResponse(
            status_code=422,
            content={"code": 4220, "message": result["error"]},
        )

    # Auto-start the migration task
    start_result = await service.start_task(result["task_id"])
    result["status"] = start_result.get("status", "pending")

    return result


async def list_migration_tasks(request: Request, ctx: object) -> JSONResponse:
    """GET /admin/plugins/storage-migration/api/tasks / 接口/路由 — Query params: page, page_size."""
    from ..services.migration_service import StorageMigrationService

    page = _safe_int(
        request.query_params.get("page[number]") or request.query_params.get("page"),
        1,
    )
    page_size = _safe_int(
        request.query_params.get("page[size]") or request.query_params.get("page_size"),
        20,
    )

    db = _get_raw_db(ctx)
    service = StorageMigrationService(db)
    result = await service.list_tasks(page=page, page_size=page_size)
    return result


async def get_migration_task(request: Request, ctx: object) -> JSONResponse:
    """GET /admin/plugins/storage-migration/api/tasks/{task_id} / 接口/路由 — Query params: log_status, log_page, log_page_size."""
    from ..services.migration_service import StorageMigrationService

    task_id = _safe_int(request.path_params.get("task_id"), 0)
    if not task_id:
        return JSONResponse(
            status_code=400,
            content={"code": 4001, "message": "task_id is required"},
        )

    db = _get_raw_db(ctx)
    service = StorageMigrationService(db)

    task = await service.get_task(task_id)
    if not task:
        return JSONResponse(
            status_code=404,
            content={"code": 4040, "message": "Task not found"},
        )

    # Optionally include logs
    log_status = request.query_params.get("log_status")
    log_page = _safe_int(
        request.query_params.get("log_page[number]") or request.query_params.get("log_page"),
        1,
    )
    log_page_size = _safe_int(
        request.query_params.get("log_page[size]") or request.query_params.get("log_page_size"),
        50,
    )

    logs = await service.get_task_logs(
        task_id, status_filter=log_status,
        page=log_page, page_size=log_page_size,
    )

    task["logs"] = logs
    return task


# ── Task Control ───────────────────────────────────────────────


async def pause_migration_task(request: Request, ctx: object) -> JSONResponse:
    """POST /admin/plugins/storage-migration/api/tasks/{task_id}/pause / 接口/路由"""
    from ..services.migration_service import StorageMigrationService

    task_id = _safe_int(request.path_params.get("task_id"), 0)
    if not task_id:
        return JSONResponse(
            status_code=400,
            content={"code": 4001, "message": "task_id is required"},
        )
    db = _get_raw_db(ctx)
    service = StorageMigrationService(db)

    result = await service.pause_task(task_id)
    if "error" in result:
        return JSONResponse(
            status_code=422,
            content={"code": 4220, "message": result["error"]},
        )
    return result


async def resume_migration_task(request: Request, ctx: object) -> JSONResponse:
    """POST /admin/plugins/storage-migration/api/tasks/{task_id}/resume / 接口/路由"""
    from ..services.migration_service import StorageMigrationService

    task_id = _safe_int(request.path_params.get("task_id"), 0)
    if not task_id:
        return JSONResponse(
            status_code=400,
            content={"code": 4001, "message": "task_id is required"},
        )
    db = _get_raw_db(ctx)
    service = StorageMigrationService(db)

    result = await service.resume_task(task_id)
    if "error" in result:
        return JSONResponse(
            status_code=422,
            content={"code": 4220, "message": result["error"]},
        )

    return result


async def cancel_migration_task(request: Request, ctx: object) -> JSONResponse:
    """POST /admin/plugins/storage-migration/api/tasks/{task_id}/cancel / 接口/路由"""
    from ..services.migration_service import StorageMigrationService

    task_id = _safe_int(request.path_params.get("task_id"), 0)
    if not task_id:
        return JSONResponse(
            status_code=400,
            content={"code": 4001, "message": "task_id is required"},
        )
    db = _get_raw_db(ctx)
    service = StorageMigrationService(db)

    result = await service.cancel_task(task_id)
    if "error" in result:
        return JSONResponse(
            status_code=422,
            content={"code": 4220, "message": result["error"]},
        )
    return result


# ── Retry & Rollback ──────────────────────────────────────────


async def retry_failed_files(request: Request, ctx: object) -> JSONResponse:
    """POST /admin/plugins/storage-migration/api/tasks/{task_id}/retry-failed / 接口/路由"""
    from ..services.migration_service import StorageMigrationService

    task_id = _safe_int(request.path_params.get("task_id"), 0)
    if not task_id:
        return JSONResponse(
            status_code=400,
            content={"code": 4001, "message": "task_id is required"},
        )
    db = _get_raw_db(ctx)
    service = StorageMigrationService(db)

    result = await service.retry_failed(task_id)
    if "error" in result:
        return JSONResponse(
            status_code=422,
            content={"code": 4220, "message": result["error"]},
        )
    return result


async def rollback_migration_task(request: Request, ctx: object) -> JSONResponse:
    """POST /admin/plugins/storage-migration/api/tasks/{task_id}/rollback / 接口/路由"""
    from ..services.migration_service import StorageMigrationService

    task_id = _safe_int(request.path_params.get("task_id"), 0)
    if not task_id:
        return JSONResponse(
            status_code=400,
            content={"code": 4001, "message": "task_id is required"},
        )
    db = _get_raw_db(ctx)
    service = StorageMigrationService(db)

    result = await service.rollback_task(task_id)
    if "error" in result:
        return JSONResponse(
            status_code=422,
            content={"code": 4220, "message": result["error"]},
        )
    return result


async def cleanup_source_files(request: Request, ctx: object) -> JSONResponse:
    """DELETE /admin/plugins/storage-migration/api/tasks/{task_id}/source-files / 接口/路由"""
    from ..services.migration_service import StorageMigrationService

    task_id = _safe_int(request.path_params.get("task_id"), 0)
    if not task_id:
        return JSONResponse(
            status_code=400,
            content={"code": 4001, "message": "task_id is required"},
        )
    db = _get_raw_db(ctx)
    service = StorageMigrationService(db)

    result = await service.cleanup_source_files(task_id)
    if "error" in result:
        return JSONResponse(
            status_code=422,
            content={"code": 4220, "message": result["error"]},
        )
    return result
