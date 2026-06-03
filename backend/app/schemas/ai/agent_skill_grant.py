"""
Agent skill grant schemas.
"""

from typing import Any

from pydantic import Field

from app.core.base_schema import BaseCreateSchema, BaseUpdateSchema
from app.core.i18n import _


class AgentSkillGrantCreate(BaseCreateSchema):
    """Bind a single skill to an agent."""

    skill_id: int = Field(
        ...,
        description=_("agent_skill_grant.field.skill_id"),
    )
    config_override: dict[str, Any] | None = Field(
        None,
        description=_("agent_skill_grant.field.config_override"),
    )
    sort_order: int = Field(
        0,
        ge=0,
        description=_("agent_skill_grant.field.sort_order"),
    )


class AgentSkillGrantBatchBindRequest(BaseCreateSchema):
    """Replace all skill grants on an agent."""

    skill_ids: list[int] = Field(
        ...,
        description=_("agent_skill_grant.field.skill_id"),
    )


class AgentSkillGrantUpdate(BaseUpdateSchema):
    """Update a skill grant."""

    enabled: bool | None = Field(
        None,
        description=_("agent_skill_grant.field.enabled"),
    )
    config_override: dict[str, Any] | None = Field(
        None,
        description=_("agent_skill_grant.field.config_override"),
    )
    sort_order: int | None = Field(
        None,
        ge=0,
        description=_("agent_skill_grant.field.sort_order"),
    )


__all__ = [
    "AgentSkillGrantBatchBindRequest",
    "AgentSkillGrantCreate",
    "AgentSkillGrantUpdate",
]
