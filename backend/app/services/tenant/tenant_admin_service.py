"""
企业管理员服务 / Tenant Admin Service

提供企业管理员的业务逻辑（企业隔离）
Provides tenant admin business logic (tenant-isolated).
"""

from typing import Any

from sqlalchemy import select

from app.core.base_service import TenantService
from app.core.i18n import _
from app.core.security import get_password_hash, verify_password
from app.enums import ErrorCode
from app.exceptions import BusinessException, NotFoundException
from app.models.org import TenantOrgNode
from app.models.tenant.tenant_admin import TenantAdmin
from app.repositories.tenant.tenant_admin_repository import TenantAdminRepository
from app.repositories.tenant.tenant_permission_role_repository import (
    TenantPermissionRoleRepository,
)


class TenantAdminService(TenantService[TenantAdmin, TenantAdminRepository]):
    """
    企业管理员服务 / Tenant admin service.

    提供企业管理员特有的业务方法，自动注入企业隔离
    """

    model = TenantAdmin
    repository_class = TenantAdminRepository

    async def get_by_username(self, username: str) -> TenantAdmin | None:
        """
        根据用户名获取管理员 / Get tenant admin by username.

        Args:
            username: 用户名

        Returns:
            管理员实例或 None
        """
        return await self.repo.get_by_username(username)

    async def get_by_email(self, email: str) -> TenantAdmin | None:
        """
        根据邮箱获取管理员 / Get tenant admin by email.

        Args:
            email: 邮箱

        Returns:
            管理员实例或 None
        """
        return await self.repo.get_by_email(email)

    async def get_by_username_or_email(
        self,
        username_or_email: str,
    ) -> TenantAdmin | None:
        """
        根据用户名或邮箱获取管理员（用于登录）/ Get admin by username or email (for login).

        Args:
            username_or_email: 用户名或邮箱

        Returns:
            管理员实例或 None
        """
        return await self.repo.get_by_username_or_email(username_or_email)

    async def create_admin(
        self,
        username: str,
        email: str,
        password: str,
        phone: str | None = None,
        nickname: str | None = None,
        is_active: bool = True,
        is_owner: bool = False,
        role_id: int | None = None,
        org_node_id: int | None = None,
    ) -> TenantAdmin:
        """
        创建企业管理员 / Create tenant admin.

        Args:
            username: 用户名
            email: 邮箱
            password: 明文密码
            phone: 手机号
            nickname: 昵称
            is_active: 是否激活
            is_owner: 是否企业所有者
            role_id: 权限角色 ID
            org_node_id: 组织节点 ID

        Returns:
            创建的管理员

        Raises:
            BusinessException: 用户名/邮箱/手机号已存在
        """
        # 检查用户名是否已存在（企业内唯一）
        if await self.repo.username_exists(username):
            raise BusinessException(
                message=_("tenant_admin.username_exists"),
                code=ErrorCode.ADMIN_USERNAME_EXISTS,
            )

        # 检查邮箱是否已存在（企业内唯一）
        if await self.repo.email_exists(email):
            raise BusinessException(
                message=_("tenant_admin.email_exists"),
                code=ErrorCode.ADMIN_EMAIL_EXISTS,
            )

        # 检查手机号是否已存在（企业内唯一）
        if phone and await self.repo.phone_exists(phone):
            raise BusinessException(
                message=_("tenant_admin.phone_exists"),
                code=ErrorCode.ADMIN_PHONE_EXISTS,
            )

        # 检查管理员数配额
        from sqlalchemy.orm import selectinload

        from app.models.tenant.tenant import Tenant
        from app.services.tenant.quota_service import QuotaService
        tenant_obj = (await self.db.execute(
            select(Tenant)
            .options(selectinload(Tenant.tenant_plan))
            .where(Tenant.id == self.tenant_id)
        )).scalar_one_or_none()
        if tenant_obj:
            quota_svc = QuotaService(self.db, tenant_obj)
            quota_check = await quota_svc.check_admin_quota()
            if not quota_check.allowed:
                raise BusinessException(
                    message=quota_check.message or _("quota.admins_exceeded"),
                    code=ErrorCode.CONFLICT,
                )

        # 如果是企业所有者，获取根节点
        root_node = None
        if is_owner:
            root_node = await self._get_tenant_root_node()
            # 如果未指定角色，自动关联到根节点
            if root_node and org_node_id is None:
                org_node_id = root_node.id

        await self._validate_permission_role(role_id)
        await self._validate_org_node(org_node_id)

        # 创建管理员（tenant_id 由 TenantService 自动注入）
        data = {
            "username": username,
            "email": email,
            "password_hash": get_password_hash(password),
            "phone": phone,
            "nickname": nickname,
            "is_active": is_active,
            "is_owner": is_owner,
            "role_id": role_id,
            "org_node_id": org_node_id,
        }

        admin = await self.create(data)

        # 如果是企业所有者，设为根节点负责人
        if is_owner and root_node and root_node.leader_id is None:
            root_node.leader_id = admin.id
            await self.db.flush()

        return admin

    async def update_admin(
        self,
        admin_id: int,
        data: dict[str, Any],
    ) -> TenantAdmin:
        """
        更新企业管理员 / Update tenant admin.

        Args:
            admin_id: 管理员 ID
            data: 更新数据（不含密码）

        Returns:
            更新后的管理员

        Raises:
            NotFoundException: 管理员不存在
            BusinessException: 邮箱/手机号已存在
        """
        admin = await self.get_by_id(admin_id)
        if not admin:
            raise NotFoundException(
                message=_("tenant_admin.not_found"),
            )

        # 检查邮箱是否已被其他管理员使用
        if (
            "email" in data
            and data["email"]
            and await self.repo.email_exists(data["email"], exclude_id=admin_id)
        ):
            raise BusinessException(
                message=_("tenant_admin.email_exists"),
                code=ErrorCode.ADMIN_EMAIL_EXISTS,
            )

        # 检查手机号是否已被其他管理员使用
        if (
            "phone" in data
            and data["phone"]
            and await self.repo.phone_exists(data["phone"], exclude_id=admin_id)
        ):
            raise BusinessException(
                message=_("tenant_admin.phone_exists"),
                code=ErrorCode.ADMIN_PHONE_EXISTS,
            )

        if "role_id" in data:
            await self._validate_permission_role(data["role_id"])

        if "org_node_id" in data:
            await self._validate_org_node(data["org_node_id"])

        # 移除不允许直接更新的字段
        data.pop("password", None)
        data.pop("password_hash", None)
        data.pop("username", None)  # 用户名不允许修改
        data.pop("tenant_id", None)  # 企业 ID 不允许修改

        result = await self.update(admin_id, data)
        if not result:
            raise NotFoundException(message=_("tenant_admin.not_found"))
        return result

    async def change_password(
        self,
        admin_id: int,
        old_password: str,
        new_password: str,
    ) -> bool:
        """
        修改密码（管理员自己操作）/ Change password (self-service).

        Args:
            admin_id: 管理员 ID
            old_password: 旧密码
            new_password: 新密码

        Returns:
            是否成功

        Raises:
            NotFoundException: 管理员不存在
            BusinessException: 旧密码错误
        """
        admin = await self.get_by_id(admin_id)
        if not admin:
            raise NotFoundException(
                message=_("tenant_admin.not_found"),
            )

        # 验证旧密码
        if not verify_password(old_password, admin.password_hash):
            raise BusinessException(
                message=_("tenant_admin.password_incorrect"),
                code=ErrorCode.OLD_PASSWORD_INCORRECT,
            )

        # 更新密码
        await self.update(admin_id, {
            "password_hash": get_password_hash(new_password),
        })

        return True

    async def reset_password(
        self,
        admin_id: int,
        new_password: str,
    ) -> bool:
        """
        重置密码（企业所有者操作）/ Reset password (owner operation).

        Args:
            admin_id: 管理员 ID
            new_password: 新密码

        Returns:
            是否成功

        Raises:
            NotFoundException: 管理员不存在
        """
        admin = await self.get_by_id(admin_id)
        if not admin:
            raise NotFoundException(
                message=_("tenant_admin.not_found"),
            )

        # 更新密码
        await self.update(admin_id, {
            "password_hash": get_password_hash(new_password),
        })

        return True

    async def toggle_status(self, admin_id: int, is_active: bool) -> TenantAdmin:
        """
        切换管理员状态 / Toggle admin active status.

        Args:
            admin_id: 管理员 ID
            is_active: 是否激活

        Returns:
            更新后的管理员

        Raises:
            NotFoundException: 管理员不存在
        """
        admin = await self.get_by_id(admin_id)
        if not admin:
            raise NotFoundException(
                message=_("tenant_admin.not_found"),
            )

        result = await self.update(admin_id, {"is_active": is_active})
        if not result:
            raise NotFoundException(message=_("tenant_admin.not_found"))
        return result

    async def _get_tenant_root_node(self) -> TenantOrgNode | None:
        """
        获取企业的组织架构根节点 / Get tenant org root node.

        Returns:
            根节点实例或 None
        """
        result = await self.db.execute(
            select(TenantOrgNode).where(
                TenantOrgNode.tenant_id == self.tenant_id,
                TenantOrgNode.code == "tenant_root",
                TenantOrgNode.is_system.is_(True),
                TenantOrgNode.is_deleted.is_(False),
            )
        )
        return result.scalar_one_or_none()

    async def _validate_permission_role(self, role_id: int | None) -> None:
        if role_id is None:
            return

        repo = TenantPermissionRoleRepository(self.db, self.tenant_id)
        if await repo.get_by_id(role_id) is None:
            raise NotFoundException(message=_("role.not_found"))

    async def _validate_org_node(self, org_node_id: int | None) -> None:
        if org_node_id is None:
            return

        result = await self.db.execute(
            select(TenantOrgNode.id).where(
                TenantOrgNode.id == org_node_id,
                TenantOrgNode.tenant_id == self.tenant_id,
                TenantOrgNode.is_deleted.is_(False),
            )
        )
        if result.scalar_one_or_none() is None:
            raise NotFoundException(message=_("role.not_found"))


__all__ = ["TenantAdminService"]
