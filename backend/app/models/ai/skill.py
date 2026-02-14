"""
技能模型

定义智能体可使用的技能，包括 Toolkit、知识库、数据智能、Builtin 四种类型
Skill 是面向用户的管理单元，通过 SkillResolver 转换为面向 LLM 的 ToolDefinition
"""

from sqlalchemy import Boolean, Column, ForeignKey, Index, Integer, String, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base_model import TenantModel
from app.core.i18n import _
from app.enums.agent import SkillTypeEnum


class Skill(TenantModel):
    """
    技能模型

    Skill 是更高层的抽象，封装 Agent 可使用的能力。
    Skill 属于 SkillPackage，作用域和租户归属由所属技能包决定。
    Agent 通过绑定 SkillPackage 间接获得包内所有 Skill。
    """

    __tablename__ = "skills"

    # 覆盖 TenantModel 的 tenant_id，由所属 SkillPackage 决定
    tenant_id = Column(
        Integer,
        nullable=True,
        index=True,
        comment="租户ID（由所属技能包决定）"
    )

    # 允许前端筛选的字段
    __filterable__ = {
        "id": "id",
        "name": "name",
        "type": "type",
        "is_active": "is_active",
        "package_id": "package_id",
        "is_system": "is_system",
        "created_at": "created_at",
    }

    # 允许排序的字段
    __sortable__ = {
        "id": "id",
        "name": "name",
        "sort_order": "sort_order",
        "created_at": "created_at",
        "updated_at": "updated_at",
    }

    # 下拉选择配置
    __selectable__ = {
        "label": "name",
        "value": "id",
        "search": ["name"],
    }

    # ==================== 所属技能包 ====================

    package_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("skill_packages.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment=_("skill.field.package_id"),
    )

    # ==================== 基本信息 ====================

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment=_("skill.field.name"),
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment=_("skill.field.description"),
    )
    avatar: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment=_("skill.field.avatar"),
    )

    # ==================== 类型 ====================

    type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default=SkillTypeEnum.TOOLKIT.value,
        index=True,
        comment=_("skill.field.type"),
    )

    # ==================== 类型特定配置 ====================

    config: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        default=dict,
        comment=_("skill.field.config"),
    )

    # ==================== Toolkit 字段 ====================

    toolkit_content: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        default=None,
        comment=_("skill.field.toolkit_content"),
    )
    toolkit_meta: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        default=None,
        comment=_("skill.field.toolkit_meta"),
    )

    # ==================== Schema 定义 ====================

    input_schema: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        default=None,
        comment=_("skill.field.input_schema"),
    )
    output_schema: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        default=None,
        comment=_("skill.field.output_schema"),
    )

    # ==================== 系统标记 ====================

    is_system: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
        comment=_("skill.field.is_system"),
    )

    # ==================== 状态与排序 ====================

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment=_("skill.field.is_active"),
    )
    sort_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment=_("skill.field.sort_order"),
    )
    timeout: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=30,
        comment=_("skill.field.timeout"),
    )

    # ==================== 关系 ====================

    package = relationship(
        "SkillPackage",
        back_populates="skills",
        lazy="noload",
    )

    # ==================== 复合索引 ====================

    __table_args__ = (
        Index("ix_skills_tenant_type", "tenant_id", "type"),
        Index("ix_skills_tenant_active", "tenant_id", "is_active"),
    )

    def __repr__(self) -> str:
        return f"<Skill(id={self.id}, name={self.name}, type={self.type})>"


__all__ = ["Skill"]
