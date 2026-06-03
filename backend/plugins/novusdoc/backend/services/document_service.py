"""
NovusDoc document service / NovusDoc 文档服务

Data isolation via tenant_id:
- tenant_id=0 is the admin/platform space
- tenant_id=N (N>0) is tenant N's private space
All queries filter by tenant_id with standard equality. No special-casing.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.data_permission import (
    apply_data_permission_if_needed,
    enrich_create_data_with_data_permission,
)

PLATFORM_TENANT_ID = 0


async def list_documents(
    db: AsyncSession,
    tenant_id: int,
    *,
    folder_id: int | None = None,
    status: str | None = None,
    page: int = 1,
    size: int = 20,
) -> dict[str, Any]:
    from ..models.document import NovusdocDocument

    base = [
        NovusdocDocument.tenant_id == tenant_id,
        NovusdocDocument.is_deleted.is_(False),
    ]

    query = apply_data_permission_if_needed(
        select(NovusdocDocument).where(*base),
        NovusdocDocument,
    )
    count_query = apply_data_permission_if_needed(
        select(func.count()).select_from(NovusdocDocument).where(*base),
        NovusdocDocument,
    )

    if folder_id is not None:
        query = query.where(NovusdocDocument.folder_id == folder_id)
        count_query = count_query.where(NovusdocDocument.folder_id == folder_id)
    if status:
        query = query.where(NovusdocDocument.status == status)
        count_query = count_query.where(NovusdocDocument.status == status)

    total = (await db.execute(count_query)).scalar() or 0
    query = (
        query.order_by(
            NovusdocDocument.is_pinned.desc(),
            NovusdocDocument.updated_at.desc(),
        )
        .offset((page - 1) * size)
        .limit(size)
    )

    result = await db.execute(query)
    docs = result.scalars().all()

    return {
        "items": [_doc_to_dict(d) for d in docs],
        "total": total,
        "page": page,
        "size": size,
    }


async def get_document(
    db: AsyncSession,
    tenant_id: int,
    doc_id: int,
) -> dict[str, Any] | None:
    from ..models.document import NovusdocDocument

    stmt = apply_data_permission_if_needed(
        select(NovusdocDocument).where(
            NovusdocDocument.id == doc_id,
            NovusdocDocument.tenant_id == tenant_id,
            NovusdocDocument.is_deleted.is_(False),
        ),
        NovusdocDocument,
    )
    result = await db.execute(stmt)
    doc = result.scalar_one_or_none()
    return _doc_to_dict(doc, include_content=True) if doc else None


async def create_document(
    db: AsyncSession,
    tenant_id: int,
    data: dict[str, Any],
) -> dict[str, Any]:
    from ..models.document import NovusdocDocument

    create_payload = {
        "tenant_id": tenant_id,
        "title": data.get("title", "Untitled"),
        "content": data.get("content"),
        "content_text": data.get("content_text", ""),
        "word_count": data.get("word_count", 0),
        "folder_id": data.get("folder_id"),
        "status": data.get("status", "draft"),
    }
    if data.get("created_by") is not None:
        create_payload["created_by"] = data["created_by"]

    create_data = enrich_create_data_with_data_permission(
        NovusdocDocument,
        create_payload,
    )
    doc = NovusdocDocument(**create_data)
    db.add(doc)
    await db.flush()
    await db.refresh(doc)
    return _doc_to_dict(doc, include_content=True)


async def update_document(
    db: AsyncSession,
    tenant_id: int,
    doc_id: int,
    data: dict[str, Any],
) -> dict[str, Any] | None:
    from ..models.document import NovusdocDocument

    stmt = apply_data_permission_if_needed(
        select(NovusdocDocument).where(
            NovusdocDocument.id == doc_id,
            NovusdocDocument.tenant_id == tenant_id,
            NovusdocDocument.is_deleted.is_(False),
        ),
        NovusdocDocument,
    )
    result = await db.execute(stmt)
    doc = result.scalar_one_or_none()
    if not doc:
        return None

    for key in (
        "title",
        "content",
        "content_text",
        "content_html",
        "word_count",
        "folder_id",
        "status",
        "is_pinned",
        "cover_image",
    ):
        if key in data:
            setattr(doc, key, data[key])

    await db.flush()
    await db.refresh(doc)
    return _doc_to_dict(doc, include_content=True)


async def delete_document(
    db: AsyncSession,
    tenant_id: int,
    doc_id: int,
) -> bool:
    from ..models.document import NovusdocDocument

    stmt = apply_data_permission_if_needed(
        select(NovusdocDocument).where(
            NovusdocDocument.id == doc_id,
            NovusdocDocument.tenant_id == tenant_id,
            NovusdocDocument.is_deleted.is_(False),
        ),
        NovusdocDocument,
    )
    result = await db.execute(stmt)
    doc = result.scalar_one_or_none()
    if not doc:
        return False

    doc.is_deleted = True
    await db.flush()
    return True


def _doc_to_dict(doc: Any, *, include_content: bool = False) -> dict[str, Any]:
    d = {
        "id": doc.id,
        "title": doc.title,
        "word_count": doc.word_count,
        "status": doc.status,
        "is_pinned": doc.is_pinned,
        "folder_id": doc.folder_id,
        "cover_image": doc.cover_image,
        "created_at": doc.created_at.isoformat() if doc.created_at else None,
        "updated_at": doc.updated_at.isoformat() if doc.updated_at else None,
    }
    if include_content:
        d["content"] = doc.content
        d["content_text"] = doc.content_text
    return d
