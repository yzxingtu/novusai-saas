"""
任务相关枚举 / Task Enums
"""

from app.enums.base import StrEnum


class TaskStatusEnum(StrEnum):
    """Async Task Status Enum / 异步任务状态枚举"""

    PENDING = ("pending", "enum.task_status.pending")
    RUNNING = ("running", "enum.task_status.running")
    SUCCESS = ("success", "enum.task_status.success")
    FAILED = ("failed", "enum.task_status.failed")
    RETRYING = ("retrying", "enum.task_status.retrying")


class ScheduleTypeEnum(StrEnum):
    """Schedule Type Enum / 定时任务调度类型枚举"""

    CRON = ("cron", "enum.schedule_type.cron")
    INTERVAL = ("interval", "enum.schedule_type.interval")


__all__ = [
    "TaskStatusEnum",
    "ScheduleTypeEnum",
]
