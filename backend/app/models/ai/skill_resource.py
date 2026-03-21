"""
Skill resource model.
"""

from sqlalchemy import ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base_model import BaseModel
from app.enums.skill import SkillResourceTypeEnum


class SkillResource(BaseModel):
    """Skill resource entry aligned with AgentScope directory semantics."""

    __tablename__ = "skill_resources"

    skill_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("skills.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Skill ID / 技能 ID",
    )
    path: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Resource path / 资源路径",
    )
    resource_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=SkillResourceTypeEnum.OTHER.value,
        index=True,
        comment="Resource type / 资源类型",
    )
    title: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Resource title / 资源标题",
    )
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Resource content / 资源内容",
    )
    mime_type: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="MIME type / MIME 类型",
    )
    checksum: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        comment="Checksum / 校验和",
    )
    sort_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Sort order / 排序",
    )

    skill = relationship(
        "Skill",
        back_populates="resources",
        lazy="noload",
    )

    __table_args__ = (
        UniqueConstraint("skill_id", "path", name="uq_skill_resource_path"),
        Index("ix_skill_resources_skill_type", "skill_id", "resource_type"),
    )


__all__ = ["SkillResource"]
