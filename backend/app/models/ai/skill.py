"""
技能模型 / Skill Model

定义智能体可使用的技能，包括 Toolkit、知识库、数据智能、Builtin 四种类型。
Defines skills usable by agents, including Toolkit, KnowledgeBase, DataIntelligence, Builtin types.
Skill 是面向用户的管理单元，通过 SkillResolver 转换为面向 LLM 的 ToolDefinition。
Skill is a user-facing management unit, converted to LLM-facing ToolDefinition via SkillResolver.
"""

from sqlalchemy import JSON, Boolean, Column, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base_model import TenantModel
from app.core.i18n import _
from app.enums.agent import SkillTypeEnum
from app.enums.skill import SkillSourceTypeEnum, SkillStatusEnum


class Skill(TenantModel):
    """
    技能模型 / Skill model.

    Skill 封装 Agent 在运行时可用的能力单元，经 SkillResolver 解析为工具定义。
    Skill 必须归属某个 SkillPackage（目录/归组）；包负责来源与目录语义，不承担运行时绑定。
    Agent 是否持有某 Skill 仅由 AgentSkillGrant 决定，而非绑定整包。
    """

    __tablename__ = "skills"

    # 覆盖 TenantModel 的 tenant_id，逐步从 SkillPackage 归属迁移为 Skill 自有归属
    tenant_id = Column(
        Integer, nullable=True, index=True, comment="企业ID（过渡期可继承自技能包）"
    )

    # 允许前端筛选的字段 / Fields exposed for list filtering
    __filterable__ = {
        "id": "id",
        "name": "name",
        "key": "key",
        "type": "type",
        "source_type": "source_type",
        "is_active": "is_active",
        "package_id": "package_id",
        "is_system": "is_system",
        "created_at": "created_at",
    }

    # 允许排序的字段 / Sortable columns for UI
    __sortable__ = {
        "id": "id",
        "name": "name",
        "sort_order": "sort_order",
        "created_at": "created_at",
        "updated_at": "updated_at",
    }

    # 下拉选择配置 / Select dropdown config
    __selectable__ = {
        "label": "name",
        "value": "id",
        "search": ["name"],
    }

    # ==================== 所属技能包 ==================== / Owning package

    package_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("skill_packages.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment=_("skill.field.package_id"),
    )

    # ==================== 基本信息 ==================== / Basic info

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment=_("skill.field.name"),
    )
    key: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        unique=True,
        index=True,
        comment="Stable skill key / 稳定技能 Key",
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

    # ==================== 类型 ==================== / Type and source

    type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default=SkillTypeEnum.TOOLKIT.value,
        index=True,
        comment=_("skill.field.type"),
    )
    source_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default=SkillSourceTypeEnum.CUSTOM.value,
        index=True,
        comment="Skill source type / 技能来源类型",
    )
    source_ref: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Skill source reference / 技能来源引用",
    )
    skill_md: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="AgentScope-style SKILL.md content / AgentScope 风格 SKILL.md 内容",
    )
    version: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="1.0.0",
        comment="Skill version / 技能版本",
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=SkillStatusEnum.ACTIVE.value,
        index=True,
        comment="Skill status / 技能状态",
    )
    is_readonly: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Readonly managed skill / 只读托管技能",
    )

    # ==================== 类型特定配置 ==================== / Type-specific JSON

    config: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        default=dict,
        comment=_("skill.field.config"),
    )

    # ==================== Toolkit 字段 ==================== / Toolkit payload

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

    # ==================== Schema 定义 ==================== / IO schemas

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

    # ==================== 系统标记 ==================== / System flags

    is_system: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
        comment=_("skill.field.is_system"),
    )

    # ==================== 状态与排序 ==================== / Status and order

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

    # ==================== 关系 ==================== / Relationships

    package = relationship(
        "SkillPackage",
        back_populates="skills",
        lazy="noload",
    )
    resources = relationship(
        "SkillResource",
        back_populates="skill",
        lazy="noload",
        cascade="all, delete-orphan",
    )
    capability_bindings = relationship(
        "SkillCapabilityBinding",
        back_populates="skill",
        lazy="noload",
        cascade="all, delete-orphan",
    )
    agent_grants = relationship(
        "AgentSkillGrant",
        back_populates="skill",
        lazy="noload",
    )

    # ==================== 复合索引 ==================== / Composite indexes

    __table_args__ = (
        Index("ix_skills_tenant_type", "tenant_id", "type"),
        Index("ix_skills_tenant_active", "tenant_id", "is_active"),
        Index("ix_skills_source_status", "source_type", "status"),
    )

    def __repr__(self) -> str:
        return f"<Skill(id={self.id}, name={self.name}, type={self.type})>"


__all__ = ["Skill"]
