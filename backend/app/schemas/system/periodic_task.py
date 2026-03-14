"""
定时任务相关 Schema / Periodic Task Schema

定义定时任务管理 API 的请求和响应数据结构
Defines periodic task management API request and response data structures.
"""

from datetime import datetime

from pydantic import Field, model_validator

from app.core.base_schema import BaseSchema
from app.enums.common import ResourceScopeEnum


class PeriodicTaskResponse(BaseSchema):
    """定时任务响应"""

    id: int = Field(..., description="ID")
    name: str = Field(..., description="任务名称")
    task_path: str = Field(..., description="任务路径")
    schedule_type: str = Field(..., description="调度类型")
    cron_expression: str | None = Field(None, description="Cron 表达式")
    interval_seconds: int | None = Field(None, description="间隔秒数")
    is_active: bool = Field(True, description="是否启用")
    last_run_at: datetime | None = Field(None, description="上次执行时间")
    next_run_at: datetime | None = Field(None, description="下次执行时间")
    description: str | None = Field(None, description="任务描述")
    scope: str = Field("admin_only", description="作用范围")
    tenant_id: int | None = Field(None, description="所属企业ID")
    is_locked: bool = Field(False, description="是否禁止删除")
    is_editable: bool = Field(True, description="是否允许编辑")
    max_retries: int = Field(0, description="最大重试次数")
    retry_delay: int = Field(60, description="重试间隔（秒）")
    timeout: int = Field(3600, description="执行超时（秒）")
    notify_on_failure: bool = Field(False, description="失败时是否通知")
    notify_emails: str | None = Field(None, description="通知邮箱列表")
    created_at: datetime = Field(..., description="创建时间")


class PeriodicTaskCreateRequest(BaseSchema):
    """创建定时任务请求"""

    name: str = Field(..., min_length=1, max_length=255, description="任务名称")
    task_path: str = Field(..., min_length=1, description="任务路径")
    schedule_type: str = Field("interval", description="调度类型（cron/interval）")
    cron_expression: str | None = Field(None, description="Cron 表达式")
    interval_seconds: int | None = Field(None, ge=10, description="间隔秒数（最小10秒）")
    args: dict | None = Field(None, description="位置参数")
    kwargs: dict | None = Field(None, description="关键字参数")
    is_active: bool = Field(True, description="是否启用")
    description: str | None = Field(None, description="任务描述")
    scope: str = Field("admin_only", description="作用范围（platform/tenant/all_tenants）")
    tenant_id: int | None = Field(None, description="所属企业ID（scope=tenant时必填）")
    is_locked: bool = Field(False, description="是否禁止删除")
    is_editable: bool = Field(True, description="是否允许编辑")
    max_retries: int = Field(0, ge=0, le=10, description="最大重试次数")
    retry_delay: int = Field(60, ge=1, le=3600, description="重试间隔（秒）")
    timeout: int = Field(3600, ge=10, le=86400, description="执行超时（秒）")
    notify_on_failure: bool = Field(False, description="失败时是否通知")
    notify_emails: str | None = Field(None, description="通知邮箱列表（逗号分隔）")

    @model_validator(mode="after")
    def validate_scope_tenant(self):
        if self.scope == ResourceScopeEnum.ALL_TENANTS.value and self.tenant_id is None:
            raise ValueError("tenant_id is required when scope is all_tenants")
        if self.scope != ResourceScopeEnum.ALL_TENANTS.value and self.tenant_id is not None:
            self.tenant_id = None
        return self


class PeriodicTaskUpdateRequest(BaseSchema):
    """更新定时任务请求"""

    name: str | None = Field(None, min_length=1, max_length=255, description="任务名称")
    task_path: str | None = Field(None, min_length=1, description="任务路径")
    schedule_type: str | None = Field(None, description="调度类型")
    cron_expression: str | None = Field(None, description="Cron 表达式")
    interval_seconds: int | None = Field(None, ge=10, description="间隔秒数")
    args: dict | None = Field(None, description="位置参数")
    kwargs: dict | None = Field(None, description="关键字参数")
    is_active: bool | None = Field(None, description="是否启用")
    description: str | None = Field(None, description="任务描述")
    scope: str | None = Field(None, description="作用范围")
    tenant_id: int | None = Field(None, description="所属企业ID")
    is_locked: bool | None = Field(None, description="是否禁止删除")
    is_editable: bool | None = Field(None, description="是否允许编辑")
    max_retries: int | None = Field(None, ge=0, le=10, description="最大重试次数")
    retry_delay: int | None = Field(None, ge=1, le=3600, description="重试间隔（秒）")
    timeout: int | None = Field(None, ge=10, le=86400, description="执行超时（秒）")
    notify_on_failure: bool | None = Field(None, description="失败时是否通知")
    notify_emails: str | None = Field(None, description="通知邮箱列表")


class PeriodicTaskToggleRequest(BaseSchema):
    """启用/禁用请求"""

    is_active: bool = Field(..., description="是否启用")


__all__ = [
    "PeriodicTaskResponse",
    "PeriodicTaskCreateRequest",
    "PeriodicTaskUpdateRequest",
    "PeriodicTaskToggleRequest",
]
