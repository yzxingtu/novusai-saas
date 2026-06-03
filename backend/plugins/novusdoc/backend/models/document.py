"""
NovusDoc document model / NovusDoc 文档模型

Reuses existing px_novusdoc_documents table if present.
/ 如已有 px_novusdoc_documents 表则复用。
"""

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base_model import BaseModel


class NovusdocDocument(BaseModel):
    __tablename__ = "px_novusdoc_documents"
    __data_permission__ = True

    tenant_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        index=True,
        comment="0=platform/admin space, N=tenant N's space",
    )
    folder_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("px_novusdoc_folders.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    title: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        default="Untitled",
    )
    content: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        comment="Tiptap JSON content",
    )
    content_text: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Plain text for search",
    )
    content_html: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="HTML export cache",
    )
    word_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="draft",
    )
    is_pinned: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    cover_image: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )
    created_by: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
