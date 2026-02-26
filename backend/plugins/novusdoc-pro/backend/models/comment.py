"""
NovusDoc Pro 评论模型

表名: px_novusdoc_pro_comments + px_novusdoc_pro_comment_replies
"""

from __future__ import annotations

from sqlalchemy import ForeignKey, Index, Integer, String, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base_model import TenantModel


class NovusdocProComment(TenantModel):
    """评论"""

    __tablename__ = "px_novusdoc_pro_comments"

    __filterable__ = {
        "id": "id",
        "tenant_id": "tenant_id",
        "document_id": "document_id",
        "creator_id": "creator_id",
        "is_resolved": "is_resolved",
        "created_at": "created_at",
    }

    __sortable__ = ["id", "created_at", "updated_at"]

    document_id: Mapped[int] = mapped_column(
        Integer, nullable=False, index=True, comment="文档 ID（引用 novusdoc）",
    )
    content: Mapped[str] = mapped_column(
        Text, nullable=False, comment="评论内容",
    )
    creator_id: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="评论者 ID",
    )
    creator_name: Mapped[str | None] = mapped_column(
        String(100), nullable=True, comment="评论者名称（冗余缓存）",
    )
    is_resolved: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, comment="是否已解决",
    )
    anchor_from: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="批注起始位置（ProseMirror pos）",
    )
    anchor_to: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="批注结束位置",
    )
    quoted_text: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="被批注的原文摘录",
    )

    __table_args__ = (
        Index("ix_ndpro_comments_doc", "document_id", "tenant_id"),
    )


class NovusdocProCommentReply(TenantModel):
    """评论回复"""

    __tablename__ = "px_novusdoc_pro_comment_replies"

    comment_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("px_novusdoc_pro_comments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="父评论 ID",
    )
    content: Mapped[str] = mapped_column(
        Text, nullable=False, comment="回复内容",
    )
    creator_id: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="回复者 ID",
    )
    creator_name: Mapped[str | None] = mapped_column(
        String(100), nullable=True, comment="回复者名称",
    )
