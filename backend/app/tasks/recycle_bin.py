"""
Recycle-bin scheduled task / 回收站定时任务
"""

from __future__ import annotations

import asyncio
import time
from collections import defaultdict
from datetime import timedelta
from typing import Any

from sqlalchemy import select

from app.api.shared.recycle_bin_registry import (
    get_delete_scope,
    get_model,
    get_module_codes_for_side,
    get_service,
    get_tenant_field_name,
)
from app.core.base_model import utc_now
from app.core.config import settings
from app.core.i18n import _
from app.core.logging import LogManager
from app.enums.common import RecycleStageEnum
from app.tasks.async_db import task_async_session as _task_async_session
from app.tasks.base import BaseTask, register_task

logger = LogManager.get_logger("task")

_SIDE_ORDER: tuple[str, ...] = ("tenant", "admin")
_BATCH_SIZE = 100


def _resolve_retention_days(
    *,
    retention_days: int | None,
    module_retention_days: int | None,
    global_retention_days: int | None,
) -> tuple[int, int]:
    if retention_days is not None:
        return retention_days, retention_days

    return (
        module_retention_days or settings.RECYCLE_BIN_MODULE_RETENTION_DAYS,
        global_retention_days or settings.RECYCLE_BIN_GLOBAL_RETENTION_DAYS,
    )


async def _fetch_expired_rows(
    db: Any,
    *,
    module_code: str,
    side: str,
    recycle_stage: str,
    cutoff,
    limit: int = _BATCH_SIZE,
) -> list[dict[str, int | None]]:
    model_cls = get_model(module_code)
    tenant_field = get_tenant_field_name(model_cls) if side == "tenant" else None
    time_field_name = (
        "deleted_at"
        if recycle_stage == RecycleStageEnum.MODULE.value
        else "promoted_to_global_at"
    )
    time_field = getattr(model_cls, time_field_name)

    columns = [model_cls.id]
    if tenant_field:
        columns.append(getattr(model_cls, tenant_field).label("tenant_id"))

    stmt = (
        select(*columns)
        .where(
            model_cls.is_deleted.is_(True),
            model_cls.delete_level == get_delete_scope(side),
            model_cls.recycle_stage == recycle_stage,
            time_field.is_not(None),
            time_field < cutoff,
        )
        .order_by(time_field.asc(), model_cls.id.asc())
        .limit(limit)
    )
    rows = (await db.execute(stmt)).all()
    result: list[dict[str, int | None]] = []
    for row in rows:
        result.append(
            {
                "id": int(row[0]),
                "tenant_id": int(row[1])
                if len(row) > 1 and row[1] is not None
                else None,
            }
        )
    return result


async def _promote_rows(
    db: Any,
    *,
    module_code: str,
    side: str,
    rows: list[dict[str, int | None]],
) -> int:
    if not rows:
        return 0

    success_count = 0
    if side == "admin":
        service = get_service(module_code, side, db)
        for row in rows:
            item_id = int(row["id"])
            try:
                instance = await service.promote_to_global(item_id)
                if instance:
                    await db.commit()
                    success_count += 1
                else:
                    await db.rollback()
            except Exception as exc:
                await db.rollback()
                logger.error(
                    "Recycle-bin promote failed module={} side={} item_id={} error={}",
                    module_code,
                    side,
                    item_id,
                    exc,
                )
        return success_count

    grouped: dict[int, list[int]] = defaultdict(list)
    for row in rows:
        tenant_id = row.get("tenant_id")
        if tenant_id is None:
            logger.warning(
                "Recycle-bin promote skipped module={} side={} item_id={} reason=missing_tenant_id",
                module_code,
                side,
                row["id"],
            )
            continue
        grouped[int(tenant_id)].append(int(row["id"]))

    for tenant_id, ids in grouped.items():
        service = get_service(module_code, side, db, tenant_id=tenant_id)
        for item_id in ids:
            try:
                instance = await service.promote_to_global(item_id)
                if instance:
                    await db.commit()
                    success_count += 1
                else:
                    await db.rollback()
            except Exception as exc:
                await db.rollback()
                logger.error(
                    "Recycle-bin promote failed module={} side={} tenant_id={} item_id={} error={}",
                    module_code,
                    side,
                    tenant_id,
                    item_id,
                    exc,
                )

    return success_count


async def _permanently_delete_rows(
    db: Any,
    *,
    module_code: str,
    side: str,
    rows: list[dict[str, int | None]],
) -> int:
    if not rows:
        return 0

    success_count = 0
    if side == "admin":
        service = get_service(module_code, side, db)
        for row in rows:
            item_id = int(row["id"])
            try:
                result = await service.permanent_delete(item_id)
                if result:
                    await db.commit()
                    success_count += 1
                else:
                    await db.rollback()
            except Exception as exc:
                await db.rollback()
                logger.error(
                    "Recycle-bin final delete failed module={} side={} item_id={} error={}",
                    module_code,
                    side,
                    item_id,
                    exc,
                )
        return success_count

    grouped: dict[int, list[int]] = defaultdict(list)
    for row in rows:
        tenant_id = row.get("tenant_id")
        if tenant_id is None:
            logger.warning(
                "Recycle-bin final delete skipped module={} side={} item_id={} reason=missing_tenant_id",
                module_code,
                side,
                row["id"],
            )
            continue
        grouped[int(tenant_id)].append(int(row["id"]))

    for tenant_id, ids in grouped.items():
        service = get_service(module_code, side, db, tenant_id=tenant_id)
        for item_id in ids:
            try:
                result = await service.permanent_delete(item_id)
                if result:
                    await db.commit()
                    success_count += 1
                else:
                    await db.rollback()
            except Exception as exc:
                await db.rollback()
                logger.error(
                    "Recycle-bin final delete failed module={} side={} tenant_id={} item_id={} error={}",
                    module_code,
                    side,
                    tenant_id,
                    item_id,
                    exc,
                )

    return success_count


async def _run_cleanup(
    *,
    module_retention_days: int,
    global_retention_days: int,
) -> dict[str, Any]:
    module_cutoff = utc_now() - timedelta(days=module_retention_days)
    global_cutoff = utc_now() - timedelta(days=global_retention_days)
    promote_details: dict[str, int] = {}
    delete_details: dict[str, int] = {}
    total_promoted = 0
    total_deleted = 0

    async with _task_async_session() as db:
        for side in _SIDE_ORDER:
            for module_code in get_module_codes_for_side(side):
                module_promoted = 0
                while True:
                    rows = await _fetch_expired_rows(
                        db,
                        module_code=module_code,
                        side=side,
                        recycle_stage=RecycleStageEnum.MODULE.value,
                        cutoff=module_cutoff,
                    )
                    if not rows:
                        break
                    module_promoted += await _promote_rows(
                        db,
                        module_code=module_code,
                        side=side,
                        rows=rows,
                    )

                if module_promoted > 0:
                    promote_details[f"{side}:{module_code}"] = module_promoted
                    total_promoted += module_promoted
                    logger.info(
                        "Recycle-bin promote phase module={} side={} count={} cutoff={}",
                        module_code,
                        side,
                        module_promoted,
                        module_cutoff.isoformat(),
                    )

        for side in _SIDE_ORDER:
            for module_code in get_module_codes_for_side(side):
                module_deleted = 0
                while True:
                    rows = await _fetch_expired_rows(
                        db,
                        module_code=module_code,
                        side=side,
                        recycle_stage=RecycleStageEnum.GLOBAL.value,
                        cutoff=global_cutoff,
                    )
                    if not rows:
                        break
                    module_deleted += await _permanently_delete_rows(
                        db,
                        module_code=module_code,
                        side=side,
                        rows=rows,
                    )

                if module_deleted > 0:
                    delete_details[f"{side}:{module_code}"] = module_deleted
                    total_deleted += module_deleted
                    logger.info(
                        "Recycle-bin final-delete phase module={} side={} count={} cutoff={}",
                        module_code,
                        side,
                        module_deleted,
                        global_cutoff.isoformat(),
                    )

    return {
        "total_promoted": total_promoted,
        "total_deleted": total_deleted,
        "promote_details": promote_details,
        "delete_details": delete_details,
        "module_retention_days": module_retention_days,
        "global_retention_days": global_retention_days,
    }


@register_task(
    queue="scheduled",
    description=(
        "Advance expired module-stage recycle-bin records to global stage, "
        "then permanently delete expired global-stage records / "
        "推进模块回收站过期记录到总回收站，并清理总回收站过期记录"
    ),
    max_retries=1,
)
def cleanup_recycle_bin(
    self: BaseTask,
    retention_days: int | None = None,
    module_retention_days: int | None = None,
    global_retention_days: int | None = None,
) -> dict[str, Any]:
    """
    Execute two-stage recycle-bin cleanup / 执行两阶段回收站清理

    Args:
        retention_days: 兼容旧参数，若传入则同时覆盖两个阶段 / Backward-compatible override for both phases
        module_retention_days: 模块回收站保留天数 / Module recycle-bin retention days
        global_retention_days: 总回收站保留天数 / Global recycle-bin retention days
    """

    start = time.monotonic()
    resolved_module_days, resolved_global_days = _resolve_retention_days(
        retention_days=retention_days,
        module_retention_days=module_retention_days,
        global_retention_days=global_retention_days,
    )

    logger.info(
        "Recycle-bin cleanup start module_retention_days={} global_retention_days={}",
        resolved_module_days,
        resolved_global_days,
    )

    loop = asyncio.new_event_loop()
    try:
        result = loop.run_until_complete(
            _run_cleanup(
                module_retention_days=resolved_module_days,
                global_retention_days=resolved_global_days,
            )
        )
    finally:
        loop.close()

    elapsed = time.monotonic() - start
    logger.info(
        "{} promoted={} deleted={} module_retention_days={} global_retention_days={} elapsed={}s",
        _("task.log.recycle_bin_cleanup_total"),
        result["total_promoted"],
        result["total_deleted"],
        resolved_module_days,
        resolved_global_days,
        round(elapsed, 2),
    )

    return {
        **result,
        "elapsed_seconds": round(elapsed, 2),
    }


__all__ = ["cleanup_recycle_bin"]
