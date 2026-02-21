"""
插件租户分配模型

记录管理端为特定租户分配插件的关系（scope=assigned_tenants 时使用）
"""

from datetime import datetime

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base_model import BaseModel, utc_now


class PluginTenantAssignment(BaseModel):
    """
    插件租户分配记录

    管理端为特定租户分配插件时创建。
    plugin_id + tenant_id 联合唯一，一个插件对一个租户只有一条分配记录。
    """

    __tablename__ = "plugin_tenant_assignments"

    __filterable__ = {
        "id": "id",
        "plugin_id": "plugin_id",
        "tenant_id": "tenant_id",
        "assigned_by": "assigned_by",
        "created_at": "created_at",
    }

    __sortable__ = ["created_at"]

    __table_args__ = (
        UniqueConstraint(
            "plugin_id", "tenant_id",
            name="uq_plugin_tenant_assignments_plugin_tenant",
        ),
    )

    plugin_id: Mapped[int] = mapped_column(
        ForeignKey("plugins.id", ondelete="CASCADE"),
        index=True,
        comment="插件 ID",
    )
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"),
        index=True,
        comment="租户 ID",
    )
    assigned_by: Mapped[int | None] = mapped_column(
        ForeignKey("admins.id", ondelete="SET NULL"),
        default=None,
        comment="分配操作的管理员 ID",
    )
    assigned_at: Mapped[datetime] = mapped_column(
        default=lambda: utc_now(),
        comment="分配时间",
    )
