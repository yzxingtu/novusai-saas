"""
智能体相关 Schema

定义智能体的请求和响应数据结构
"""

from pydantic import BaseModel, Field, field_validator

from app.core.base_schema import (
    BaseCreateSchema,
    BaseUpdateSchema,
    TenantResponseSchema,
)
from app.core.i18n import _
from app.enums.common import AudienceEnum

# ============================================
# Shared field mixins
# ============================================

class _AgentOptionalFields(BaseModel):
    """Agent 共享可选字段（Create/Update/Response 通用）"""

    description: str | None = Field(None, description=_("enum.agent_model.description"))
    avatar: str | None = Field(None, max_length=255, description=_("enum.agent_model.avatar"))
    max_tokens: int | None = Field(None, ge=1, description=_("enum.agent_model.max_tokens"))
    top_p: float | None = Field(None, ge=0.0, le=1.0, description=_("enum.agent_model.top_p"))
    input_variables: list | None = Field(None, description=_("enum.agent_model.input_variables"))
    welcome_message: str | None = Field(None, description=_("enum.agent_model.welcome_message"))
    suggested_questions: list | None = Field(None, description=_("enum.agent_model.suggested_questions"))
    rag_config: dict | None = Field(None, description=_("enum.agent_model.rag_config"))
    context_config: dict | None = Field(None, description=_("enum.agent_model.context_config"))
    output_schema: list | None = Field(None, description=_("enum.agent_model.output_schema"))
    quota_config: dict | None = Field(None, description=_("enum.agent_model.quota_config"))
    routing_config: dict | None = Field(None, description=_("enum.agent_model.routing_config"))
    memory_enabled: bool | None = Field(None, description=_("enum.agent_model.memory_enabled"))


# ============================================
# Tenant schemas
# ============================================

class AgentCreate(_AgentOptionalFields, BaseCreateSchema):
    """创建智能体请求"""

    name: str = Field(..., max_length=100, description=_("enum.agent_model.name"))
    system_prompt: str | None = Field("", description=_("enum.agent_model.system_prompt"))

    @field_validator("system_prompt", mode="before")
    @classmethod
    def _coerce_prompt(cls, v: object) -> str:
        return v if isinstance(v, str) else ""
    model_id: int = Field(..., description=_("enum.agent_model.model_id"))
    temperature: float = Field(0.7, ge=0.0, le=2.0, description=_("enum.agent_model.temperature"))
    execution_mode: str = Field("conversation", description=_("enum.agent_model.execution_mode"))
    visibility: str = Field("public", description=_("enum.agent_model.visibility"))

class AgentUpdate(_AgentOptionalFields, BaseUpdateSchema):
    """更新智能体请求"""

    name: str | None = Field(None, max_length=100, description=_("enum.agent_model.name"))
    system_prompt: str | None = Field(None, description=_("enum.agent_model.system_prompt"))
    model_id: int | None = Field(None, description=_("enum.agent_model.model_id"))
    temperature: float | None = Field(None, ge=0.0, le=2.0, description=_("enum.agent_model.temperature"))
    # NOTE: status removed - use publish/rollback endpoints to change status
    execution_mode: str | None = Field(None, description=_("enum.agent_model.execution_mode"))
    visibility: str | None = Field(None, description=_("enum.agent_model.visibility"))


# ============================================
# Admin schemas
# ============================================

class AdminAgentCreate(_AgentOptionalFields, BaseCreateSchema):
    """管理端创建智能体请求（支持 scope）"""

    name: str = Field(..., max_length=100, description=_("enum.agent_model.name"))
    scope: str = Field("all_tenants", description=_("enum.agent_model.scope"))
    target_audience: str = Field(AudienceEnum.ADMIN_TENANT.value, max_length=20, description=_("enum.agent_model.target_audience"))
    tenant_id: int | None = Field(None, description=_("enum.agent_model.tenant_id"))
    tenant_ids: list[int] | None = Field(None, description="分配的租户 ID 列表（scope=assigned_tenants/admin_and_assigned 时使用）")
    system_prompt: str | None = Field("", description=_("enum.agent_model.system_prompt"))

    @field_validator("system_prompt", mode="before")
    @classmethod
    def _coerce_prompt(cls, v: object) -> str:
        return v if isinstance(v, str) else ""
    model_id: int = Field(..., description=_("enum.agent_model.model_id"))
    temperature: float = Field(0.7, ge=0.0, le=2.0, description=_("enum.agent_model.temperature"))
    execution_mode: str = Field("conversation", description=_("enum.agent_model.execution_mode"))
    visibility: str = Field("public", description=_("enum.agent_model.visibility"))


class AdminAgentUpdate(_AgentOptionalFields, BaseUpdateSchema):
    """管理端更新智能体请求"""

    name: str | None = Field(None, max_length=100, description=_("enum.agent_model.name"))
    scope: str | None = Field(None, description=_("enum.agent_model.scope"))
    target_audience: str | None = Field(None, max_length=20, description=_("enum.agent_model.target_audience"))
    tenant_id: int | None = Field(None, description=_("enum.agent_model.tenant_id"))
    tenant_ids: list[int] | None = Field(None, description="分配的租户 ID 列表（scope=assigned_tenants/admin_and_assigned 时使用）")
    system_prompt: str | None = Field(None, description=_("enum.agent_model.system_prompt"))
    model_id: int | None = Field(None, description=_("enum.agent_model.model_id"))
    temperature: float | None = Field(None, ge=0.0, le=2.0, description=_("enum.agent_model.temperature"))
    execution_mode: str | None = Field(None, description=_("enum.agent_model.execution_mode"))
    visibility: str | None = Field(None, description=_("enum.agent_model.visibility"))
    status: str | None = Field(None, description=_("enum.agent_model.status"))


class AgentResponse(_AgentOptionalFields, TenantResponseSchema):
    """智能体详情响应"""

    name: str = Field(..., description=_("enum.agent_model.name"))
    system_prompt: str = Field(..., description=_("enum.agent_model.system_prompt"))
    model_id: int = Field(..., description=_("enum.agent_model.model_id"))
    temperature: float = Field(..., description=_("enum.agent_model.temperature"))
    status: str = Field(..., description=_("enum.agent_model.status"))
    execution_mode: str = Field(..., description=_("enum.agent_model.execution_mode"))
    published_version: int | None = Field(None, description=_("enum.agent_model.published_version"))
    visibility: str | None = Field(None, description=_("enum.agent_model.visibility"))
    scope: str | None = Field(None, description=_("enum.agent_model.scope"))
    target_audience: str = Field(AudienceEnum.ADMIN_TENANT.value, description=_("enum.agent_model.target_audience"))
    is_system: bool = Field(False, description=_("enum.agent_model.is_system"))
    # 关联字段
    model_name: str | None = Field(None, description=_("enum.agent_model.model_name"))
    model_code: str | None = Field(None, description=_("enum.agent_model.model_code"))
    effective_memory_enabled: bool | None = Field(
        None,
        description=_("enum.agent_model.effective_memory_enabled"),
    )
    memory_disabled_by_tenant: bool | None = Field(
        None,
        description=_("enum.agent_model.memory_disabled_by_tenant"),
    )


class AgentListItem(TenantResponseSchema):
    """智能体列表项响应（精简字段）"""

    name: str = Field(..., description=_("enum.agent_model.name"))
    avatar: str | None = Field(None, description=_("enum.agent_model.avatar"))
    description: str | None = Field(None, description=_("enum.agent_model.description"))
    status: str = Field(..., description=_("enum.agent_model.status"))
    execution_mode: str = Field(..., description=_("enum.agent_model.execution_mode"))
    is_system: bool = Field(False, description=_("enum.agent_model.is_system"))
    model_name: str | None = Field(None, description=_("enum.agent_model.model_name"))


__all__ = [
    "AgentCreate",
    "AgentUpdate",
    "AdminAgentCreate",
    "AdminAgentUpdate",
    "AgentResponse",
    "AgentListItem",
]
