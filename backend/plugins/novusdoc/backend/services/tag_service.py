"""
NovusDoc 标签服务

负责标签 CRUD 业务逻辑，handler 层不直接操作 DB。
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select

from ..models.tag import NovusdocTag


async def list_tags(db, tenant_id: int) -> list[dict[str, Any]]:
    """标签列表"""
    result = await db.execute(
        select(NovusdocTag).where(
            NovusdocTag.tenant_id == tenant_id,
            NovusdocTag.is_deleted.is_(False),
        ).order_by(NovusdocTag.name)
    )
    rows = result.scalars().all()
    return [{"id": t.id, "name": t.name, "color": t.color} for t in rows]


async def create_tag(
    db, tenant_id: int, *, name: str, color: str | None = None
) -> dict[str, Any] | None:
    """
    创建标签。

    Returns:
        标签 dict，若已存在同名标签则返回 None。
    """
    existing = await db.execute(
        select(NovusdocTag).where(
            NovusdocTag.tenant_id == tenant_id,
            NovusdocTag.name == name,
            NovusdocTag.is_deleted.is_(False),
        )
    )
    if existing.scalar_one_or_none():
        return None

    tag = NovusdocTag(tenant_id=tenant_id, name=name, color=color)
    db.add(tag)
    await db.flush()
    await db.refresh(tag)
    return {"id": tag.id, "name": tag.name, "color": tag.color}


async def delete_tag(db, tenant_id: int, tag_id: int) -> bool:
    """软删除标签"""
    result = await db.execute(
        select(NovusdocTag).where(
            NovusdocTag.id == tag_id,
            NovusdocTag.tenant_id == tenant_id,
            NovusdocTag.is_deleted.is_(False),
        )
    )
    tag = result.scalar_one_or_none()
    if not tag:
        return False
    tag.soft_delete(level="tenant")
    await db.flush()
    return True
