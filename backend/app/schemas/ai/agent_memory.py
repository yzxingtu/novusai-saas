"""
智能体记忆开关 Schema / Agent Memory Schema

定义管理端/企业端对 Agent 记忆功能的开关与覆盖请求。
Defines admin/tenant requests for agent memory toggle and override.
"""

from pydantic import BaseModel, Field

from app.core.i18n import _


class AgentMemoryToggleRequest(BaseModel):
    """管理端：设置 Agent 级记忆开关 / Admin: set agent-level memory toggle."""

    enabled: bool = Field(
        ...,
        description=_("enum.agent_model.memory_enabled"),
    )


class AgentMemoryDisableRequest(BaseModel):
    """企业端：关闭/恢复默认（禁用覆盖） / Tenant: disable or restore default (disable override)."""

    disabled: bool = Field(
        ...,
        description=_("enum.agent_model.memory_disabled_by_tenant"),
    )


__all__ = [
    "AgentMemoryToggleRequest",
    "AgentMemoryDisableRequest",
]
