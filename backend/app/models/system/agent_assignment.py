"""
系统智能体绑定模型 / System Agent Assignment Model

将功能代码（feature_code）映射到指定智能体，用于系统级功能自动选择对应智能体。
Maps feature_code to designated agents for system-level features (e.g. global AI Chat, plugin AI features).
"""

from sqlalchemy import (
    JSON,
    Boolean,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base_model import BaseModel
from app.core.i18n import _


class SystemAgentAssignment(BaseModel):
    """
    系统智能体绑定模型 / System agent assignment model.

    每条记录表示一个功能代码绑定了一个智能体。
    全局默认记录 tenant_id=NULL，企业覆盖记录 tenant_id=<id>。
    Resolve 顺序：企业覆盖 → 全局默认。
    """

    __tablename__ = "system_agent_assignments"

    __table_args__ = (
        UniqueConstraint("feature_code", "tenant_id", name="uq_feature_code_tenant_id"),
        Index(
            "ix_feature_code_global",
            "feature_code",
            unique=True,
            postgresql_where=text("tenant_id IS NULL"),
        ),
    )

    __filterable__ = {
        "id": "id",
        "feature_code": "feature_code",
        "tenant_id": "tenant_id",
        "agent_id": "agent_id",
        "is_active": "is_active",
        "created_at": "created_at",
        "updated_at": "updated_at",
    }

    __sortable__ = {"id", "feature_code", "created_at", "updated_at"}

    __selectable__ = {
        "label": "feature_name",
        "value": "id",
        "search": ["feature_code", "feature_name"],
        "extra": ["agent_id", "is_active"],
    }

    feature_code: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment=_("system_agent_assignment.field.feature_code"),
    )

    tenant_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
        default=None,
        comment=_("system_agent_assignment.field.tenant_id"),
    )

    feature_name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        comment=_("system_agent_assignment.field.feature_name"),
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment=_("system_agent_assignment.field.description"),
    )

    agent_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("agents.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment=_("system_agent_assignment.field.agent_id"),
    )

    config: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        default=None,
        comment=_("system_agent_assignment.field.config"),
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment=_("system_agent_assignment.field.is_active"),
    )

    # ==================== 关系 / Relationships ====================

    agent = relationship(
        "Agent",
        lazy="selectin",
    )

    tenant = relationship(
        "Tenant",
        lazy="noload",
    )

    def __repr__(self) -> str:
        return (
            f"<SystemAgentAssignment(id={self.id}, "
            f"feature_code='{self.feature_code}', tenant_id={self.tenant_id}, agent_id={self.agent_id})>"
        )


__all__ = ["SystemAgentAssignment"]
