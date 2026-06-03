"""NovusDoc search API handler / NovusDoc 搜索 API 处理器"""

from __future__ import annotations

from sqlalchemy import func, select

from .documents import _resolve_tenant_id


async def search_docs(request, db, ctx):
    tenant_id = _resolve_tenant_id(request, ctx)

    q = request.query_params.get("q", "").strip()
    if not q:
        return {"items": [], "total": 0}

    page = int(request.query_params.get("page", "1"))
    size = min(int(request.query_params.get("size", "20")), 100)

    from ..models.document import NovusdocDocument

    keyword = f"%{q}%"
    base_filter = [
        NovusdocDocument.tenant_id == tenant_id,
        NovusdocDocument.is_deleted.is_(False),
        (
            NovusdocDocument.title.ilike(keyword)
            | NovusdocDocument.content_text.ilike(keyword)
        ),
    ]

    count_query = select(func.count()).select_from(NovusdocDocument).where(*base_filter)
    total = (await db.execute(count_query)).scalar() or 0

    query = (
        select(NovusdocDocument)
        .where(*base_filter)
        .order_by(NovusdocDocument.updated_at.desc())
        .offset((page - 1) * size)
        .limit(size)
    )
    result = await db.execute(query)
    docs = result.scalars().all()

    return {
        "items": [
            {
                "id": d.id,
                "title": d.title,
                "word_count": d.word_count,
                "status": d.status,
                "is_pinned": d.is_pinned,
                "folder_id": d.folder_id,
                "cover_image": d.cover_image,
                "created_at": d.created_at.isoformat() if d.created_at else None,
                "updated_at": d.updated_at.isoformat() if d.updated_at else None,
            }
            for d in docs
        ],
        "total": total,
    }
