"""
智能体访问权限 Schema

定义访问权限配置的请求/响应数据结构
"""

from pydantic import BaseModel, Field

from app.core.i18n import _


class AgentAccessUpdate(BaseModel):
    """更新智能体访问权限配置（仅角色 ID 列表）"""

    admin_role_ids: list[int] | None = Field(
        None,
        description=_("agent_access.admin_role_ids"),
    )
    tenant_role_ids: list[int] | None = Field(
        None,
        description=_("agent_access.tenant_role_ids"),
    )
    user_role_ids: list[int] | None = Field(
        None,
        description=_("agent_access.user_role_ids"),
    )


class AgentAccessResponse(BaseModel):
    """智能体访问权限响应"""

    agent_id: int = Field(..., description=_("agent_access.agent_id"))
    admin_role_ids: list[int] | None = Field(None, description=_("agent_access.admin_role_ids"))
    tenant_role_ids: list[int] | None = Field(None, description=_("agent_access.tenant_role_ids"))
    user_role_ids: list[int] | None = Field(None, description=_("agent_access.user_role_ids"))


__all__ = ["AgentAccessUpdate", "AgentAccessResponse"]
