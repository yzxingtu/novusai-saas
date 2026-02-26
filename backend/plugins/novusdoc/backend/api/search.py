"""
NovusDoc 全文搜索 API handler
"""

from __future__ import annotations

from sqlalchemy import func, select

from app.core.logging import get_logger

from ..models.document import NovusdocDocument

logger = get_logger("plugin.novusdoc.api")


async def search_docs(request, db, ctx):
    """GET /search — 全文搜索文档"""
    tenant_id = ctx.get_current_tenant_id()
    if not tenant_id:
        return {"error": "tenant_id required", "code": 4010}

    q = request.query_params.get("q", "").strip()
    if not q:
        return {"items": [], "total": 0}

    try:
        page = max(1, int(request.query_params.get("page[number]", "1")))
        size = max(1, min(100, int(request.query_params.get("page[size]", "20"))))
    except (ValueError, TypeError):
        page, size = 1, 20

    base = select(NovusdocDocument).where(
        NovusdocDocument.tenant_id == tenant_id,
        NovusdocDocument.is_deleted.is_(False),
        func.to_tsvector(
            "simple",
            func.coalesce(NovusdocDocument.content_text, ""),
        ).match(q, postgresql_regconfig="simple"),
    )

    # total
    count_q = select(func.count()).select_from(base.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    # paginate
    offset = (page - 1) * size
    result = await db.execute(
        base.order_by(NovusdocDocument.updated_at.desc())
        .offset(offset)
        .limit(size)
    )
    rows = result.scalars().all()

    items = [
        {
            "id": doc.id,
            "title": doc.title,
            "status": doc.status,
            "word_count": doc.word_count,
            "folder_id": doc.folder_id,
            "updated_at": str(doc.updated_at) if doc.updated_at else None,
        }
        for doc in rows
    ]

    return {"items": items, "total": total, "page": page, "size": size}
