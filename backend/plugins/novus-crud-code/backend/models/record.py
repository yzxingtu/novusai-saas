"""
DataForge Studio — 动态数据记录模型

表名: ncc_records
data JSONB 存储任意字段键值对，结构由对应 NccTableSchema.schema_config 定义
"""

from __future__ import annotations

from sqlalchemy import ForeignKey, Integer
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base_model import BaseModel


class NccRecord(BaseModel):
    """动态数据行表"""

    __tablename__ = "ncc_records"

    __filterable__ = {
        "id": "id",
        "schema_id": "schema_id",
        "project_id": "project_id",
        "created_at": "created_at",
        "updated_at": "updated_at",
    }

    __sortable__ = ["id", "sort_order", "created_at", "updated_at"]

    schema_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("ncc_table_schemas.id", ondelete="CASCADE", name="fk_ncc_rec_schema"),
        nullable=False,
        index=True,
        comment="所属表结构 ID",
    )
    project_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("ncc_projects.id", ondelete="CASCADE", name="fk_ncc_rec_project"),
        nullable=False,
        index=True,
        comment="所属项目 ID",
    )
    data: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict, comment="动态字段数据（JSONB）",
    )
    sort_order: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="排序权重",
    )
