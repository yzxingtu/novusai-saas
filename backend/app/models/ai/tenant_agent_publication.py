"""
Tenant Agent Publication Model / 企业智能体用户发布模型

Controls whether an agent available to a tenant is published to tenant users.
控制企业可用智能体是否发布给企业用户使用。
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base_model import TenantModel
from app.enums.agent import AgentPublicationAccessTypeEnum


class TenantAgentPublication(TenantModel):
    """
    企业智能体用户发布配置 / Tenant agent publication config.

    每个企业对每个智能体最多一条记录，负责企业用户开放开关与发布规则。
    One row per tenant-agent pair, responsible for tenant-user publication state and rules.
    """

    __tablename__ = "tenant_agent_publications"

    __filterable__ = {
        "id": "id",
        "tenant_id": "tenant_id",
        "agent_id": "agent_id",
        "enabled_for_users": "enabled_for_users",
        "access_type": "access_type",
        "created_at": "created_at",
    }

    __sortable__ = {
        "id": "id",
        "created_at": "created_at",
        "updated_at": "updated_at",
    }

    agent_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="智能体 ID / Agent ID",
    )
    enabled_for_users: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
        comment="是否向企业用户开放 / Enabled for tenant users",
    )
    access_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=AgentPublicationAccessTypeEnum.ALL_USERS.value,
        comment="发布访问类型 / Publication access type",
    )
    tenant_user_role_ids: Mapped[list | None] = mapped_column(
        JSON,
        nullable=True,
        default=None,
        comment="授权用户角色 ID 列表 / Tenant user role IDs",
    )
    tenant_user_ids: Mapped[list | None] = mapped_column(
        JSON,
        nullable=True,
        default=None,
        comment="授权用户 ID 列表 / Tenant user IDs",
    )
    org_node_ids: Mapped[list | None] = mapped_column(
        JSON,
        nullable=True,
        default=None,
        comment="授权组织节点 ID 列表 / Organization node IDs",
    )
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
        comment="发布时间 / Published at",
    )
    published_by: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="发布人 ID / Published by",
    )

    __table_args__ = (
        Index(
            "ix_tenant_agent_publications_tenant_agent",
            "tenant_id",
            "agent_id",
            unique=True,
        ),
    )

    agent = relationship("Agent", lazy="noload")

    def __repr__(self) -> str:
        return (
            f"<TenantAgentPublication(id={self.id}, tenant_id={self.tenant_id}, "
            f"agent_id={self.agent_id}, enabled_for_users={self.enabled_for_users})>"
        )


__all__ = ["TenantAgentPublication"]
