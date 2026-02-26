"""
NovusDoc Pro 版本历史 API handlers
"""

from __future__ import annotations

from sqlalchemy import select

from app.core.base_model import utc_now
from app.core.logging import get_logger

from ..models.version import NovusdocProVersion

logger = get_logger("plugin.novusdoc-pro.api")


def _safe_int(val, name: str = "id") -> tuple[int | None, dict | None]:
    if val is None:
        return None, {"error": f"{name} required", "code": 4001}
    try:
        return int(val), None
    except (ValueError, TypeError):
        return None, {"error": f"invalid {name}", "code": 4001}


async def list_versions(request, db, ctx):
    """GET /docs/{doc_id}/versions"""
    tenant_id = ctx.get_current_tenant_id()
    if not tenant_id:
        return {"error": "tenant_id required", "code": 4010}
    doc_id, err = _safe_int(request.path_params.get("doc_id"), "doc_id")
    if err:
        return err
    result = await db.execute(
        select(NovusdocProVersion).where(
            NovusdocProVersion.tenant_id == tenant_id,
            NovusdocProVersion.document_id == doc_id,
            NovusdocProVersion.is_deleted.is_(False),
        ).order_by(NovusdocProVersion.created_at.desc())
    )
    rows = result.scalars().all()
    items = [
        {"id": v.id, "title": v.title, "word_count": v.word_count,
         "creator_name": v.creator_name, "version_note": v.version_note,
         "created_at": str(v.created_at) if v.created_at else None}
        for v in rows
    ]
    return {"items": items, "total": len(items)}


async def create_version(request, db, ctx):
    """POST /docs/{doc_id}/versions"""
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
    version = NovusdocProVersion(
        tenant_id=tenant_id, document_id=doc_id,
        title=body.get("title", ""), content=body.get("content"),
        content_text=body.get("content_text", ""), word_count=body.get("word_count", 0),
        creator_id=ctx.get_current_user_id(), creator_name=body.get("creator_name", ""),
        version_note=body.get("version_note", ""),
    )
    db.add(version)
    await db.flush()
    await db.refresh(version)
    await db.commit()
    return {"id": version.id, "title": version.title}


async def get_version(request, db, ctx):
    """GET /docs/{doc_id}/versions/{vid}"""
    tenant_id = ctx.get_current_tenant_id()
    if not tenant_id:
        return {"error": "tenant_id required", "code": 4010}
    doc_id, err = _safe_int(request.path_params.get("doc_id"), "doc_id")
    if err:
        return err
    vid, err = _safe_int(request.path_params.get("vid"), "vid")
    if err:
        return err
    result = await db.execute(
        select(NovusdocProVersion).where(
            NovusdocProVersion.id == vid,
            NovusdocProVersion.document_id == doc_id,
            NovusdocProVersion.tenant_id == tenant_id,
        )
    )
    v = result.scalar_one_or_none()
    if not v:
        return {"error": "version not found", "code": 4040, "status_code": 404}
    return {"id": v.id, "title": v.title, "content": v.content,
            "word_count": v.word_count, "version_note": v.version_note,
            "created_at": str(v.created_at) if v.created_at else None}


async def restore_version(request, db, ctx):
    """POST /docs/{doc_id}/versions/{vid}/restore"""
    tenant_id = ctx.get_current_tenant_id()
    if not tenant_id:
        return {"error": "tenant_id required", "code": 4010}
    doc_id, err = _safe_int(request.path_params.get("doc_id"), "doc_id")
    if err:
        return err
    vid, err = _safe_int(request.path_params.get("vid"), "vid")
    if err:
        return err
    result = await db.execute(
        select(NovusdocProVersion).where(
            NovusdocProVersion.id == vid,
            NovusdocProVersion.document_id == doc_id,
            NovusdocProVersion.tenant_id == tenant_id,
        )
    )
    v = result.scalar_one_or_none()
    if not v:
        return {"error": "version not found", "code": 4040, "status_code": 404}
    return {"message": "restored", "version_id": v.id, "content": v.content}
