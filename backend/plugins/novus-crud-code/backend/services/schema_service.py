"""DataForge Studio — 表结构服务"""
from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_model import utc_now
from app.core.i18n import _

from ..models.table_relation import NccTableRelation
from ..models.table_schema import NccTableSchema


async def list_schemas(db: AsyncSession, project_id: int, *,
                       page: int = 1, size: int = 50,
                       ) -> tuple[list[dict[str, Any]], int]:
    base = select(NccTableSchema).where(
        NccTableSchema.project_id == project_id,
        NccTableSchema.is_deleted.is_(False),
    )
    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar() or 0
    rows = (await db.execute(
        base.order_by(NccTableSchema.sort_order.asc(), NccTableSchema.created_at.asc())
            .offset((page - 1) * size).limit(size)
    )).scalars().all()
    return [_schema_to_dict(r) for r in rows], total


async def get_schema(db: AsyncSession, project_id: int, schema_id: int,
                     ) -> dict[str, Any] | None:
    obj = await db.get(NccTableSchema, schema_id)
    if obj is None or obj.is_deleted or obj.project_id != project_id:
        return None
    return _schema_to_dict(obj)


async def create_schema(db: AsyncSession, project_id: int,
                        data: dict[str, Any]) -> dict[str, Any]:
    obj = NccTableSchema(
        project_id=project_id,
        name=data["name"],
        display_name=data.get("display_name") or data["name"],
        description=data.get("description"),
        schema_config=data.get("schema_config", {"fields": []}),
        form_config=data.get("form_config", {}),
        ui_config=data.get("ui_config", {}),
        sort_order=data.get("sort_order", 0),
    )
    db.add(obj)
    await db.flush()
    return _schema_to_dict(obj)


async def update_schema(db: AsyncSession, project_id: int, schema_id: int,
                        data: dict[str, Any]) -> dict[str, Any] | None:
    obj = await db.get(NccTableSchema, schema_id)
    if obj is None or obj.is_deleted or obj.project_id != project_id:
        return None
    for f in ("name", "display_name", "description", "schema_config",
              "form_config", "ui_config", "sort_order"):
        if f in data:
            setattr(obj, f, data[f])
    obj.updated_at = utc_now()
    await db.flush()
    return _schema_to_dict(obj)


async def delete_schema(db: AsyncSession, project_id: int, schema_id: int) -> bool:
    obj = await db.get(NccTableSchema, schema_id)
    if obj is None or obj.is_deleted or obj.project_id != project_id:
        return False
    obj.soft_delete(level="admin")
    await db.flush()
    return True


# ── Relations ──────────────────────────────────────────────────────────────

async def list_relations(db: AsyncSession, project_id: int,
                         ) -> list[dict[str, Any]]:
    rows = (await db.execute(
        select(NccTableRelation).where(
            NccTableRelation.project_id == project_id,
            NccTableRelation.is_deleted.is_(False),
        ).order_by(NccTableRelation.created_at.asc())
    )).scalars().all()
    return [_relation_to_dict(r) for r in rows]


async def create_relation(db: AsyncSession, project_id: int,
                          data: dict[str, Any]) -> dict[str, Any]:
    from_id = int(data["from_schema_id"])
    to_id = int(data["to_schema_id"])
    # 验证两张表都属于当前 project，防止跨项目关联
    from_s = await db.get(NccTableSchema, from_id)
    to_s = await db.get(NccTableSchema, to_id)
    if not from_s or from_s.is_deleted or from_s.project_id != project_id:
        raise ValueError(
            _("plugin.novus-crud-code.error.from_schema_not_found").format(
                from_id=from_id,
                project_id=project_id,
            )
        )
    if not to_s or to_s.is_deleted or to_s.project_id != project_id:
        raise ValueError(
            _("plugin.novus-crud-code.error.to_schema_not_found").format(
                to_id=to_id,
                project_id=project_id,
            )
        )
    obj = NccTableRelation(
        project_id=project_id,
        from_schema_id=from_id,
        to_schema_id=to_id,
        from_field=data["from_field"],
        to_field=data["to_field"],
        relation_type=data.get("relation_type", "one_to_many"),
        label=data.get("label"),
    )
    db.add(obj)
    await db.flush()
    return _relation_to_dict(obj)


async def update_relation(db: AsyncSession, project_id: int, relation_id: int,
                          data: dict[str, Any]) -> dict[str, Any] | None:
    obj = await db.get(NccTableRelation, relation_id)
    if obj is None or obj.is_deleted or obj.project_id != project_id:
        return None
    for f in ("from_field", "to_field", "relation_type", "label"):
        if f in data:
            setattr(obj, f, data[f])
    obj.updated_at = utc_now()
    await db.flush()
    return _relation_to_dict(obj)


async def delete_relation(db: AsyncSession, project_id: int, relation_id: int) -> bool:
    obj = await db.get(NccTableRelation, relation_id)
    if obj is None or obj.is_deleted or obj.project_id != project_id:
        return False
    obj.soft_delete(level="admin")
    await db.flush()
    return True


def _schema_to_dict(obj: NccTableSchema) -> dict[str, Any]:
    return {"id": obj.id, "project_id": obj.project_id, "name": obj.name,
            "display_name": obj.display_name, "description": obj.description,
            "schema_config": obj.schema_config, "form_config": obj.form_config,
            "ui_config": obj.ui_config, "sort_order": obj.sort_order,
            "created_at": obj.created_at.isoformat() if obj.created_at else None,
            "updated_at": obj.updated_at.isoformat() if obj.updated_at else None}


def _relation_to_dict(obj: NccTableRelation) -> dict[str, Any]:
    return {"id": obj.id, "project_id": obj.project_id,
            "from_schema_id": obj.from_schema_id, "to_schema_id": obj.to_schema_id,
            "from_field": obj.from_field, "to_field": obj.to_field,
            "relation_type": obj.relation_type, "label": obj.label,
            "created_at": obj.created_at.isoformat() if obj.created_at else None}
