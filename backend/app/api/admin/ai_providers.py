"""
平台端 AI 供应商管理 API

提供 AI 供应商的 CRUD 接口（平台管理员专用）
"""

from fastapi import Request

from app.core.base_controller import GlobalController
from app.core.deps import DbSession, QueryParams, ActiveAdmin
from app.core.base_schema import PageResponse
from app.core.i18n import _
from app.core.response import success
from app.enums.rbac import PermissionScope
from app.rbac.decorators import (
    permission_resource,
    MenuConfig,
    action_read,
    action_create,
    action_update,
    action_delete,
)
from app.schemas.ai.provider import (
    AIProviderCreate,
    AIProviderUpdate,
    AIProviderResponse,
)
from app.schemas.common import ReorderRequest
from app.core.recycle_bin import register_admin_recycle_bin_routes
from app.services.ai import AIProviderService


@permission_resource(
    resource="ai_provider",
    name="menu.admin.ai_provider",
    scope=PermissionScope.ADMIN_ONLY,
    menu=MenuConfig(
        icon="lucide:cpu",
        path="/ai/providers",
        component="ai/providers/index",
        parent="ai_infra",
        sort_order=10,
    ),
)
class AdminAIProviderController(GlobalController):
    """
    AI 供应商管理控制器

    提供 AI 供应商 CRUD、状态切换等接口
    """

    prefix = "/ai/providers"
    tags = [_("menu.tags.admin_ai_provider")]
    service_class = AIProviderService

    def _register_routes(self) -> None:
        """注册路由"""
        router = self.router

        # 回收站路由必须在 /{id} 之前注册，避免路径冲突
        register_admin_recycle_bin_routes(
            router=router,
            service_class=AIProviderService,
            resource_name="ai_provider",
        )

        @router.get("/adapter-types", summary="获取可用适配器类型列表")
        @action_read("action.ai_provider.list")
        async def list_adapter_types(
            request: Request,
            db: DbSession,
            admin: ActiveAdmin,
        ):
            """
            获取所有可用的适配器类型（内置 + 插件注册）

            返回每种适配器类型的名称、来源（builtin/plugin）、供应商信息。
            前端用于供应商类型下拉列表。
            """
            from app.ai.adapters import AdapterRegistry

            all_types = AdapterRegistry.list_adapters()

            result = []
            for adapter_type in all_types:
                entry = {
                    "type": adapter_type,
                    "source": "builtin",
                    "display_name": adapter_type,
                }
                result.append(entry)

            return success(data=result)

        @router.get("", summary="获取 AI 供应商列表")
        @action_read("action.ai_provider.list")
        async def list_providers(
            request: Request,
            db: DbSession,
            spec: QueryParams,
            admin: ActiveAdmin,
        ):
            """
            获取 AI 供应商列表

            - 支持通用筛选: filter[field][op]=value
            - 支持排序: sort=-created_at,name
            - 支持分页: page[number]=1&page[size]=20

            权限: ai_provider:list
            """
            service = AIProviderService(db)
            items, total = await service.query_list(spec)

            return success(
                data=PageResponse.create(
                    items=[AIProviderResponse.model_validate(item, from_attributes=True) for item in items],
                    total=total,
                    page=spec.page,
                    page_size=spec.size,
                ),
                message=_("common.success"),
            )

        # ========== 排序管理 ==========
        # 注意：/reorder 必须放在 /{provider_id} 之前

        @router.put("/reorder", summary="批量重排序 AI 供应商")
        @action_update("action.ai_provider.reorder")
        async def reorder_providers(
            request: Request,
            db: DbSession,
            data: ReorderRequest,
            admin: ActiveAdmin,
        ):
            """
            批量重排序 AI 供应商

            权限: ai_provider:reorder
            """
            service = AIProviderService(db)
            try:
                updated_count = await service.reorder(ordered_ids=data.ids)
                await db.commit()
                return success(
                    data={"updated_count": updated_count},
                    message=_("common.reorder_success"),
                )
            except ValueError as e:
                from fastapi import HTTPException, status
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=str(e),
                )

        @router.get("/{provider_id}", summary="获取 AI 供应商详情")
        @action_read("action.ai_provider.detail")
        async def get_provider(
            request: Request,
            db: DbSession,
            provider_id: int,
            admin: ActiveAdmin,
        ):
            """
            获取 AI 供应商详情

            权限: ai_provider:detail
            """
            service = AIProviderService(db)
            provider = await service.get_by_id(provider_id)

            if not provider:
                from app.exceptions import NotFoundException
                raise NotFoundException(message=_("ai.error.provider_not_found"))

            return success(
                data=AIProviderResponse.model_validate(provider, from_attributes=True),
                message=_("common.success"),
            )

        @router.post("", summary="创建 AI 供应商")
        @action_create("action.ai_provider.create")
        async def create_provider(
            request: Request,
            db: DbSession,
            data: AIProviderCreate,
            admin: ActiveAdmin,
        ):
            """
            创建 AI 供应商

            权限: ai_provider:create
            """
            service = AIProviderService(db)
            provider = await service.create_provider(data)
            await db.commit()

            return success(
                data=AIProviderResponse.model_validate(provider, from_attributes=True),
                message=_("ai.provider.created"),
            )

        @router.put("/{provider_id}", summary="更新 AI 供应商")
        @action_update("action.ai_provider.update")
        async def update_provider(
            request: Request,
            db: DbSession,
            provider_id: int,
            data: AIProviderUpdate,
            admin: ActiveAdmin,
        ):
            """
            更新 AI 供应商信息

            权限: ai_provider:update
            """
            service = AIProviderService(db)
            provider = await service.update_provider(provider_id, data)
            await db.commit()

            return success(
                data=AIProviderResponse.model_validate(provider, from_attributes=True),
                message=_("ai.provider.updated"),
            )

        @router.delete("/{provider_id}", summary="删除 AI 供应商")
        @action_delete("action.ai_provider.delete")
        async def delete_provider(
            request: Request,
            db: DbSession,
            provider_id: int,
            admin: ActiveAdmin,
        ):
            """
            删除 AI 供应商（软删除）

            权限: ai_provider:delete
            """
            service = AIProviderService(db)
            await service.delete_provider(provider_id)
            await db.commit()

            return success(message=_("ai.provider.deleted"))

        @router.put("/{provider_id}/status", summary="切换 AI 供应商启用状态")
        @action_update("action.ai_provider.toggle_status")
        async def toggle_provider_status(
            request: Request,
            db: DbSession,
            provider_id: int,
            admin: ActiveAdmin,
        ):
            """
            启用或禁用 AI 供应商

            权限: ai_provider:toggle_status
            """
            service = AIProviderService(db)
            provider = await service.toggle_status(provider_id)
            await db.commit()

            return success(
                data=AIProviderResponse.model_validate(provider, from_attributes=True),
                message=_("ai.provider.status_updated"),
            )


# 导出路由器
router = AdminAIProviderController.get_router()

__all__ = ["router", "AdminAIProviderController"]
