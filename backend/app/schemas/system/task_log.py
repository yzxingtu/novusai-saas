"""
任务日志相关 Schema / Task Log Schema

定义任务管理 API 的请求和响应数据结构
Defines task management API request and response data structures.
"""

from datetime import datetime
from typing import Any

from pydantic import Field

from app.core.base_schema import BaseSchema


class TaskLogResponse(BaseSchema):
    """任务日志响应 / Task log response"""

    id: int = Field(..., description="ID")
    task_id: str = Field(..., description="Celery Task ID")
    task_name: str = Field(..., description="任务名称")
    handler_path: str | None = Field(None, description="处理器路径")
    queue: str = Field("default", description="队列名称")
    status: str = Field(..., description="任务状态")
    args: Any = Field(None, description="位置参数")
    kwargs: Any = Field(None, description="关键字参数")
    result: Any = Field(None, description="执行结果")
    error_message: str | None = Field(None, description="错误信息")
    trigger_source: str | None = Field(None, description="触发来源")
    run_kind: str | None = Field(None, description="运行类型")
    trace_id: str | None = Field(None, description="链路追踪 ID")
    started_at: datetime | None = Field(None, description="开始时间")
    finished_at: datetime | None = Field(None, description="完成时间")
    duration_ms: int | None = Field(None, description="耗时(毫秒)")
    retry_count: int = Field(0, description="重试次数")
    tenant_id: int | None = Field(None, description="企业ID")
    created_at: datetime = Field(..., description="创建时间")


class TaskLogDetailResponse(TaskLogResponse):
    """任务日志详情响应（含堆栈） / Task log detail response (with traceback)"""

    traceback: str | None = Field(None, description="异常堆栈")


class TaskStatsResponse(BaseSchema):
    """任务统计响应 / Task stats response"""

    status: str = Field(..., description="任务状态")
    count: int = Field(0, description="数量")
    avg_duration_ms: float = Field(0, description="平均耗时(毫秒)")


class TaskRetryRequest(BaseSchema):
    """任务重试请求 / Task retry request"""

    queue: str | None = Field(None, description="指定队列（留空使用原队列）")


class ActiveTaskResponse(BaseSchema):
    """活跃任务响应 / Active task response"""

    task_id: str = Field(..., description="Task ID")
    task_name: str = Field(..., description="任务名称")
    worker: str = Field(..., description="Worker 名称")
    started_at: float | None = Field(None, description="开始时间戳")


__all__ = [
    "TaskLogResponse",
    "TaskLogDetailResponse",
    "TaskStatsResponse",
    "TaskRetryRequest",
    "ActiveTaskResponse",
]
