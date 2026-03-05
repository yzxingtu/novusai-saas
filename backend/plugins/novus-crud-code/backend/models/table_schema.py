"""
DataForge Studio — 表结构模型

表名: ncc_table_schemas
schema_config JSONB 格式:
{
  "fields": [
    {"name": "title", "type": "string", "required": true, "label": "标题", "default": null},
    {"name": "count", "type": "integer", "required": false, "label": "数量", "default": 0},
    ...
  ]
}
"""

from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base_model import BaseModel


class NccTableSchema(BaseModel):
    """表结构定义表"""

    __tablename__ = "ncc_table_schemas"

    __filterable__ = {
        "id": "id",
        "project_id": "project_id",
        "name": "name",
        "display_name": "display_name",
        "created_at": "created_at",
        "updated_at": "updated_at",
    }

    __sortable__ = ["id", "name", "display_name", "sort_order", "created_at", "updated_at"]

    project_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("ncc_projects.id", ondelete="CASCADE", name="fk_ncc_ts_project"),
        nullable=False,
        index=True,
        comment="所属项目 ID",
    )
    name: Mapped[str] = mapped_column(
        String(200), nullable=False, comment="表唯一标识名（snake_case）",
    )
    display_name: Mapped[str] = mapped_column(
        String(200), nullable=False, default="", comment="表显示名称",
    )
    description: Mapped[str | None] = mapped_column(
        Text, nullable=True, default=None, comment="表描述",
    )
    schema_config: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict, comment="字段定义列表（JSONB）",
    )
    form_config: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict, comment="表单布局配置（JSONB）",
    )
    ui_config: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict, comment="ER图节点位置等 UI 配置（JSONB）",
    )
    sort_order: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="排序权重",
    )
