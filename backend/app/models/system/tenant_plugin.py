"""
租户插件模型

租户级插件实例，管理租户对插件的启用状态和自定义配置
"""

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base_model import BaseModel


class TenantPlugin(BaseModel):
    """
    租户插件实例

    记录租户对平台插件的启用状态和自定义配置。
    tenant_id + plugin_id 联合唯一，一个租户对一个插件只有一条记录。
    """

    __tablename__ = "tenant_plugins"

    __filterable__ = {
        "id": "id",
        "tenant_id": "tenant_id",
        "plugin_id": "plugin_id",
        "is_active": "is_active",
        "created_at": "created_at",
    }

    __sortable__ = ["created_at", "updated_at"]

    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "plugin_id",
            name="uq_tenant_plugins_tenant_plugin",
        ),
    )

    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"),
        index=True,
        comment="租户 ID",
    )
    plugin_id: Mapped[int] = mapped_column(
        ForeignKey("plugins.id", ondelete="CASCADE"),
        index=True,
        comment="插件 ID",
    )
    is_active: Mapped[bool] = mapped_column(
        default=False,
        comment="是否启用",
    )
    config: Mapped[dict | None] = mapped_column(
        JSONB,
        default=None,
        comment="租户自定义配置（覆盖插件默认配置）",
    )
