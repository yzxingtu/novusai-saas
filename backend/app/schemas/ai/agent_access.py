"""
智能体访问权限 Schema

定义访问权限配置的请求/响应数据结构
"""

from pydantic import BaseModel, Field

from app.core.i18n import _


class AgentAccessUpdate(BaseModel):
    """更新智能体访问权限配置"""

    visibility: str = Field(
        "public",
        description=_("agent_access.visibility"),
    )
    access_type: str = Field(
        "all_users",
        description=_("agent_access.access_type"),
    )
    org_node_ids: list[int] | None = Field(
        None,
        description=_("agent_access.org_node_ids"),
    )
    user_ids: list[int] | None = Field(
        None,
        description=_("agent_access.user_ids"),
    )


__all__ = ["AgentAccessUpdate"]
