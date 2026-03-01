"""
NovusDoc 文件夹模型

表名: px_novusdoc_folders
支持无限层级嵌套（parent_id 自引用）
"""

from __future__ import annotations

from sqlalchemy import ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base_model import TenantModel


class NovusdocFolder(TenantModel):
    """文件夹"""

    __tablename__ = "px_novusdoc_folders"

    __filterable__ = {
        "id": "id",
        "tenant_id": "tenant_id",
        "parent_id": "parent_id",
        "name": "name",
        "creator_id": "creator_id",
        "created_at": "created_at",
    }

    __sortable__ = ["id", "name", "sort_order", "created_at"]

    name: Mapped[str] = mapped_column(
        String(200), nullable=False, comment="文件夹名称",
    )
    parent_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("px_novusdoc_folders.id", ondelete="CASCADE"),
        nullable=True,
        default=None,
        comment="父文件夹 ID（NULL 表示根级）",
    )
    sort_order: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="排序序号",
    )
    creator_id: Mapped[int | None] = mapped_column(
        Integer, nullable=True, default=None, comment="创建者 ID",
    )

    __table_args__ = (
        Index("ix_novusdoc_folders_tenant_parent", "tenant_id", "parent_id"),
    )
