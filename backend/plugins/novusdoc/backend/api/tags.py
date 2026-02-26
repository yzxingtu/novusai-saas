"""
NovusDoc 标签 API handlers
"""

from __future__ import annotations

from sqlalchemy import select

from app.core.logging import get_logger

from ..models.tag import NovusdocTag

logger = get_logger("plugin.novusdoc.api")


async def list_tags(request, db, ctx):
    """GET /tags — 标签列表"""
    tenant_id = ctx.get_current_tenant_id()
    if not tenant_id:
        return {"error": "tenant_id required", "code": 4010}

    result = await db.execute(
        select(NovusdocTag).where(
            NovusdocTag.tenant_id == tenant_id,
            NovusdocTag.is_deleted.is_(False),
        ).order_by(NovusdocTag.name)
    )
    rows = result.scalars().all()

    items = [
        {"id": t.id, "name": t.name, "color": t.color}
        for t in rows
    ]
    return {"items": items, "total": len(items)}


async def create_tag(request, db, ctx):
    """POST /tags — 创建标签"""
    tenant_id = ctx.get_current_tenant_id()
    if not tenant_id:
        return {"error": "tenant_id required", "code": 4010}

    body = await request.json()
    name = body.get("name", "").strip()
    if not name:
        return {"error": "name is required", "code": 4001}

    # 检查重复
    existing = await db.execute(
        select(NovusdocTag).where(
            NovusdocTag.tenant_id == tenant_id,
            NovusdocTag.name == name,
            NovusdocTag.is_deleted.is_(False),
        )
    )
    if existing.scalar_one_or_none():
        return {"error": "tag already exists", "code": 4220}

    tag = NovusdocTag(
        tenant_id=tenant_id,
        name=name,
        color=body.get("color"),
    )
    db.add(tag)
    await db.flush()
    await db.refresh(tag)
    await db.commit()

    return {"id": tag.id, "name": tag.name, "color": tag.color}


async def delete_tag(request, db, ctx):
    """DELETE /tags/{id} — 删除标签"""
    tenant_id = ctx.get_current_tenant_id()
    if not tenant_id:
        return {"error": "tenant_id required", "code": 4010}

    tag_id_str = request.path_params.get("id")
    if not tag_id_str:
        return {"error": "tag id required", "code": 4001}

    try:
        tag_id = int(tag_id_str)
    except (ValueError, TypeError):
        return {"error": "invalid tag id", "code": 4001}

    result = await db.execute(
        select(NovusdocTag).where(
            NovusdocTag.id == tag_id,
            NovusdocTag.tenant_id == tenant_id,
            NovusdocTag.is_deleted.is_(False),
        )
    )
    tag = result.scalar_one_or_none()
    if not tag:
        return {"error": "tag not found", "code": 4040, "status_code": 404}

    tag.soft_delete(level="tenant")
    await db.flush()
    await db.commit()

    return {"message": "deleted"}
