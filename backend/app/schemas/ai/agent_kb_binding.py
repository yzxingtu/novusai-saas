"""
智能体知识库绑定相关 Schema / Agent KB Binding Schema
"""

from pydantic import Field

from app.core.base_schema import BaseCreateSchema, BaseUpdateSchema
from app.core.i18n import _


class AgentKBBindRequest(BaseCreateSchema):
    """单个知识库绑定请求"""

    knowledge_base_id: int = Field(..., description=_("agent_kb_binding.field.knowledge_base_id"))
    weight: float = Field(1.0, ge=0.1, le=2.0, description=_("agent_kb_binding.field.weight"))
    sort_order: int = Field(0, ge=0, description=_("agent_kb_binding.field.sort_order"))
    enabled: bool = Field(True, description=_("agent_kb_binding.field.enabled"))


class AgentKBBatchBindRequest(BaseCreateSchema):
    """批量知识库绑定请求（替换模式）"""

    knowledge_base_ids: list[int] = Field(..., description=_("agent_kb_binding.field.knowledge_base_id"))


class AgentKBBindingUpdate(BaseUpdateSchema):
    """更新知识库绑定请求"""

    weight: float | None = Field(None, ge=0.1, le=2.0, description=_("agent_kb_binding.field.weight"))
    enabled: bool | None = Field(None, description=_("agent_kb_binding.field.enabled"))
    sort_order: int | None = Field(None, ge=0, description=_("agent_kb_binding.field.sort_order"))


__all__ = [
    "AgentKBBindRequest",
    "AgentKBBatchBindRequest",
    "AgentKBBindingUpdate",
]
