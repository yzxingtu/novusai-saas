"""NovusDoc tag API handlers / NovusDoc 标签 API 处理器"""

from __future__ import annotations

from .documents import _resolve_tenant_id


async def list_tags(request, db, ctx):
    tenant_id = _resolve_tenant_id(request, ctx)

    from ..services.tag_service import list_tags as _list

    tags = await _list(db, tenant_id)
    return {"items": tags, "total": len(tags)}


async def create_tag(request, db, ctx):
    tenant_id = _resolve_tenant_id(request, ctx)

    body = await request.json()
    from ..services.tag_service import create_tag as _create

    tag = await _create(db, tenant_id, body)
    return {"tag": tag}


async def delete_tag(request, db, ctx):
    tenant_id = _resolve_tenant_id(request, ctx)

    tag_id = int(request.path_params["tag_id"])
    from ..services.tag_service import delete_tag as _delete

    ok = await _delete(db, tenant_id, tag_id)
    if not ok:
        return {"error": "Tag not found", "status_code": 404}
    return {"message": "Deleted"}
