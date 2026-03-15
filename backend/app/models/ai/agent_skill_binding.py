"""
智能体技能包绑定模型 / Agent Skill Binding Model

定义 Agent 与 SkillPackage 的多对多关系
Defines Agent-SkillPackage many-to-many relationship.
"""

from typing import TYPE_CHECKING

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

from app.core.base_model import TenantModel
from app.core.i18n import _
from app.enums.agent import ToolConsentModeEnum


class AgentSkillBinding(TenantModel):
    """
    智能体技能包绑定模型 / Agent-SkillPackage binding model.

    记录 Agent 与 SkillPackage 的 M:N 关系。
    每条记录表示一个 Agent 绑定了一个 SkillPackage，支持：
      - enabled: 是否启用该绑定
      - config_override: 每个 Agent 可覆盖 SkillPackage 的部分配置
      - sort_order: 绑定排序
    """

    __tablename__ = "agent_skill_bindings"

    # 覆盖 TenantModel 的 tenant_id，跟随 Agent 的 tenant_id
    tenant_id = Column(
        Integer,
        nullable=True,
        index=True,
        comment="企业ID（跟随 Agent 的 tenant_id）"
    )

    # ==================== 关联 ====================

    agent_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment=_("agent_skill_binding.field.agent_id"),
    )
    package_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("skill_packages.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment=_("agent_skill_binding.field.package_id"),
    )

    # ==================== 绑定配置 ====================

    enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment=_("agent_skill_binding.field.enabled"),
    )
    config_override: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        default=None,
        comment=_("agent_skill_binding.field.config_override"),
    )
    sort_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment=_("agent_skill_binding.field.sort_order"),
    )
    consent_mode: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=ToolConsentModeEnum.AUTO.value,
        comment=_("agent_skill_binding.field.consent_mode"),
    )
    skill_consent_overrides: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        default=None,
        comment=_("agent_skill_binding.field.skill_consent_overrides"),
    )

    # ==================== 约束与索引 ====================

    __table_args__ = (
        UniqueConstraint("agent_id", "package_id", name="uq_agent_skill_package_binding"),
        Index("ix_agent_skill_bindings_agent_enabled", "agent_id", "enabled"),
    )

    # ==================== 关系 ====================

    agent = relationship(
        "Agent",
        lazy="noload",
        overlaps="skill_bindings",
    )
    package = relationship(
        "SkillPackage",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return (
            f"<AgentSkillBinding(id={self.id}, agent_id={self.agent_id}, "
            f"package_id={self.package_id}, enabled={self.enabled})>"
        )


if TYPE_CHECKING:
    pass


__all__ = ["AgentSkillBinding"]
