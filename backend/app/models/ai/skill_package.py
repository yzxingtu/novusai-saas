"""
技能包模型 / Skill Package Model

技能包是 Skill 的上层分组容器，一个技能包包含多个技能。
Skill package is the grouping container for Skills; one package contains multiple skills.
运行时直接绑定 Skill，SkillPackage 仅保留分组、来源和展示职责。
Runtime binds Skills directly; SkillPackage remains a grouping, source, and management unit.
tenant_id=NULL 表示平台级包，tenant_id=X 表示企业自有包。
tenant_id=NULL means platform-level package, tenant_id=X means tenant-owned package.
"""

from sqlalchemy import Boolean, Column, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base_model import TenantModel
from app.core.deletion import DeletionDep, DeletionStrategy
from app.core.i18n import _


class SkillPackage(TenantModel):
    """
    技能包模型 / Skill package model.

    技能包是归组、来源与目录单元，将多个 Skill 组织为可浏览、可管理的目录项；
    Agent 运行时是否生效由 AgentSkillGrant 决定，而非包级自动绑定。
    """

    __tablename__ = "skill_packages"

    __delete_deps__ = [
        DeletionDep(
            "Skill",
            "package_id",
            DeletionStrategy.CASCADE_SOFT,
            label_field="name",
            i18n_key="skill",
        ),
    ]

    tenant_id = Column(
        Integer,
        nullable=True,
        index=True,
        comment="企业ID（平台级包为 NULL，企业自有包为企业 ID）/ Tenant ID (NULL for platform packages, tenant ID for tenant-owned)",
    )

    # 允许前端筛选的字段 / Fields exposed for list filtering
    __filterable__ = {
        "id": "id",
        "name": "name",
        "is_active": "is_active",
        "is_system": "is_system",
        "is_recommended": "is_recommended",
        "tenant_id": "tenant_id",
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
        "extra": ["is_system", "source_plugin"],
    }

    # ==================== 基本信息 ==================== / Basic info

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment=_("skill_package.field.name"),
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment=_("skill_package.field.description"),
    )
    avatar: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment=_("skill_package.field.avatar"),
    )

    # ==================== 推荐标记 ==================== / Recommendation flag

    is_recommended: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment=_("skill_package.field.is_recommended"),
    )

    # ==================== 来源标记 ==================== / Source plugin

    source_plugin: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        default=None,
        index=True,
        comment=_("skill_package.field.source_plugin"),
    )

    # ==================== 系统标记 ==================== / System flags

    is_system: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
        comment=_("skill_package.field.is_system"),
    )

    # ==================== Valves 配置 ==================== / Valves schema

    valves_schema: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        default=None,
        comment=_("skill_package.field.valves_schema"),
    )
    valves_config: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        default=None,
        comment=_("skill_package.field.valves_config"),
    )

    # ==================== 状态与排序 ==================== / Status and order

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment=_("skill_package.field.is_active"),
    )
    sort_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment=_("skill_package.field.sort_order"),
    )

    # ==================== 关系 ==================== / Relationships

    skills = relationship(
        "Skill",
        back_populates="package",
        lazy="noload",
        cascade="all, delete-orphan",
    )

    # ==================== 复合索引 ==================== / Composite indexes

    __table_args__ = (
        Index("ix_skill_packages_tenant_active", "tenant_id", "is_active"),
    )

    def __repr__(self) -> str:
        return f"<SkillPackage(id={self.id}, name={self.name})>"


__all__ = ["SkillPackage"]
