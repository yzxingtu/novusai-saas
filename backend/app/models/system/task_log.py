"""
任务日志模型 / Task Log Model

记录 Celery 异步任务的执行历史
Records Celery async task execution history.
"""

from datetime import datetime

from sqlalchemy import Index, Text
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base_model import BaseModel
from app.enums.task import TaskStatusEnum


class TaskLog(BaseModel):
    """
    任务日志模型

    记录异步任务的执行状态、参数、结果和耗时
    """

    __tablename__ = "task_logs"

    __filterable__ = {
        "id": "id",
        "task_id": "task_id",
        "task_name": "task_name",
        "queue": "queue",
        "status": "status",
        "tenant_id": "tenant_id",
        "created_at": "created_at",
    }

    __sortable__ = ["created_at", "duration_ms", "task_name"]

    __table_args__ = (
        Index("ix_task_logs_name_status", "task_name", "status"),
        Index("ix_task_logs_tenant_id", "tenant_id"),
    )

    task_id: Mapped[str] = mapped_column(
        comment="Celery Task ID",
        index=True,
    )
    task_name: Mapped[str] = mapped_column(
        comment="任务名称",
    )
    queue: Mapped[str] = mapped_column(
        default="default",
        comment="队列名称",
    )
    status: Mapped[str] = mapped_column(
        default=TaskStatusEnum.PENDING.value,
        comment="任务状态",
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
    result: Mapped[dict | None] = mapped_column(
        JSON,
        default=None,
        comment="执行结果",
    )
    error_message: Mapped[str | None] = mapped_column(
        Text,
        default=None,
        comment="错误信息",
    )
    traceback: Mapped[str | None] = mapped_column(
        Text,
        default=None,
        comment="异常堆栈",
    )
    started_at: Mapped[datetime | None] = mapped_column(
        default=None,
        comment="开始时间",
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        default=None,
        comment="完成时间",
    )
    duration_ms: Mapped[int | None] = mapped_column(
        default=None,
        comment="耗时(毫秒)",
    )
    retry_count: Mapped[int] = mapped_column(
        default=0,
        comment="重试次数",
    )
    tenant_id: Mapped[int | None] = mapped_column(
        default=None,
        comment="企业ID(可选)",
    )
