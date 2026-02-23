"""
插件租户分配模型
"""

from sqlalchemy import Boolean, ForeignKey, Integer, JSON, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base_model import BaseModel


class PluginTenantAssignment(BaseModel):
    """
    插件租户分配表
    """

    __tablename__ = "plugin_tenant_assignments"

    __table_args__ = (
        UniqueConstraint("plugin_id", "tenant_id", name="uq_plugin_tenant"),
    )

    __filterable__ = {"id": "id", "plugin_id": "plugin_id", "tenant_id": "tenant_id", "is_active": "is_active"}
    __sortable__ = {"id", "created_at", "updated_at"}

    plugin_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("plugins.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="插件ID",
    )
    tenant_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="租户ID",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, comment="是否启用",
    )
    config: Mapped[dict] = mapped_column(
        JSON, nullable=False, default=dict, comment="租户级配置",
    )

    plugin = relationship(
        "Plugin", back_populates="tenant_assignments", lazy="noload",
    )
    tenant = relationship("Tenant", lazy="noload")
