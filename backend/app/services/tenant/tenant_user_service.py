"""
企业用户服务 / Tenant User Service

提供企业业务用户的业务逻辑（企业隔离）
Provides tenant business user logic (tenant-isolated).
"""

from __future__ import annotations

from typing import Any

from app.core.base_service import TenantService
from app.core.i18n import _
from app.core.security import get_password_hash
from app.enums import ErrorCode
from app.enums.common import ApprovalStatusEnum
from app.exceptions import BusinessException, NotFoundException
from app.models.tenant.tenant_user import TenantUser
from app.repositories.tenant.tenant_user_repository import TenantUserRepository
from app.services.common.notification_service import notify


class TenantUserService(TenantService[TenantUser, TenantUserRepository]):
    """
    企业用户服务 / Tenant user service.

    提供企业用户特有的业务方法，自动注入企业隔离
    """

    model = TenantUser
    repository_class = TenantUserRepository

    async def create_user(
        self,
        username: str,
        email: str,
        password: str,
        phone: str | None = None,
        nickname: str | None = None,
        is_active: bool = True,
        role_id: int | None = None,
        org_node_id: int | None = None,
    ) -> TenantUser:
        """
        创建企业用户（管理员操作）/ Create tenant user (admin action).

        Args:
            username: 用户名
            email: 邮箱
            password: 明文密码
            phone: 手机号
            nickname: 昵称
            is_active: 是否激活
            role_id: 权限角色 ID
            org_node_id: 组织归属节点 ID

        Returns:
            创建的用户

        Raises:
            BusinessException: 用户名/邮箱/手机号已存在
        """
        # 检查用户数配额
        from sqlalchemy import select
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
            quota_check = await quota_svc.check_user_quota()
            if not quota_check.allowed:
                raise BusinessException(
                    message=quota_check.message or _("quota.users_exceeded"),
                    code=ErrorCode.CONFLICT,
                )

        if await self.repo.username_exists(username):
            raise BusinessException(
                message=_("auth.username_taken"),
                code=ErrorCode.CONFLICT,
            )

        if await self.repo.email_exists(email):
            raise BusinessException(
                message=_("auth.email_taken"),
                code=ErrorCode.CONFLICT,
            )

        if phone and await self.repo.phone_exists(phone):
            raise BusinessException(
                message=_("auth.phone_taken"),
                code=ErrorCode.CONFLICT,
            )

        await self._validate_permission_role(role_id)
        await self._validate_org_node(org_node_id)

        data = {
            "username": username,
            "email": email,
            "password_hash": get_password_hash(password),
            "phone": phone,
            "nickname": nickname,
            "is_active": is_active,
            "role_id": role_id,
            "org_node_id": org_node_id,
            "approval_status": ApprovalStatusEnum.APPROVED.value,
        }

        return await self.create(data)

    async def update_user(
        self,
        user_id: int,
        data: dict[str, Any],
    ) -> TenantUser:
        """
        更新企业用户 / Update tenant user.

        Args:
            user_id: 用户 ID
            data: 更新数据（不含密码）

        Returns:
            更新后的用户

        Raises:
            NotFoundException: 用户不存在
            BusinessException: 邮箱/手机号已存在
        """
        user = await self.get_by_id(user_id)
        if not user:
            raise NotFoundException(
                message=_("tenant_user.not_found"),
            )

        if (
            "email" in data
            and data["email"]
            and await self.repo.email_exists(data["email"], exclude_id=user_id)
        ):
            raise BusinessException(
                message=_("auth.email_taken"),
                code=ErrorCode.CONFLICT,
            )

        if (
            "phone" in data
            and data["phone"]
            and await self.repo.phone_exists(data["phone"], exclude_id=user_id)
        ):
            raise BusinessException(
                message=_("auth.phone_taken"),
                code=ErrorCode.CONFLICT,
            )

        if "role_id" in data:
            await self._validate_permission_role(data["role_id"])

        if "org_node_id" in data:
            await self._validate_org_node(data["org_node_id"])

        # 移除不允许直接更新的字段
        data.pop("password", None)
        data.pop("password_hash", None)
        data.pop("username", None)
        data.pop("tenant_id", None)

        result = await self.update(user_id, data)
        if not result:
            raise NotFoundException(message=_("tenant_user.not_found"))
        return result

    async def reset_password(
        self,
        user_id: int,
        new_password: str,
    ) -> bool:
        """
        重置用户密码（管理员操作）/ Reset user password (admin action).

        Args:
            user_id: 用户 ID
            new_password: 新密码

        Returns:
            是否成功

        Raises:
            NotFoundException: 用户不存在
        """
        user = await self.get_by_id(user_id)
        if not user:
            raise NotFoundException(
                message=_("tenant_user.not_found"),
            )

        await self.update(user_id, {
            "password_hash": get_password_hash(new_password),
        })

        return True

    async def toggle_status(self, user_id: int, is_active: bool) -> TenantUser:
        """
        切换用户状态 / Toggle user active status.

        Args:
            user_id: 用户 ID
            is_active: 是否激活

        Returns:
            更新后的用户

        Raises:
            NotFoundException: 用户不存在
        """
        user = await self.get_by_id(user_id)
        if not user:
            raise NotFoundException(
                message=_("tenant_user.not_found"),
            )

        result = await self.update(user_id, {"is_active": is_active})
        if not result:
            raise NotFoundException(message=_("tenant_user.not_found"))
        return result

    async def approve_user(self, user_id: int) -> TenantUser:
        """
        审批通过用户 / Approve user.

        Args:
            user_id: 用户 ID

        Returns:
            更新后的用户

        Raises:
            NotFoundException: 用户不存在
            BusinessException: 用户非待审批状态
        """
        user = await self.get_by_id(user_id)
        if not user:
            raise NotFoundException(
                message=_("tenant_user.not_found"),
            )

        if user.approval_status != ApprovalStatusEnum.PENDING.value:
            raise BusinessException(
                message=_("tenant_user.not_pending"),
                code=ErrorCode.VALIDATION_ERROR,
            )

        result = await self.update(user_id, {
            "approval_status": ApprovalStatusEnum.APPROVED.value,
            "is_active": True,
        })
        if not result:
            raise NotFoundException(message=_("tenant_user.not_found"))

        await self._send_approval_notification(result, approved=True)
        return result

    async def reject_user(self, user_id: int) -> TenantUser:
        """
        审批拒绝用户 / Reject user.

        Args:
            user_id: 用户 ID

        Returns:
            更新后的用户

        Raises:
            NotFoundException: 用户不存在
            BusinessException: 用户非待审批状态
        """
        user = await self.get_by_id(user_id)
        if not user:
            raise NotFoundException(
                message=_("tenant_user.not_found"),
            )

        if user.approval_status != ApprovalStatusEnum.PENDING.value:
            raise BusinessException(
                message=_("tenant_user.not_pending"),
                code=ErrorCode.VALIDATION_ERROR,
            )

        result = await self.update(user_id, {
            "approval_status": ApprovalStatusEnum.REJECTED.value,
            "is_active": False,
        })
        if not result:
            raise NotFoundException(message=_("tenant_user.not_found"))

        await self._send_approval_notification(result, approved=False)
        return result

    async def batch_approve(self, user_ids: list[int]) -> list[TenantUser]:
        """
        批量审批通过用户 / Batch approve users.

        Args:
            user_ids: 用户 ID 列表

        Returns:
            更新后的用户列表
        """
        results = []
        for user_id in user_ids:
            user = await self.get_by_id(user_id)
            if user and user.approval_status == ApprovalStatusEnum.PENDING.value:
                result = await self.update(user_id, {
                    "approval_status": ApprovalStatusEnum.APPROVED.value,
                    "is_active": True,
                })
                if result:
                    results.append(result)
        for user in results:
            await self._send_approval_notification(user, approved=True)
        return results

    async def batch_reject(self, user_ids: list[int]) -> list[TenantUser]:
        """
        批量审批拒绝用户 / Batch reject users.

        Args:
            user_ids: 用户 ID 列表

        Returns:
            更新后的用户列表
        """
        results = []
        for user_id in user_ids:
            user = await self.get_by_id(user_id)
            if user and user.approval_status == ApprovalStatusEnum.PENDING.value:
                result = await self.update(user_id, {
                    "approval_status": ApprovalStatusEnum.REJECTED.value,
                    "is_active": False,
                })
                if result:
                    results.append(result)
        for user in results:
            await self._send_approval_notification(user, approved=False)
        return results

    async def _get_tenant_name(self) -> str:
        """获取当前企业名称 / Get current tenant name."""
        from sqlalchemy import select

        from app.models.tenant.tenant import Tenant

        result = await self.db.execute(
            select(Tenant.name).where(Tenant.id == self.tenant_id)
        )
        return result.scalar_one_or_none() or ""

    async def _send_approval_notification(
        self,
        user: TenantUser,
        *,
        approved: bool,
    ) -> None:
        """发送审批结果通知给用户 / Send approval result notification to user."""
        tenant_name = await self._get_tenant_name()
        template_code = "biz.user_approved" if approved else "biz.user_rejected"
        await notify(
            self.db,
            template_code=template_code,
            recipients=[("tenant_user", user.id)],
            data={"tenant_name": tenant_name},
            tenant_id=self.tenant_id,
        )

    async def _validate_permission_role(self, role_id: int | None) -> None:
        """校验权限角色归属 / Validate tenant user permission role assignment."""
        if role_id is None:
            return

        if not await self.repo.permission_role_exists(role_id):
            raise NotFoundException(message=_("tenant_user.permission_role_not_found"))

    async def _validate_org_node(self, org_node_id: int | None) -> None:
        """校验组织节点归属 / Validate tenant user organization assignment."""
        if org_node_id is None:
            return

        if not await self.repo.org_node_exists(org_node_id):
            raise NotFoundException(message=_("tenant_user.org_node_not_found"))


__all__ = ["TenantUserService"]
