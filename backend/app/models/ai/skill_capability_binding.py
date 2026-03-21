"""
Skill to capability binding model.
"""

from sqlalchemy import ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base_model import BaseModel
from app.enums.skill import SkillActivationModeEnum


class SkillCapabilityBinding(BaseModel):
    """Binds a Skill to one Capability contract."""

    __tablename__ = "skill_capability_bindings"

    skill_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("skills.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Skill ID / 技能 ID",
    )
    capability_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("capabilities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Capability ID / 能力 ID",
    )
    activation_mode: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=SkillActivationModeEnum.ON_DEMAND.value,
        comment="Activation mode / 激活模式",
    )
    sort_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Sort order / 排序",
    )

    skill = relationship(
        "Skill",
        back_populates="capability_bindings",
        lazy="noload",
    )
    capability = relationship(
        "Capability",
        back_populates="skill_bindings",
        lazy="noload",
    )

    __table_args__ = (
        UniqueConstraint(
            "skill_id", "capability_id", name="uq_skill_capability_binding"
        ),
        Index("ix_skill_capability_binding_sort", "skill_id", "sort_order"),
    )


__all__ = ["SkillCapabilityBinding"]
