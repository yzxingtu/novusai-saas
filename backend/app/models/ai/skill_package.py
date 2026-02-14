"""
技能包模型

技能包是 Skill 的上层容器，一个技能包包含多个技能。
Agent 通过绑定技能包来获取其中所有技能的能力。

作用域:
  - scope=tenant: 租户端使用（tenant_id 必填）
  - scope=admin: 仅管理端使用（tenant_id 为 NULL）
"""

from sqlalchemy import Boolean, Column, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base_model import TenantModel
from app.core.i18n import _
from app.enums.common import ResourceScopeEnum


class SkillPackage(TenantModel):
    """
    技能包模型

    技能包是面向用户的管理单元，将多个 Skill 组织为一个可整体绑定的能力集合。
    例如：「客服知识库包」包含若干知识库 Skill，「数据分析包」包含若干数据智能 Skill。
    """

    __tablename__ = "skill_packages"

    # 覆盖 TenantModel 的 tenant_id，admin scope 时为 NULL
    tenant_id = Column(
        Integer,
        nullable=True,
        index=True,
        comment="租户ID（scope=tenant 时必填，scope=admin 时为 NULL）"
    )

    # 允许前端筛选的字段
    __filterable__ = {
        "id": "id",
        "name": "name",
        "scope": "scope",
        "is_active": "is_active",
        "is_system": "is_system",
        "tenant_id": "tenant_id",
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

    # ==================== 基本信息 ====================

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

    # ==================== 作用域 ====================

    scope: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=ResourceScopeEnum.TENANT.value,
        index=True,
        comment=_("skill_package.field.scope"),
    )

    # ==================== 来源标记 ====================

    source_plugin: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        default=None,
        index=True,
        comment=_("skill_package.field.source_plugin"),
    )

    # ==================== 系统标记 ====================

    is_system: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
        comment=_("skill_package.field.is_system"),
    )

    # ==================== Valves 配置 ====================

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

    # ==================== 状态与排序 ====================

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

    # ==================== 关系 ====================

    skills = relationship(
        "Skill",
        back_populates="package",
        lazy="noload",
        cascade="all, delete-orphan",
    )

    # ==================== 复合索引 ====================

    __table_args__ = (
        Index("ix_skill_packages_tenant_scope", "tenant_id", "scope"),
        Index("ix_skill_packages_tenant_active", "tenant_id", "is_active"),
    )

    def __repr__(self) -> str:
        return f"<SkillPackage(id={self.id}, name={self.name}, scope={self.scope})>"


__all__ = ["SkillPackage"]
