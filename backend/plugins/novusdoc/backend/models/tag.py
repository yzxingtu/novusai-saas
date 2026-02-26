"""
NovusDoc 标签模型

表名: px_novusdoc_tags + px_novusdoc_doc_tags
"""

from __future__ import annotations

from sqlalchemy import ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base_model import TenantModel


class NovusdocTag(TenantModel):
    """标签"""

    __tablename__ = "px_novusdoc_tags"

    __filterable__ = {
        "id": "id",
        "tenant_id": "tenant_id",
        "name": "name",
        "created_at": "created_at",
    }

    __sortable__ = ["id", "name", "created_at"]

    name: Mapped[str] = mapped_column(
        String(100), nullable=False, comment="标签名称",
    )
    color: Mapped[str | None] = mapped_column(
        String(20), nullable=True, default=None, comment="标签颜色（hex）",
    )

    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_novusdoc_tag_tenant_name"),
    )


class NovusdocDocTag(TenantModel):
    """文档-标签关联"""

    __tablename__ = "px_novusdoc_doc_tags"

    document_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("px_novusdoc_documents.id", ondelete="CASCADE"),
        nullable=False,
        comment="文档 ID",
    )
    tag_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("px_novusdoc_tags.id", ondelete="CASCADE"),
        nullable=False,
        comment="标签 ID",
    )

    __table_args__ = (
        UniqueConstraint("document_id", "tag_id", name="uq_novusdoc_doc_tag"),
        Index("ix_novusdoc_doc_tags_doc", "document_id"),
        Index("ix_novusdoc_doc_tags_tag", "tag_id"),
    )
