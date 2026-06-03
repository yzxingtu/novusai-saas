"""
平台管理员服务 / Admin Service

提供平台管理员的业务逻辑
Provides platform admin business logic.
"""

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.base_service import GlobalService
from app.core.i18n import _
from app.core.identity import (
    build_identity_select_extra,
    resolve_identity_display_name,
)
from app.core.security import get_password_hash, verify_password
from app.enums import ErrorCode
from app.exceptions import BusinessException, NotFoundException
from app.models.org import AdminOrgNode
from app.models.system.admin import Admin
from app.repositories.system.admin_permission_role_repository import (
    AdminPermissionRoleRepository,
)
from app.repositories.system.admin_repository import AdminRepository
from app.schemas.common.select import SelectOption, SelectResponse


class AdminService(GlobalService[Admin, AdminRepository]):
    """
    平台管理员服务 / Platform admin service.

    提供管理员特有的业务方法
    """

    model = Admin
    repository_class = AdminRepository

    async def get_by_username(self, username: str) -> Admin | None:
        """
        根据用户名获取管理员 / Get admin by username.

        Args:
            username: 用户名

        Returns:
            管理员实例或 None
        """
        return await self.repo.get_by_username(username)

    async def get_by_email(self, email: str) -> Admin | None:
        """
        根据邮箱获取管理员 / Get admin by email.

        Args:
            email: 邮箱

        Returns:
            管理员实例或 None
        """
        return await self.repo.get_by_email(email)

    async def get_by_username_or_email(
        self,
        username_or_email: str,
    ) -> Admin | None:
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
        ai_enabled: bool = True,
        is_super: bool = False,
        role_id: int | None = None,
        org_node_id: int | None = None,
    ) -> Admin:
        """
        创建管理员 / Create admin.

        Args:
            username: 用户名
            email: 邮箱
            password: 明文密码
            phone: 手机号
            nickname: 昵称
            is_active: 是否激活
            is_super: 是否超级管理员
            role_id: 角色 ID

        Returns:
            创建的管理员

        Raises:
            BusinessException: 用户名/邮箱/手机号已存在
        """
        # 检查用户名是否已存在 / Check username exists
        if await self.repo.username_exists(username):
            raise BusinessException(
                message=_("admin.username_exists"),
                code=ErrorCode.ADMIN_USERNAME_EXISTS,
            )

        # 检查邮箱是否已存在 / Check email exists
        if await self.repo.email_exists(email):
            raise BusinessException(
                message=_("admin.email_exists"),
                code=ErrorCode.ADMIN_EMAIL_EXISTS,
            )

        # 检查手机号是否已存在 / Check phone exists
        if phone and await self.repo.phone_exists(phone):
            raise BusinessException(
                message=_("admin.phone_exists"),
                code=ErrorCode.ADMIN_PHONE_EXISTS,
            )

        await self._validate_permission_role(role_id)
        await self._validate_org_node(org_node_id)

        # 创建管理员 / Create admin
        data = {
            "username": username,
            "email": email,
            "password_hash": get_password_hash(password),
            "phone": phone,
            "nickname": nickname,
            "is_active": is_active,
            "ai_enabled": ai_enabled,
            "is_super": is_super,
            "role_id": role_id,
            "org_node_id": org_node_id,
        }

        return await self.create(data)

    async def update_admin(
        self,
        admin_id: int,
        data: dict[str, Any],
    ) -> Admin:
        """
        更新管理员 / Update admin.

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
                message=_("admin.not_found"),
            )

        # 检查邮箱是否已被其他管理员使用 / Check email used by other admin
        if (
            "email" in data
            and data["email"]
            and await self.repo.email_exists(data["email"], exclude_id=admin_id)
        ):
            raise BusinessException(
                message=_("admin.email_exists"),
                code=ErrorCode.ADMIN_EMAIL_EXISTS,
            )

        # 检查手机号是否已被其他管理员使用 / Check phone used by other admin
        if (
            "phone" in data
            and data["phone"]
            and await self.repo.phone_exists(data["phone"], exclude_id=admin_id)
        ):
            raise BusinessException(
                message=_("admin.phone_exists"),
                code=ErrorCode.ADMIN_PHONE_EXISTS,
            )

        if "role_id" in data:
            await self._validate_permission_role(data["role_id"])

        if "org_node_id" in data:
            await self._validate_org_node(data["org_node_id"])

        # 移除不允许直接更新的字段 / Remove fields not directly updatable
        data.pop("password", None)
        data.pop("password_hash", None)
        data.pop("username", None)  # 用户名不允许修改 / policy guard
        if data.get("ai_enabled") is None:
            data.pop("ai_enabled", None)

        result = await self.update(admin_id, data)
        if not result:
            raise NotFoundException(message=_("admin.not_found"))
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
                message=_("admin.not_found"),
            )

        # 验证旧密码 / Validate old password
        if not verify_password(old_password, admin.password_hash):
            raise BusinessException(
                message=_("admin.password_incorrect"),
                code=ErrorCode.OLD_PASSWORD_INCORRECT,
            )

        # 更新密码 / Update password
        await self.update(
            admin_id,
            {
                "password_hash": get_password_hash(new_password),
            },
        )

        return True

    async def reset_password(
        self,
        admin_id: int,
        new_password: str,
    ) -> bool:
        """
        重置密码（超级管理员操作）/ Reset password (super admin operation).

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
                message=_("admin.not_found"),
            )

        # 更新密码 / Update password
        await self.update(
            admin_id,
            {
                "password_hash": get_password_hash(new_password),
            },
        )

        return True

    async def toggle_status(self, admin_id: int, is_active: bool) -> Admin:
        """
        切换管理员状态 / Toggle admin status.

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
                message=_("admin.not_found"),
            )

        result = await self.update(admin_id, {"is_active": is_active})
        if not result:
            raise NotFoundException(message=_("admin.not_found"))
        return result

    async def get_identity_select_options(
        self,
        search: str = "",
        page: int = 1,
        page_size: int = 20,
    ) -> SelectResponse:
        """
        获取管理端身份分页选择器 / Get paginated admin identity select options.
        """
        admins, total = await self.repo.query_identity_select(
            search=search or None,
            page=page,
            page_size=page_size,
        )
        items = [self._build_identity_select_option(admin) for admin in admins]
        return SelectResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            has_more=(page * page_size) < total,
        )

    async def get_identity_detail(self, admin_id: int) -> Admin:
        """
        获取平台管理员详情，含角色/组织信息 / Get platform admin detail with role and org.
        """
        stmt = (
            select(self.model)
            .options(
                selectinload(self.model.role),
                selectinload(self.model.org_node),
            )
            .where(self.model.id == admin_id, self.model.is_deleted.is_(False))
        )
        result = await self.db.execute(stmt)
        admin = result.scalar_one_or_none()
        if not admin:
            raise NotFoundException(message=_("admin.not_found"))
        return admin

    async def _validate_permission_role(self, role_id: int | None) -> None:
        if role_id is None:
            return

        repo = AdminPermissionRoleRepository(self.db)
        if await repo.get_by_id(role_id) is None:
            raise NotFoundException(message=_("role.not_found"))

    async def _validate_org_node(self, org_node_id: int | None) -> None:
        if org_node_id is None:
            return

        result = await self.db.execute(
            select(AdminOrgNode.id).where(
                AdminOrgNode.id == org_node_id,
                AdminOrgNode.is_deleted.is_(False),
            )
        )
        if result.scalar_one_or_none() is None:
            raise NotFoundException(message=_("role.not_found"))

    @staticmethod
    def _build_identity_select_option(admin: Admin) -> SelectOption:
        role = getattr(admin, "role", None)
        org_node = getattr(admin, "org_node", None)
        is_leader = bool(org_node and getattr(org_node, "leader_id", None) == admin.id)
        display_name = resolve_identity_display_name(
            admin.id,
            admin.nickname,
            admin.username,
        )
        return SelectOption(
            label=display_name,
            value=admin.id,
            extra=build_identity_select_extra(
                display_name=display_name,
                username=admin.username,
                nickname=admin.nickname,
                avatar=admin.avatar,
                org_node_id=admin.org_node_id,
                org_node_name=getattr(org_node, "name", None),
                role_name=getattr(role, "name", None),
                user_type="admin",
                is_active=admin.is_active,
                is_leader=is_leader,
                is_owner=False,
            ),
            disabled=not admin.is_active,
        )


__all__ = ["AdminService"]
