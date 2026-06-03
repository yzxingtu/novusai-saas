"""NovusDoc tag service / NovusDoc 标签服务"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.data_permission import (
    apply_data_permission_if_needed,
    enrich_create_data_with_data_permission,
)


async def list_tags(
    db: AsyncSession,
    tenant_id: int,
) -> list[dict[str, Any]]:
    from ..models.tag import NovusdocTag

    stmt = apply_data_permission_if_needed(
        select(NovusdocTag)
        .where(
            NovusdocTag.tenant_id == tenant_id,
            NovusdocTag.is_deleted.is_(False),
        )
        .order_by(NovusdocTag.name),
        NovusdocTag,
    )
    result = await db.execute(stmt)
    tags = result.scalars().all()
    return [{"id": t.id, "name": t.name, "color": t.color} for t in tags]


async def create_tag(
    db: AsyncSession,
    tenant_id: int,
    data: dict[str, Any],
) -> dict[str, Any]:
    from ..models.tag import NovusdocTag

    create_payload = {
        "tenant_id": tenant_id,
        "name": data["name"],
        "color": data.get("color"),
    }
    if data.get("created_by") is not None:
        create_payload["created_by"] = data["created_by"]
    tag = NovusdocTag(
        **enrich_create_data_with_data_permission(
            NovusdocTag,
            create_payload,
        )
    )
    db.add(tag)
    await db.flush()
    await db.refresh(tag)
    return {"id": tag.id, "name": tag.name, "color": tag.color}


async def delete_tag(
    db: AsyncSession,
    tenant_id: int,
    tag_id: int,
) -> bool:
    from ..models.tag import NovusdocTag

    stmt = apply_data_permission_if_needed(
        select(NovusdocTag).where(
            NovusdocTag.id == tag_id,
            NovusdocTag.tenant_id == tenant_id,
            NovusdocTag.is_deleted.is_(False),
        ),
        NovusdocTag,
    )
    result = await db.execute(stmt)
    tag = result.scalar_one_or_none()
    if not tag:
        return False

    tag.is_deleted = True
    await db.flush()
    return True
