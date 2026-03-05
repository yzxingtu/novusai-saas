"""
NovusDoc 文档模型

表名: px_novusdoc_documents
"""

from __future__ import annotations

from datetime import datetime as dt

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base_model import TenantModel

from ..enums import DocStatus


class NovusdocDocument(TenantModel):
    """文档主表"""

    __tablename__ = "px_novusdoc_documents"

    __filterable__ = {
        "id": "id",
        "tenant_id": "tenant_id",
        "folder_id": "folder_id",
        "title": "title",
        "status": "status",
        "is_starred": "is_starred",
        "creator_id": "creator_id",
        "creator_type": "creator_type",
        "created_at": "created_at",
        "updated_at": "updated_at",
        "last_edited_at": "last_edited_at",
    }

    __sortable__ = [
        "id", "title", "status", "is_starred", "word_count",
        "created_at", "updated_at", "last_edited_at",
    ]

    # ── 内容 ──
    title: Mapped[str] = mapped_column(
        String(500), nullable=False, default="", comment="文档标题",
    )
    content: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True, default=None, comment="Tiptap JSON 内容",
    )
    content_text: Mapped[str | None] = mapped_column(
        Text, nullable=True, default=None, comment="纯文本（全文搜索用）",
    )
    content_html: Mapped[str | None] = mapped_column(
        Text, nullable=True, default=None, comment="HTML 渲染缓存",
    )
    word_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="字数统计",
    )

    # ── 归属 ──
    folder_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("px_novusdoc_folders.id", ondelete="SET NULL"),
        nullable=True,
        default=None,
        comment="所属文件夹 ID",
    )
    creator_id: Mapped[int | None] = mapped_column(
        Integer, nullable=True, default=None, comment="创建者 ID",
    )
    creator_type: Mapped[str | None] = mapped_column(
        String(20), nullable=True, default=None,
        comment="创建者类型: admin / tenant_admin",
    )

    # ── 状态 ──
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=DocStatus.DRAFT.value, comment="文档状态",
    )
    is_starred: Mapped[bool] = mapped_column(
        default=False, nullable=False, comment="是否收藏",
    )
    cover_image: Mapped[str | None] = mapped_column(
        String(500), nullable=True, default=None, comment="封面图 URL",
    )

    # ── 编辑追踪 ──
    last_edited_by: Mapped[int | None] = mapped_column(
        Integer, nullable=True, default=None, comment="最后编辑者 ID",
    )
    last_edited_at: Mapped[dt | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None, comment="最后编辑时间",
    )

    __table_args__ = (
        Index("ix_novusdoc_docs_tenant_folder", "tenant_id", "folder_id"),
        Index("ix_novusdoc_docs_tenant_status", "tenant_id", "status"),
        Index("ix_novusdoc_docs_creator", "creator_id", "creator_type"),
        Index("ix_novusdoc_docs_starred", "tenant_id", "is_starred"),
    )
