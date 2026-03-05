"""
DataForge Studio — 表关联模型

表名: ncc_table_relations
relation_type: one_to_many | many_to_one | one_to_one | many_to_many
"""

from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base_model import BaseModel


class NccTableRelation(BaseModel):
    """表关联关系表"""

    __tablename__ = "ncc_table_relations"

    __filterable__ = {
        "id": "id",
        "project_id": "project_id",
        "from_schema_id": "from_schema_id",
        "to_schema_id": "to_schema_id",
        "relation_type": "relation_type",
    }

    __sortable__ = ["id", "relation_type", "created_at"]

    project_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("ncc_projects.id", ondelete="CASCADE", name="fk_ncc_rel_project"),
        nullable=False,
        index=True,
        comment="所属项目 ID",
    )
    from_schema_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("ncc_table_schemas.id", ondelete="CASCADE", name="fk_ncc_rel_from"),
        nullable=False,
        index=True,
        comment="来源表 ID",
    )
    to_schema_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("ncc_table_schemas.id", ondelete="CASCADE", name="fk_ncc_rel_to"),
        nullable=False,
        index=True,
        comment="目标表 ID",
    )
    from_field: Mapped[str] = mapped_column(
        String(200), nullable=False, comment="来源字段名",
    )
    to_field: Mapped[str] = mapped_column(
        String(200), nullable=False, comment="目标字段名",
    )
    relation_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default="one_to_many",
        comment="关联类型: one_to_many / many_to_one / one_to_one / many_to_many",
    )
    label: Mapped[str | None] = mapped_column(
        String(200), nullable=True, default=None, comment="关联显示标签",
    )
