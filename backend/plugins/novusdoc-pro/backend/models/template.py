"""
NovusDoc Pro 文档模板模型

表名: px_novusdoc_pro_templates
"""

from __future__ import annotations

from sqlalchemy import Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base_model import TenantModel


class NovusdocProTemplate(TenantModel):
    """文档模板"""

    __tablename__ = "px_novusdoc_pro_templates"

    __filterable__ = {
        "id": "id",
        "tenant_id": "tenant_id",
        "name": "name",
        "category": "category",
        "created_at": "created_at",
    }

    __sortable__ = ["id", "name", "sort_order", "created_at"]

    name: Mapped[str] = mapped_column(
        String(200), nullable=False, comment="模板名称",
    )
    description: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="模板描述",
    )
    content: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True, comment="Tiptap JSON 模板内容",
    )
    cover_image: Mapped[str | None] = mapped_column(
        String(500), nullable=True, comment="封面图",
    )
    category: Mapped[str | None] = mapped_column(
        String(50), nullable=True, comment="分类",
    )
    sort_order: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="排序",
    )
    creator_id: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="创建者 ID",
    )
