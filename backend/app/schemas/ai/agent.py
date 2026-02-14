"""
智能体相关 Schema

定义智能体的请求和响应数据结构
"""

from pydantic import Field

from app.core.base_schema import (
    BaseCreateSchema,
    BaseUpdateSchema,
    TenantResponseSchema,
)
from app.core.i18n import _


class AgentCreate(BaseCreateSchema):
    """创建智能体请求"""

    name: str = Field(..., max_length=100, description=_("enum.agent_model.name"))
    description: str | None = Field(None, description=_("enum.agent_model.description"))
    avatar: str | None = Field(None, max_length=255, description=_("enum.agent_model.avatar"))
    system_prompt: str = Field(..., description=_("enum.agent_model.system_prompt"))
    model_id: int = Field(..., description=_("enum.agent_model.model_id"))
    temperature: float = Field(0.7, ge=0.0, le=2.0, description=_("enum.agent_model.temperature"))
    max_tokens: int | None = Field(None, ge=1, description=_("enum.agent_model.max_tokens"))
    top_p: float | None = Field(None, ge=0.0, le=1.0, description=_("enum.agent_model.top_p"))
    execution_mode: str = Field("conversation", description=_("enum.agent_model.execution_mode"))
    tool_bindings: list | None = Field(None, description=_("enum.agent_model.tool_bindings"))
    input_variables: list | None = Field(None, description=_("enum.agent_model.input_variables"))
    welcome_message: str | None = Field(None, description=_("enum.agent_model.welcome_message"))
    suggested_questions: list | None = Field(None, description=_("enum.agent_model.suggested_questions"))
    context_config: dict | None = Field(None, description=_("enum.agent_model.context_config"))
    output_schema: list | None = Field(None, description=_("enum.agent_model.output_schema"))
    quota_config: dict | None = Field(None, description=_("enum.agent_model.quota_config"))
    visibility: str = Field("public", description=_("enum.agent_model.visibility"))

class AgentUpdate(BaseUpdateSchema):
    """更新智能体请求"""

    name: str | None = Field(None, max_length=100, description=_("enum.agent_model.name"))
    description: str | None = Field(None, description=_("enum.agent_model.description"))
    avatar: str | None = Field(None, max_length=255, description=_("enum.agent_model.avatar"))
    system_prompt: str | None = Field(None, description=_("enum.agent_model.system_prompt"))
    model_id: int | None = Field(None, description=_("enum.agent_model.model_id"))
    temperature: float | None = Field(None, ge=0.0, le=2.0, description=_("enum.agent_model.temperature"))
    max_tokens: int | None = Field(None, ge=1, description=_("enum.agent_model.max_tokens"))
    top_p: float | None = Field(None, ge=0.0, le=1.0, description=_("enum.agent_model.top_p"))
    # NOTE: status removed - use publish/rollback endpoints to change status
    execution_mode: str | None = Field(None, description=_("enum.agent_model.execution_mode"))
    tool_bindings: list | None = Field(None, description=_("enum.agent_model.tool_bindings"))
    input_variables: list | None = Field(None, description=_("enum.agent_model.input_variables"))
    welcome_message: str | None = Field(None, description=_("enum.agent_model.welcome_message"))
    suggested_questions: list | None = Field(None, description=_("enum.agent_model.suggested_questions"))
    context_config: dict | None = Field(None, description=_("enum.agent_model.context_config"))
    output_schema: list | None = Field(None, description=_("enum.agent_model.output_schema"))
    quota_config: dict | None = Field(None, description=_("enum.agent_model.quota_config"))
    visibility: str | None = Field(None, description=_("enum.agent_model.visibility"))

class AdminAgentCreate(BaseCreateSchema):
    """管理端创建智能体请求（支持 scope）"""

    name: str = Field(..., max_length=100, description=_("enum.agent_model.name"))
    description: str | None = Field(None, description=_("enum.agent_model.description"))
    avatar: str | None = Field(None, max_length=255, description=_("enum.agent_model.avatar"))
    scope: str = Field("tenant", description=_("enum.agent_model.scope"))
    tenant_id: int | None = Field(None, description=_("enum.agent_model.tenant_id"))
    system_prompt: str = Field(..., description=_("enum.agent_model.system_prompt"))
    model_id: int = Field(..., description=_("enum.agent_model.model_id"))
    temperature: float = Field(0.7, ge=0.0, le=2.0, description=_("enum.agent_model.temperature"))
    max_tokens: int | None = Field(None, ge=1, description=_("enum.agent_model.max_tokens"))
    top_p: float | None = Field(None, ge=0.0, le=1.0, description=_("enum.agent_model.top_p"))
    execution_mode: str = Field("conversation", description=_("enum.agent_model.execution_mode"))
    tool_bindings: list | None = Field(None, description=_("enum.agent_model.tool_bindings"))
    input_variables: list | None = Field(None, description=_("enum.agent_model.input_variables"))
    welcome_message: str | None = Field(None, description=_("enum.agent_model.welcome_message"))
    suggested_questions: list | None = Field(None, description=_("enum.agent_model.suggested_questions"))
    context_config: dict | None = Field(None, description=_("enum.agent_model.context_config"))
    output_schema: list | None = Field(None, description=_("enum.agent_model.output_schema"))
    quota_config: dict | None = Field(None, description=_("enum.agent_model.quota_config"))
    visibility: str = Field("public", description=_("enum.agent_model.visibility"))


class AdminAgentUpdate(BaseUpdateSchema):
    """管理端更新智能体请求"""

    name: str | None = Field(None, max_length=100, description=_("enum.agent_model.name"))
    description: str | None = Field(None, description=_("enum.agent_model.description"))
    avatar: str | None = Field(None, max_length=255, description=_("enum.agent_model.avatar"))
    scope: str | None = Field(None, description=_("enum.agent_model.scope"))
    tenant_id: int | None = Field(None, description=_("enum.agent_model.tenant_id"))
    system_prompt: str | None = Field(None, description=_("enum.agent_model.system_prompt"))
    model_id: int | None = Field(None, description=_("enum.agent_model.model_id"))
    temperature: float | None = Field(None, ge=0.0, le=2.0, description=_("enum.agent_model.temperature"))
    max_tokens: int | None = Field(None, ge=1, description=_("enum.agent_model.max_tokens"))
    top_p: float | None = Field(None, ge=0.0, le=1.0, description=_("enum.agent_model.top_p"))
    execution_mode: str | None = Field(None, description=_("enum.agent_model.execution_mode"))
    tool_bindings: list | None = Field(None, description=_("enum.agent_model.tool_bindings"))
    input_variables: list | None = Field(None, description=_("enum.agent_model.input_variables"))
    welcome_message: str | None = Field(None, description=_("enum.agent_model.welcome_message"))
    suggested_questions: list | None = Field(None, description=_("enum.agent_model.suggested_questions"))
    context_config: dict | None = Field(None, description=_("enum.agent_model.context_config"))
    output_schema: list | None = Field(None, description=_("enum.agent_model.output_schema"))
    quota_config: dict | None = Field(None, description=_("enum.agent_model.quota_config"))
    visibility: str | None = Field(None, description=_("enum.agent_model.visibility"))
    status: str | None = Field(None, description=_("enum.agent_model.status"))


class AgentResponse(TenantResponseSchema):
    """智能体详情响应"""

    name: str = Field(..., description=_("enum.agent_model.name"))
    description: str | None = Field(None, description=_("enum.agent_model.description"))
    avatar: str | None = Field(None, description=_("enum.agent_model.avatar"))
    system_prompt: str = Field(..., description=_("enum.agent_model.system_prompt"))
    model_id: int = Field(..., description=_("enum.agent_model.model_id"))
    temperature: float = Field(..., description=_("enum.agent_model.temperature"))
    max_tokens: int | None = Field(None, description=_("enum.agent_model.max_tokens"))
    top_p: float | None = Field(None, description=_("enum.agent_model.top_p"))
    status: str = Field(..., description=_("enum.agent_model.status"))
    execution_mode: str = Field(..., description=_("enum.agent_model.execution_mode"))
    published_version: int | None = Field(None, description=_("enum.agent_model.published_version"))
    tool_bindings: list | None = Field(None, description=_("enum.agent_model.tool_bindings"))
    input_variables: list | None = Field(None, description=_("enum.agent_model.input_variables"))
    welcome_message: str | None = Field(None, description=_("enum.agent_model.welcome_message"))
    suggested_questions: list | None = Field(None, description=_("enum.agent_model.suggested_questions"))
    context_config: dict | None = Field(None, description=_("enum.agent_model.context_config"))
    output_schema: list | None = Field(None, description=_("enum.agent_model.output_schema"))
    quota_config: dict | None = Field(None, description=_("enum.agent_model.quota_config"))
    visibility: str | None = Field(None, description=_("enum.agent_model.visibility"))
    scope: str | None = Field(None, description=_("enum.agent_model.scope"))
    is_system: bool = Field(False, description=_("enum.agent_model.is_system"))
    # 关联字段
    model_name: str | None = Field(None, description=_("enum.agent_model.model_name"))
    model_code: str | None = Field(None, description=_("enum.agent_model.model_code"))


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
