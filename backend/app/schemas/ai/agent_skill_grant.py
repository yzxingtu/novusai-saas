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
    default_consent_mode: str = Field(
        "auto",
        description=_("agent_skill_grant.field.default_consent_mode"),
    )
    capability_consent_overrides: dict[str, str] | None = Field(
        None,
        description=_("agent_skill_grant.field.capability_consent_overrides"),
    )


class AgentSkillGrantBatchBindRequest(BaseCreateSchema):
    """Replace all skill grants on an agent."""

    skill_ids: list[int] = Field(
        ...,
        description=_("agent_skill_grant.field.skill_id"),
    )
    default_consent_modes: dict[str, str] | None = Field(
        None,
        description=_("agent_skill_grant.field.default_consent_mode"),
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
    default_consent_mode: str | None = Field(
        None,
        description=_("agent_skill_grant.field.default_consent_mode"),
    )
    capability_consent_overrides: dict[str, str] | None = Field(
        None,
        description=_("agent_skill_grant.field.capability_consent_overrides"),
    )


__all__ = [
    "AgentSkillGrantBatchBindRequest",
    "AgentSkillGrantCreate",
    "AgentSkillGrantUpdate",
]
