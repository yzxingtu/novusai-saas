"""
任务运行记录模型 / Task Run Model

作为下一代统一运行中心的执行事实表。
Acts as the execution fact table for the next-generation task run center.
"""

from datetime import datetime

from sqlalchemy import ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base_model import BaseModel
from app.enums.task import TaskRunKindEnum, TaskStatusEnum, TaskTriggerSourceEnum


class TaskRun(BaseModel):
    """
    任务运行记录模型 / Task run model.

    记录单次执行与调度定义、企业绑定、触发来源之间的关系。
    Records a single execution and its relation to definitions, tenant bindings, and trigger source.
    """

    __tablename__ = "task_runs"

    __filterable__ = {
        "id": "id",
        "celery_task_id": "celery_task_id",
        "task_id": "celery_task_id",
        "task_definition_id": "task_definition_id",
        "binding_id": "binding_id",
        "task_name": "task_name_snapshot",
        "handler_path": "handler_path_snapshot",
        "queue": "queue",
        "status": "status",
        "trigger_source": "trigger_source",
        "run_kind": "run_kind",
        "owner_tenant_id": "owner_tenant_id",
        "effective_tenant_id": "effective_tenant_id",
        "tenant_id": "effective_tenant_id",
        "created_at": "created_at",
    }

    __sortable__ = {
        "id": "id",
        "created_at": "created_at",
        "started_at": "started_at",
        "finished_at": "finished_at",
        "duration_ms": "duration_ms",
        "task_name": "task_name_snapshot",
        "handler_path": "handler_path_snapshot",
    }

    __table_args__ = (
        Index("ix_task_runs_celery_task_id", "celery_task_id", unique=True),
        Index(
            "ix_task_runs_definition_status",
            "task_definition_id",
            "status",
        ),
        Index(
            "ix_task_runs_effective_tenant_created",
            "effective_tenant_id",
            "created_at",
        ),
        Index(
            "ix_task_runs_trigger_kind_created",
            "trigger_source",
            "run_kind",
            "created_at",
        ),
    )

    celery_task_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Celery 任务 ID",
    )
    task_definition_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("task_definitions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="任务定义 ID",
    )
    binding_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("tenant_task_bindings.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="企业任务绑定 ID",
    )
    task_code_snapshot: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="运行时任务编码快照",
    )
    task_name_snapshot: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        comment="运行时任务名称快照",
    )
    handler_path_snapshot: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="运行时处理器路径快照",
    )
    trigger_source: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default=TaskTriggerSourceEnum.SCHEDULER.value,
        comment="触发来源",
    )
    run_kind: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default=TaskRunKindEnum.PLATFORM.value,
        comment="运行类型",
    )
    owner_tenant_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("tenants.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="资源归属企业 ID",
    )
    effective_tenant_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("tenants.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="本次执行影响的企业 ID",
    )
    queue: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="default",
        comment="执行队列",
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=TaskStatusEnum.PENDING.value,
        comment="执行状态",
    )
    summary: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="结果摘要",
    )
    args_summary: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        default=None,
        comment="输入摘要",
    )
    result_summary: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        default=None,
        comment="输出摘要",
    )
    error_code: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="错误代码",
    )
    error_message_public: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="对外错误信息",
    )
    error_message_internal: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="内部错误信息",
    )
    traceback_internal: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="内部异常堆栈",
    )
    trace_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="链路追踪 ID",
    )
    started_at: Mapped[datetime | None] = mapped_column(
        nullable=True,
        default=None,
        comment="开始时间",
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        nullable=True,
        default=None,
        comment="完成时间",
    )
    duration_ms: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        default=None,
        comment="耗时（毫秒）",
    )
    retry_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="重试次数",
    )


__all__ = ["TaskRun"]
