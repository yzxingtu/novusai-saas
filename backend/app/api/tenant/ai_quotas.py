"""
企业端 AI 配额和速率限制配置 API / Tenant AI Quota and Rate Limit Config API

提供企业级配额管理和速率限制配置接口
Provides tenant-level quota management and rate limit configuration endpoints
"""

from fastapi import Query, Request

from app.core.base_controller import TenantController
from app.core.deps import ActiveTenantAdmin, DbSession
from app.core.i18n import _
from app.core.response import success
from app.enums.rbac import PermissionScope
from app.exceptions import AuthorizationException, NotFoundException
from app.rbac.decorators import (
    MenuConfig,
    action_create,
    action_delete,
    action_read,
    action_update,
    permission_resource,
)
from app.schemas.ai.tenant_quota import (
    TenantQuotaCreate,
    TenantQuotaResponse,
    TenantQuotaUpdate,
)
from app.schemas.ai.tenant_rate_limit import (
    TenantRateLimitCreate,
    TenantRateLimitResponse,
    TenantRateLimitUpdate,
)
from app.services.ai.tenant_quota_service import TenantQuotaService
from app.services.ai.tenant_rate_limit_service import TenantRateLimitService


@permission_resource(
    resource="ai_quota",
    name="menu.tenant.ai_quota",
    scope=PermissionScope.TENANT,
    parent_resource="ai_settings",
    menu=MenuConfig(
        icon="lucide:gauge",
        path="/ai/quotas",
        component="ai/quotas/index",
        parent="ai_settings",
        sort_order=20,
    ),
)
class TenantAIQuotaController(TenantController):
    """
    企业 AI 配额和速率限制控制器 / Tenant AI Quota and Rate Limit Controller

    提供配额管理和速率限制配置接口
    Provides quota management and rate limit configuration endpoints
    """

    prefix = "/ai/quotas"
    tags = [_("menu.tags.tenant_ai_quota")]

    def _register_routes(self) -> None:
        """注册路由 / Register routes"""
        router = self.router

        # ========== 配额管理 / Quota Management ==========

        @router.get("", summary="获取配额配置列表")
        @action_read("action.ai_quota.list_quotas")
        async def get_quotas(
            request: Request,
            db: DbSession,
            tenant_admin: ActiveTenantAdmin,
            model_id: int | None = Query(None, description=_("api.param.model_id")),
            period: str | None = Query(None, description=_("api.param.period")),
            include_usage: bool = Query(False, description=_("api.param.include_usage")),
            is_active: bool | None = Query(None, description=_("api.param.is_active")),
        ):
            """
            获取企业配额配置列表 / Get tenant quota config list

            权限 / Permission: ai_quota:list_quotas
            """
            service = TenantQuotaService(db, tenant_admin.tenant_id)

            if include_usage:
                raw_list = await service.get_all_quotas_with_usage(
                    period=period,
                    model_id=model_id,
                    is_active=is_active,
                )

                # 将 ORM 对象序列化为包含 model_name 的字典 / Serialize ORM objects to dicts containing model_name
                result = []
                for item in raw_list:
                    result.append({
                        "quota": TenantQuotaResponse.from_orm_model(item["quota"]).model_dump(),
                        "usage": item["usage"],
                        "limit": item["limit"],
                        "usage_percent": item["usage_percent"],
                        "is_warning": item["is_warning"],
                        "is_exceeded": item["is_exceeded"],
                        "remaining": item["remaining"],
                    })
            else:
                quotas = await service.list_quotas(
                    period=period,
                    model_id=model_id,
                    is_active=is_active,
                )
                result = [TenantQuotaResponse.from_orm_model(q).model_dump() for q in quotas]

            return success(data=result, message=_("common.success"))

        # ========== 速率限制管理 / Rate Limit Management ==========
        # 注意：rate-limits 路由必须在 /{quota_id} 之前注册，
        # 否则 "rate-limits" 会被 FastAPI 匹配为 {quota_id} 参数
        # Note: rate-limits routes must be registered before /{quota_id},
        # otherwise "rate-limits" would be matched as {quota_id} parameter by FastAPI

        @router.get("/rate-limits", summary="获取速率限制配置列表")
        @action_read("action.ai_quota.list_rate_limits")
        async def get_rate_limits(
            request: Request,
            db: DbSession,
            tenant_admin: ActiveTenantAdmin,
            model_id: int | None = Query(None, description=_("api.param.model_id")),
            is_active: bool | None = Query(None, description=_("api.param.is_active")),
        ):
            """
            获取速率限制配置列表 / Get rate limit config list

            权限 / Permission: ai_quota:list_rate_limits
            """
            service = TenantRateLimitService(db, tenant_admin.tenant_id)
            items = await service.get_active_limits(
                model_id=model_id,
                is_active=is_active,
            )
            result = [TenantRateLimitResponse.from_orm_model(item).model_dump() for item in items]

            return success(data=result, message=_("common.success"))

        @router.get("/rate-limits/effective/{model_id}", summary="获取有效速率限制")
        @action_read("action.ai_quota.effective_rate_limits")
        async def get_effective_rate_limits(
            request: Request,
            db: DbSession,
            model_id: int,
            tenant_admin: ActiveTenantAdmin,
        ):
            """
            获取有效的速率限制 / Get effective rate limits

            权限 / Permission: ai_quota:effective_rate_limits
            """
            service = TenantRateLimitService(db, tenant_admin.tenant_id)
            result = await service.get_effective_rate_limits(model_id)

            return success(data=result, message=_("common.success"))

        @router.post("/rate-limits", summary="创建速率限制配置")
        @action_create("action.ai_quota.create_rate_limit")
        async def create_rate_limit(
            request: Request,
            db: DbSession,
            data: TenantRateLimitCreate,
            tenant_admin: ActiveTenantAdmin,
        ):
            """
            创建速率限制配置 / Create rate limit config

            权限 / Permission: ai_quota:create_rate_limit
            """
            service = TenantRateLimitService(db, tenant_admin.tenant_id)
            rate_limit = await service.create_rate_limit(
                model_id=data.model_id,
                rpm_limit=data.rpm_limit,
                tpm_limit=data.tpm_limit,
                description=data.description,
            )
            await db.commit()

            return success(data=rate_limit, message=_("ai.rate_limit.created"))

        @router.put("/rate-limits/{rate_limit_id}", summary="更新速率限制配置")
        @action_update("action.ai_quota.update_rate_limit")
        async def update_rate_limit(
            request: Request,
            db: DbSession,
            rate_limit_id: int,
            data: TenantRateLimitUpdate,
            tenant_admin: ActiveTenantAdmin,
        ):
            """
            更新速率限制配置 / Update rate limit config

            权限 / Permission: ai_quota:update_rate_limit
            """
            service = TenantRateLimitService(db, tenant_admin.tenant_id)
            rate_limit = await service.get_by_id(rate_limit_id)

            if not rate_limit:
                raise NotFoundException(message=_("ai.error.rate_limit_not_found"))

            if rate_limit.tenant_id != tenant_admin.tenant_id:
                raise AuthorizationException(message=_("common.forbidden"))

            update_data = data.model_dump(exclude_unset=True)
            updated = await service.update(rate_limit.id, update_data)
            await db.commit()

            return success(data=updated, message=_("ai.rate_limit.updated"))

        @router.delete("/rate-limits/{rate_limit_id}", summary="删除速率限制配置")
        @action_delete("action.ai_quota.delete_rate_limit")
        async def delete_rate_limit(
            request: Request,
            db: DbSession,
            rate_limit_id: int,
            tenant_admin: ActiveTenantAdmin,
        ):
            """
            删除速率限制配置 / Delete rate limit config

            权限 / Permission: ai_quota:delete_rate_limit
            """
            service = TenantRateLimitService(db, tenant_admin.tenant_id)
            rate_limit = await service.get_by_id(rate_limit_id)

            if not rate_limit:
                raise NotFoundException(message=_("ai.error.rate_limit_not_found"))

            if rate_limit.tenant_id != tenant_admin.tenant_id:
                raise AuthorizationException(message=_("common.forbidden"))

            await service.delete(rate_limit_id)
            await db.commit()

            return success(message=_("ai.rate_limit.deleted"))

        # ========== 配额详情与 CRUD（含路径参数） / Quota Details & CRUD (with path params) ==========

        @router.get("/{quota_id}", summary="获取配额配置详情")
        @action_read("action.ai_quota.detail_quota")
        async def get_quota(
            request: Request,
            db: DbSession,
            quota_id: int,
            tenant_admin: ActiveTenantAdmin,
        ):
            """
            获取配额配置详情 / Get quota config details

            权限 / Permission: ai_quota:detail_quota
            """
            service = TenantQuotaService(db, tenant_admin.tenant_id)
            quota = await service.get_by_id(quota_id)

            if not quota:
                raise NotFoundException(message=_("ai.error.quota_not_found"))

            if quota.tenant_id != tenant_admin.tenant_id:
                raise AuthorizationException(message=_("common.forbidden"))

            quota_with_usage = await service.build_quota_with_usage(quota)

            if quota_with_usage:
                response_data = {
                    "quota": TenantQuotaResponse.from_orm_model(quota_with_usage["quota"]).model_dump(),
                    "usage": quota_with_usage["usage"],
                    "limit": quota_with_usage["limit"],
                    "usage_percent": quota_with_usage["usage_percent"],
                    "is_warning": quota_with_usage["is_warning"],
                    "is_exceeded": quota_with_usage["is_exceeded"],
                    "remaining": quota_with_usage["remaining"],
                }
            else:
                response_data = None

            return success(data=response_data, message=_("common.success"))

        @router.post("", summary="创建配额配置")
        @action_create("action.ai_quota.create_quota")
        async def create_quota(
            request: Request,
            db: DbSession,
            data: TenantQuotaCreate,
            tenant_admin: ActiveTenantAdmin,
        ):
            """
            创建配额配置 / Create quota config

            权限 / Permission: ai_quota:create_quota
            """
            service = TenantQuotaService(db, tenant_admin.tenant_id)
            quota = await service.create_quota(
                model_id=data.model_id,
                period=data.period,
                limit=data.limit,
                quota_type=data.quota_type,
                warning_threshold=data.warning_threshold,
                description=data.description,
            )
            await db.commit()

            return success(data=quota, message=_("ai.quota.created"))

        @router.put("/{quota_id}", summary="更新配额配置")
        @action_update("action.ai_quota.update_quota")
        async def update_quota(
            request: Request,
            db: DbSession,
            quota_id: int,
            data: TenantQuotaUpdate,
            tenant_admin: ActiveTenantAdmin,
        ):
            """
            更新配额配置 / Update quota config

            权限 / Permission: ai_quota:update_quota
            """
            service = TenantQuotaService(db, tenant_admin.tenant_id)
            quota = await service.get_by_id(quota_id)

            if not quota:
                raise NotFoundException(message=_("ai.error.quota_not_found"))

            if quota.tenant_id != tenant_admin.tenant_id:
                raise AuthorizationException(message=_("common.forbidden"))

            update_data = data.model_dump(exclude_unset=True)
            updated = await service.update(quota.id, update_data)
            await db.commit()

            return success(data=updated, message=_("ai.quota.updated"))

        @router.delete("/{quota_id}", summary="删除配额配置")
        @action_delete("action.ai_quota.delete_quota")
        async def delete_quota(
            request: Request,
            db: DbSession,
            quota_id: int,
            tenant_admin: ActiveTenantAdmin,
        ):
            """
            删除配额配置 / Delete quota config

            权限 / Permission: ai_quota:delete_quota
            """
            service = TenantQuotaService(db, tenant_admin.tenant_id)
            quota = await service.get_by_id(quota_id)

            if not quota:
                raise NotFoundException(message=_("ai.error.quota_not_found"))

            if quota.tenant_id != tenant_admin.tenant_id:
                raise AuthorizationException(message=_("common.forbidden"))

            await service.delete(quota_id)
            await db.commit()

            return success(message=_("ai.quota.deleted"))


# 导出路由器 / Export router
router = TenantAIQuotaController.get_router()

__all__ = ["router", "TenantAIQuotaController"]
