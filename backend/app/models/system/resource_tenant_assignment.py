"""
资源-企业分配模型 / Resource-Tenant Assignment Model

通用分配表，支持所有需要「部分企业」作用域的资源类型：
Generic assignment table for all resource types requiring "assigned tenants" scope:
- skill_package: 技能包分配给指定企业
- agent: 智能体分配给指定企业
- knowledge_base: 知识库分配给指定企业
- plugin: 插件分配给指定企业（替代旧 PluginTenantAssignment）

当资源的 scope 为 selected_tenants 或 admin_and_selected_tenants 时，
通过本表记录哪些企业可以访问该资源。
"""

from sqlalchemy import (
    JSON,
    Boolean,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base_model import BaseModel


class ResourceTenantAssignment(BaseModel):
    """
    资源-企业分配表（通用）/ Resource-tenant assignment (generic).

    所有支持「部分企业」作用域的资源共用此表，
    通过 resource_type + resource_id 标识目标资源。
    """

    __tablename__ = "resource_tenant_assignments"

    __table_args__ = (
        UniqueConstraint(
            "resource_type", "resource_id", "tenant_id",
            name="uq_resource_tenant_assignment",
        ),
        Index("ix_rta_type_resource", "resource_type", "resource_id"),
        Index("ix_rta_tenant", "tenant_id"),
    )

    __filterable__ = {
        "id": "id",
        "resource_type": "resource_type",
        "resource_id": "resource_id",
        "tenant_id": "tenant_id",
        "is_active": "is_active",
    }

    __sortable__ = {"id", "created_at", "updated_at"}

    resource_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="资源类型（skill_package / agent / knowledge_base / plugin 等）",
    )
    resource_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="资源 ID",
    )
    tenant_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        comment="被分配的企业 ID",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="是否启用",
    )
    config: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        default=None,
        comment="企业级配置（可选，如插件的企业级配置）",
    )

    tenant = relationship("Tenant", lazy="noload")

    def __repr__(self) -> str:
        return (
            f"<ResourceTenantAssignment("
            f"type={self.resource_type}, "
            f"resource_id={self.resource_id}, "
            f"tenant_id={self.tenant_id})>"
        )


__all__ = ["ResourceTenantAssignment"]
