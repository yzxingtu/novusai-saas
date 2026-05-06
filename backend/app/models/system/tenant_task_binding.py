"""
企业任务绑定模型 / Tenant Task Binding Model

表达企业对平台任务定义的启用、覆盖与运行态。
Represents tenant enablement, overrides, and runtime state for task definitions.
"""

from datetime import datetime

from sqlalchemy import ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base_model import BaseModel


class TenantTaskBinding(BaseModel):
    """
    企业任务绑定模型 / Tenant task binding model.

    每条记录表示“某企业是否启用某任务定义，以及如何覆盖默认策略”。
    Each record represents whether a tenant enables a task definition and how it overrides defaults.
    """

    __tablename__ = "tenant_task_bindings"

    __filterable__ = {
        "id": "id",
        "task_definition_id": "task_definition_id",
        "tenant_id": "tenant_id",
        "is_enabled": "is_enabled",
        "last_status": "last_status",
        "created_at": "created_at",
    }

    __sortable__ = {
        "id",
        "created_at",
        "updated_at",
        "last_run_at",
        "next_run_at",
    }

    __table_args__ = (
        UniqueConstraint(
            "task_definition_id",
            "tenant_id",
            name="uq_tenant_task_binding_definition_tenant",
        ),
        Index(
            "ix_tenant_task_bindings_tenant_enabled",
            "tenant_id",
            "is_enabled",
        ),
        Index(
            "ix_tenant_task_bindings_definition_enabled",
            "task_definition_id",
            "is_enabled",
        ),
    )

    task_definition_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("task_definitions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="任务定义 ID",
    )
    tenant_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="企业 ID",
    )
    is_enabled: Mapped[bool] = mapped_column(
        nullable=False,
        default=True,
        comment="是否启用",
    )
    disabled_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        default=None,
        comment="禁用原因",
    )
    schedule_type_override: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        default=None,
        comment="覆盖调度类型",
    )
    cron_expression_override: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="覆盖 Cron 表达式",
    )
    interval_seconds_override: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="覆盖间隔秒数",
    )
    config_override: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        default=None,
        comment="覆盖配置",
    )
    args_override: Mapped[dict | list | None] = mapped_column(
        JSON,
        nullable=True,
        default=None,
        comment="覆盖位置参数",
    )
    kwargs_override: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        default=None,
        comment="覆盖任务关键字参数",
    )
    last_run_at: Mapped[datetime | None] = mapped_column(
        nullable=True,
        default=None,
        comment="上次执行时间",
    )
    next_run_at: Mapped[datetime | None] = mapped_column(
        nullable=True,
        default=None,
        comment="下次执行时间",
    )
    last_status: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        default=None,
        comment="最近一次运行状态",
    )
    last_error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="最近一次失败摘要",
    )


__all__ = ["TenantTaskBinding"]
