"""DataForge Studio — 项目服务"""
from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_model import utc_now

from ..models.project import NccProject


async def list_projects(db: AsyncSession, *, search: str | None = None,
                        page: int = 1, size: int = 20, sort: str = "-created_at",
                        ) -> tuple[list[dict[str, Any]], int]:
    base = select(NccProject).where(NccProject.is_deleted.is_(False))
    if search:
        base = base.where(NccProject.name.ilike(f"%{search}%"))
    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar() or 0
    desc_sort = sort.startswith("-")
    col_name = sort.lstrip("-")
    _sortable = {"id", "name", "display_name", "created_at", "updated_at"}
    if col_name not in _sortable:
        col_name = "created_at"
    col = getattr(NccProject, col_name, NccProject.created_at)
    base = base.order_by(col.desc() if desc_sort else col.asc())
    rows = (await db.execute(base.offset((page - 1) * size).limit(size))).scalars().all()
    return [_to_dict(r) for r in rows], total


async def get_project(db: AsyncSession, project_id: int) -> dict[str, Any] | None:
    obj = await db.get(NccProject, project_id)
    return _to_dict(obj) if obj and not obj.is_deleted else None


async def create_project(db: AsyncSession, data: dict[str, Any]) -> dict[str, Any]:
    obj = NccProject(name=data["name"],
                     display_name=data.get("display_name") or data["name"],
                     description=data.get("description"),
                     color=data.get("color"),
                     icon=data.get("icon", "lucide:database"))
    db.add(obj)
    await db.flush()
    return _to_dict(obj)


async def update_project(db: AsyncSession, project_id: int,
                         data: dict[str, Any]) -> dict[str, Any] | None:
    obj = await db.get(NccProject, project_id)
    if obj is None or obj.is_deleted:
        return None
    for f in ("name", "display_name", "description", "color", "icon"):
        if f in data:
            setattr(obj, f, data[f])
    obj.updated_at = utc_now()
    await db.flush()
    return _to_dict(obj)


async def delete_project(db: AsyncSession, project_id: int) -> bool:
    obj = await db.get(NccProject, project_id)
    if obj is None or obj.is_deleted:
        return False
    obj.soft_delete(level="admin")
    await db.flush()
    return True


def _to_dict(obj: NccProject) -> dict[str, Any]:
    return {"id": obj.id, "name": obj.name, "display_name": obj.display_name,
            "description": obj.description, "color": obj.color, "icon": obj.icon,
            "created_at": obj.created_at.isoformat() if obj.created_at else None,
            "updated_at": obj.updated_at.isoformat() if obj.updated_at else None}
