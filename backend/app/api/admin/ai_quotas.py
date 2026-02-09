"""
平台端 AI 配额管理 API

提供租户 AI 配额的 CRUD 接口（平台管理员专用）
"""

from fastapi import Request

from app.core.base_controller import GlobalController
from app.core.base_schema import PageResponse
from app.core.deps import DbSession, QueryParams, ActiveAdmin
from app.core.i18n import _
from app.core.response import success
from app.enums.rbac import PermissionScope
from app.exceptions import NotFoundException
from app.rbac.decorators import (
    MenuConfig,
    action_create,
    action_delete,
    action_read,
    action_update,
    permission_resource,
)
from app.repositories.ai.tenant_quota_repository import AdminTenantQuotaRepository
from app.schemas.ai.tenant_quota import (
    AdminTenantQuotaCreate,
    TenantQuotaResponse,
    TenantQuotaUpdate,
)
from app.services.ai.tenant_quota_service import TenantQuotaService


def _build_quota_response(quota) -> dict:
    """
    构建配额响应数据

    手动从关系中提取 tenant_name 和 model_name
    """
    tenant_name = None
    model_name = None

    try:
        tenant = getattr(quota, 'tenant', None)
        if tenant is not None:
            tenant_name = tenant.name
    except (AttributeError, Exception):
        pass

    try:
        model = getattr(quota, 'model', None)
        if model is not None:
            model_name = model.name
    except (AttributeError, Exception):
        pass

    return {
        "id": quota.id,
        "tenant_id": quota.tenant_id,
        "model_id": quota.model_id,
        "period": quota.period,
        "limit": quota.limit,
        "quota_type": quota.quota_type,
        "warning_threshold": quota.warning_threshold,
        "is_active": quota.is_active,
        "description": quota.description,
        "tenant_name": tenant_name,
        "model_name": model_name,
        "created_at": quota.created_at,
        "updated_at": quota.updated_at,
    }


@permission_resource(
    resource="ai_quota",
    name="menu.admin.ai_quota",
    scope=PermissionScope.ADMIN,
    menu=MenuConfig(
        icon="lucide:gauge",
        path="/ai/quotas",
        component="ai/quotas/index",
        parent="ai_mgmt",
        sort_order=50,
    ),
)
class AdminAIQuotaController(GlobalController):
    """
    AI 配额管理控制器

    提供租户 AI 配额 CRUD 接口
    """

    prefix = "/ai/quotas"
    tags = [_("menu.admin.ai_quota")]
    service_class = TenantQuotaService

    def _register_routes(self) -> None:
        """注册路由"""
        router = self.router

        @router.get("", summary=_("action.ai_quota.list"))
        @action_read("action.ai_quota.list")
        async def list_quotas(
            request: Request,
            db: DbSession,
            spec: QueryParams,
            admin: ActiveAdmin,
        ):
            """
            获取配额列表（跨租户）

            权限: ai_quota:list
            """
            repo = AdminTenantQuotaRepository(db)
            items, total = await repo.query_list(spec)

            return success(
                data=PageResponse.create(
                    items=[
                        TenantQuotaResponse(**_build_quota_response(item))
                        for item in items
                    ],
                    total=total,
                    page=spec.page,
                    page_size=spec.size,
                ),
                message=_("common.success"),
            )

        @router.get("/{quota_id}", summary=_("action.ai_quota.detail"))
        @action_read("action.ai_quota.detail")
        async def get_quota(
            request: Request,
            db: DbSession,
            quota_id: int,
            admin: ActiveAdmin,
        ):
            """
            获取配额详情

            权限: ai_quota:detail
            """
            repo = AdminTenantQuotaRepository(db)
            quota = await repo.get_by_id(quota_id)

            if not quota:
                raise NotFoundException(
                    message=_("ai.error.quota_not_found")
                )

            return success(
                data=TenantQuotaResponse.model_validate(
                    quota, from_attributes=True
                ),
                message=_("common.success"),
            )

        @router.post("", summary=_("action.ai_quota.create"))
        @action_create("action.ai_quota.create")
        async def create_quota(
            request: Request,
            db: DbSession,
            data: AdminTenantQuotaCreate,
            admin: ActiveAdmin,
        ):
            """
            创建配额（需指定 tenant_id）

            权限: ai_quota:create
            """
            service = TenantQuotaService(db, data.tenant_id)
            quota = await service.create(
                data.model_dump(exclude={"tenant_id"})
            )
            await db.commit()

            return success(
                data=TenantQuotaResponse.model_validate(
                    quota, from_attributes=True
                ),
                message=_("ai.quota.created"),
            )

        @router.put("/{quota_id}", summary=_("action.ai_quota.update"))
        @action_update("action.ai_quota.update")
        async def update_quota(
            request: Request,
            db: DbSession,
            quota_id: int,
            data: TenantQuotaUpdate,
            admin: ActiveAdmin,
        ):
            """
            更新配额

            权限: ai_quota:update
            """
            repo = AdminTenantQuotaRepository(db)
            quota = await repo.get_by_id(quota_id)

            if not quota:
                raise NotFoundException(
                    message=_("ai.error.quota_not_found")
                )

            service = TenantQuotaService(db, quota.tenant_id)
            updated = await service.update(
                quota_id, data.model_dump(exclude_unset=True)
            )
            await db.commit()

            return success(
                data=TenantQuotaResponse.model_validate(
                    updated, from_attributes=True
                ),
                message=_("ai.quota.updated"),
            )

        @router.delete("/{quota_id}", summary=_("action.ai_quota.delete"))
        @action_delete("action.ai_quota.delete")
        async def delete_quota(
            request: Request,
            db: DbSession,
            quota_id: int,
            admin: ActiveAdmin,
        ):
            """
            删除配额

            权限: ai_quota:delete
            """
            repo = AdminTenantQuotaRepository(db)
            quota = await repo.get_by_id(quota_id)

            if not quota:
                raise NotFoundException(
                    message=_("ai.error.quota_not_found")
                )

            service = TenantQuotaService(db, quota.tenant_id)
            await service.delete(quota_id)
            await db.commit()

            return success(message=_("ai.quota.deleted"))


# 导出路由器
router = AdminAIQuotaController.get_router()

__all__ = ["router", "AdminAIQuotaController"]
