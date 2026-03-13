"""
NovusDoc 搜索服务

负责全文搜索业务逻辑，handler 层不直接操作 DB。
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, or_, select

from ..models.document import NovusdocDocument


async def search_documents(
    db,
    tenant_id: int,
    *,
    query: str,
    page: int = 1,
    size: int = 20,
) -> tuple[list[dict[str, Any]], int]:
    """全文搜索文档（标题 ILIKE + PostgreSQL tsvector）"""
    like_pattern = f"%{query}%"
    title_match = NovusdocDocument.title.ilike(like_pattern)
    # NOTE: Never pass raw user input as tsquery, otherwise special characters
    # can cause PostgreSQL parsing errors and return 500.
    content_match = func.to_tsvector(
        "simple",
        func.coalesce(NovusdocDocument.content_text, ""),
    ).op("@@")(func.plainto_tsquery("simple", query))

    base = select(NovusdocDocument).where(
        NovusdocDocument.tenant_id == tenant_id,
        NovusdocDocument.is_deleted.is_(False),
        or_(title_match, content_match),
    )

    count_q = select(func.count()).select_from(base.subquery())
    total = (await db.execute(count_q)).scalar() or 0

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
            "updated_at": doc.updated_at.isoformat() if doc.updated_at else None,
        }
        for doc in rows
    ]

    return items, total
