"""
工具定义模型

定义智能体可使用的工具，包括 HTTP/DB/Email/Builtin 等类型
支持租户自定义工具和系统内置工具
"""

from sqlalchemy import Boolean, Index, Integer, String, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base_model import TenantModel
from app.core.i18n import _
from app.enums.agent import ToolTypeEnum


class ToolDefinition(TenantModel):
    """
    工具定义模型

    存储智能体可调用的工具配置，包括输入输出 Schema、执行配置等
    系统工具: is_system=True, tenant_id 可为 NULL
    租户工具: is_system=False, tenant_id 关联租户
    """

    __tablename__ = "tool_definitions"

    # 允许前端筛选的字段
    __filterable__ = {
        "id": "id",
        "name": "name",
        "type": "type",
        "is_system": "is_system",
        "is_active": "is_active",
        "tenant_id": "tenant_id",
        "created_at": "created_at",
    }

    # 允许排序的字段
    __sortable__ = {
        "id": "id",
        "name": "name",
        "created_at": "created_at",
        "updated_at": "updated_at",
    }

    # 下拉选择配置
    __selectable__ = {
        "label": "name",
        "value": "id",
        "search": ["name"],
    }

    # ==================== 基本信息 ====================

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment=_("tool_definition.field.name"),
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment=_("tool_definition.field.description"),
    )
    type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=ToolTypeEnum.HTTP.value,
        index=True,
        comment=_("tool_definition.field.type"),
    )

    # ==================== Schema 定义 ====================

    input_schema: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        default=dict,
        comment=_("tool_definition.field.input_schema"),
    )
    output_schema: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        default=dict,
        comment=_("tool_definition.field.output_schema"),
    )

    # ==================== 执行配置 ====================

    config: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        default=dict,
        comment=_("tool_definition.field.config"),
    )
    timeout: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=30,
        comment=_("tool_definition.field.timeout"),
    )

    # ==================== 状态标识 ====================

    is_system: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
        comment=_("tool_definition.field.is_system"),
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment=_("tool_definition.field.is_active"),
    )

    # ==================== 复合索引 ====================

    __table_args__ = (
        Index("ix_tool_definitions_tenant_type", "tenant_id", "type"),
        Index("ix_tool_definitions_tenant_active", "tenant_id", "is_active"),
    )

    def __repr__(self) -> str:
        return f"<ToolDefinition(id={self.id}, name={self.name}, type={self.type})>"


__all__ = ["ToolDefinition"]
