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


class TaskDefinitionTypeEnum(StrEnum):
    """Task definition type / 任务定义类型"""

    SYSTEM = ("system", "enum.task_definition_type.system")
    PLUGIN = ("plugin", "enum.task_definition_type.plugin")
    BUSINESS = ("business", "enum.task_definition_type.business")


class TaskRunKindEnum(StrEnum):
    """Task run kind / 任务运行类型"""

    PLATFORM = ("platform", "enum.task_run_kind.platform")
    TENANT_BINDING = ("tenant_binding", "enum.task_run_kind.tenant_binding")
    ON_DEMAND = ("on_demand", "enum.task_run_kind.on_demand")


class TaskTriggerSourceEnum(StrEnum):
    """Task trigger source / 任务触发来源"""

    SCHEDULER = ("scheduler", "enum.task_trigger_source.scheduler")
    ADMIN_MANUAL = ("admin_manual", "enum.task_trigger_source.admin_manual")
    TENANT_MANUAL = ("tenant_manual", "enum.task_trigger_source.tenant_manual")
    SYSTEM_RECOVERY = ("system_recovery", "enum.task_trigger_source.system_recovery")


__all__ = [
    "TaskStatusEnum",
    "ScheduleTypeEnum",
    "TaskDefinitionTypeEnum",
    "TaskRunKindEnum",
    "TaskTriggerSourceEnum",
]
