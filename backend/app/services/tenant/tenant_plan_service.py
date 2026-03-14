"""
企业套餐服务 / Tenant Plan Service

提供套餐的业务逻辑（平台级，非企业隔离）
Provides plan business logic (platform-level, no tenant isolation).

"""
import secrets
import string
from typing import Any

from sqlalchemy import select

from app.core.base_service import GlobalService
from app.core.i18n import _
from app.enums import ErrorCode, PermissionScope, PermissionType
from app.exceptions import BusinessException, NotFoundException
from app.models.auth.permission import Permission
from app.models.tenant.tenant_plan import TenantPlan
from app.repositories.tenant.tenant_plan_repository import TenantPlanRepository
from app.schemas.tenant.plan import (
    TenantPlanCreateRequest,
    TenantPlanUpdateRequest,
)


class TenantPlanService(GlobalService[TenantPlan, TenantPlanRepository]):
    """
    企业套餐服务

    提供套餐特有的业务方法
    注意：套餐是平台级数据，不做企业隔离
    """

    model = TenantPlan
    repository_class = TenantPlanRepository

    async def get_by_code(self, code: str) -> TenantPlan | None:
        """
        根据代码获取套餐

        Args:
            code: 套餐代码

        Returns:
            套餐实例或 None
        """
        return await self.repo.get_by_code(code)

    async def get_with_permissions(self, plan_id: int) -> TenantPlan | None:
        """
        获取套餐及其权限

        Args:
            plan_id: 套餐 ID

        Returns:
            套餐实例（含权限）或 None
        """
        return await self.repo.get_with_permissions(plan_id)

    async def get_active_plans(self) -> list[TenantPlan]:
        """
        获取所有启用的套餐

        Returns:
            启用的套餐列表
        """
        return await self.repo.get_active_plans()

    async def _generate_plan_code(self) -> str:
        """
        生成唯一的套餐代码

        格式: plan_ + 6位小写字母数字（如 plan_a8k2m9）

        Returns:
            唯一的套餐代码
        """
        charset = string.ascii_lowercase + string.digits
        max_attempts = 10

        for _attempt in range(max_attempts):
            # 生成 plan_ + 6位随机字符
            random_part = ''.join(secrets.choice(charset) for _ in range(6))
            code = f"plan_{random_part}"

            # 检查是否已存在
            if not await self.repo.code_exists(code):
                return code

        # 极端情况：多次尝试后仍重复，加长随机部分
        random_part = ''.join(secrets.choice(charset) for _ in range(10))
        return f"plan_{random_part}"

    async def create_plan(
        self,
        request: TenantPlanCreateRequest,
    ) -> TenantPlan:
        """
        创建套餐

        Args:
            request: 创建请求

        Returns:
            创建的套餐
        """
        # 自动生成套餐代码
        code = await self._generate_plan_code()

        # 构建创建数据
        data = {
            "code": code,
            "name": request.name,
            "description": request.description,
            "price": request.price,
            "billing_cycle": request.billing_cycle,
            "is_active": request.is_active,
            "sort_order": request.sort_order,
            "quota": request.quota.to_dict() if request.quota else None,
            "features": request.features.to_dict() if request.features else None,
        }

        return await self.create(data)

    async def update_plan(
        self,
        plan_id: int,
        request: TenantPlanUpdateRequest,
    ) -> TenantPlan:
        """
        更新套餐

        Args:
            plan_id: 套餐 ID
            request: 更新请求

        Returns:
            更新后的套餐

        Raises:
            NotFoundException: 套餐不存在
        """
        plan = await self.get_by_id(plan_id)
        if not plan:
            raise NotFoundException(
                message=_("tenant_plan.not_found"),
            )

        # 构建更新数据（仅包含非 None 字段）
        data: dict[str, Any] = {}

        if request.name is not None:
            data["name"] = request.name
        if request.description is not None:
            data["description"] = request.description
        if request.price is not None:
            data["price"] = request.price
        if request.billing_cycle is not None:
            data["billing_cycle"] = request.billing_cycle
        if request.is_active is not None:
            data["is_active"] = request.is_active
        if request.sort_order is not None:
            data["sort_order"] = request.sort_order
        if request.quota is not None:
            data["quota"] = request.quota.to_dict()
        if request.features is not None:
            data["features"] = request.features.to_dict()

        result = await self.update(plan_id, data)
        if not result:
            raise NotFoundException(message=_("tenant_plan.not_found"))
        return result

    async def delete_plan(self, plan_id: int) -> bool:
        """
        删除套餐

        Args:
            plan_id: 套餐 ID

        Returns:
            是否删除成功

        Raises:
            NotFoundException: 套餐不存在
            BusinessException: 套餐正在被企业使用
        """
        plan = await self.repo.get_with_tenants(plan_id)
        if not plan:
            raise NotFoundException(
                message=_("tenant_plan.not_found"),
            )

        # 检查是否有企业使用该套餐
        if plan.has_tenants:
            raise BusinessException(
                message=_("tenant_plan.has_tenants"),
                code=ErrorCode.CONFLICT,
            )

        return await self.delete(plan_id)

    async def assign_permissions(
        self,
        plan_id: int,
        permission_ids: list[int],
    ) -> TenantPlan:
        """
        分配套餐权限

        Args:
            plan_id: 套餐 ID
            permission_ids: 权限 ID 列表（仅支持 tenant scope 的 menu 类型）

        Returns:
            更新后的套餐

        Raises:
            NotFoundException: 套餐不存在
            BusinessException: 权限无效
        """
        plan = await self.repo.get_with_permissions(plan_id)
        if not plan:
            raise NotFoundException(
                message=_("tenant_plan.not_found"),
            )

        # 获取有效的权限列表（仅 tenant/both scope 的 menu 类型）
        valid_permissions = await self._get_valid_permissions(permission_ids)

        # 更新套餐权限
        plan.permissions = valid_permissions
        await self.db.flush()
        await self.db.refresh(plan)

        return plan

    async def get_plan_permissions(self, plan_id: int) -> list[Permission]:
        """
        获取套餐权限列表

        Args:
            plan_id: 套餐 ID

        Returns:
            权限列表

        Raises:
            NotFoundException: 套餐不存在
        """
        plan = await self.repo.get_with_permissions(plan_id)
        if not plan:
            raise NotFoundException(
                message=_("tenant_plan.not_found"),
            )

        return plan.permissions

    async def _get_valid_permissions(
        self,
        permission_ids: list[int],
    ) -> list[Permission]:
        """
        获取有效的权限列表

        仅返回 tenant/both scope 的 menu 类型权限

        Args:
            permission_ids: 权限 ID 列表

        Returns:
            有效的权限列表
        """
        if not permission_ids:
            return []

        # 查询有效权限
        query = (
            select(Permission)
            .where(
                Permission.id.in_(permission_ids),
                Permission.is_deleted.is_(False),
                Permission.is_enabled.is_(True),
                Permission.type == PermissionType.MENU.value,
                Permission.scope.in_([
                    PermissionScope.ALL_TENANTS.value,
                    PermissionScope.ADMIN_AND_ALL.value,
                ]),
            )
        )
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_available_permissions(self) -> list[Permission]:
        """
        获取可分配给套餐的权限列表

        返回所有 tenant/both scope 的 menu 类型权限

        Returns:
            可用权限列表
        """
        query = (
            select(Permission)
            .where(
                Permission.is_deleted.is_(False),
                Permission.is_enabled.is_(True),
                Permission.type == PermissionType.MENU.value,
                Permission.scope.in_([
                    PermissionScope.ALL_TENANTS.value,
                    PermissionScope.ADMIN_AND_ALL.value,
                ]),
            )
            .order_by(Permission.sort_order, Permission.id)
        )
        result = await self.db.execute(query)
        return list(result.scalars().all())


__all__ = ["TenantPlanService"]
