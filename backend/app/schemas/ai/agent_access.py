"""
智能体访问权限 Schema / Agent Access Schema

定义访问权限配置的请求/响应数据结构
Defines access control configuration request/response data structures.
"""

from pydantic import BaseModel, Field

from app.core.i18n import _


class AgentAccessUpdate(BaseModel):
    """更新智能体访问权限配置（仅角色 ID 列表） / Update agent access config (role ID lists only)."""

    admin_role_ids: list[int] | None = Field(
        None,
        description=_("agent_access.admin_role_ids"),
    )
    tenant_role_ids: list[int] | None = Field(
        None,
        description=_("agent_access.tenant_role_ids"),
    )


class AgentAccessResponse(BaseModel):
    """智能体访问权限响应 / Agent access response schema."""

    agent_id: int = Field(..., description=_("agent_access.agent_id"))
    admin_role_ids: list[int] | None = Field(None, description=_("agent_access.admin_role_ids"))
    tenant_role_ids: list[int] | None = Field(None, description=_("agent_access.tenant_role_ids"))


__all__ = ["AgentAccessUpdate", "AgentAccessResponse"]
