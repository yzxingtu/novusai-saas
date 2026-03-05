"""
NovusDoc Pro 评论 API handlers

handler 签名：(request, db, ctx)
"""

from __future__ import annotations

from sqlalchemy import select

from app.core.base_model import utc_now
from app.core.logging import get_logger

from ..models.comment import NovusdocProComment, NovusdocProCommentReply
from .utils import resolve_tenant_id
from .utils import safe_int as _safe_int

logger = get_logger("plugin.novusdoc-pro.api")


async def list_comments(request, db, ctx):
    """GET /docs/{doc_id}/comments"""
    tenant_id = resolve_tenant_id(ctx)
    if tenant_id is None:
        return {"error": "tenant_id required", "code": 4010, "status_code": 401}

    doc_id, err = _safe_int(request.path_params.get("doc_id"), "doc_id")
    if err:
        return err

    result = await db.execute(
        select(NovusdocProComment).where(
            NovusdocProComment.tenant_id == tenant_id,
            NovusdocProComment.document_id == doc_id,
            NovusdocProComment.is_deleted.is_(False),
        ).order_by(NovusdocProComment.created_at.desc())
    )
    rows = result.scalars().all()

    items = [
        {
            "id": c.id, "document_id": c.document_id, "content": c.content,
            "creator_id": c.creator_id, "creator_name": c.creator_name,
            "is_resolved": c.is_resolved, "anchor_from": c.anchor_from,
            "anchor_to": c.anchor_to, "quoted_text": c.quoted_text,
            "created_at": str(c.created_at) if c.created_at else None,
        }
        for c in rows
    ]
    return {"items": items, "total": len(items)}


async def create_comment(request, db, ctx):
    """POST /docs/{doc_id}/comments"""
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

    comment = NovusdocProComment(
        tenant_id=tenant_id,
        document_id=doc_id,
        content=body.get("content", ""),
        creator_id=ctx.get_current_user_id(),
        creator_name=body.get("creator_name", ""),
        anchor_from=body.get("anchor_from"),
        anchor_to=body.get("anchor_to"),
        quoted_text=body.get("quoted_text"),
    )
    db.add(comment)
    await db.flush()
    await db.refresh(comment)
    await db.commit()

    return {"id": comment.id, "content": comment.content, "creator_id": comment.creator_id}


async def update_comment(request, db, ctx):
    """PUT /docs/{doc_id}/comments/{cid}"""
    tenant_id = resolve_tenant_id(ctx)
    if tenant_id is None:
        return {"error": "tenant_id required", "code": 4010, "status_code": 401}

    doc_id, err = _safe_int(request.path_params.get("doc_id"), "doc_id")
    if err:
        return err
    cid, err = _safe_int(request.path_params.get("cid"), "cid")
    if err:
        return err
    result = await db.execute(
        select(NovusdocProComment).where(
            NovusdocProComment.id == cid,
            NovusdocProComment.document_id == doc_id,
            NovusdocProComment.tenant_id == tenant_id,
            NovusdocProComment.is_deleted.is_(False),
        )
    )
    comment = result.scalar_one_or_none()
    if not comment:
        return {"error": "comment not found", "code": 4040, "status_code": 404}

    body = await request.json()
    if "content" in body:
        comment.content = body["content"]
    comment.updated_at = utc_now()
    await db.flush()
    await db.commit()

    return {"id": comment.id, "content": comment.content}


async def delete_comment(request, db, ctx):
    """DELETE /docs/{doc_id}/comments/{cid}"""
    tenant_id = resolve_tenant_id(ctx)
    if tenant_id is None:
        return {"error": "tenant_id required", "code": 4010, "status_code": 401}

    doc_id, err = _safe_int(request.path_params.get("doc_id"), "doc_id")
    if err:
        return err
    cid, err = _safe_int(request.path_params.get("cid"), "cid")
    if err:
        return err
    result = await db.execute(
        select(NovusdocProComment).where(
            NovusdocProComment.id == cid,
            NovusdocProComment.document_id == doc_id,
            NovusdocProComment.tenant_id == tenant_id,
            NovusdocProComment.is_deleted.is_(False),
        )
    )
    comment = result.scalar_one_or_none()
    if not comment:
        return {"error": "comment not found", "code": 4040, "status_code": 404}

    comment.soft_delete(level="tenant")
    await db.flush()
    await db.commit()
    return {"message": "deleted"}


async def resolve_comment(request, db, ctx):
    """POST /docs/{doc_id}/comments/{cid}/resolve"""
    tenant_id = resolve_tenant_id(ctx)
    if tenant_id is None:
        return {"error": "tenant_id required", "code": 4010, "status_code": 401}

    doc_id, err = _safe_int(request.path_params.get("doc_id"), "doc_id")
    if err:
        return err
    cid, err = _safe_int(request.path_params.get("cid"), "cid")
    if err:
        return err
    result = await db.execute(
        select(NovusdocProComment).where(
            NovusdocProComment.id == cid,
            NovusdocProComment.document_id == doc_id,
            NovusdocProComment.tenant_id == tenant_id,
            NovusdocProComment.is_deleted.is_(False),
        )
    )
    comment = result.scalar_one_or_none()
    if not comment:
        return {"error": "comment not found", "code": 4040, "status_code": 404}

    comment.is_resolved = True
    comment.updated_at = utc_now()
    await db.flush()
    await db.commit()
    return {"id": comment.id, "is_resolved": True}


async def reply_comment(request, db, ctx):
    """POST /docs/{doc_id}/comments/{cid}/replies"""
    tenant_id = resolve_tenant_id(ctx)
    if tenant_id is None:
        return {"error": "tenant_id required", "code": 4010, "status_code": 401}

    doc_id, err = _safe_int(request.path_params.get("doc_id"), "doc_id")
    if err:
        return err
    cid, err = _safe_int(request.path_params.get("cid"), "cid")
    if err:
        return err

    # 校验父评论存在、属于该文档且未删除
    result = await db.execute(
        select(NovusdocProComment).where(
            NovusdocProComment.id == cid,
            NovusdocProComment.document_id == doc_id,
            NovusdocProComment.tenant_id == tenant_id,
            NovusdocProComment.is_deleted.is_(False),
        )
    )
    if not result.scalar_one_or_none():
        return {"error": "comment not found", "code": 4040, "status_code": 404}

    body = await request.json()

    reply = NovusdocProCommentReply(
        tenant_id=tenant_id,
        comment_id=cid,
        content=body.get("content", ""),
        creator_id=ctx.get_current_user_id(),
        creator_name=body.get("creator_name", ""),
    )
    db.add(reply)
    await db.flush()
    await db.refresh(reply)
    await db.commit()

    return {"id": reply.id, "comment_id": reply.comment_id, "content": reply.content}
