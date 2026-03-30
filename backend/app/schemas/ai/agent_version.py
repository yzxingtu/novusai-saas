"""
智能体版本相关 Schema / Agent Version Schema

定义版本发布、回滚、列表、对比等请求和响应数据结构
Defines version publish, rollback, list, diff request and response data structures.
"""


from pydantic import Field

from app.core.base_schema import (
    BaseCreateSchema,
    TenantResponseSchema,
)
from app.core.i18n import _


class AgentPublishRequest(BaseCreateSchema):
    """发布智能体请求 / Publish agent request."""

    change_log: str | None = Field(
        None,
        max_length=2000,
        description=_("agent.version.field.change_log"),
    )


class AgentRollbackRequest(BaseCreateSchema):
    """回滚智能体请求 / Rollback agent request."""

    version: int = Field(
        ...,
        ge=1,
        description=_("agent.version.field.version"),
    )


class AgentVersionResponse(TenantResponseSchema):
    """智能体版本详情响应 / Agent version detail response."""

    agent_id: int = Field(..., description=_("agent.version.field.agent_id"))
    version: int = Field(..., description=_("agent.version.field.version"))
    system_prompt: str = Field(..., description=_("agent.version.field.system_prompt"))
    model_id: int = Field(..., description=_("agent.version.field.model_id"))
    temperature: float = Field(..., description=_("agent.version.field.temperature"))
    max_tokens: int | None = Field(None, description=_("agent.version.field.max_tokens"))
    top_p: float | None = Field(None, description=_("agent.version.field.top_p"))
    execution_mode: str = Field(..., description=_("agent.version.field.execution_mode"))
    skill_grant_snapshot: list | None = Field(None, description=_("agent.version.field.skill_grant_snapshot"))
    input_variables: list | None = Field(None, description=_("agent.version.field.input_variables"))
    welcome_message: str | None = Field(None, description=_("agent.version.field.welcome_message"))
    suggested_questions: list | None = Field(None, description=_("agent.version.field.suggested_questions"))
    context_config: dict | None = Field(None, description=_("agent.version.field.context_config"))
    output_schema: list | None = Field(None, description=_("agent.version.field.output_schema"))
    quota_config: dict | None = Field(None, description=_("agent.version.field.quota_config"))
    rag_config: dict | None = Field(None, description=_("agent.version.field.rag_config"))
    change_log: str | None = Field(None, description=_("agent.version.field.change_log"))
    created_by: int | None = Field(None, description=_("agent.version.field.created_by"))


class AgentVersionListItem(TenantResponseSchema):
    """智能体版本列表项响应（精简字段） / Agent version list item response."""

    agent_id: int = Field(..., description=_("agent.version.field.agent_id"))
    version: int = Field(..., description=_("agent.version.field.version"))
    change_log: str | None = Field(None, description=_("agent.version.field.change_log"))
    created_by: int | None = Field(None, description=_("agent.version.field.created_by"))
    execution_mode: str = Field(..., description=_("agent.version.field.execution_mode"))


__all__ = [
    "AgentPublishRequest",
    "AgentRollbackRequest",
    "AgentVersionResponse",
    "AgentVersionListItem",
]
