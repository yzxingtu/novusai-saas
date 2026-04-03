"""
平台端 AI 模型管理 API / Platform AI Model API

提供 AI 模型的 CRUD 接口（平台管理员专用）
Provides AI model CRUD endpoints (platform admin only).
"""

from fastapi import Query, Request

from app.core.base_controller import GlobalController
from app.core.base_schema import PageResponse
from app.core.deps import ActiveAdmin, DbSession, QueryParams
from app.core.i18n import _
from app.core.recycle_bin import register_admin_recycle_bin_routes
from app.core.response import success
from app.enums.rbac import PermissionScope
from app.rbac.decorators import (
    MenuConfig,
    action_create,
    action_delete,
    action_read,
    action_update,
    permission_resource,
)
from app.schemas.ai.model import (
    AIModelCreate,
    AIModelResponse,
    AIModelUpdate,
)
from app.services.ai import AIModelService


@permission_resource(
    resource="ai_model",
    name="menu.admin.ai_model",
    scope=PermissionScope.ADMIN,
    parent_resource="ai_infra",
    menu=MenuConfig(
        icon="lucide:brain",
        path="/ai/models",
        component="ai/models/index",
        parent="ai_infra",
        sort_order=20,
    ),
)
class AdminAIModelController(GlobalController):
    """
    AI 模型管理控制器 / AI Model Management Controller

    提供 AI 模型 CRUD 接口 / Provides AI model CRUD endpoints
    """

    prefix = "/ai/models"
    tags = [_("menu.tags.admin_ai_model")]
    service_class = AIModelService

    def _register_routes(self) -> None:
        """注册路由 / Register routes"""
        router = self.router

        # 回收站路由必须在 /{id} 之前注册，避免路径冲突 / Recycle bin routes must be registered before /{id} to avoid path conflicts
        register_admin_recycle_bin_routes(
            router=router,
            service_class=AIModelService,
            resource_name="ai_model",
        )

        @router.get("/select", summary="获取 AI 模型下拉选项")
        @action_read("action.ai_model.list")
        async def select_models(
            request: Request,
            db: DbSession,
            admin: ActiveAdmin,
            search: str = Query("", description=_("api.param.search")),
            page: int = Query(0, ge=0, description=_("api.param.page")),
            page_size: int = Query(
                20, ge=1, le=100, description=_("api.param.page_size")
            ),
            type: str = Query("", description=_("api.param.type")),
            supports_vision: str = Query(
                "", description=_("enum.ai_model.filter_supports_vision")
            ),
            supports_audio: str = Query(
                "", description=_("enum.ai_model.filter_supports_audio")
            ),
            supports_video: str = Query(
                "", description=_("enum.ai_model.filter_supports_video")
            ),
        ):
            service = AIModelService(db)
            extra_filters: dict = {"is_active": True}
            if type:
                extra_filters["type"] = type
            if supports_vision.lower() == "true":
                extra_filters["supports_vision"] = True
            if supports_audio.lower() == "true":
                extra_filters["supports_audio"] = True
            if supports_video.lower() == "true":
                extra_filters["supports_video"] = True
            response = await service.get_select_options(
                search=search,
                page=page,
                page_size=page_size,
                **extra_filters,
            )
            return success(data=response, message=_("common.success"))

        @router.get("", summary="获取 AI 模型列表")
        @action_read("action.ai_model.list")
        async def list_models(
            request: Request,
            db: DbSession,
            spec: QueryParams,
            admin: ActiveAdmin,
        ):
            """
            获取 AI 模型列表 / Get AI model list

            - 支持通用筛选 / General filtering: filter[field][op]=value
            - 支持排序 / Sorting: sort=-created_at,name
            - 支持分页 / Pagination: page[number]=1&page[size]=20

            权限 / Permission: ai_model:list
            """
            service = AIModelService(db)
            items, total = await service.query_list(spec)

            return success(
                data=PageResponse.create(
                    items=[
                        AIModelResponse.model_validate(item, from_attributes=True)
                        for item in items
                    ],
                    total=total,
                    page=spec.page,
                    page_size=spec.size,
                ),
                message=_("common.success"),
            )

        @router.get("/provider/{provider_id}", summary="获取供应商的 AI 模型列表")
        @action_read("action.ai_model.list_by_provider")
        async def list_models_by_provider(
            request: Request,
            db: DbSession,
            provider_id: int,
            admin: ActiveAdmin,
        ):
            """
            根据供应商 ID 获取其所有模型 / Get all models by provider ID

            权限 / Permission: ai_model:list_by_provider
            """
            service = AIModelService(db)
            models = await service.get_by_provider(provider_id)

            return success(
                data=[
                    AIModelResponse.model_validate(m, from_attributes=True)
                    for m in models
                ],
                message=_("common.success"),
            )

        @router.get(
            "/fetch-remote/{provider_id}", summary="从供应商远程拉取可用模型列表"
        )
        @action_read("action.ai_model.list")
        async def fetch_remote_models(
            request: Request,
            db: DbSession,
            provider_id: int,
            admin: ActiveAdmin,
        ):
            """
            从供应商 API 远程拉取可用模型列表 / Fetch available model list from provider API remotely

            通过供应商配置的 API 地址和密钥，调用 /models 接口获取可用模型。
            Calls /models endpoint via provider's configured API address and key.
            用于创建模型时自动填充模型代码和名称。
            Used for auto-filling model code and name when creating models.

            权限 / Permission: ai_model:list
            """
            service = AIModelService(db)
            remote_models = await service.fetch_remote_models(provider_id)

            return success(
                data=remote_models,
                message=_("common.success"),
            )

        @router.get("/{model_id}", summary="获取 AI 模型详情")
        @action_read("action.ai_model.detail")
        async def get_model(
            request: Request,
            db: DbSession,
            model_id: int,
            admin: ActiveAdmin,
        ):
            """
            获取 AI 模型详情 / Get AI model details

            权限 / Permission: ai_model:detail
            """
            service = AIModelService(db)
            model = await service.get_by_id(model_id)

            if not model:
                from app.exceptions import NotFoundException

                raise NotFoundException(message=_("ai.error.model_not_found"))

            return success(
                data=AIModelResponse.model_validate(model, from_attributes=True),
                message=_("common.success"),
            )

        @router.post("", summary="创建 AI 模型")
        @action_create("action.ai_model.create")
        async def create_model(
            request: Request,
            db: DbSession,
            data: AIModelCreate,
            admin: ActiveAdmin,
        ):
            """
            创建 AI 模型 / Create AI model

            权限 / Permission: ai_model:create
            """
            service = AIModelService(db)
            model = await service.create_model(data)
            await db.commit()
            await db.refresh(model, ["provider", "fallback_model"])

            return success(
                data=AIModelResponse.model_validate(model, from_attributes=True),
                message=_("ai.model.created"),
            )

        @router.put("/{model_id}", summary="更新 AI 模型")
        @action_update("action.ai_model.update")
        async def update_model(
            request: Request,
            db: DbSession,
            model_id: int,
            data: AIModelUpdate,
            admin: ActiveAdmin,
        ):
            """
            更新 AI 模型信息 / Update AI model info

            权限 / Permission: ai_model:update
            """
            service = AIModelService(db)
            model = await service.update_model(model_id, data)
            await db.commit()
            await db.refresh(model, ["provider", "fallback_model"])

            return success(
                data=AIModelResponse.model_validate(model, from_attributes=True),
                message=_("ai.model.updated"),
            )

        @router.delete("/{model_id}", summary="删除 AI 模型")
        @action_delete("action.ai_model.delete")
        async def delete_model(
            request: Request,
            db: DbSession,
            model_id: int,
            admin: ActiveAdmin,
        ):
            """
            删除 AI 模型（软删除） / Delete AI model (soft delete)

            权限 / Permission: ai_model:delete
            """
            service = AIModelService(db)
            await service.delete_model(model_id)
            await db.commit()

            return success(message=_("ai.model.deleted"))


# 导出路由器 / Export router
router = AdminAIModelController.get_router()

__all__ = ["router", "AdminAIModelController"]
