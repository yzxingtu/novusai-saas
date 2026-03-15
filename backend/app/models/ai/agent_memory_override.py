"""
智能体记忆开关企业覆盖模型 / Agent Memory Override Model

用于企业端对特定智能体执行"关闭记忆"覆盖。
Allows tenants to override "disable memory" for specific agents.
规则：仅记录 disabled=True 的覆盖项，不支持企业端强制开启。
Rule: Only records disabled=True overrides; tenants cannot force-enable memory.
"""

from sqlalchemy import Boolean, Index, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base_model import TenantModel
from app.core.i18n import _


class AgentMemoryOverride(TenantModel):
    """
    智能体记忆开关企业覆盖 / Agent memory override (tenant-level).

    unique(tenant_id, agent_id)：每个企业对同一智能体最多一条覆盖记录。
    """

    __tablename__ = "agent_memory_overrides"

    __table_args__ = (
        Index(
            "uq_agent_memory_overrides_tenant_agent",
            "tenant_id",
            "agent_id",
            unique=True,
        ),
    )

    __filterable__ = {
        "id": "id",
        "tenant_id": "tenant_id",
        "agent_id": "agent_id",
        "disabled": "disabled",
        "created_at": "created_at",
        "updated_at": "updated_at",
    }

    __sortable__ = {"id", "tenant_id", "agent_id", "created_at", "updated_at"}

    agent_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True,
        comment=_("agent_memory_override.field.agent_id"),
    )

    disabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment=_("agent_memory_override.field.disabled"),
    )

    def __repr__(self) -> str:
        return (
            f"<AgentMemoryOverride(id={self.id}, tenant_id={self.tenant_id}, "
            f"agent_id={self.agent_id}, disabled={self.disabled})>"
        )


__all__ = ["AgentMemoryOverride"]
