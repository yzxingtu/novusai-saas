"""
NovusDoc Pro 文档模板 API handlers
"""

from __future__ import annotations

from sqlalchemy import select

from app.core.logging import get_logger

from ..models.template import NovusdocProTemplate
from .utils import resolve_tenant_id
from .utils import safe_int as _safe_int

logger = get_logger("plugin.novusdoc-pro.api")


async def list_templates(request, db, ctx):
    """GET /templates"""
    tenant_id = resolve_tenant_id(ctx)
    if tenant_id is None:
        return {"error": "tenant_id required", "code": 4010, "status_code": 401}
    result = await db.execute(
        select(NovusdocProTemplate).where(
            NovusdocProTemplate.tenant_id == tenant_id,
            NovusdocProTemplate.is_deleted.is_(False),
        ).order_by(NovusdocProTemplate.sort_order)
    )
    rows = result.scalars().all()
    items = [
        {"id": t.id, "name": t.name, "description": t.description,
         "category": t.category, "cover_image": t.cover_image}
        for t in rows
    ]
    return {"items": items, "total": len(items)}


async def create_template(request, db, ctx):
    """POST /templates"""
    from ..services.license_gate import check_license_valid, license_required_error
    is_valid, license_info = await check_license_valid(ctx)
    if not is_valid:
        return license_required_error(license_info)

    tenant_id = resolve_tenant_id(ctx)
    if tenant_id is None:
        return {"error": "tenant_id required", "code": 4010, "status_code": 401}
    body = await request.json()
    template = NovusdocProTemplate(
        tenant_id=tenant_id, name=body.get("title") or body.get("name") or "",
        description=body.get("description"), content=body.get("content"),
        category=body.get("category"), creator_id=ctx.get_current_user_id(),
    )
    db.add(template)
    await db.flush()
    await db.refresh(template)
    await db.commit()
    return {"id": template.id, "name": template.name}


async def get_template(request, db, ctx):
    """GET /templates/{id}"""
    tenant_id = resolve_tenant_id(ctx)
    if tenant_id is None:
        return {"error": "tenant_id required", "code": 4010, "status_code": 401}
    tid, err = _safe_int(request.path_params.get("id"), "id")
    if err:
        return err
    result = await db.execute(
        select(NovusdocProTemplate).where(
            NovusdocProTemplate.id == tid,
            NovusdocProTemplate.tenant_id == tenant_id,
            NovusdocProTemplate.is_deleted.is_(False),
        )
    )
    t = result.scalar_one_or_none()
    if not t:
        return {"error": "template not found", "code": 4040, "status_code": 404}
    return {"id": t.id, "name": t.name, "content": t.content, "description": t.description}
