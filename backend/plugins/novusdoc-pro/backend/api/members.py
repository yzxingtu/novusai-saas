"""
NovusDoc Pro 文档成员 API handlers
"""

from __future__ import annotations

from sqlalchemy import select

from app.core.base_model import utc_now
from app.core.logging import get_logger

from ..models.member import NovusdocProDocMember

logger = get_logger("plugin.novusdoc-pro.api")


def _safe_int(val, name: str = "id") -> tuple[int | None, dict | None]:
    if val is None:
        return None, {"error": f"{name} required", "code": 4001}
    try:
        return int(val), None
    except (ValueError, TypeError):
        return None, {"error": f"invalid {name}", "code": 4001}


async def list_members(request, db, ctx):
    """GET /docs/{doc_id}/members"""
    tenant_id = ctx.get_current_tenant_id()
    if not tenant_id:
        return {"error": "tenant_id required", "code": 4010}
    doc_id, err = _safe_int(request.path_params.get("doc_id"), "doc_id")
    if err:
        return err
    result = await db.execute(
        select(NovusdocProDocMember).where(
            NovusdocProDocMember.tenant_id == tenant_id,
            NovusdocProDocMember.document_id == doc_id,
            NovusdocProDocMember.is_deleted.is_(False),
        )
    )
    rows = result.scalars().all()
    items = [{"id": m.id, "user_id": m.user_id, "role": m.role} for m in rows]
    return {"items": items, "total": len(items)}


async def add_member(request, db, ctx):
    """POST /docs/{doc_id}/members"""
    from ..services.license_gate import check_license_valid, license_required_error
    is_valid, license_info = await check_license_valid(ctx)
    if not is_valid:
        return license_required_error(license_info)

    tenant_id = ctx.get_current_tenant_id()
    if not tenant_id:
        return {"error": "tenant_id required", "code": 4010}
    doc_id, err = _safe_int(request.path_params.get("doc_id"), "doc_id")
    if err:
        return err
    from ..services.doc_validator import verify_document_exists
    if not await verify_document_exists(db, tenant_id, doc_id):
        return {"error": "document not found", "code": 4040, "status_code": 404}

    body = await request.json()

    # 协作角色策略：仅允许 tenant_admin 加入协作
    user_type = body.get("user_type", "tenant_admin")
    if user_type != "tenant_admin":
        return {"error": "only tenant_admin users can join collaboration", "code": 4030, "status_code": 403}

    member = NovusdocProDocMember(
        tenant_id=tenant_id, document_id=doc_id,
        user_id=body.get("user_id"), user_type="tenant_admin",
        role=body.get("role", "editor"),
    )
    db.add(member)
    await db.flush()
    await db.refresh(member)
    await db.commit()
    return {"id": member.id, "user_id": member.user_id, "role": member.role}


async def update_member(request, db, ctx):
    """PUT /docs/{doc_id}/members/{mid}"""
    tenant_id = ctx.get_current_tenant_id()
    if not tenant_id:
        return {"error": "tenant_id required", "code": 4010}
    doc_id, err = _safe_int(request.path_params.get("doc_id"), "doc_id")
    if err:
        return err
    mid, err = _safe_int(request.path_params.get("mid"), "mid")
    if err:
        return err
    body = await request.json()
    result = await db.execute(
        select(NovusdocProDocMember).where(
            NovusdocProDocMember.id == mid,
            NovusdocProDocMember.document_id == doc_id,
            NovusdocProDocMember.tenant_id == tenant_id,
        )
    )
    member = result.scalar_one_or_none()
    if not member:
        return {"error": "member not found", "code": 4040, "status_code": 404}
    if "role" in body:
        member.role = body["role"]
    member.updated_at = utc_now()
    await db.flush()
    await db.commit()
    return {"id": member.id, "role": member.role}


async def remove_member(request, db, ctx):
    """DELETE /docs/{doc_id}/members/{mid}"""
    tenant_id = ctx.get_current_tenant_id()
    if not tenant_id:
        return {"error": "tenant_id required", "code": 4010}
    doc_id, err = _safe_int(request.path_params.get("doc_id"), "doc_id")
    if err:
        return err
    mid, err = _safe_int(request.path_params.get("mid"), "mid")
    if err:
        return err
    result = await db.execute(
        select(NovusdocProDocMember).where(
            NovusdocProDocMember.id == mid,
            NovusdocProDocMember.document_id == doc_id,
            NovusdocProDocMember.tenant_id == tenant_id,
        )
    )
    member = result.scalar_one_or_none()
    if not member:
        return {"error": "member not found", "code": 4040, "status_code": 404}
    member.soft_delete(level="tenant")
    await db.flush()
    await db.commit()
    return {"message": "removed"}
