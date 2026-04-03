"""
Admin organization node service / 管理后台组织节点服务
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import selectinload

from app.core.base_service import GlobalService
from app.core.i18n import _
from app.enums import ErrorCode, RoleType
from app.enums.rbac import PermissionScope
from app.enums.role import DataScope
from app.exceptions import BusinessException, NotFoundException
from app.models.auth.permission import Permission
from app.models.org.admin_org_node import (
    AdminOrgNode,
    AdminOrgScopePolicy,
    AdminOrgScopeTarget,
)
from app.models.system.admin import Admin
from app.repositories.system.admin_org_node_repository import AdminOrgNodeRepository
from app.services.common.role_tree_mixin import MAX_ROLE_DEPTH, RoleTreeMixin
from app.services.system.admin_service import AdminService


class AdminOrgNodeService(
    GlobalService[AdminOrgNode, AdminOrgNodeRepository], RoleTreeMixin[AdminOrgNode]
):
    """Service for admin organization nodes / 管理后台组织节点服务"""

    model = AdminOrgNode
    repository_class = AdminOrgNodeRepository

    @staticmethod
    def _validate_org_node_type(node_type: str) -> None:
        if node_type not in {RoleType.DEPARTMENT.value, RoleType.POSITION.value}:
            raise BusinessException(
                message=_("role.invalid_child_type"),
                code=ErrorCode.ROLE_INVALID_CHILD_TYPE,
            )

    @staticmethod
    def _validate_child_type(parent_type: str, child_type: str) -> bool:
        allowed = {
            RoleType.DEPARTMENT.value: {
                RoleType.DEPARTMENT.value,
                RoleType.POSITION.value,
            },
            RoleType.POSITION.value: set(),
        }
        return child_type in allowed.get(parent_type, set())

    def _generate_org_node_code(self) -> str:
        return f"org_{uuid.uuid4().hex[:12]}"

    async def _normalize_permission_ids(
        self, permission_ids: list[int] | None
    ) -> list[int]:
        if not permission_ids:
            return []

        deduped = list(dict.fromkeys(permission_ids))
        result = await self.db.execute(
            select(Permission.id).where(
                Permission.id.in_(deduped),
                Permission.scope.in_(
                    [PermissionScope.ADMIN.value, PermissionScope.BOTH.value]
                ),
                Permission.is_deleted.is_(False),
            )
        )
        existing_ids = set(result.scalars().all())
        missing_ids = [item for item in deduped if item not in existing_ids]
        if missing_ids:
            raise NotFoundException(message=_("permission.not_found"))
        return deduped

    async def _normalize_custom_target_ids(
        self, org_node_ids: list[int] | None
    ) -> list[int]:
        if not org_node_ids:
            return []

        deduped = list(dict.fromkeys(org_node_ids))
        result = await self.db.execute(
            select(AdminOrgNode.id).where(
                AdminOrgNode.id.in_(deduped),
                AdminOrgNode.is_deleted.is_(False),
            )
        )
        existing_ids = set(result.scalars().all())
        missing_ids = [item for item in deduped if item not in existing_ids]
        if missing_ids:
            raise NotFoundException(message=_("role.not_found"))
        return deduped

    async def _upsert_scope_policy(
        self,
        org_node: AdminOrgNode,
        scope_mode: str,
        custom_org_node_ids: list[int] | None,
    ) -> None:
        normalized_custom_ids = await self._normalize_custom_target_ids(
            custom_org_node_ids
        )
        if org_node.scope_policy is None:
            policy = AdminOrgScopePolicy(
                org_node_id=org_node.id,
                scope_mode=scope_mode,
            )
            self.db.add(policy)
            await self.db.flush()
            org_node.scope_policy = policy
        else:
            policy = org_node.scope_policy
            policy.scope_mode = scope_mode

        await self.db.execute(
            delete(AdminOrgScopeTarget).where(
                AdminOrgScopeTarget.policy_id == policy.id,
            )
        )
        await self.db.flush()

        if scope_mode == DataScope.CUSTOM.value:
            for target_id in normalized_custom_ids:
                self.db.add(
                    AdminOrgScopeTarget(
                        policy_id=policy.id,
                        target_org_node_id=target_id,
                    )
                )
        await self.db.flush()

    async def _assign_permissions(
        self,
        org_node: AdminOrgNode,
        permission_ids: list[int] | None,
    ) -> None:
        normalized_permission_ids = await self._normalize_permission_ids(permission_ids)
        if not normalized_permission_ids:
            org_node.permissions = []
            await self.db.flush()
            return

        result = await self.db.execute(
            select(Permission).where(
                Permission.id.in_(normalized_permission_ids),
                Permission.is_deleted.is_(False),
            )
        )
        permissions = list(result.scalars().all())
        permission_map = {permission.id: permission for permission in permissions}
        org_node.permissions = [
            permission_map[permission_id]
            for permission_id in normalized_permission_ids
            if permission_id in permission_map
        ]
        await self.db.flush()

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
        data_scope: str = DataScope.DEPT_AND_CHILDREN.value,
        custom_dept_ids: list[int] | None = None,
        permission_ids: list[int] | None = None,
    ) -> AdminOrgNode:
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
                "code": self._generate_org_node_code(),
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
        new_path = self._build_path(parent_path, org_node.id)
        await self.repo.update(org_node.id, {"path": new_path})
        org_node = await self.repo.get_by_id(org_node.id)
        await self._upsert_scope_policy(
            org_node,
            data_scope or DataScope.DEPT_AND_CHILDREN.value,
            custom_dept_ids,
        )
        await self._assign_permissions(org_node, permission_ids)
        await self.db.refresh(org_node)
        return await self.repo.get_with_members(org_node.id)

    async def update_org_node(
        self, org_node_id: int, data: dict[str, Any]
    ) -> AdminOrgNode:
        org_node = await self.repo.get_by_id(org_node_id)
        if not org_node:
            raise NotFoundException(message=_("role.not_found"))

        if org_node.is_system and "parent_id" in data:
            raise BusinessException(
                message=_("role.system_role_cannot_change_parent"),
                code=ErrorCode.ROLE_SYSTEM_CANNOT_CHANGE_PARENT,
            )

        scope_mode = data.pop("data_scope", None)
        custom_org_node_ids = data.pop("custom_dept_ids", None)
        permission_ids = data.pop("permission_ids", None)

        if "type" in data and data["type"] is not None:
            self._validate_org_node_type(data["type"])

        if "parent_id" in data and data["parent_id"] != org_node.parent_id:
            new_parent_id = data["parent_id"]
            parent_path, parent_level = await self.validate_parent(
                new_parent_id, exclude_id=org_node_id
            )
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

            old_path = org_node.path or f"/{org_node_id}/"
            new_path = self._build_path(parent_path, org_node_id)
            data["path"] = new_path
            data["level"] = new_level
            updated = await self.repo.update(org_node_id, data)
            await self._update_descendants_path(
                org_node_id, old_path, new_path, new_level
            )
            org_node = updated or await self.repo.get_by_id(org_node_id)
        elif data:
            updated = await self.repo.update(org_node_id, data)
            org_node = updated or await self.repo.get_by_id(org_node_id)

        if scope_mode is not None or custom_org_node_ids is not None:
            await self._upsert_scope_policy(
                org_node,
                scope_mode or org_node.scope_mode,
                custom_org_node_ids
                if custom_org_node_ids is not None
                else org_node.custom_org_node_ids,
            )
        if permission_ids is not None:
            await self._assign_permissions(org_node, permission_ids)

        return await self.repo.get_with_members(org_node_id)

    async def update_authority_policy(
        self,
        org_node_id: int,
        data_scope: str,
        custom_dept_ids: list[int] | None,
    ) -> AdminOrgNode:
        org_node = await self.repo.get_by_id(org_node_id)
        if not org_node:
            raise NotFoundException(message=_("role.not_found"))

        await self._upsert_scope_policy(org_node, data_scope, custom_dept_ids)
        return await self.repo.get_with_members(org_node_id)

    async def get_organization_root_nodes(self) -> list[AdminOrgNode]:
        return await self.repo.get_organization_root_nodes()

    async def get_visible_org_tree(
        self,
        visible_org_node_ids: list[int] | None = None,
    ) -> list[AdminOrgNode]:
        """按可见范围获取组织树 / Get organization tree within the visible scope."""
        if visible_org_node_ids is None:
            return await self.repo.get_tree()
        if not visible_org_node_ids:
            return []

        scope_ids = set(visible_org_node_ids)
        roots: list[AdminOrgNode] = []
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
    ) -> list[AdminOrgNode]:
        """按可见范围获取根节点 / Get root nodes within the visible scope."""
        if visible_org_node_ids is None:
            return await self.get_organization_root_nodes()
        if not visible_org_node_ids:
            return []

        scope_ids = set(visible_org_node_ids)
        items: list[AdminOrgNode] = []
        for org_node_id in sorted(scope_ids):
            org_node = await self.repo.get_with_members(org_node_id)
            if org_node and (
                org_node.parent_id is None or org_node.parent_id not in scope_ids
            ):
                items.append(org_node)
        return items

    async def get_org_node_detail(self, org_node_id: int) -> AdminOrgNode:
        """获取组织节点详情 / Get organization node detail."""
        org_node = await self.repo.get_with_members(org_node_id)
        if not org_node:
            raise NotFoundException(message=_("role.not_found"))
        return org_node

    async def get_organization_children(self, org_node_id: int) -> list[AdminOrgNode]:
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

    async def move_org_node(
        self, org_node_id: int, new_parent_id: int | None
    ) -> AdminOrgNode:
        await self.move_node(org_node_id, new_parent_id)
        return await self.repo.get_with_members(org_node_id)

    async def set_leader(self, org_node_id: int, leader_id: int | None) -> AdminOrgNode:
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
                select(Admin).where(
                    Admin.id == leader_id,
                    Admin.is_deleted.is_(False),
                    Admin.org_node_id == org_node_id,
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

    async def _load_member_detail(self, admin_id: int) -> Admin:
        result = await self.db.execute(
            select(Admin)
            .where(
                Admin.id == admin_id,
                Admin.is_deleted.is_(False),
            )
            .options(
                selectinload(Admin.org_node),
                selectinload(Admin.role),
            )
        )
        admin = result.scalar_one_or_none()
        if not admin:
            raise NotFoundException(message=_("admin.not_found"))
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
    ) -> Admin:
        org_node = await self.repo.get_by_id(org_node_id)
        if not org_node:
            raise NotFoundException(message=_("role.not_found"))
        if not org_node.allow_members:
            raise BusinessException(
                message=_("role.cannot_add_member"),
                code=ErrorCode.ROLE_CANNOT_ADD_MEMBER,
            )

        admin = await AdminService(self.db).create_admin(
            username=username,
            email=email,
            password=password,
            phone=phone,
            nickname=nickname,
            is_active=is_active,
            is_super=False,
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
    ) -> Admin:
        _, admin = await self._require_member_in_scope(org_node_id, admin_id)

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

        updated = await AdminService(self.db).update_admin(admin.id, update_data)
        return await self._load_member_detail(updated.id)

    async def reset_member_password(
        self, org_node_id: int, admin_id: int, new_password: str
    ) -> bool:
        _, admin = await self._require_member_in_scope(org_node_id, admin_id)
        return await AdminService(self.db).reset_password(admin.id, new_password)

    async def toggle_member_status(
        self, org_node_id: int, admin_id: int, is_active: bool
    ) -> Admin:
        _, admin = await self._require_member_in_scope(org_node_id, admin_id)
        updated = await AdminService(self.db).toggle_status(admin.id, is_active)
        return await self._load_member_detail(updated.id)

    async def add_member(self, org_node_id: int, admin_id: int) -> Admin:
        org_node = await self.repo.get_by_id(org_node_id)
        if not org_node:
            raise NotFoundException(message=_("role.not_found"))
        if not org_node.allow_members:
            raise BusinessException(
                message=_("role.cannot_add_member"),
                code=ErrorCode.ROLE_CANNOT_ADD_MEMBER,
            )

        admin_service = AdminService(self.db)
        admin = await admin_service.get_by_id(admin_id)
        if not admin:
            raise NotFoundException(message=_("admin.not_found"))
        if admin.org_node_id == org_node_id:
            raise BusinessException(
                message=_("role.member_exists"),
                code=ErrorCode.ROLE_MEMBER_EXISTS,
            )
        updated = await admin_service.update_admin(
            admin_id, {"org_node_id": org_node_id}
        )
        return await self._load_member_detail(updated.id)

    async def remove_member(self, org_node_id: int, admin_id: int) -> Admin:
        org_node, admin = await self._require_member_in_scope(org_node_id, admin_id)
        if admin.is_super:
            raise BusinessException(
                message=_(ErrorCode.ADMIN_CANNOT_REMOVE_SUPER.message_key),
                code=ErrorCode.ADMIN_CANNOT_REMOVE_SUPER,
            )
        if org_node.leader_id == admin_id:
            await self.repo.update(org_node.id, {"leader_id": None})
        updated = await AdminService(self.db).update_admin(
            admin_id, {"org_node_id": None}
        )
        return await self._load_member_detail(updated.id)

    async def get_members(
        self,
        org_node_id: int,
        search: str | None = None,
        page: int = 1,
        page_size: int = 20,
        include_descendants: bool = True,
    ) -> tuple[list[Admin], int]:
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

    async def _require_member_in_scope(
        self, org_node_id: int, admin_id: int
    ) -> tuple[AdminOrgNode, Admin]:
        org_node = await self.repo.get_by_id(org_node_id)
        if not org_node:
            raise NotFoundException(message=_("role.not_found"))

        result = await self.db.execute(
            select(Admin)
            .where(
                Admin.id == admin_id,
                Admin.is_deleted.is_(False),
            )
            .options(selectinload(Admin.org_node))
        )
        admin = result.scalar_one_or_none()
        if not admin or admin.org_node_id is None or admin.org_node is None:
            raise BusinessException(
                message=_("role.member_not_in_node"),
                code=ErrorCode.ROLE_MEMBER_NOT_IN_NODE,
            )

        scope_path = org_node.path or f"/{org_node.id}/"
        member_path = admin.org_node.path or f"/{admin.org_node_id}/"
        if admin.org_node_id != org_node.id and not member_path.startswith(scope_path):
            raise BusinessException(
                message=_("role.member_not_in_node"),
                code=ErrorCode.ROLE_MEMBER_NOT_IN_NODE,
            )

        return org_node, admin


__all__ = ["AdminOrgNodeService"]
