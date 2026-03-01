"""
NovusDoc Pro 版本历史模型

表名: px_novusdoc_pro_versions
"""

from __future__ import annotations

from sqlalchemy import Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base_model import TenantModel


class NovusdocProVersion(TenantModel):
    """文档版本快照"""

    __tablename__ = "px_novusdoc_pro_versions"

    __filterable__ = {
        "id": "id",
        "tenant_id": "tenant_id",
        "document_id": "document_id",
        "creator_id": "creator_id",
        "created_at": "created_at",
    }

    __sortable__ = ["id", "created_at"]

    document_id: Mapped[int] = mapped_column(
        Integer, nullable=False, index=True, comment="文档 ID",
    )
    title: Mapped[str] = mapped_column(
        String(500), nullable=False, default="", comment="版本标题",
    )
    content: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True, comment="Tiptap JSON 快照",
    )
    content_text: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="纯文本快照",
    )
    word_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="字数",
    )
    creator_id: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="创建者 ID",
    )
    creator_name: Mapped[str | None] = mapped_column(
        String(100), nullable=True, comment="创建者名称",
    )
    version_note: Mapped[str | None] = mapped_column(
        String(500), nullable=True, comment="版本说明",
    )
