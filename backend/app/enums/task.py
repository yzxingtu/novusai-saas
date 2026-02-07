"""
任务相关枚举
"""

from app.enums.base import StrEnum


class TaskStatusEnum(StrEnum):
    """异步任务状态枚举"""

    PENDING = ("pending", "enum.task_status.pending")
    RUNNING = ("running", "enum.task_status.running")
    SUCCESS = ("success", "enum.task_status.success")
    FAILED = ("failed", "enum.task_status.failed")
    RETRYING = ("retrying", "enum.task_status.retrying")


class ScheduleTypeEnum(StrEnum):
    """定时任务调度类型枚举"""

    CRON = ("cron", "enum.schedule_type.cron")
    INTERVAL = ("interval", "enum.schedule_type.interval")


class TaskScopeEnum(StrEnum):
    """定时任务作用范围枚举"""

    PLATFORM = ("platform", "enum.task_scope.platform")
    TENANT = ("tenant", "enum.task_scope.tenant")
    ALL_TENANTS = ("all_tenants", "enum.task_scope.all_tenants")


__all__ = [
    "TaskStatusEnum",
    "ScheduleTypeEnum",
    "TaskScopeEnum",
]
