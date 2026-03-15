"""
智能体访问权限模型 / Agent Access Model

定义智能体的访问控制配置：可见范围、授权用户/组织节点，与 Agent 为一对一关系
Defines agent access control config: visibility scope, authorized users/org nodes. One-to-one with Agent.
"""

from sqlalchemy import JSON, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base_model import TenantModel
from app.core.i18n import _
from app.enums.agent import AccessTypeEnum


class AgentAccess(TenantModel):
    """
    智能体访问权限配置 / Agent access config.

    每个智能体至多一条记录，控制该智能体的用户可见性。
    当 Agent.visibility == 'private' 时，根据本表的 access_type 决定谁能访问。
    """

    __tablename__ = "agent_access"

    # 允许前端筛选的字段
    __filterable__ = {
        "id": "id",
        "agent_id": "agent_id",
        "access_type": "access_type",
        "tenant_id": "tenant_id",
        "created_at": "created_at",
    }

    # 允许排序的字段
    __sortable__ = {
        "id": "id",
        "created_at": "created_at",
    }

    # 关联的智能体（一对一）
    agent_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=False,
        comment=_("agent_access.agent_id"),
    )

    # 访问类型
    access_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=AccessTypeEnum.ALL_USERS.value,
        comment=_("agent_access.access_type"),
    )

    # 授权的组织节点 ID 列表（access_type == org_node 时使用）
    org_node_ids: Mapped[list | None] = mapped_column(
        JSON,
        nullable=True,
        default=None,
        comment=_("agent_access.org_node_ids"),
    )

    # 授权的用户 ID 列表（access_type == specific_users 时使用）
    user_ids: Mapped[list | None] = mapped_column(
        JSON,
        nullable=True,
        default=None,
        comment=_("agent_access.user_ids"),
    )

    # ==================== 三端独立角色授权（新增） ====================

    # 管理端角色 ID 列表（admin 端限制访问时使用）
    admin_role_ids: Mapped[list | None] = mapped_column(
        JSON,
        nullable=True,
        default=None,
        comment=_("agent_access.admin_role_ids"),
    )

    # 企业端角色 ID 列表（tenant 端限制访问时使用）
    tenant_role_ids: Mapped[list | None] = mapped_column(
        JSON,
        nullable=True,
        default=None,
        comment=_("agent_access.tenant_role_ids"),
    )

    # 用户端角色 ID 列表（user 端限制访问时使用）
    user_role_ids: Mapped[list | None] = mapped_column(
        JSON,
        nullable=True,
        default=None,
        comment=_("agent_access.user_role_ids"),
    )

    # 复合索引
    __table_args__ = (
        Index("ix_agent_access_tenant_agent", "tenant_id", "agent_id", unique=True),
    )

    # 关系
    agent = relationship(
        "Agent",
        lazy="noload",
    )

    def __repr__(self) -> str:
        return (
            f"<AgentAccess(id={self.id}, agent_id={self.agent_id}, "
            f"access_type={self.access_type})>"
        )


__all__ = ["AgentAccess"]
