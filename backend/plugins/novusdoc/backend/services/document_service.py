"""
NovusDoc 文档服务

负责文档 CRUD 业务逻辑、content_text 同步、软删除。
通过 PluginContext 获取 DB 和企业信息。
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_model import utc_now

from ..enums import DocStatus
from ..models.document import NovusdocDocument
from .content_converter import count_words, tiptap_to_html, tiptap_to_text


async def list_documents(
    db: AsyncSession,
    tenant_id: int,
    *,
    folder_id: int | None = None,
    status: str | None = None,
    is_starred: bool | None = None,
    search: str | None = None,
    sort: str = "-updated_at",
    page: int = 1,
    size: int = 20,
) -> tuple[list[dict[str, Any]], int]:
    """文档列表（分页 + 筛选 + 排序 + 全文搜索）"""
    base = select(NovusdocDocument).where(
        NovusdocDocument.tenant_id == tenant_id,
        NovusdocDocument.is_deleted.is_(False),
    )

    if folder_id is not None:
        base = base.where(NovusdocDocument.folder_id == folder_id)
    if status:
        base = base.where(NovusdocDocument.status == status)
    if is_starred is not None:
        base = base.where(NovusdocDocument.is_starred == is_starred)
    if search:
        like_pattern = f"%{search}%"
        title_match = NovusdocDocument.title.ilike(like_pattern)
        content_match = func.to_tsvector(
            "simple", func.coalesce(NovusdocDocument.content_text, "")
        ).match(search, postgresql_regconfig="simple")
        base = base.where(or_(title_match, content_match))

    # total count
    count_q = select(func.count()).select_from(base.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    # sort
    order_col = _resolve_sort(sort)
    base = base.order_by(order_col)

    # paginate
    offset = (page - 1) * size
    base = base.offset(offset).limit(size)

    result = await db.execute(base)
    rows = result.scalars().all()

    items = [_doc_to_dict(row) for row in rows]
    return items, total


async def get_document(
    db: AsyncSession,
    tenant_id: int,
    doc_id: int,
) -> dict[str, Any] | None:
    """获取文档详情"""
    result = await db.execute(
        select(NovusdocDocument).where(
            NovusdocDocument.id == doc_id,
            NovusdocDocument.tenant_id == tenant_id,
            NovusdocDocument.is_deleted.is_(False),
        )
    )
    row = result.scalar_one_or_none()
    if not row:
        return None
    return _doc_to_dict(row, include_content=True)


async def create_document(
    db: AsyncSession,
    tenant_id: int,
    *,
    title: str = "",
    content: dict[str, Any] | None = None,
    folder_id: int | None = None,
    status: str = DocStatus.DRAFT.value,
    creator_id: int | None = None,
    creator_type: str | None = None,
) -> dict[str, Any]:
    """创建文档"""
    content_text = tiptap_to_text(content)
    content_html = tiptap_to_html(content)
    word_count = count_words(content_text)

    doc = NovusdocDocument(
        tenant_id=tenant_id,
        title=title or "",
        content=content,
        content_text=content_text,
        content_html=content_html,
        word_count=word_count,
        folder_id=folder_id,
        status=status,
        creator_id=creator_id,
        creator_type=creator_type,
        last_edited_by=creator_id,
        last_edited_at=utc_now(),
    )
    db.add(doc)
    await db.flush()
    await db.refresh(doc)
    return _doc_to_dict(doc, include_content=True)


async def update_document(
    db: AsyncSession,
    tenant_id: int,
    doc_id: int,
    data: dict[str, Any],
    *,
    editor_id: int | None = None,
) -> dict[str, Any] | None:
    """更新文档（含 content_text 同步）"""
    result = await db.execute(
        select(NovusdocDocument).where(
            NovusdocDocument.id == doc_id,
            NovusdocDocument.tenant_id == tenant_id,
            NovusdocDocument.is_deleted.is_(False),
        )
    )
    doc = result.scalar_one_or_none()
    if not doc:
        return None

    # 允许更新的字段
    allowed_fields = {"title", "content", "folder_id", "status", "is_starred", "cover_image"}
    for key, value in data.items():
        if key in allowed_fields:
            setattr(doc, key, value)

    # content 变化时同步衍生字段
    if "content" in data:
        doc.content_text = tiptap_to_text(doc.content)
        doc.content_html = tiptap_to_html(doc.content)
        doc.word_count = count_words(doc.content_text)

    doc.last_edited_by = editor_id
    doc.last_edited_at = utc_now()
    doc.updated_at = utc_now()

    await db.flush()
    await db.refresh(doc)
    return _doc_to_dict(doc, include_content=True)


async def delete_document(
    db: AsyncSession,
    tenant_id: int,
    doc_id: int,
) -> bool:
    """软删除文档"""
    result = await db.execute(
        select(NovusdocDocument).where(
            NovusdocDocument.id == doc_id,
            NovusdocDocument.tenant_id == tenant_id,
            NovusdocDocument.is_deleted.is_(False),
        )
    )
    doc = result.scalar_one_or_none()
    if not doc:
        return False

    doc.soft_delete(level="tenant")
    await db.flush()
    return True


async def cleanup_auto_saves() -> None:
    """定时任务：清理超过 7 天的自动保存草稿

    由 plugin.yaml tasks 声明，每小时执行一次。
    只清理 status=draft 且超过 7 天未编辑的文档（软删除）。
    """
    from app.core.database import async_session_factory

    try:
        async with async_session_factory() as db:
            from datetime import timedelta
            cutoff = utc_now() - timedelta(days=7)

            result = await db.execute(
                select(NovusdocDocument).where(
                    NovusdocDocument.status == DocStatus.DRAFT.value,
                    NovusdocDocument.is_deleted.is_(False),
                    NovusdocDocument.updated_at < cutoff,
                    NovusdocDocument.content.is_(None),
                )
            )
            stale_docs = result.scalars().all()

            for doc in stale_docs:
                doc.soft_delete(level="tenant")

            if stale_docs:
                await db.commit()
                from app.core.logging import get_logger
                logger = get_logger("plugin.novusdoc.task")
                logger.info("cleanup_auto_saves: removed %d stale empty drafts", len(stale_docs))
    except Exception as exc:
        from app.core.logging import get_logger
        logger = get_logger("plugin.novusdoc.task")
        logger.error("cleanup_auto_saves failed: %s", exc)


# ── helpers ──

def _doc_to_dict(doc: NovusdocDocument, *, include_content: bool = False) -> dict[str, Any]:
    """文档模型 → 响应 dict"""
    result: dict[str, Any] = {
        "id": doc.id,
        "tenant_id": doc.tenant_id,
        "title": doc.title,
        "folder_id": doc.folder_id,
        "status": doc.status,
        "is_starred": doc.is_starred,
        "word_count": doc.word_count,
        "cover_image": doc.cover_image,
        "creator_id": doc.creator_id,
        "creator_type": doc.creator_type,
        "last_edited_by": doc.last_edited_by,
        "last_edited_at": doc.last_edited_at,
        "created_at": doc.created_at.isoformat() if doc.created_at else None,
        "updated_at": doc.updated_at.isoformat() if doc.updated_at else None,
    }
    if include_content:
        result["content"] = doc.content
        result["content_text"] = doc.content_text
        result["content_html"] = doc.content_html
    return result


def _resolve_sort(sort_str: str):
    """解析排序参数 → SQLAlchemy order clause"""
    desc = sort_str.startswith("-")
    field_name = sort_str.lstrip("-")

    column_map = {
        "id": NovusdocDocument.id,
        "title": NovusdocDocument.title,
        "status": NovusdocDocument.status,
        "word_count": NovusdocDocument.word_count,
        "is_starred": NovusdocDocument.is_starred,
        "created_at": NovusdocDocument.created_at,
        "updated_at": NovusdocDocument.updated_at,
        "last_edited_at": NovusdocDocument.last_edited_at,
    }

    col = column_map.get(field_name, NovusdocDocument.updated_at)
    return col.desc() if desc else col.asc()
