"""
Tenant organization models / 企业组织架构模型
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base_model import TenantModel
from app.core.deletion import DeletionDep, DeletionStrategy
from app.enums.role import DataScope, RoleType


class TenantOrgNode(TenantModel):
    """Tenant organization node / 企业组织节点"""

    __tablename__ = "tenant_org_nodes"

    __delete_deps__ = [
        DeletionDep("TenantOrgNode", "parent_id", DeletionStrategy.BLOCK,
                    label_field="name", i18n_key="tenant_org_node"),
        DeletionDep("TenantAdmin", "org_node_id", DeletionStrategy.BLOCK,
                    label_field="username", i18n_key="tenant_admin"),
        DeletionDep("TenantUser", "org_node_id", DeletionStrategy.BLOCK,
                    label_field="username", i18n_key="tenant_user"),
    ]

    __filterable__ = {
        "id": "id",
        "tenant_id": "tenant_id",
        "name": "name",
        "code": "code",
        "is_system": "is_system",
        "is_active": "is_active",
        "sort_order": "sort_order",
        "parent_id": "parent_id",
        "level": "level",
        "type": "type",
        "leader_id": "leader_id",
        "created_at": "created_at",
        "updated_at": "updated_at",
    }

    __selectable__ = {
        "label": "name",
        "value": "id",
        "search": ["name", "code"],
        "extra": ["code", "type", "level"],
        "tree": {
            "parent_field": "parent_id",
            "children_field": "children",
            "order_by": "sort_order",
        },
    }

    __sortable__ = {
        "field": "sort_order",
        "step": 1000,
        "scope_fields": ["tenant_id", "parent_id"],
    }

    name: Mapped[str] = mapped_column(String(50), comment="节点名称")
    code: Mapped[str] = mapped_column(String(50), index=True, comment="节点编码")
    description: Mapped[str | None] = mapped_column(Text, nullable=True, comment="节点描述")
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, comment="是否系统节点")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, comment="是否启用")
    sort_order: Mapped[int] = mapped_column(Integer, default=0, comment="排序")
    parent_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("tenant_org_nodes.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="父节点 ID",
    )
    path: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        index=True,
        comment="物化路径",
    )
    level: Mapped[int] = mapped_column(Integer, default=1, comment="层级深度")
    type: Mapped[str] = mapped_column(
        String(20),
        default=RoleType.DEPARTMENT.value,
        index=True,
        comment="节点类型",
    )
    allow_members: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        comment="是否允许成员挂载",
    )
    leader_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("tenant_admins.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="负责人 ID",
    )

    parent: Mapped["TenantOrgNode | None"] = relationship(
        "TenantOrgNode",
        remote_side="TenantOrgNode.id",
        back_populates="children",
        lazy="selectin",
    )
    children: Mapped[list["TenantOrgNode"]] = relationship(
        "TenantOrgNode",
        back_populates="parent",
        lazy="selectin",
    )
    leader: Mapped["TenantAdmin | None"] = relationship(
        "TenantAdmin",
        foreign_keys=[leader_id],
        lazy="selectin",
    )
    admins: Mapped[list["TenantAdmin"]] = relationship(
        "TenantAdmin",
        back_populates="org_node",
        lazy="selectin",
        foreign_keys="TenantAdmin.org_node_id",
    )
    users: Mapped[list["TenantUser"]] = relationship(
        "TenantUser",
        back_populates="org_node",
        lazy="selectin",
        foreign_keys="TenantUser.org_node_id",
    )
    scope_policy: Mapped["TenantOrgScopePolicy | None"] = relationship(
        "TenantOrgScopePolicy",
        back_populates="org_node",
        uselist=False,
        lazy="selectin",
        cascade="all, delete-orphan",
    )

    @property
    def children_count(self) -> int:
        children = self.__dict__.get("children")
        if children is None:
            return int(getattr(self, "_children_count", 0))

        count = len([child for child in children if not child.is_deleted])
        self._children_count = count
        self._has_children = count > 0
        return count

    @property
    def member_count(self) -> int:
        admins = self.__dict__.get("admins")
        users = self.__dict__.get("users")
        if admins is None and users is None:
            return int(getattr(self, "_member_count", 0))

        admin_count = len([admin for admin in (admins or []) if not admin.is_deleted])
        user_count = len([user for user in (users or []) if not user.is_deleted])
        count = admin_count + user_count
        self._member_count = count
        return count

    @property
    def has_children(self) -> bool:
        children = self.__dict__.get("children")
        if children is None:
            return bool(getattr(self, "_has_children", False))
        return any(not child.is_deleted for child in children)

    @property
    def has_admins(self) -> bool:
        admins = self.__dict__.get("admins")
        if admins is None:
            return self.member_count > 0
        return any(not admin.is_deleted for admin in admins)

    @property
    def leader_name(self) -> str | None:
        leader = self.__dict__.get("leader")
        if leader is None:
            return getattr(self, "_leader_name", None)
        if leader and not leader.is_deleted:
            return leader.nickname or leader.username
        return None

    @property
    def data_scope(self) -> str:
        return self.scope_mode

    @property
    def custom_dept_ids(self) -> list[int]:
        return self.custom_org_node_ids

    @property
    def permissions_count(self) -> int:
        return 0

    @property
    def scope_mode(self) -> str:
        policy = self.__dict__.get("scope_policy")
        if policy is None:
            return getattr(self, "_scope_mode", DataScope.DEPT_AND_CHILDREN.value)
        if policy and not policy.is_deleted:
            return policy.scope_mode
        return DataScope.DEPT_AND_CHILDREN.value

    @property
    def custom_org_node_ids(self) -> list[int]:
        policy = self.__dict__.get("scope_policy")
        if policy is None:
            return list(getattr(self, "_custom_org_node_ids", []))
        if not policy:
            return []
        return [
            target.target_org_node_id
            for target in policy.targets
            if not target.is_deleted
        ]


class TenantOrgScopePolicy(TenantModel):
    """Tenant organization scope policy / 企业组织范围策略"""

    __tablename__ = "tenant_org_scope_policies"

    org_node_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("tenant_org_nodes.id", ondelete="CASCADE"),
        unique=True,
        comment="组织节点 ID",
    )
    scope_mode: Mapped[str] = mapped_column(
        String(20),
        default=DataScope.DEPT_AND_CHILDREN.value,
        index=True,
        comment="范围模式",
    )

    org_node: Mapped["TenantOrgNode"] = relationship(
        "TenantOrgNode",
        back_populates="scope_policy",
        lazy="selectin",
    )
    targets: Mapped[list["TenantOrgScopeTarget"]] = relationship(
        "TenantOrgScopeTarget",
        back_populates="policy",
        lazy="selectin",
        cascade="all, delete-orphan",
    )


class TenantOrgScopeTarget(TenantModel):
    """Tenant organization custom scope target / 企业组织自定义范围目标"""

    __tablename__ = "tenant_org_scope_targets"

    policy_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("tenant_org_scope_policies.id", ondelete="CASCADE"),
        index=True,
        comment="策略 ID",
    )
    target_org_node_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("tenant_org_nodes.id", ondelete="CASCADE"),
        index=True,
        comment="目标组织节点 ID",
    )

    policy: Mapped["TenantOrgScopePolicy"] = relationship(
        "TenantOrgScopePolicy",
        back_populates="targets",
        lazy="selectin",
    )
    target_org_node: Mapped["TenantOrgNode"] = relationship(
        "TenantOrgNode",
        lazy="selectin",
    )


if TYPE_CHECKING:
    from app.models.tenant.tenant_admin import TenantAdmin
    from app.models.tenant.tenant_user import TenantUser


__all__ = [
    "TenantOrgNode",
    "TenantOrgScopePolicy",
    "TenantOrgScopeTarget",
]
