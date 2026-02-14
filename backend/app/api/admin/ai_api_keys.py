"""
平台端 AI API Key 管理 API

提供 AI API Key 的 CRUD 接口（平台管理员专用）
"""

from fastapi import Query, Request

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
from app.schemas.ai.api_key import (
    ProviderApiKeyCreate,
    ProviderApiKeyUpdate,
    ProviderApiKeyResponse,
)
from app.services.ai import ProviderApiKeyService


def _make_key_preview(key) -> str | None:
    """
    生成 API Key 明文掩码预览（如 sk-ab****wxyz）
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


def _build_api_key_response(key) -> dict:
    """
    构建 API Key 响应数据
    
    手动处理 is_available 方法和其他字段
    """
    # 安全地访问关系，避免 AttributeError
    provider_name = None
    tenant_name = None
    
    # 只有在 tenant_id 不为 None 时才尝试访问 tenant 关系
    if key.tenant_id is not None:
        try:
            tenant = getattr(key, 'tenant', None)
            if tenant is not None:
                tenant_name = tenant.name
        except (AttributeError, Exception):
            pass
    
    # 尝试访问 provider 关系
    try:
        provider = getattr(key, 'provider', None)
        if provider is not None:
            provider_name = provider.name
    except (AttributeError, Exception):
        pass
    
    return {
        "id": key.id,
        "provider_id": key.provider_id,
        "tenant_id": key.tenant_id,
        "name": key.name,
        "is_active": key.is_active,
        "usage_limit": key.usage_limit,
        "usage_count": key.usage_count,
        "last_used_at": key.last_used_at,
        "expires_at": key.expires_at,
        "created_at": key.created_at,
        "updated_at": key.updated_at,
        "is_deleted": key.is_deleted,
        "is_available": key.is_available(),  # 调用方法
        "key_preview": _make_key_preview(key),
        "provider_name": provider_name,
        "tenant_name": tenant_name,
    }


@permission_resource(
    resource="ai_api_key",
    name="menu.admin.ai_api_key",
    scope=PermissionScope.ADMIN,
    menu=MenuConfig(
        icon="lucide:key",
        path="/ai/api-keys",
        component="ai/api-keys/index",
        parent="ai_infra",
        sort_order=30,
    ),
)
class AdminAIApiKeyController(GlobalController):
    """
    AI API Key 管理控制器

    提供 AI API Key CRUD、状态切换等接口
    """

    prefix = "/ai/api-keys"
    tags = [_("menu.tags.admin_ai_api_key")]
    service_class = ProviderApiKeyService

    def _register_routes(self) -> None:
        """注册路由"""
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
            获取 AI API Key 列表

            - 支持通用筛选: filter[field][op]=value
            - 支持排序: sort=-created_at,name
            - 支持分页: page[number]=1&page[size]=20

            权限: ai_api_key:list
            """
            service = ProviderApiKeyService(db)
            items, total = await service.query_list(spec)

            return success(
                data=PageResponse.create(
                    items=[ProviderApiKeyResponse(**_build_api_key_response(item)) for item in items],
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
            tenant_id: int | None = Query(None, description="租户 ID"),
        ):
            """
            根据供应商 ID 获取其所有 API Key

            权限: ai_api_key:list_by_provider
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

        @router.get("/{key_id}", summary="获取 AI API Key 详情")
        @action_read("action.ai_api_key.detail")
        async def get_api_key(
            request: Request,
            db: DbSession,
            key_id: int,
            admin: ActiveAdmin,
        ):
            """
            获取 AI API Key 详情

            权限: ai_api_key:detail
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
            创建 AI API Key

            权限: ai_api_key:create
            """
            service = ProviderApiKeyService(db)
            key = await service.create_key(data)
            await db.commit()

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
            更新 AI API Key 信息

            权限: ai_api_key:update
            """
            service = ProviderApiKeyService(db)
            key = await service.update_key(key_id, data)
            await db.commit()

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
            删除 AI API Key（软删除）

            权限: ai_api_key:delete
            """
            service = ProviderApiKeyService(db)
            await service.delete_key(key_id)
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
            启用或禁用 AI API Key

            权限: ai_api_key:toggle_status
            """
            service = ProviderApiKeyService(db)
            key = await service.toggle_status(key_id)
            await db.commit()

            return success(
                data=ProviderApiKeyResponse(**_build_api_key_response(key)),
                message=_("ai.api_key.status_updated"),
            )


# 导出路由器
router = AdminAIApiKeyController.get_router()

__all__ = ["router", "AdminAIApiKeyController"]
