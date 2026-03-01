"""
NovusDoc 标签 API handlers

分层规范：handler 仅负责参数解析与响应封装，业务逻辑委托给 tag_service。
"""

from __future__ import annotations

from ..services import tag_service
from .utils import resolve_tenant_id, safe_int


async def list_tags(request, db, ctx):
    """GET /tags — 标签列表"""
    tenant_id = resolve_tenant_id(ctx)
    if tenant_id is None:
        return {"error": "tenant_id required", "code": 4010, "status_code": 401}

    items = await tag_service.list_tags(db, tenant_id)
    return {"items": items, "total": len(items)}


async def create_tag(request, db, ctx):
    """POST /tags — 创建标签"""
    tenant_id = resolve_tenant_id(ctx)
    if tenant_id is None:
        return {"error": "tenant_id required", "code": 4010, "status_code": 401}

    body = await request.json()
    name = body.get("name", "").strip()
    if not name:
        return {"error": "name is required", "code": 4001, "status_code": 400}

    result = await tag_service.create_tag(
        db, tenant_id, name=name, color=body.get("color"),
    )
    if result is None:
        return {"error": "tag already exists", "code": 4220, "status_code": 422}

    await db.commit()
    return result


async def delete_tag(request, db, ctx):
    """DELETE /tags/{id} — 删除标签"""
    tenant_id = resolve_tenant_id(ctx)
    if tenant_id is None:
        return {"error": "tenant_id required", "code": 4010, "status_code": 401}

    tag_id, err = safe_int(request.path_params.get("id"), "tag id")
    if err:
        return err

    deleted = await tag_service.delete_tag(db, tenant_id, tag_id)
    if not deleted:
        return {"error": "tag not found", "code": 4040, "status_code": 404}

    await db.commit()
    return {"message": "deleted"}
