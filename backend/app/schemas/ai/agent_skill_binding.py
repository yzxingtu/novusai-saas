"""
智能体技能绑定相关 Schema / Agent Skill Binding Schema
"""

from typing import Any

from pydantic import Field

from app.core.base_schema import BaseCreateSchema, BaseUpdateSchema
from app.core.i18n import _


class AgentSkillBindRequest(BaseCreateSchema):
    """单个技能包绑定请求"""

    package_id: int = Field(..., description=_("agent_skill_binding.field.package_id"))
    config_override: dict[str, Any] | None = Field(None, description=_("agent_skill_binding.field.config_override"))
    sort_order: int = Field(0, ge=0, description=_("agent_skill_binding.field.sort_order"))
    consent_mode: str = Field("auto", description=_("agent_skill_binding.field.consent_mode"))


class AgentSkillBatchBindRequest(BaseCreateSchema):
    """批量技能包绑定请求（替换模式）"""

    package_ids: list[int] = Field(..., description=_("agent_skill_binding.field.package_id"))
    consent_modes: dict[str, str] | None = Field(None, description=_("agent_skill_binding.field.consent_mode"))


class AgentSkillBindingUpdate(BaseUpdateSchema):
    """更新技能绑定请求"""

    enabled: bool | None = Field(None, description=_("agent_skill_binding.field.enabled"))
    config_override: dict[str, Any] | None = Field(None, description=_("agent_skill_binding.field.config_override"))
    sort_order: int | None = Field(None, ge=0, description=_("agent_skill_binding.field.sort_order"))
    consent_mode: str | None = Field(None, description=_("agent_skill_binding.field.consent_mode"))
    skill_consent_overrides: dict[str, str] | None = Field(None, description=_("agent_skill_binding.field.skill_consent_overrides"))


__all__ = [
    "AgentSkillBindRequest",
    "AgentSkillBatchBindRequest",
    "AgentSkillBindingUpdate",
]
