"""
平台端 AI API Key 管理 API / Platform AI API Key API

提供 AI API Key 的 CRUD 接口（平台管理员专用）
Provides AI API key CRUD endpoints (platform admin only).
"""

from fastapi import Query, Request
from sqlalchemy import func, select

from app.core.base_controller import GlobalController
from app.core.base_schema import PageResponse
from app.core.deps import ActiveAdmin, DbSession, QueryParams
from app.core.i18n import _
from app.core.recycle_bin import register_admin_recycle_bin_routes
from app.core.response import success
from app.enums.rbac import PermissionScope
from app.models.ai import AIModel
from app.rbac.decorators import (
    MenuConfig,
    action_create,
    action_delete,
    action_read,
    action_update,
    permission_resource,
)
from app.schemas.ai.api_key import (
    ProviderApiKeyCreate,
    ProviderApiKeyResponse,
    ProviderApiKeyUpdate,
)
from app.services.ai import ProviderApiKeyService


def _make_key_preview(key) -> str | None:
    """
    生成 API Key 明文掩码预览（如 sk-ab****wxyz） / Generate API Key plaintext masked preview (e.g. sk-ab****wxyz)
    """
    try:
        plain_key = key.decrypt_key()
        if not plain_key:
            return None
        if len(plain_key) <= 8:
            return plain_key[:2] + "****"
        return plain_key[:4] + "****" + plain_key[-4:]
    except Exception:
        return None


def _build_api_key_response(key, model_count_map: dict[int, int] | None = None) -> dict:
    """
    构建 API Key 响应数据 / Build API Key response data

    Args:
        key: ProviderApiKey instance
        model_count_map: provider_id → active model count (pre-queried for efficiency)
    """
    provider_name = None
    tenant_name = None

    if key.tenant_id is not None:
        try:
            tenant = getattr(key, 'tenant', None)
            if tenant is not None:
                tenant_name = tenant.name
        except AttributeError:
            pass

    provider_icon = None
    provider_model_count = 0
    try:
        provider = getattr(key, 'provider', None)
        if provider is not None:
            provider_name = provider.name
            provider_icon = provider.icon
    except AttributeError:
        pass

    if model_count_map:
        provider_model_count = model_count_map.get(key.provider_id, 0)

    _otid = getattr(key, "owner_tenant_id", None)
    return {
        "id": key.id,
        "provider_id": key.provider_id,
        "scope": key.scope,
        "tenant_id": _otid,
        "owner_tenant_id": _otid,
        "name": key.name,
        "is_active": key.is_active,
        "usage_limit": key.usage_limit,
        "usage_count": key.usage_count,
        "last_used_at": key.last_used_at,
        "expires_at": key.expires_at,
        "created_at": key.created_at,
        "updated_at": key.updated_at,
        "is_deleted": key.is_deleted,
        "is_available": key.is_available(),
        "key_preview": _make_key_preview(key),
        "provider_name": provider_name,
        "provider_icon": provider_icon,
        "provider_model_count": provider_model_count,
        "tenant_name": tenant_name,
    }


@permission_resource(
    resource="ai_api_key",
    name="menu.admin.ai_api_key",
    scope=PermissionScope.ADMIN,
    parent_resource="ai_infra",
    menu=MenuConfig(
        icon="lucide:key",
        path="/ai/api-keys",
        component="ai/api-keys/index",
        parent="ai_infra",
        sort_order=15,
    ),
)
class AdminAIApiKeyController(GlobalController):
    """
    AI API Key 管理控制器 / AI API Key Management Controller

    提供 AI API Key CRUD、状态切换等接口 / Provides AI API Key CRUD, status toggle endpoints
    """

    prefix = "/ai/api-keys"
    tags = [_("menu.tags.admin_ai_api_key")]
    service_class = ProviderApiKeyService

    def _register_routes(self) -> None:
        """注册路由 / Register routes"""
        router = self.router

        @router.get("", summary="获取 AI API Key 列表")
        @action_read("action.ai_api_key.list")
        async def list_api_keys(
            request: Request,
            db: DbSession,
            spec: QueryParams,
            admin: ActiveAdmin,
        ):
            """
            获取 AI API Key 列表 / Get AI API Key list

            - 支持通用筛选 / General filtering: filter[field][op]=value
            - 支持排序 / Sorting: sort=-created_at,name
            - 支持分页 / Pagination: page[number]=1&page[size]=20

            权限 / Permission: ai_api_key:list
            """
            service = ProviderApiKeyService(db)
            items, total = await service.query_list(spec)

            provider_ids = {item.provider_id for item in items}
            model_count_map: dict[int, int] = {}
            if provider_ids:
                stmt = (
                    select(AIModel.provider_id, func.count(AIModel.id))
                    .where(AIModel.provider_id.in_(provider_ids), AIModel.is_deleted.is_(False), AIModel.is_active.is_(True))
                    .group_by(AIModel.provider_id)
                )
                result = await db.execute(stmt)
                model_count_map = dict(result.all())

            return success(
                data=PageResponse.create(
                    items=[ProviderApiKeyResponse(**_build_api_key_response(item, model_count_map)) for item in items],
                    total=total,
                    page=spec.page,
                    page_size=spec.size,
                ),
                message=_("common.success"),
            )

        @router.get("/provider/{provider_id}", summary="获取供应商的 API Key 列表")
        @action_read("action.ai_api_key.list_by_provider")
        async def list_keys_by_provider(
            request: Request,
            db: DbSession,
            provider_id: int,
            admin: ActiveAdmin,
            tenant_id: int | None = Query(None, description=_("api.param.tenant_id_filter")),
        ):
            """
            根据供应商 ID 获取其所有 API Key / Get all API Keys by provider ID

            权限 / Permission: ai_api_key:list_by_provider
            """
            service = ProviderApiKeyService(db)
            keys = await service.get_keys_by_provider(
                provider_id=provider_id,
                tenant_id=tenant_id,
            )

            return success(
                data=[ProviderApiKeyResponse(**_build_api_key_response(k)) for k in keys],
                message=_("common.success"),
            )

        register_admin_recycle_bin_routes(
            router=router,
            service_class=ProviderApiKeyService,
            resource_name="ai_api_key",
        )

        @router.get("/{key_id}", summary="获取 AI API Key 详情")
        @action_read("action.ai_api_key.detail")
        async def get_api_key(
            request: Request,
            db: DbSession,
            key_id: int,
            admin: ActiveAdmin,
        ):
            """
            获取 AI API Key 详情 / Get AI API Key details

            权限 / Permission: ai_api_key:detail
            """
            service = ProviderApiKeyService(db)
            key = await service.get_by_id(key_id)

            if not key:
                from app.exceptions import NotFoundException
                raise NotFoundException(message=_("ai.error.api_key_not_found"))

            return success(
                data=ProviderApiKeyResponse(**_build_api_key_response(key)),
                message=_("common.success"),
            )

        @router.post("", summary="创建 AI API Key")
        @action_create("action.ai_api_key.create")
        async def create_api_key(
            request: Request,
            db: DbSession,
            data: ProviderApiKeyCreate,
            admin: ActiveAdmin,
        ):
            """
            创建 AI API Key / Create AI API Key

            权限 / Permission: ai_api_key:create
            """
            service = ProviderApiKeyService(db)
            key = await service.create_key(data)
            await db.commit()
            await db.refresh(key, ['provider'])

            return success(
                data=ProviderApiKeyResponse(**_build_api_key_response(key)),
                message=_("ai.api_key.created"),
            )

        @router.put("/{key_id}", summary="更新 AI API Key")
        @action_update("action.ai_api_key.update")
        async def update_api_key(
            request: Request,
            db: DbSession,
            key_id: int,
            data: ProviderApiKeyUpdate,
            admin: ActiveAdmin,
        ):
            """
            更新 AI API Key 信息 / Update AI API Key info

            权限 / Permission: ai_api_key:update
            """
            service = ProviderApiKeyService(db)
            key = await service.update_key(key_id, data)
            await db.commit()
            await db.refresh(key, ['provider'])

            return success(
                data=ProviderApiKeyResponse(**_build_api_key_response(key)),
                message=_("ai.api_key.updated"),
            )

        @router.delete("/{key_id}", summary="删除 AI API Key")
        @action_delete("action.ai_api_key.delete")
        async def delete_api_key(
            request: Request,
            db: DbSession,
            key_id: int,
            admin: ActiveAdmin,
        ):
            """
            删除 AI API Key（软删除） / Delete AI API Key (soft delete)

            权限 / Permission: ai_api_key:delete
            """
            service = ProviderApiKeyService(db)
            key = await service.get_by_id(key_id)
            if not key:
                from app.exceptions import NotFoundException
                raise NotFoundException(message=_("ai.error.api_key_not_found"))

            await service.delete(key_id)
            await db.commit()

            return success(message=_("ai.api_key.deleted"))

        @router.put("/{key_id}/status", summary="切换 AI API Key 启用状态")
        @action_update("action.ai_api_key.toggle_status")
        async def toggle_api_key_status(
            request: Request,
            db: DbSession,
            key_id: int,
            admin: ActiveAdmin,
        ):
            """
            启用或禁用 AI API Key / Enable or disable AI API Key

            权限 / Permission: ai_api_key:toggle_status
            """
            service = ProviderApiKeyService(db)
            key = await service.toggle_status(key_id)
            await db.commit()

            return success(
                data=ProviderApiKeyResponse(**_build_api_key_response(key)),
                message=_("ai.api_key.status_updated"),
            )


# 导出路由器 / Export router
router = AdminAIApiKeyController.get_router()

__all__ = ["router", "AdminAIApiKeyController"]
