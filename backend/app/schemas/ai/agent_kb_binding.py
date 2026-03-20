"""
智能体知识库绑定相关 Schema / Agent KB Binding Schema

定义智能体与知识库绑定的请求/响应数据结构。
Defines request/response schemas for agent–knowledge-base bindings.
"""

from pydantic import Field

from app.core.base_schema import BaseCreateSchema, BaseUpdateSchema
from app.core.i18n import _


class AgentKBBindRequest(BaseCreateSchema):
    """单个知识库绑定请求 / Single knowledge base binding request."""

    knowledge_base_id: int = Field(..., description=_("agent_kb_binding.field.knowledge_base_id"))
    weight: float = Field(1.0, ge=0.1, le=2.0, description=_("agent_kb_binding.field.weight"))
    sort_order: int = Field(0, ge=0, description=_("agent_kb_binding.field.sort_order"))
    enabled: bool = Field(True, description=_("agent_kb_binding.field.enabled"))


class AgentPlatformKbSuppressRequest(BaseCreateSchema):
    """本企业停用平台全局知识库 / Opt out of platform KB for this tenant."""

    knowledge_base_id: int = Field(
        ..., description=_("agent_kb_binding.field.knowledge_base_id")
    )


class AgentKBBatchBindRequest(BaseCreateSchema):
    """批量知识库绑定请求（替换模式） / Batch KB bind request (replace mode)."""

    knowledge_base_ids: list[int] = Field(..., description=_("agent_kb_binding.field.knowledge_base_id"))


class AgentKBBindingUpdate(BaseUpdateSchema):
    """更新知识库绑定请求 / Update KB binding request."""

    weight: float | None = Field(None, ge=0.1, le=2.0, description=_("agent_kb_binding.field.weight"))
    enabled: bool | None = Field(None, description=_("agent_kb_binding.field.enabled"))
    sort_order: int | None = Field(None, ge=0, description=_("agent_kb_binding.field.sort_order"))


__all__ = [
    "AgentKBBindRequest",
    "AgentKBBatchBindRequest",
    "AgentKBBindingUpdate",
    "AgentPlatformKbSuppressRequest",
]
