"""
智能体记忆开关 Schema / Agent Memory Schema
"""

from pydantic import BaseModel, Field

from app.core.i18n import _


class AgentMemoryToggleRequest(BaseModel):
    """管理端：设置 Agent 级记忆开关"""

    enabled: bool = Field(
        ...,
        description=_("enum.agent_model.memory_enabled"),
    )


class AgentMemoryDisableRequest(BaseModel):
    """企业端：关闭/恢复默认（禁用覆盖）"""

    disabled: bool = Field(
        ...,
        description=_("enum.agent_model.memory_disabled_by_tenant"),
    )


__all__ = [
    "AgentMemoryToggleRequest",
    "AgentMemoryDisableRequest",
]
