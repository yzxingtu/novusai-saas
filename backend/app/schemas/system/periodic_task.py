"""
定时任务相关 Schema / Periodic Task Schema

定义定时任务管理 API 的请求和响应数据结构
Defines periodic task management API request and response data structures.
"""

from datetime import datetime

from pydantic import Field, field_validator, model_validator

from app.core.base_schema import BaseSchema
from app.enums.common import ResourceScopeEnum

ALLOWED_PERIODIC_TASK_SCOPES = {
    ResourceScopeEnum.GLOBAL_SHARED.value,
    ResourceScopeEnum.ADMIN_ONLY.value,
    ResourceScopeEnum.ALL_TENANTS.value,
    ResourceScopeEnum.ADMIN_AND_SELECTED_TENANTS.value,
    ResourceScopeEnum.SELECTED_TENANTS.value,
}


class PeriodicTaskResponse(BaseSchema):
    """定时任务响应 / Periodic task response."""

    id: int = Field(..., description="ID")
    name: str = Field(..., description="任务名称")
    definition_type: str = Field("system", description="任务定义类型")
    task_path: str = Field(..., description="任务路径")
    schedule_type: str = Field(..., description="调度类型")
    cron_expression: str | None = Field(None, description="Cron 表达式")
    interval_seconds: int | None = Field(None, description="间隔秒数")
    is_active: bool = Field(True, description="是否启用")
    last_run_at: datetime | None = Field(None, description="上次执行时间")
    next_run_at: datetime | None = Field(None, description="下次执行时间")
    description: str | None = Field(None, description="任务描述")
    plugin_name: str | None = Field(None, description="插件名称（插件任务时返回）")
    plugin_enabled: bool = Field(True, description="关联插件当前是否已启用")
    scope: str = Field("admin_only", description="资源作用域 ResourceScopeEnum")
    owner_tenant_id: int | None = Field(None, description="归属企业ID（平台级为 NULL）")
    assigned_tenant_ids: list[int] = Field(
        default_factory=list,
        description="当前已绑定的企业 ID 列表",
    )
    assigned_tenant_names: list[str] = Field(
        default_factory=list,
        description="当前已绑定的企业名称列表",
    )
    binding_count: int = Field(0, description="已绑定企业数量")
    binding_required: bool = Field(False, description="当前 scope 是否要求选择企业")
    binding_configured: bool = Field(True, description="当前分发模式是否已完成绑定")
    tenant_access_mode: str = Field(
        "none", description="企业覆盖模式 none/all/selected"
    )
    binding_summary: str | None = Field(None, description="绑定摘要")
    is_locked: bool = Field(False, description="是否禁止删除")
    is_editable: bool = Field(True, description="是否允许编辑")
    default_priority: int | None = Field(
        None,
        ge=0,
        le=9,
        description="默认 Celery broker 优先级（0-9）",
    )
    required_feature_codes: list[str] = Field(
        default_factory=list,
        description="要求的企业套餐特性代码",
    )
    required_plugin_names: list[str] = Field(
        default_factory=list,
        description="要求的企业可用插件名称",
    )
    max_retries: int = Field(0, description="最大重试次数")
    retry_delay: int = Field(60, description="重试间隔（秒）")
    timeout: int = Field(3600, description="执行超时（秒）")
    notify_on_failure: bool = Field(False, description="失败时是否通知")
    notify_emails: str | None = Field(None, description="通知邮箱列表")
    created_at: datetime = Field(..., description="创建时间")


class PeriodicTaskCreateRequest(BaseSchema):
    """创建定时任务请求 / Create periodic task request."""

    name: str = Field(..., min_length=1, max_length=255, description="任务名称")
    task_path: str = Field(..., min_length=1, description="任务路径")
    schedule_type: str = Field("interval", description="调度类型（cron/interval）")
    cron_expression: str | None = Field(None, description="Cron 表达式")
    interval_seconds: int | None = Field(
        None, ge=10, description="间隔秒数（最小10秒）"
    )
    args: dict | None = Field(None, description="位置参数")
    kwargs: dict | None = Field(None, description="关键字参数")
    is_active: bool = Field(True, description="是否启用")
    description: str | None = Field(None, description="任务描述")
    scope: str = Field("admin_only", description="资源作用域 ResourceScopeEnum（五类）")
    owner_tenant_id: int | None = Field(
        None, description="归属企业ID（单企业任务时填写）"
    )
    tenant_ids: list[int] = Field(default_factory=list, description="分发企业 ID 列表")
    default_priority: int | None = Field(
        None,
        ge=0,
        le=9,
        description="默认 Celery broker 优先级（0-9）",
    )
    required_feature_codes: list[str] = Field(
        default_factory=list,
        description="要求的企业套餐特性代码",
    )
    required_plugin_names: list[str] = Field(
        default_factory=list,
        description="要求的企业可用插件名称",
    )
    max_retries: int = Field(0, ge=0, le=10, description="最大重试次数")
    retry_delay: int = Field(60, ge=1, le=3600, description="重试间隔（秒）")
    timeout: int = Field(3600, ge=10, le=86400, description="执行超时（秒）")
    notify_on_failure: bool = Field(False, description="失败时是否通知")
    notify_emails: str | None = Field(None, description="通知邮箱列表（逗号分隔）")

    @field_validator("scope")
    @classmethod
    def validate_scope_value(cls, value: str) -> str:
        if value not in ALLOWED_PERIODIC_TASK_SCOPES:
            raise ValueError("invalid scope")
        return value

    @model_validator(mode="after")
    def validate_scope_owner(self):
        if self.scope in (
            ResourceScopeEnum.ADMIN_ONLY.value,
            ResourceScopeEnum.GLOBAL_SHARED.value,
            ResourceScopeEnum.ALL_TENANTS.value,
        ):
            self.owner_tenant_id = None
        if self.scope not in (
            ResourceScopeEnum.SELECTED_TENANTS.value,
            ResourceScopeEnum.ADMIN_AND_SELECTED_TENANTS.value,
        ):
            self.tenant_ids = []
        return self


class PeriodicTaskUpdateRequest(BaseSchema):
    """更新定时任务请求 / Update periodic task request."""

    name: str | None = Field(None, min_length=1, max_length=255, description="任务名称")
    task_path: str | None = Field(None, min_length=1, description="任务路径")
    schedule_type: str | None = Field(None, description="调度类型")
    cron_expression: str | None = Field(None, description="Cron 表达式")
    interval_seconds: int | None = Field(None, ge=10, description="间隔秒数")
    args: dict | None = Field(None, description="位置参数")
    kwargs: dict | None = Field(None, description="关键字参数")
    is_active: bool | None = Field(None, description="是否启用")
    description: str | None = Field(None, description="任务描述")
    scope: str | None = Field(None, description="资源作用域")
    owner_tenant_id: int | None = Field(None, description="归属企业ID")
    tenant_ids: list[int] | None = Field(None, description="分发企业 ID 列表")
    default_priority: int | None = Field(
        None,
        ge=0,
        le=9,
        description="默认 Celery broker 优先级（0-9）",
    )
    required_feature_codes: list[str] | None = Field(
        None,
        description="要求的企业套餐特性代码",
    )
    required_plugin_names: list[str] | None = Field(
        None,
        description="要求的企业可用插件名称",
    )
    max_retries: int | None = Field(None, ge=0, le=10, description="最大重试次数")
    retry_delay: int | None = Field(None, ge=1, le=3600, description="重试间隔（秒）")
    timeout: int | None = Field(None, ge=10, le=86400, description="执行超时（秒）")
    notify_on_failure: bool | None = Field(None, description="失败时是否通知")
    notify_emails: str | None = Field(None, description="通知邮箱列表")

    @field_validator("scope")
    @classmethod
    def validate_scope_value(cls, value: str | None) -> str | None:
        if value is not None and value not in ALLOWED_PERIODIC_TASK_SCOPES:
            raise ValueError("invalid scope")
        return value

    @model_validator(mode="after")
    def validate_selected_scope_tenants(self):
        if self.scope in (
            ResourceScopeEnum.ADMIN_ONLY.value,
            ResourceScopeEnum.GLOBAL_SHARED.value,
            ResourceScopeEnum.ALL_TENANTS.value,
        ):
            self.owner_tenant_id = None
        return self


class PeriodicTaskToggleRequest(BaseSchema):
    """启用/禁用请求 / Enable/disable request."""

    is_active: bool = Field(..., description="是否启用")


class PeriodicTaskBindingResponse(BaseSchema):
    """定时任务企业绑定响应 / Periodic task tenant binding response."""

    id: int = Field(..., description="绑定 ID")
    tenant_id: int = Field(..., description="企业 ID")
    tenant_name: str | None = Field(None, description="企业名称")
    is_enabled: bool = Field(True, description="是否启用")
    disabled_reason: str | None = Field(None, description="禁用原因")
    schedule_type_override: str | None = Field(None, description="覆盖调度类型")
    cron_expression_override: str | None = Field(None, description="覆盖 Cron 表达式")
    interval_seconds_override: int | None = Field(None, description="覆盖间隔秒数")
    config_override: dict | None = Field(None, description="覆盖配置")
    args_override: dict | list | None = Field(None, description="覆盖位置参数")
    kwargs_override: dict | None = Field(None, description="覆盖关键字参数")
    effective_schedule_type: str | None = Field(None, description="生效调度类型")
    effective_cron_expression: str | None = Field(None, description="生效 Cron 表达式")
    effective_interval_seconds: int | None = Field(None, description="生效间隔秒数")
    last_run_at: datetime | None = Field(None, description="上次执行时间")
    next_run_at: datetime | None = Field(None, description="下次执行时间")


class PeriodicTaskBindingUpdateRequest(BaseSchema):
    """单条企业绑定更新请求 / Single tenant binding update request."""

    is_enabled: bool | None = Field(None, description="是否启用")
    disabled_reason: str | None = Field(None, max_length=500, description="禁用原因")
    schedule_type_override: str | None = Field(None, description="覆盖调度类型")
    cron_expression_override: str | None = Field(None, description="覆盖 Cron 表达式")
    interval_seconds_override: int | None = Field(
        None,
        ge=10,
        description="覆盖间隔秒数",
    )
    config_override: dict | None = Field(None, description="覆盖配置")
    args_override: dict | list | None = Field(None, description="覆盖位置参数")
    kwargs_override: dict | None = Field(None, description="覆盖关键字参数")

    @field_validator("schedule_type_override")
    @classmethod
    def validate_schedule_type_override(cls, value: str | None) -> str | None:
        if value is not None and value not in {"cron", "interval"}:
            raise ValueError("invalid schedule_type_override")
        return value


class PeriodicTaskBindingSyncItem(PeriodicTaskBindingUpdateRequest):
    """批量同步中的单条企业绑定配置 / Tenant binding config in batch sync."""

    tenant_id: int = Field(..., description="企业 ID")


class PeriodicTaskBindingSyncRequest(BaseSchema):
    """定时任务企业绑定同步请求 / Periodic task tenant binding sync request."""

    tenant_ids: list[int] = Field(default_factory=list, description="企业 ID 列表")
    bindings: list[PeriodicTaskBindingSyncItem] = Field(
        default_factory=list,
        description="企业绑定覆盖配置列表",
    )
    scope: str | None = Field(
        None,
        description="同步后的目标作用域；不传时按是否有企业绑定自动推导",
    )

    @field_validator("scope")
    @classmethod
    def validate_scope_value(cls, value: str | None) -> str | None:
        if value is not None and value not in ALLOWED_PERIODIC_TASK_SCOPES:
            raise ValueError("invalid scope")
        return value

    @model_validator(mode="after")
    def normalize_tenant_ids_for_non_explicit_scope(self):
        if self.scope is not None and self.scope not in (
            ResourceScopeEnum.SELECTED_TENANTS.value,
            ResourceScopeEnum.ADMIN_AND_SELECTED_TENANTS.value,
            ResourceScopeEnum.ALL_TENANTS.value,
        ):
            self.tenant_ids = []
        return self


__all__ = [
    "PeriodicTaskResponse",
    "PeriodicTaskCreateRequest",
    "PeriodicTaskUpdateRequest",
    "PeriodicTaskToggleRequest",
    "PeriodicTaskBindingResponse",
    "PeriodicTaskBindingUpdateRequest",
    "PeriodicTaskBindingSyncItem",
    "PeriodicTaskBindingSyncRequest",
]
