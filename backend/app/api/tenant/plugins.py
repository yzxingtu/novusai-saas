"""
租户端插件管理 API

提供租户可用插件列表、启用/禁用、配置更新等接口
"""

from fastapi import Path, Request

from app.core.base_controller import TenantController
from app.core.deps import DbSession, ActiveTenantAdmin, QueryParams
from app.core.response import success, created, paginated
from app.enums.rbac import PermissionScope
from app.rbac.decorators import (
    permission_resource,
    MenuConfig,
    action_read,
    action_create,
    action_update,
    action_delete,
)
from app.schemas.system.plugin import (
    PluginResponse,
    TenantPluginResponse,
    TenantPluginEnableRequest,
    TenantPluginConfigRequest,
)
from app.services.system.tenant_plugin_service import TenantPluginService


async def _mask_tenant_plugin_response(db, tp) -> dict:
    """序列化 TenantPlugin 并对敏感配置字段脱敏"""
    resp = TenantPluginResponse.model_validate(tp, from_attributes=True).model_dump()
    if resp.get("config"):
        from app.repositories.system.plugin_repository import PluginRepository
        from app.plugins.security import mask_sensitive_config
        plugin = await PluginRepository(db).get_by_id(resp["plugin_id"])
        if plugin and plugin.config_schema:
            resp["config"] = mask_sensitive_config(resp["config"], plugin.config_schema)
    return resp


@permission_resource(
    resource="tenant_plugin",
    name="menu.tenant.plugin",
    scope=PermissionScope.TENANT,
    menu=MenuConfig(
        icon="lucide:plug",
        path="/system/plugins",
        component="tenant/system/plugins/index",
        parent="system",
        sort_order=50,
    ),
)
class TenantPluginController(TenantController):
    """
    租户插件管理控制器
    """

    prefix = "/plugins"
    tags = ["Tenant Plugin Management"]

    def _register_routes(self) -> None:
        router = self.router

        @router.get("", summary="获取可用插件列表")
        @action_read("action.tenant_plugin.list")
        async def list_available_plugins(
            request: Request,
            db: DbSession,
            tenant_admin: ActiveTenantAdmin,
            query: QueryParams,
        ):
            """
            获取平台已启用的插件列表（租户可选用的插件）
            """
            from app.enums.plugin import PluginStatusEnum
            from app.schemas.common.query import FilterRule
            from app.services.system.plugin_service import PluginService

            service = PluginService(db)
            items, total = await service.query_list(
                query,
                forced_filters=[
                    FilterRule(field="status", value=PluginStatusEnum.ENABLED.value),
                ],
            )
            from app.plugins.security import mask_sensitive_config

            masked_items = []
            for item in items:
                resp = PluginResponse.model_validate(
                    item, from_attributes=True
                ).model_dump()
                if resp.get("default_config") and item.config_schema:
                    resp["default_config"] = mask_sensitive_config(
                        resp["default_config"], item.config_schema
                    )
                masked_items.append(resp)

            return paginated(
                items=masked_items,
                total=total,
                page=query.page,
                page_size=query.size,
            )

        @router.get("/frontend-config", summary="获取已启用插件的前端配置")
        @action_read("action.tenant_plugin.list")
        async def get_plugin_frontend_config(
            request: Request,
            db: DbSession,
            tenant_admin: ActiveTenantAdmin,
        ):
            """返回当前租户可用的已启用插件前端配置（路由+菜单+i18n）"""
            from app.enums.plugin import PluginStatusEnum, PluginScopeEnum
            from app.services.system.plugin_service import PluginService
            from app.schemas.common.query import QuerySpec

            service = PluginService(db)
            items, _ = await service.query_list(QuerySpec(page=1, size=100))

            tenant_id = tenant_admin.tenant_id
            configs = []
            for plugin in items:
                if plugin.status != PluginStatusEnum.ENABLED.value:
                    continue
                manifest = plugin.manifest or {}
                frontend = manifest.get("frontend")
                if not frontend:
                    continue

                # 检查插件 scope 对当前租户是否可见
                scope = plugin.scope
                if scope == PluginScopeEnum.PLATFORM_ONLY.value:
                    continue
                if scope == PluginScopeEnum.ASSIGNED_TENANTS.value:
                    from app.repositories.system.plugin_tenant_assignment_repository import (
                        PluginTenantAssignmentRepository,
                    )
                    assign_repo = PluginTenantAssignmentRepository(db)
                    assignments = await assign_repo.get_by_plugin(plugin.id)
                    assigned_ids = {a.tenant_id for a in assignments}
                    if tenant_id not in assigned_ids:
                        continue

                locales = frontend.get("locales", {})
                if not locales:
                    from app.api.admin.plugins import _load_plugin_locales
                    locales = _load_plugin_locales(plugin.name)

                configs.append({
                    "plugin_name": plugin.name,
                    "plugin_version": plugin.version,
                    "scope": plugin.scope,
                    "endpoint": frontend.get("endpoint", "tenant"),
                    "menus": frontend.get("menus", []),
                    "routes": frontend.get("routes", []),
                    "locales": locales,
                })
            return success(data=configs)

        @router.get("/enabled", summary="获取租户已启用插件")
        @action_read("action.tenant_plugin.list_enabled")
        async def list_enabled_plugins(
            request: Request,
            db: DbSession,
            tenant_admin: ActiveTenantAdmin,
        ):
            """
            获取当前租户已启用的插件列表
            """
            service = TenantPluginService(db)
            items = await service.get_tenant_active_plugins(
                tenant_admin.tenant_id
            )
            return success(
                data=[
                    await _mask_tenant_plugin_response(db, item)
                    for item in items
                ]
            )

        @router.post("/enable", summary="启用插件")
        @action_create("action.tenant_plugin.enable")
        async def enable_plugin(
            request: Request,
            db: DbSession,
            tenant_admin: ActiveTenantAdmin,
            body: TenantPluginEnableRequest,
        ):
            """
            为当前租户启用一个插件
            """
            from app.plugins.manager import get_plugin_manager

            manager = get_plugin_manager()
            result = await manager.enable_tenant(
                db,
                tenant_id=tenant_admin.tenant_id,
                plugin_id=body.plugin_id,
                config=body.config,
            )
            return created(
                data=await _mask_tenant_plugin_response(db, result)
            )

        @router.post("/{plugin_id}/disable", summary="禁用插件")
        @action_delete("action.tenant_plugin.disable")
        async def disable_plugin(
            request: Request,
            db: DbSession,
            tenant_admin: ActiveTenantAdmin,
            plugin_id: int = Path(..., description="插件 ID"),
        ):
            """
            为当前租户禁用一个插件
            """
            from app.plugins.manager import get_plugin_manager

            manager = get_plugin_manager()
            result = await manager.disable_tenant(
                db,
                tenant_id=tenant_admin.tenant_id,
                plugin_id=plugin_id,
            )
            return success(
                data=await _mask_tenant_plugin_response(db, result)
            )

        @router.put("/{plugin_id}/config", summary="更新插件配置")
        @action_update("action.tenant_plugin.configure")
        async def update_plugin_config(
            request: Request,
            db: DbSession,
            tenant_admin: ActiveTenantAdmin,
            body: TenantPluginConfigRequest,
            plugin_id: int = Path(..., description="插件 ID"),
        ):
            """
            更新当前租户的插件配置（带 JSON Schema 校验）
            """
            from app.plugins.manager import get_plugin_manager

            manager = get_plugin_manager()
            result = await manager.configure_tenant(
                db,
                tenant_id=tenant_admin.tenant_id,
                plugin_id=plugin_id,
                config=body.config,
            )
            return success(
                data=await _mask_tenant_plugin_response(db, result)
            )


router = TenantPluginController.get_router()
