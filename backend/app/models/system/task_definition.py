"""
任务定义模型 / Task Definition Model

作为下一代定时任务架构的目录层，统一承载平台任务定义。
Serves as the catalog layer for the next-generation task scheduling architecture.
"""

from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base_model import BaseModel
from app.enums.common import ResourceScopeEnum
from app.enums.task import ScheduleTypeEnum, TaskDefinitionTypeEnum


class TaskDefinition(BaseModel):
    """
    任务定义模型 / Task definition model.

    仅描述“这是什么任务”，不直接表达企业启停或执行结果。
    Describes what a task is, without directly modeling tenant enablement or runs.
    """

    __tablename__ = "task_definitions"

    __filterable__ = {
        "id": "id",
        "code": "code",
        "name": "name",
        "task_path": "handler_path",
        "definition_type": "definition_type",
        "schedule_type": "default_schedule_type",
        "cron_expression": "default_cron_expression",
        "interval_seconds": "default_interval_seconds",
        "scope": "scope",
        "owner_tenant_id": "owner_tenant_id",
        "is_enabled": "is_enabled",
        "is_active": "is_enabled",
        "is_editable": "is_editable",
        "is_deletable": "is_deletable",
        "default_priority": "default_priority",
        "max_retries": "max_retries",
        "retry_delay": "retry_delay",
        "timeout": "timeout",
        "notify_on_failure": "notify_on_failure",
        "last_run_at": "last_run_at",
        "next_run_at": "next_run_at",
        "created_at": "created_at",
    }

    __sortable__ = {
        "id",
        "code",
        "name",
        "handler_path",
        "default_priority",
        "created_at",
        "updated_at",
        "last_run_at",
        "next_run_at",
    }

    __table_args__ = (
        CheckConstraint(
            "default_priority IS NULL OR (default_priority >= 0 AND default_priority <= 9)",
            name="ck_task_definitions_default_priority_range",
        ),
        Index("ix_task_definitions_code", "code", unique=True),
        Index(
            "ix_task_definitions_scope_type",
            "scope",
            "definition_type",
        ),
        Index(
            "ix_task_definitions_owner_enabled",
            "owner_tenant_id",
            "is_enabled",
        ),
        Index("ix_task_definitions_default_priority", "default_priority"),
    )

    owner_tenant_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
        comment="归属企业ID（平台定义为 NULL）",
    )
    code: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="任务唯一编码",
    )
    name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        comment="任务名称",
    )
    definition_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default=TaskDefinitionTypeEnum.SYSTEM.value,
        comment="任务定义类型",
    )
    handler_path: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="真实执行处理器路径",
    )
    category: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="maintenance",
        comment="任务分类",
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="任务描述",
    )
    scope: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=ResourceScopeEnum.ADMIN_ONLY.value,
        comment="资源投放范围 ResourceScopeEnum",
    )
    default_schedule_type: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        default=ScheduleTypeEnum.INTERVAL.value,
        comment="默认调度类型",
    )
    default_cron_expression: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="默认 Cron 表达式",
    )
    default_interval_seconds: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="默认间隔秒数",
    )
    default_queue: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="scheduled",
        comment="默认队列",
    )
    default_priority: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        default=None,
        comment="默认队列优先级 / Default broker priority",
    )
    default_args: Mapped[dict | list | None] = mapped_column(
        JSON,
        nullable=True,
        default=None,
        comment="默认位置参数",
    )
    default_kwargs: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        default=None,
        comment="默认关键字参数",
    )
    config_schema: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        default=None,
        comment="覆盖配置 Schema",
    )
    is_system_builtin: Mapped[bool] = mapped_column(
        nullable=False,
        default=False,
        comment="是否系统内置任务",
    )
    max_retries: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="最大重试次数",
    )
    retry_delay: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=60,
        comment="重试间隔（秒）",
    )
    timeout: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=3600,
        comment="执行超时（秒）",
    )
    notify_on_failure: Mapped[bool] = mapped_column(
        nullable=False,
        default=False,
        comment="失败时是否通知",
    )
    notify_emails: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        default=None,
        comment="通知邮箱列表",
    )
    is_enabled: Mapped[bool] = mapped_column(
        nullable=False,
        default=True,
        comment="是否启用定义",
    )
    is_editable: Mapped[bool] = mapped_column(
        nullable=False,
        default=True,
        comment="是否允许编辑",
    )
    is_deletable: Mapped[bool] = mapped_column(
        nullable=False,
        default=True,
        comment="是否允许删除",
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


__all__ = ["TaskDefinition"]
