"""
DataForge Studio — 项目模型

表名: ncc_projects
"""

from __future__ import annotations

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base_model import BaseModel


class NccProject(BaseModel):
    """项目主表 — 一个项目包含多张逻辑表"""

    __tablename__ = "ncc_projects"

    __filterable__ = {
        "id": "id",
        "name": "name",
        "display_name": "display_name",
        "created_at": "created_at",
        "updated_at": "updated_at",
    }

    __sortable__ = ["id", "name", "display_name", "created_at", "updated_at"]

    name: Mapped[str] = mapped_column(
        String(200), nullable=False, unique=True, comment="项目唯一标识名（snake_case）",
    )
    display_name: Mapped[str] = mapped_column(
        String(200), nullable=False, default="", comment="项目显示名称",
    )
    description: Mapped[str | None] = mapped_column(
        Text, nullable=True, default=None, comment="项目描述",
    )
    color: Mapped[str | None] = mapped_column(
        String(20), nullable=True, default=None, comment="主题色（hex）",
    )
    icon: Mapped[str] = mapped_column(
        String(100), nullable=False, default="lucide:database", comment="图标（Iconify key）",
    )
