"""
租户端 AI 配置 API

提供租户端 AI 模型查询、API Key 管理等接口
"""

from fastapi import Query, Request

from app.core.base_controller import TenantController
from app.core.deps import DbSession, ActiveTenantAdmin
from app.core.i18n import _
from app.core.response import success
from app.enums.rbac import PermissionScope
from app.exceptions import NotFoundException
from app.rbac.decorators import (
    permission_resource,
    MenuConfig,
    action_read,
    action_create,
    action_delete,
)
from app.schemas.ai.api_key import (
    ProviderApiKeyCreate,
    ProviderApiKeyResponse,
)
from app.schemas.ai.model import AIModelResponse
from app.services.ai import AIModelService, AIProviderService, ProviderApiKeyService


@permission_resource(
    resource="ai_config",
    name="menu.tenant.ai_config",
    scope=PermissionScope.TENANT,
    menu=MenuConfig(
        icon="lucide:settings-2",
        path="/ai/config",
        component="ai/config/index",
        parent="ai_settings",
        sort_order=10,
    ),
)
class TenantAIConfigController(TenantController):
    """
    租户 AI 配置控制器

    提供租户可用模型查询、API Key 管理等接口
    """

    prefix = "/ai/config"
    tags = [_("menu.tags.tenant_ai_config")]

    def _register_routes(self) -> None:
        """注册路由"""
        router = self.router

        @router.get("/models", summary="获取可用 AI 模型列表")
        @action_read("action.ai_config.models")
        async def get_available_models(
            request: Request,
            db: DbSession,
            tenant_admin: ActiveTenantAdmin,
            provider_id: int | None = Query(None, description="供应商 ID"),
        ):
            """
            获取租户可用的 AI 模型列表

            权限: ai_config:models
            """
            service = AIModelService(db)

            if provider_id:
                models = await service.get_by_provider(provider_id)
            else:
                provider_service = AIProviderService(db)
                providers = await provider_service.get_active_providers()
                models = []
                for provider in providers:
                    provider_models = await service.get_by_provider(provider.id)
                    models.extend(provider_models)

            return success(
                data=[AIModelResponse.model_validate(m, from_attributes=True) for m in models],
                message=_("common.success"),
            )

        @router.get("/keys", summary="获取我的 API Keys")
        @action_read("action.ai_config.keys")
        async def get_my_api_keys(
            request: Request,
            db: DbSession,
            tenant_admin: ActiveTenantAdmin,
        ):
            """
            获取租户自己的 AI API Keys

            权限: ai_config:keys
            """
            service = ProviderApiKeyService(db)
            keys = await service.get_keys_by_provider(
                provider_id=None,
                tenant_id=tenant_admin.tenant_id,
            )

            return success(
                data=[ProviderApiKeyResponse.model_validate(k, from_attributes=True) for k in keys],
                message=_("common.success"),
            )

        @router.post("/keys", summary="创建 API Key")
        @action_create("action.ai_config.create_key")
        async def create_api_key(
            request: Request,
            db: DbSession,
            data: ProviderApiKeyCreate,
            tenant_admin: ActiveTenantAdmin,
        ):
            """
            为租户创建 AI API Key

            权限: ai_config:create_key
            """
            # 强制设置 tenant_id 为当前认证租户，忽略前端传入值
            data.tenant_id = tenant_admin.tenant_id

            service = ProviderApiKeyService(db)
            key = await service.create_key(data)
            await db.commit()

            return success(
                data=ProviderApiKeyResponse.model_validate(key, from_attributes=True),
                message=_("ai.api_key.created"),
            )

        @router.delete("/keys/{key_id}", summary="删除 API Key")
        @action_delete("action.ai_config.delete_key")
        async def delete_api_key(
            request: Request,
            db: DbSession,
            key_id: int,
            tenant_admin: ActiveTenantAdmin,
        ):
            """
            删除租户的 AI API Key

            权限: ai_config:delete_key
            """
            service = ProviderApiKeyService(db)
            key = await service.get_by_id(key_id)

            if not key or key.tenant_id != tenant_admin.tenant_id:
                raise NotFoundException(message=_("ai.error.api_key_not_found"))

            await service.delete_key(key_id)
            await db.commit()

            return success(message=_("ai.api_key.deleted"))


# 导出路由器
router = TenantAIConfigController.get_router()

__all__ = ["router", "TenantAIConfigController"]
