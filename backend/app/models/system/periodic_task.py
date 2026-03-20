"""
定时任务模型 / Periodic Task Model

记录和管理数据库驱动的定时任务调度配置
Records and manages database-driven periodic task scheduling configuration.
"""

from datetime import datetime

from sqlalchemy import ForeignKey, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column, synonym

from app.core.base_model import BaseModel
from app.enums.common import ResourceScopeEnum
from app.enums.task import ScheduleTypeEnum


class PeriodicTask(BaseModel):
    """
    定时任务模型 / Periodic task model.

    支持 cron 表达式和间隔调度两种模式
    """

    __tablename__ = "periodic_tasks"

    __filterable__ = {
        "id": "id",
        "name": "name",
        "task_path": "task_path",
        "schedule_type": "schedule_type",
        "is_active": "is_active",
        "owner_tenant_id": "owner_tenant_id",
        "scope": "scope",
        "created_at": "created_at",
    }

    __sortable__ = ["created_at", "name", "next_run_at", "last_run_at"]

    __table_args__ = (
        UniqueConstraint("name", "owner_tenant_id", name="uq_periodic_tasks_name_owner_tenant"),
    )

    name: Mapped[str] = mapped_column(
        comment="任务名称（唯一）",
    )
    task_path: Mapped[str] = mapped_column(
        comment="任务路径（如 app.tasks.cleanup.clean_expired_sessions）",
    )
    schedule_type: Mapped[str] = mapped_column(
        default=ScheduleTypeEnum.INTERVAL.value,
        comment="调度类型（cron/interval）",
    )
    cron_expression: Mapped[str | None] = mapped_column(
        default=None,
        comment="Cron 表达式（schedule_type=cron 时使用）",
    )
    interval_seconds: Mapped[int | None] = mapped_column(
        default=None,
        comment="间隔秒数（schedule_type=interval 时使用）",
    )
    args: Mapped[dict | None] = mapped_column(
        JSON,
        default=None,
        comment="位置参数",
    )
    kwargs: Mapped[dict | None] = mapped_column(
        JSON,
        default=None,
        comment="关键字参数",
    )
    is_active: Mapped[bool] = mapped_column(
        default=True,
        comment="是否启用",
    )
    last_run_at: Mapped[datetime | None] = mapped_column(
        default=None,
        comment="上次执行时间",
    )
    next_run_at: Mapped[datetime | None] = mapped_column(
        default=None,
        comment="下次执行时间",
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        default=None,
        comment="任务描述",
    )
    owner_tenant_id: Mapped[int | None] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"),
        default=None,
        index=True,
        comment="所属企业ID（NULL表示平台级任务）",
    )
    # TenantRepository 仍注入/过滤 tenant_id；映射到 owner_tenant_id 列
    tenant_id = synonym("owner_tenant_id")
    scope: Mapped[str] = mapped_column(
        default=ResourceScopeEnum.ADMIN_ONLY.value,
        comment="资源作用域 ResourceScopeEnum（五类）/ Resource scope",
    )
    is_locked: Mapped[bool] = mapped_column(
        default=False,
        comment="是否禁止删除",
    )
    is_editable: Mapped[bool] = mapped_column(
        default=True,
        comment="是否允许编辑",
    )
    max_retries: Mapped[int] = mapped_column(
        default=0,
        comment="最大重试次数",
    )
    retry_delay: Mapped[int] = mapped_column(
        default=60,
        comment="重试间隔（秒）",
    )
    timeout: Mapped[int] = mapped_column(
        default=3600,
        comment="执行超时（秒）",
    )
    notify_on_failure: Mapped[bool] = mapped_column(
        default=False,
        comment="失败时是否通知",
    )
    notify_emails: Mapped[str | None] = mapped_column(
        Text,
        default=None,
        comment="通知邮箱列表（逗号分隔）",
    )
