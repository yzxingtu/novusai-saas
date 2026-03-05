"""DataForge Studio — 数据记录服务"""
from __future__ import annotations

from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_model import utc_now

from ..models.record import NccRecord


async def list_records(db: AsyncSession, project_id: int, schema_id: int, *,
                       page: int = 1, size: int = 50,
                       sort: str = "-created_at",
                       ) -> tuple[list[dict[str, Any]], int]:
    base = select(NccRecord).where(
        NccRecord.schema_id == schema_id,
        NccRecord.project_id == project_id,
        NccRecord.is_deleted.is_(False),
    )
    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar() or 0
    desc_sort = sort.startswith("-")
    col_name = sort.lstrip("-")
    _sortable = {"id", "sort_order", "created_at", "updated_at"}
    if col_name not in _sortable:
        col_name = "created_at"
    col = getattr(NccRecord, col_name, NccRecord.created_at)
    rows = (await db.execute(
        base.order_by(col.desc() if desc_sort else col.asc())
            .offset((page - 1) * size).limit(size)
    )).scalars().all()
    return [_to_dict(r) for r in rows], total


async def get_record(db: AsyncSession, project_id: int, schema_id: int,
                     record_id: int) -> dict[str, Any] | None:
    obj = await db.get(NccRecord, record_id)
    if obj is None or obj.is_deleted or obj.schema_id != schema_id or obj.project_id != project_id:
        return None
    return _to_dict(obj)


async def create_record(db: AsyncSession, project_id: int, schema_id: int,
                        data: dict[str, Any]) -> dict[str, Any]:
    obj = NccRecord(
        project_id=project_id,
        schema_id=schema_id,
        data=data.get("data", {}),
        sort_order=data.get("sort_order", 0),
    )
    db.add(obj)
    await db.flush()
    return _to_dict(obj)


async def update_record(db: AsyncSession, project_id: int, schema_id: int,
                        record_id: int, data: dict[str, Any]) -> dict[str, Any] | None:
    obj = await db.get(NccRecord, record_id)
    if obj is None or obj.is_deleted or obj.schema_id != schema_id or obj.project_id != project_id:
        return None
    if "data" in data:
        obj.data = data["data"]
    if "sort_order" in data:
        obj.sort_order = data["sort_order"]
    obj.updated_at = utc_now()
    await db.flush()
    return _to_dict(obj)


async def delete_record(db: AsyncSession, project_id: int, schema_id: int,
                        record_id: int) -> bool:
    obj = await db.get(NccRecord, record_id)
    if obj is None or obj.is_deleted or obj.schema_id != schema_id or obj.project_id != project_id:
        return False
    obj.soft_delete(level="admin")
    await db.flush()
    return True


async def bulk_delete_records(db: AsyncSession, project_id: int, schema_id: int,
                              record_ids: list[int]) -> int:
    if not record_ids:
        return 0
    now = utc_now()
    result = await db.execute(
        update(NccRecord)
        .where(
            NccRecord.id.in_(record_ids),
            NccRecord.schema_id == schema_id,
            NccRecord.project_id == project_id,
            NccRecord.is_deleted.is_(False),
        )
        .values(is_deleted=True, deleted_at=now, delete_level="admin", updated_at=now)
        .execution_options(synchronize_session="fetch")
    )
    return result.rowcount


def _to_dict(obj: NccRecord) -> dict[str, Any]:
    return {"id": obj.id, "schema_id": obj.schema_id, "project_id": obj.project_id,
            "data": obj.data, "sort_order": obj.sort_order,
            "created_at": obj.created_at.isoformat() if obj.created_at else None,
            "updated_at": obj.updated_at.isoformat() if obj.updated_at else None}
