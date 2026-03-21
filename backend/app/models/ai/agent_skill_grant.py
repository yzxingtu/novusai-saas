"""Agent skill grant model."""

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base_model import BaseModel
from app.enums.agent import ToolConsentModeEnum


class AgentSkillGrant(BaseModel):
    """Direct Agent to Skill grant replacing package-based binding."""

    __tablename__ = "agent_skill_grants"

    tenant_id = Column(
        Integer,
        nullable=True,
        index=True,
        comment="Tenant ID following agent ownership / 跟随智能体归属的企业 ID",
    )

    agent_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Agent ID / 智能体 ID",
    )
    skill_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("skills.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Skill ID / 技能 ID",
    )
    enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Whether enabled / 是否启用",
    )
    config_override: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        default=None,
        comment="Skill config override / 技能配置覆盖",
    )
    sort_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Sort order / 排序",
    )
    default_consent_mode: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=ToolConsentModeEnum.AUTO.value,
        comment="Default consent mode / 默认授权模式",
    )
    capability_consent_overrides: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        default=None,
        comment="Capability consent overrides / 能力授权覆盖",
    )

    agent = relationship("Agent", back_populates="skill_grants", lazy="noload")
    skill = relationship(
        "Skill",
        back_populates="agent_grants",
        lazy="noload",
    )

    __table_args__ = (
        UniqueConstraint("agent_id", "skill_id", name="uq_agent_skill_grant"),
        Index("ix_agent_skill_grant_agent_enabled", "agent_id", "enabled"),
    )


__all__ = ["AgentSkillGrant"]
