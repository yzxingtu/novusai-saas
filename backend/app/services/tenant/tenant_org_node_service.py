"""
Tenant organization node service / 企业组织节点服务
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import selectinload

from app.core.base_service import TenantService
from app.core.i18n import _
from app.enums import ErrorCode, RoleType
from app.enums.role import DataScope
from app.exceptions import BusinessException, NotFoundException
from app.models.org.tenant_org_node import (
    TenantOrgNode,
    TenantOrgScopePolicy,
    TenantOrgScopeTarget,
)
from app.models.tenant.tenant_admin import TenantAdmin
from app.repositories.tenant.tenant_org_node_repository import TenantOrgNodeRepository
from app.services.common.role_tree_mixin import MAX_ROLE_DEPTH, RoleTreeMixin
from app.services.tenant.tenant_admin_service import TenantAdminService


class TenantOrgNodeService(TenantService[TenantOrgNode, TenantOrgNodeRepository], RoleTreeMixin[TenantOrgNode]):
    """Service for tenant organization nodes / 企业组织节点服务"""

    model = TenantOrgNode
    repository_class = TenantOrgNodeRepository

    @staticmethod
    def _validate_org_node_type(node_type: str) -> None:
        if node_type not in {RoleType.DEPARTMENT.value, RoleType.POSITION.value}:
            raise BusinessException(
                message=_("role.invalid_child_type"),
                code=ErrorCode.ROLE_INVALID_CHILD_TYPE,
            )

    def _generate_org_node_code(self) -> str:
        return f"org_{uuid.uuid4().hex[:12]}"

    def _role_to_dict(self, org_node: TenantOrgNode) -> dict[str, Any]:
        base = super()._role_to_dict(org_node)
        leader = None
        if org_node.leader and not org_node.leader.is_deleted:
            leader = {
                "id": org_node.leader.id,
                "username": org_node.leader.username,
                "nickname": org_node.leader.nickname,
                "real_name": org_node.leader.nickname or org_node.leader.username,
                "avatar": org_node.leader.avatar,
            }
        base.update(
            {
                "tenant_id": org_node.tenant_id,
                "type": org_node.type,
                "allow_members": org_node.allow_members,
                "leader_id": org_node.leader_id,
                "leader": leader,
                "member_count": org_node.member_count,
                "data_scope": org_node.scope_mode,
                "custom_dept_ids": org_node.custom_org_node_ids,
            }
        )
        return base

    @staticmethod
    def _validate_child_type(parent_type: str, child_type: str) -> bool:
        allowed = {
            RoleType.DEPARTMENT.value: {RoleType.DEPARTMENT.value, RoleType.POSITION.value},
            RoleType.POSITION.value: set(),
        }
        return child_type in allowed.get(parent_type, set())

    async def _validate_custom_scope_targets(self, target_ids: list[int]) -> list[int]:
        if not target_ids:
            return []
        result = await self.db.execute(
            select(TenantOrgNode.id).where(
                TenantOrgNode.tenant_id == self.tenant_id,
                TenantOrgNode.id.in_(target_ids),
                TenantOrgNode.is_deleted.is_(False),
            )
        )
        existing_ids = list(result.scalars().all())
        if len(existing_ids) != len(set(target_ids)):
            raise BusinessException(
                message=_("role.not_found"),
                code=ErrorCode.VALIDATION_ERROR,
            )
        return list(dict.fromkeys(target_ids))

    async def _sync_scope_policy(
        self,
        org_node: TenantOrgNode,
        *,
        data_scope: str | None = None,
        custom_dept_ids: list[int] | None = None,
    ) -> None:
        scope_mode = data_scope or org_node.scope_mode
        target_ids = (
            custom_dept_ids if custom_dept_ids is not None else org_node.custom_org_node_ids
        )
        if scope_mode != DataScope.CUSTOM.value:
            target_ids = []
        target_ids = await self._validate_custom_scope_targets(target_ids)

        policy = org_node.scope_policy
        if policy is None and scope_mode == DataScope.DEPT_AND_CHILDREN.value and not target_ids:
            return

        if policy is None:
            policy = TenantOrgScopePolicy(
                tenant_id=self.tenant_id,
                org_node_id=org_node.id,
                scope_mode=scope_mode,
            )
            self.db.add(policy)
            await self.db.flush()
        else:
            policy.scope_mode = scope_mode

        await self.db.execute(
            delete(TenantOrgScopeTarget).where(
                TenantOrgScopeTarget.policy_id == policy.id,
            )
        )
        await self.db.flush()

        for target_id in target_ids:
            self.db.add(
                TenantOrgScopeTarget(
                    tenant_id=self.tenant_id,
                    policy_id=policy.id,
                    target_org_node_id=target_id,
                )
            )
        await self.db.flush()
        await self.db.refresh(org_node)

    async def create_org_node(
        self,
        name: str,
        description: str | None = None,
        is_system: bool = False,
        is_active: bool = True,
        sort_order: int = 0,
        parent_id: int | None = None,
        type: str = RoleType.DEPARTMENT.value,
        allow_members: bool = True,
        data_scope: str | None = None,
        custom_dept_ids: list[int] | None = None,
    ) -> TenantOrgNode:
        code = self._generate_org_node_code()
        self._validate_org_node_type(type)
        parent_path, parent_level = await self.validate_parent(parent_id)

        if parent_id:
            parent = await self.repo.get_by_id(parent_id)
            if parent and not self._validate_child_type(parent.type, type):
                raise BusinessException(
                    message=_("role.invalid_child_type"),
                    code=ErrorCode.ROLE_INVALID_CHILD_TYPE,
                )

        new_level = self._calculate_level(parent_level)
        if new_level > MAX_ROLE_DEPTH:
            raise BusinessException(
                message=_("role.max_depth_exceeded"),
                code=ErrorCode.ROLE_MAX_DEPTH_EXCEEDED,
            )

        org_node = await self.repo.create(
            {
                "name": name,
                "code": code,
                "description": description,
                "is_system": is_system,
                "is_active": is_active,
                "sort_order": sort_order,
                "parent_id": parent_id,
                "level": new_level,
                "type": type,
                "allow_members": allow_members,
            }
        )
        path = self._build_path(parent_path, org_node.id)
        await self.repo.update(org_node.id, {"path": path})
        org_node = await self.repo.get_by_id(org_node.id)
        if org_node is None:
            raise NotFoundException(message=_("role.not_found"))
        await self._sync_scope_policy(
            org_node,
            data_scope=data_scope,
            custom_dept_ids=custom_dept_ids,
        )
        return await self.repo.get_with_members(org_node.id)

    async def update_org_node(self, org_node_id: int, data: dict[str, Any]) -> TenantOrgNode:
        org_node = await self.repo.get_by_id(org_node_id)
        if not org_node:
            raise NotFoundException(message=_("role.not_found"))

        if org_node.is_system and "parent_id" in data:
            raise BusinessException(
                message=_("role.system_role_cannot_change_parent"),
                code=ErrorCode.ROLE_SYSTEM_CANNOT_CHANGE_PARENT,
            )

        data_scope = data.pop("data_scope", None)
        custom_dept_ids = data.pop("custom_dept_ids", None)

        if "type" in data and data["type"] is not None:
            self._validate_org_node_type(data["type"])

        if "parent_id" in data and data["parent_id"] != org_node.parent_id:
            new_parent_id = data["parent_id"]
            parent_path, parent_level = await self.validate_parent(new_parent_id, exclude_id=org_node_id)
            new_level = self._calculate_level(parent_level)
            max_descendant_depth = await self._get_max_descendant_depth(org_node_id)
            if new_level + max_descendant_depth > MAX_ROLE_DEPTH:
                raise BusinessException(
                    message=_("role.max_depth_exceeded"),
                    code=ErrorCode.ROLE_MAX_DEPTH_EXCEEDED,
                )

            if new_parent_id:
                parent = await self.repo.get_by_id(new_parent_id)
                next_type = data.get("type", org_node.type)
                if parent and not self._validate_child_type(parent.type, next_type):
                    raise BusinessException(
                        message=_("role.invalid_child_type"),
                        code=ErrorCode.ROLE_INVALID_CHILD_TYPE,
                    )

            new_path = self._build_path(parent_path, org_node_id)
            old_path = org_node.path or f"/{org_node_id}/"
            data["path"] = new_path
            data["level"] = new_level
            updated = await self.repo.update(org_node_id, data)
            await self._update_descendants_path(org_node_id, old_path, new_path, new_level)
        else:
            updated = await self.repo.update(org_node_id, data)

        if not updated:
            raise NotFoundException(message=_("role.not_found"))

        await self._sync_scope_policy(
            updated,
            data_scope=data_scope,
            custom_dept_ids=custom_dept_ids,
        )
        return await self.repo.get_with_members(org_node_id)

    async def update_authority_policy(
        self,
        org_node_id: int,
        data_scope: str,
        custom_dept_ids: list[int] | None,
    ) -> TenantOrgNode:
        org_node = await self.repo.get_by_id(org_node_id)
        if not org_node:
            raise NotFoundException(message=_("role.not_found"))

        await self._sync_scope_policy(
            org_node,
            data_scope=data_scope,
            custom_dept_ids=custom_dept_ids,
        )
        return await self.repo.get_with_members(org_node_id)

    async def get_organization_root_nodes(self) -> list[TenantOrgNode]:
        return await self.repo.get_organization_root_nodes()

    async def get_visible_org_tree(
        self,
        visible_org_node_ids: list[int] | None = None,
    ) -> list[TenantOrgNode]:
        """按可见范围获取组织树 / Get organization tree within the visible scope."""
        if visible_org_node_ids is None:
            return await self.repo.get_tree()
        if not visible_org_node_ids:
            return []

        scope_ids = set(visible_org_node_ids)
        roots: list[TenantOrgNode] = []
        for org_node_id in sorted(scope_ids):
            org_node = await self.repo.get_by_id(org_node_id)
            if org_node and (
                org_node.parent_id is None or org_node.parent_id not in scope_ids
            ):
                roots.extend(await self.repo.get_tree(parent_id=org_node_id))
        return roots

    async def get_visible_root_nodes(
        self,
        visible_org_node_ids: list[int] | None = None,
    ) -> list[TenantOrgNode]:
        """按可见范围获取根节点 / Get root nodes within the visible scope."""
        if visible_org_node_ids is None:
            return await self.get_organization_root_nodes()
        if not visible_org_node_ids:
            return []

        scope_ids = set(visible_org_node_ids)
        items: list[TenantOrgNode] = []
        for org_node_id in sorted(scope_ids):
            org_node = await self.repo.get_with_members(org_node_id)
            if org_node and (
                org_node.parent_id is None or org_node.parent_id not in scope_ids
            ):
                items.append(org_node)
        return items

    async def get_org_node_detail(self, org_node_id: int) -> TenantOrgNode:
        """获取组织节点详情 / Get organization node detail."""
        org_node = await self.repo.get_with_members(org_node_id)
        if not org_node:
            raise NotFoundException(message=_("role.not_found"))
        return org_node

    async def get_organization_children(self, org_node_id: int) -> list[TenantOrgNode]:
        return await self.repo.get_children_with_details(org_node_id)

    async def delete_org_node(self, org_node_id: int) -> bool:
        org_node = await self.repo.get_by_id(org_node_id)
        if not org_node:
            raise NotFoundException(message=_("role.not_found"))
        if org_node.is_system:
            raise BusinessException(
                message=_("role.system_role_cannot_delete"),
                code=ErrorCode.ROLE_SYSTEM_CANNOT_DELETE,
            )
        return await self.delete(org_node_id)

    async def move_org_node(self, org_node_id: int, new_parent_id: int | None) -> TenantOrgNode:
        await self.move_node(org_node_id, new_parent_id)
        return await self.repo.get_with_members(org_node_id)

    async def set_leader(self, org_node_id: int, leader_id: int | None) -> TenantOrgNode:
        org_node = await self.repo.get_by_id(org_node_id)
        if not org_node:
            raise NotFoundException(message=_("role.not_found"))

        if org_node.type != RoleType.DEPARTMENT.value:
            raise BusinessException(
                message=_("role.only_department_can_set_leader"),
                code=ErrorCode.ROLE_ONLY_DEPARTMENT_CAN_SET_LEADER,
            )

        if leader_id is not None:
            result = await self.db.execute(
                select(TenantAdmin).where(
                    TenantAdmin.id == leader_id,
                    TenantAdmin.tenant_id == self.tenant_id,
                    TenantAdmin.is_deleted.is_(False),
                    TenantAdmin.org_node_id == org_node_id,
                )
            )
            leader = result.scalar_one_or_none()
            if not leader:
                raise BusinessException(
                    message=_("role.member_not_in_node"),
                    code=ErrorCode.ROLE_MEMBER_NOT_IN_NODE,
                )

        updated = await self.repo.update(org_node_id, {"leader_id": leader_id})
        if not updated:
            raise NotFoundException(message=_("role.not_found"))
        return await self.repo.get_with_members(org_node_id)

    async def _load_member_detail(self, admin_id: int) -> TenantAdmin:
        result = await self.db.execute(
            select(TenantAdmin)
            .where(
                TenantAdmin.id == admin_id,
                TenantAdmin.tenant_id == self.tenant_id,
                TenantAdmin.is_deleted.is_(False),
            )
            .options(
                selectinload(TenantAdmin.org_node),
                selectinload(TenantAdmin.role),
            )
        )
        admin = result.scalar_one_or_none()
        if not admin:
            raise NotFoundException(message=_("tenant_admin.not_found"))
        return admin

    async def create_member(
        self,
        org_node_id: int,
        username: str,
        email: str,
        password: str,
        phone: str | None = None,
        nickname: str | None = None,
        is_active: bool = True,
        role_id: int | None = None,
    ) -> TenantAdmin:
        org_node = await self.repo.get_by_id(org_node_id)
        if not org_node:
            raise NotFoundException(message=_("role.not_found"))
        if not org_node.allow_members:
            raise BusinessException(
                message=_("role.cannot_add_member"),
                code=ErrorCode.ROLE_CANNOT_ADD_MEMBER,
            )

        admin_service = TenantAdminService(self.db, self.tenant_id)
        admin = await admin_service.create_admin(
            username=username,
            email=email,
            password=password,
            phone=phone,
            nickname=nickname,
            is_active=is_active,
            is_owner=False,
            role_id=role_id,
            org_node_id=org_node_id,
        )
        return await self._load_member_detail(admin.id)

    async def update_member(
        self,
        org_node_id: int,
        admin_id: int,
        email: str | None = None,
        phone: str | None = None,
        nickname: str | None = None,
        avatar: str | None = None,
        is_active: bool | None = None,
        new_org_node_id: int | None = None,
        role_id: int | None = None,
        update_permission_role: bool = False,
    ) -> TenantAdmin:
        result = await self.db.execute(
            select(TenantAdmin).where(
                TenantAdmin.id == admin_id,
                TenantAdmin.tenant_id == self.tenant_id,
                TenantAdmin.is_deleted.is_(False),
                TenantAdmin.org_node_id == org_node_id,
            )
        )
        admin = result.scalar_one_or_none()
        if not admin:
            raise BusinessException(
                message=_("role.member_not_in_node"),
                code=ErrorCode.ROLE_MEMBER_NOT_IN_NODE,
            )

        update_data: dict[str, Any] = {}
        if email is not None:
            update_data["email"] = email
        if phone is not None:
            update_data["phone"] = phone
        if nickname is not None:
            update_data["nickname"] = nickname
        if avatar is not None:
            update_data["avatar"] = avatar
        if is_active is not None:
            update_data["is_active"] = is_active
        if new_org_node_id is not None:
            target_org_node = await self.repo.get_by_id(new_org_node_id)
            if not target_org_node:
                raise NotFoundException(message=_("role.not_found"))
            if not target_org_node.allow_members:
                raise BusinessException(
                    message=_("role.cannot_add_member"),
                    code=ErrorCode.ROLE_CANNOT_ADD_MEMBER,
                )
            update_data["org_node_id"] = new_org_node_id
        if update_permission_role:
            update_data["role_id"] = role_id

        updated = await TenantAdminService(self.db, self.tenant_id).update_admin(admin_id, update_data)
        return await self._load_member_detail(updated.id)

    async def reset_member_password(self, org_node_id: int, admin_id: int, new_password: str) -> bool:
        await self._require_member_in_org_node(org_node_id, admin_id)
        return await TenantAdminService(self.db, self.tenant_id).reset_password(admin_id, new_password)

    async def toggle_member_status(self, org_node_id: int, admin_id: int, is_active: bool) -> TenantAdmin:
        await self._require_member_in_org_node(org_node_id, admin_id)
        updated = await TenantAdminService(self.db, self.tenant_id).toggle_status(admin_id, is_active)
        return await self._load_member_detail(updated.id)

    async def add_member(self, org_node_id: int, admin_id: int) -> TenantAdmin:
        org_node = await self.repo.get_by_id(org_node_id)
        if not org_node:
            raise NotFoundException(message=_("role.not_found"))
        if not org_node.allow_members:
            raise BusinessException(
                message=_("role.cannot_add_member"),
                code=ErrorCode.ROLE_CANNOT_ADD_MEMBER,
            )

        admin_service = TenantAdminService(self.db, self.tenant_id)
        admin = await admin_service.get_by_id(admin_id)
        if not admin:
            raise NotFoundException(message=_("admin.not_found"))
        if admin.org_node_id == org_node_id:
            raise BusinessException(
                message=_("role.member_exists"),
                code=ErrorCode.ROLE_MEMBER_EXISTS,
            )
        updated = await admin_service.update_admin(admin_id, {"org_node_id": org_node_id})
        return await self._load_member_detail(updated.id)

    async def remove_member(self, org_node_id: int, admin_id: int) -> TenantAdmin:
        org_node, admin = await self._require_member_in_org_node(org_node_id, admin_id)
        if admin.is_owner:
            raise BusinessException(
                message=_("tenant_admin.owner_cannot_disable"),
                code=ErrorCode.VALIDATION_ERROR,
            )
        if org_node.leader_id == admin_id:
            await self.repo.update(org_node_id, {"leader_id": None})
        updated = await TenantAdminService(self.db, self.tenant_id).update_admin(admin_id, {"org_node_id": None})
        return await self._load_member_detail(updated.id)

    async def get_members(
        self,
        org_node_id: int,
        search: str | None = None,
        page: int = 1,
        page_size: int = 20,
        include_descendants: bool = True,
    ) -> tuple[list[TenantAdmin], int]:
        org_node = await self.repo.get_by_id(org_node_id)
        if not org_node:
            raise NotFoundException(message=_("role.not_found"))
        return await self.repo.get_members(
            org_node_id,
            search=search,
            page=page,
            page_size=page_size,
            include_descendants=include_descendants,
        )

    async def _require_member_in_org_node(self, org_node_id: int, admin_id: int) -> tuple[TenantOrgNode, TenantAdmin]:
        org_node = await self.repo.get_by_id(org_node_id)
        if not org_node:
            raise NotFoundException(message=_("role.not_found"))

        result = await self.db.execute(
            select(TenantAdmin).where(
                TenantAdmin.id == admin_id,
                TenantAdmin.tenant_id == self.tenant_id,
                TenantAdmin.is_deleted.is_(False),
                TenantAdmin.org_node_id == org_node_id,
            )
        )
        admin = result.scalar_one_or_none()
        if not admin:
            raise BusinessException(
                message=_("role.member_not_in_node"),
                code=ErrorCode.ROLE_MEMBER_NOT_IN_NODE,
            )
        return org_node, admin


__all__ = ["TenantOrgNodeService"]
