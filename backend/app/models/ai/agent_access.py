"""
智能体访问权限模型 / Agent Access Model

定义智能体在各端内部的访问控制，与 Agent 在企业维度保持一对一关系
Defines endpoint-internal access control for agents. One-to-one with Agent per tenant.
"""

from sqlalchemy import JSON, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.core.base_model import TenantModel
from app.core.i18n import _


class AgentAccess(TenantModel):
    """
    智能体访问权限配置 / Agent access config.

    仅负责端内组织/角色限制：
    - admin_role_ids: 平台管理员组织节点限制（数据库列名沿用既有名称）
    - tenant_role_ids: 企业管理员角色限制

    用户端发布规则已迁移到 TenantAgentPublication。

    退役库表列 access_type 仍是 NOT NULL + 默认 all_users；ORM 必须映射，
    否则新建行 INSERT 会漏列并触发约束错误。
    Retired DB column access_type is NOT NULL and mapped so INSERT remains valid.
    """

    __tablename__ = "agent_access"

    # 允许前端筛选的字段 / Fields exposed for list filtering
    __filterable__ = {
        "id": "id",
        "agent_id": "agent_id",
        "tenant_id": "tenant_id",
        "created_at": "created_at",
    }

    # 允许排序的字段 / Sortable columns for UI
    __sortable__ = {
        "id": "id",
        "created_at": "created_at",
    }

    # 关联的智能体（一对一） / Linked agent (1:1)
    agent_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=False,
        comment=_("agent_access.agent_id"),
    )

    # 管理端组织节点 ID 列表（数据库列名为 admin_role_ids） / Admin org-node ids stored in admin_role_ids
    admin_role_ids: Mapped[list | None] = mapped_column(
        JSON,
        nullable=True,
        default=None,
        comment=_("agent_access.admin_role_ids"),
    )

    # 企业端角色 ID 列表（tenant 端限制访问时使用） / Tenant role ids for access control
    tenant_role_ids: Mapped[list | None] = mapped_column(
        JSON,
        nullable=True,
        default=None,
        comment=_("agent_access.tenant_role_ids"),
    )

    # 退役访问类型列；终端用户可见性使用 TenantAgentPublication /
    # Retired access type column; tenant-user visibility uses TenantAgentPublication.
    access_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="all_users",
        comment=_("agent_access.access_type"),
    )

    # 复合索引 / Composite index
    __table_args__ = (
        Index("ix_agent_access_tenant_agent", "tenant_id", "agent_id", unique=True),
    )

    # 关系 / Relationship
    agent = relationship(
        "Agent",
        lazy="noload",
    )

    @validates("access_type")
    def _reject_retired_access_type_write(self, key: str, _value: str) -> str:
        """中文: access_type 只为库表约束映射，应用层不得再写入。

        EN: access_type is mapped only for the table constraint; application
        writes are rejected.
        """
        raise ValueError(f"agent_access.{key} is retired; use TenantAgentPublication")

    def __repr__(self) -> str:
        return (
            f"<AgentAccess(id={self.id}, agent_id={self.agent_id}, "
            f"tenant_id={self.tenant_id})>"
        )


__all__ = ["AgentAccess"]
