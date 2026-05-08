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
from app.plugins.tenant_plan_preflight import run_tenant_plan_preflight
from app.repositories.tenant.tenant_plan_repository import TenantPlanRepository
from app.schemas.tenant.plan import (
    TenantPlanCreateRequest,
    TenantPlanUpdateRequest,
)
from app.services.tenant.tenant_plan_plugin_entitlement_service import (
    TenantPlanPluginEntitlementService,
)


class TenantPlanService(GlobalService[TenantPlan, TenantPlanRepository]):
    """
    企业套餐服务 / Tenant plan service.

    提供套餐特有的业务方法
    注意：套餐是平台级数据，不做企业隔离
    """

    model = TenantPlan
    repository_class = TenantPlanRepository

    async def _run_plan_preflight(
        self,
        *,
        operation: str,
        plan_id: int | None,
        features: dict[str, Any] | None,
        quota: dict[str, Any] | None,
        context: dict[str, Any] | None = None,
    ) -> None:
        """Run host-level tenant plan preflight and raise on denial.
        / 运行宿主级套餐前置校验，若被拒绝则抛异常。
        """
        result = await run_tenant_plan_preflight(
            {
                "operation": operation,
                "plan_id": plan_id,
                "tenant_id": None,
                "features": dict(features or {}),
                "quota": dict(quota or {}),
                "context": dict(context or {}),
            }
        )
        if result.get("allowed") is True:
            return

        raise BusinessException(
            message=result.get("message") or _("common.failed"),
            data={
                "reason_code": result.get("reason_code") or "preflight_denied",
                "details": result.get("details") or {},
                "operation": operation,
                "plan_id": plan_id,
            },
        )

    async def _sync_plan_plugin_entitlements(
        self,
        plan_id: int,
        features: dict[str, Any] | None,
    ) -> dict[str, dict[str, Any]]:
        """Sync feature-managed plugin entitlements for a plan.
        / 为套餐同步由 feature 驱动的插件授权。
        """
        service = TenantPlanPluginEntitlementService(self.db)
        return await service.sync_plan_feature_entitlements(plan_id, features)

    async def get_by_code(self, code: str) -> TenantPlan | None:
        """
        根据代码获取套餐 / Get plan by code.

        Args:
            code: 套餐代码

        Returns:
            套餐实例或 None
        """
        return await self.repo.get_by_code(code)

    async def get_with_permissions(self, plan_id: int) -> TenantPlan | None:
        """
        获取套餐及其权限 / Get plan with permissions.

        Args:
            plan_id: 套餐 ID

        Returns:
            套餐实例（含权限）或 None
        """
        return await self.repo.get_with_permissions(plan_id)

    async def get_active_plans(self) -> list[TenantPlan]:
        """
        获取所有启用的套餐 / Get all active plans.

        Returns:
            启用的套餐列表
        """
        return await self.repo.get_active_plans()

    async def get_tenant_counts_batch(
        self,
        plan_ids: list[int],
    ) -> dict[int, int]:
        """批量获取套餐的企业数量 / Batch get tenant counts for plans."""
        return await self.repo.get_tenant_counts_batch(plan_ids)

    async def _generate_plan_code(self) -> str:
        """
        生成唯一的套餐代码 / Generate unique plan code.

        格式: plan_ + 6位小写字母数字（如 plan_a8k2m9）

        Returns:
            唯一的套餐代码
        """
        charset = string.ascii_lowercase + string.digits
        max_attempts = 10

        for _attempt in range(max_attempts):
            # 生成 plan_ + 6位随机字符
            random_part = "".join(secrets.choice(charset) for _ in range(6))
            code = f"plan_{random_part}"

            # 检查是否已存在 / Check exists
            if not await self.repo.code_exists(code):
                return code

        # 极端情况：多次尝试后仍重复，加长随机部分 / Rare: still duplicate after retries; lengthen random part
        random_part = "".join(secrets.choice(charset) for _ in range(10))
        return f"plan_{random_part}"

    async def create_plan(
        self,
        request: TenantPlanCreateRequest,
    ) -> TenantPlan:
        """
        创建套餐 / Create plan.

        Args:
            request: 创建请求

        Returns:
            创建的套餐
        """
        # 自动生成套餐代码 / Auto-generate plan code
        code = await self._generate_plan_code()

        quota_data = request.quota.to_dict() if request.quota else None
        features_data = request.features.to_dict() if request.features else None

        await self._run_plan_preflight(
            operation="plan_create",
            plan_id=None,
            features=features_data,
            quota=quota_data,
            context={"code": code, "name": request.name},
        )

        # 构建创建数据 / Build create payload
        data = {
            "code": code,
            "name": request.name,
            "description": request.description,
            "price": request.price,
            "billing_cycle": request.billing_cycle,
            "is_active": request.is_active,
            "sort_order": request.sort_order,
            "quota": quota_data,
            "features": features_data,
        }

        plan = await self.create(data)
        await self._sync_plan_plugin_entitlements(plan.id, features_data)
        return plan

    async def update_plan(
        self,
        plan_id: int,
        request: TenantPlanUpdateRequest,
    ) -> TenantPlan:
        """
        更新套餐 / Update plan.

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

        effective_features = (
            request.features.to_dict()
            if request.features is not None
            else dict(plan.features or {})
        )
        effective_quota = (
            request.quota.to_dict()
            if request.quota is not None
            else dict(plan.quota or {})
        )

        await self._run_plan_preflight(
            operation="plan_update",
            plan_id=plan_id,
            features=effective_features,
            quota=effective_quota,
            context={"code": plan.code, "name": request.name or plan.name},
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

        await self._sync_plan_plugin_entitlements(
            result.id,
            dict(result.features or effective_features or {}),
        )
        return result

    async def delete_plan(self, plan_id: int) -> bool:
        """
        删除套餐 / Delete plan.

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

        # 检查是否有企业使用该套餐 / Check plan in use by tenants
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
        分配套餐权限 / Assign permissions to plan.

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

        requested_ids = list(dict.fromkeys(permission_ids))

        # 获取有效的权限列表（仅 tenant/both scope 的 menu 类型）
        valid_permissions = await self._get_valid_permissions(requested_ids)
        valid_ids = {permission.id for permission in valid_permissions}
        invalid_ids = sorted(set(requested_ids) - valid_ids)
        if invalid_ids:
            raise BusinessException(
                message=_("common.invalid_request"),
                code=ErrorCode.VALIDATION_ERROR,
                data={"invalid_permission_ids": invalid_ids},
            )

        # 更新套餐权限 / Update plan permissions
        plan.permissions = valid_permissions
        await self.db.flush()
        await self.db.refresh(plan)
        await self._sync_plan_plugin_entitlements(plan.id, dict(plan.features or {}))

        return plan

    async def get_plan_permissions(self, plan_id: int) -> list[Permission]:
        """
        获取套餐权限列表 / Get plan permissions list.

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
        获取有效的权限列表（仅 tenant/both scope 的 menu 类型）/ Get valid permissions (tenant/both scope, menu type only).

        Args:
            permission_ids: 权限 ID 列表

        Returns:
            有效的权限列表
        """
        if not permission_ids:
            return []

        # 查询有效权限 / Query effective permissions
        query = select(Permission).where(
            Permission.id.in_(permission_ids),
            Permission.is_deleted.is_(False),
            Permission.is_enabled.is_(True),
            Permission.type == PermissionType.MENU.value,
            Permission.scope.in_(
                [
                    PermissionScope.TENANT.value,
                    PermissionScope.BOTH.value,
                ]
            ),
        )
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_available_permissions(self) -> list[Permission]:
        """
        获取可分配给套餐的权限列表 / Get permissions assignable to plans.

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
                Permission.scope.in_(
                    [
                        PermissionScope.TENANT.value,
                        PermissionScope.BOTH.value,
                    ]
                ),
            )
            .order_by(Permission.sort_order, Permission.id)
        )
        result = await self.db.execute(query)
        return list(result.scalars().all())


__all__ = ["TenantPlanService"]
