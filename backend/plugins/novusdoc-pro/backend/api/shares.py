"""
NovusDoc Pro 分享链接 API handlers
"""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.core.base_model import utc_now
from app.core.logging import get_logger

from ..models.share import NovusdocProShare
from .utils import resolve_tenant_id
from .utils import safe_int as _safe_int

logger = get_logger("plugin.novusdoc-pro.api")


async def create_share(request, db, ctx):
    """POST /docs/{doc_id}/share"""
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

    try:
        body = await request.json()
    except Exception:
        body = {}

    _ALLOWED_PERMISSIONS = {"viewer", "editor"}
    permission = body.get("permission", "viewer")
    if permission not in _ALLOWED_PERMISSIONS:
        return {"error": f"invalid permission, must be one of {sorted(_ALLOWED_PERMISSIONS)}", "code": 4001, "status_code": 400}

    # Compute expires_at from expires_in_hours or direct expires_at
    expires_at = None
    if body.get("expires_in_hours"):
        try:
            hours = float(body["expires_in_hours"])
            expires_at = utc_now() + timedelta(hours=hours)
        except (ValueError, TypeError):
            pass
    elif body.get("expires_at"):
        try:
            raw = body["expires_at"]
            if isinstance(raw, str):
                expires_at = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            pass

    token = secrets.token_urlsafe(32)
    share = NovusdocProShare(
        tenant_id=tenant_id, document_id=doc_id, token=token,
        permission=permission,
        expires_at=expires_at,
        creator_id=ctx.get_current_user_id(),
    )
    db.add(share)
    await db.flush()
    await db.refresh(share)
    await db.commit()
    return {"token": share.token, "permission": share.permission}


async def revoke_share(request, db, ctx):
    """DELETE /docs/{doc_id}/share/{token}"""
    tenant_id = resolve_tenant_id(ctx)
    if tenant_id is None:
        return {"error": "tenant_id required", "code": 4010, "status_code": 401}
    doc_id, err = _safe_int(request.path_params.get("doc_id"), "doc_id")
    if err:
        return err
    token = request.path_params.get("token")
    result = await db.execute(
        select(NovusdocProShare).where(
            NovusdocProShare.token == token,
            NovusdocProShare.tenant_id == tenant_id,
            NovusdocProShare.document_id == doc_id,
        )
    )
    share = result.scalar_one_or_none()
    if not share:
        return {"error": "share not found", "code": 4040, "status_code": 404}
    share.is_active = False
    await db.flush()
    await db.commit()
    return {"message": "revoked"}


async def access_share(request, db, ctx):
    """GET /share/{token} — public anonymous read-only access

    Returns read-only document snapshot (title + content_html + word_count).
    Validates token state: active, not deleted, not expired.
    Never returns write capabilities or sensitive metadata.
    """
    token = request.path_params.get("token")
    result = await db.execute(
        select(NovusdocProShare).where(
            NovusdocProShare.token == token,
            NovusdocProShare.is_active.is_(True),
            NovusdocProShare.is_deleted.is_(False),
        )
    )
    share = result.scalar_one_or_none()
    if not share:
        return {"error": "share not found or revoked", "code": 4040, "status_code": 404}

    # Validate expiration (expires_at is DateTime(timezone=True) or None)
    if share.expires_at:
        try:
            expires = share.expires_at
            # Handle legacy string values during migration period
            if isinstance(expires, str):
                expires = datetime.fromisoformat(expires.replace("Z", "+00:00"))
            if expires.tzinfo is None:
                expires = expires.replace(tzinfo=timezone.utc)
            if utc_now() > expires:
                return {"error": "share link expired", "code": 4040, "status_code": 404}
        except (ValueError, TypeError, AttributeError):
            logger.warning("share: invalid expires_at for token=%s: %s", token, share.expires_at)

    # Fetch the actual document content (read-only snapshot)
    # novusdoc is a sibling plugin — use the plugin module loader for cross-plugin import
    from app.plugins.module_loader import load_plugin_handler
    get_document = load_plugin_handler("novusdoc", "services.document_service.get_document")
    if not get_document:
        return {"error": "novusdoc plugin not available", "code": 5000, "status_code": 500}
    doc = await get_document(db, share.tenant_id, share.document_id)
    if not doc:
        return {"error": "document not found", "code": 4040, "status_code": 404}

    return {
        "document_id": share.document_id,
        "permission": share.permission,
        "title": doc.get("title", ""),
        "content_html": doc.get("content_html", ""),
        "word_count": doc.get("word_count", 0),
        "updated_at": doc.get("updated_at"),
    }
