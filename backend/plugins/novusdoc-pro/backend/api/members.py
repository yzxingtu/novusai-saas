"""
NovusDoc Pro 文档成员 API handlers
"""

from __future__ import annotations

from sqlalchemy import select

from app.core.base_model import utc_now
from app.core.logging import get_logger

from ..models.member import NovusdocProDocMember
from .utils import resolve_tenant_id
from .utils import safe_int as _safe_int

logger = get_logger("plugin.novusdoc-pro.api")


async def list_members(request, db, ctx):
    """GET /docs/{doc_id}/members"""
    tenant_id = resolve_tenant_id(ctx)
    if tenant_id is None:
        return {"error": "tenant_id required", "code": 4010, "status_code": 401}
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

    tenant_id = resolve_tenant_id(ctx)
    if tenant_id is None:
        return {"error": "tenant_id required", "code": 4010, "status_code": 401}
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

    user_id, err = _safe_int(body.get("user_id"), "user_id")
    if err:
        return err

    _ALLOWED_ROLES = {"owner", "editor", "commenter", "viewer"}
    role = body.get("role", "editor")
    if role not in _ALLOWED_ROLES:
        return {"error": f"invalid role, must be one of {sorted(_ALLOWED_ROLES)}", "code": 4001, "status_code": 400}

    # 检查是否已存在该成员（含 soft-deleted，因为 unique 约束不含 is_deleted）
    existing_result = await db.execute(
        select(NovusdocProDocMember).where(
            NovusdocProDocMember.document_id == doc_id,
            NovusdocProDocMember.user_id == user_id,
        )
    )
    existing = existing_result.scalar_one_or_none()
    if existing:
        if not existing.is_deleted:
            return {"error": "member already exists", "code": 4090, "status_code": 409}
        # Reactivate soft-deleted member
        existing.is_deleted = False
        existing.deleted_at = None
        existing.role = role
        existing.updated_at = utc_now()
        await db.flush()
        await db.commit()
        return {"id": existing.id, "user_id": existing.user_id, "role": existing.role}

    member = NovusdocProDocMember(
        tenant_id=tenant_id, document_id=doc_id,
        user_id=user_id, user_type="tenant_admin",
        role=role,
    )
    db.add(member)
    await db.flush()
    await db.refresh(member)
    await db.commit()
    return {"id": member.id, "user_id": member.user_id, "role": member.role}


async def update_member(request, db, ctx):
    """PUT /docs/{doc_id}/members/{mid}"""
    tenant_id = resolve_tenant_id(ctx)
    if tenant_id is None:
        return {"error": "tenant_id required", "code": 4010, "status_code": 401}
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
            NovusdocProDocMember.is_deleted.is_(False),
        )
    )
    member = result.scalar_one_or_none()
    if not member:
        return {"error": "member not found", "code": 4040, "status_code": 404}
    if "role" in body:
        _ALLOWED_ROLES = {"owner", "editor", "commenter", "viewer"}
        if body["role"] not in _ALLOWED_ROLES:
            return {"error": f"invalid role, must be one of {sorted(_ALLOWED_ROLES)}", "code": 4001, "status_code": 400}
        member.role = body["role"]
    member.updated_at = utc_now()
    await db.flush()
    await db.commit()
    return {"id": member.id, "role": member.role}


async def remove_member(request, db, ctx):
    """DELETE /docs/{doc_id}/members/{mid}"""
    tenant_id = resolve_tenant_id(ctx)
    if tenant_id is None:
        return {"error": "tenant_id required", "code": 4010, "status_code": 401}
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
            NovusdocProDocMember.is_deleted.is_(False),
        )
    )
    member = result.scalar_one_or_none()
    if not member:
        return {"error": "member not found", "code": 4040, "status_code": 404}
    member.soft_delete(level="tenant")
    await db.flush()
    await db.commit()
    return {"message": "removed"}
