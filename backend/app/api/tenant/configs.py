"""
企业配置管理 API / Tenant Configuration Management API

提供企业级配置管理接口（企业管理员专用）
Provides tenant-level configuration management endpoints (tenant admin only)
"""

from __future__ import annotations

from fastapi import Body, Request

from app.configs.registry import config_registry
from app.core.base_controller import TenantController
from app.core.deps import ActiveTenantAdmin, DbSession
from app.core.i18n import _
from app.core.response import success
from app.enums.config import ConfigScope
from app.enums.error_code import ErrorCode
from app.enums.rbac import PermissionScope
from app.exceptions import NotFoundException
from app.rbac.decorators import (
    MenuConfig,
    action_read,
    action_update,
    permission_resource,
)
from app.schemas.system.config import (
    ConfigGroupListResponse,
    ConfigUpdateRequest,
)
from app.services.tenant.tenant_config_workflow_service import (
    TenantConfigWorkflowService,
)


@permission_resource(
    resource="tenant_config",
    name="menu.tenant.tenant_config",  # i18n key / 国际化键名
    scope=PermissionScope.TENANT,
    parent_resource="system_mgmt",
    menu=MenuConfig(
        icon="lucide:sliders-horizontal",
        path="/system-mgmt/configs",
        component="system/configs/List",
        parent="system_mgmt",  # 父菜单: 系统管理 / Parent menu: system management
        sort_order=10,
    ),
)
class TenantConfigController(TenantController):
    """
    企业配置管理控制器 / Tenant Configuration Management Controller

    提供企业级配置的查看和修改接口
    Provides tenant-level configuration viewing and editing endpoints
    """

    prefix = "/configs"
    tags = ["Tenant Configuration"]

    def _register_routes(self) -> None:
        """注册路由 / Register routes"""
        router = self.router

        @router.get("/groups", summary="获取配置分组列表")
        @action_read("action.tenant_config.groups")
        async def list_config_groups(
            request: Request,
            db: DbSession,
            current_admin: ActiveTenantAdmin,
        ):
            """
            获取企业配置分组列表 / Get tenant config group list

            返回所有企业级配置分组（不含具体配置项）
            Returns all tenant-level config groups (without config items)

            权限 / Permission: tenant_config:groups
            """
            groups = config_registry.get_groups_by_scope(ConfigScope.ALL_TENANTS)

            result = []
            for group in groups:
                if not group.is_active:
                    continue

                # 计算可见配置项数量 / Calculate visible config item count
                visible_count = sum(1 for c in group.configs if c.is_visible)

                result.append(
                    ConfigGroupListResponse(
                        code=group.code,
                        name=_(group.name_key),
                        description=_(group.description_key)
                        if group.description_key
                        else None,
                        icon=group.icon,
                        sort_order=group.sort_order,
                        config_count=visible_count,
                    )
                )

            return success(
                data=sorted(result, key=lambda x: x.sort_order),
                message=_("common.success"),
            )

        @router.get("/groups/{group_code}", summary="获取分组配置项")
        @action_read("action.tenant_config.detail")
        async def get_group_configs(
            request: Request,
            db: DbSession,
            group_code: str,
            current_admin: ActiveTenantAdmin,
        ):
            """
            获取指定分组的配置项列表（含当前值） / Get config items for specified group (with current values)

            权限 / Permission: tenant_config:detail
            """
            # 验证分组存在 / Verify group exists
            group = config_registry.get_group(group_code)
            if not group or group.scope != ConfigScope.ALL_TENANTS:
                raise NotFoundException(
                    message=_("config.group_not_found"),
                    code=ErrorCode.CONFIG_GROUP_NOT_FOUND,
                )

            # 获取配置值 / Get config values
            workflow_service = TenantConfigWorkflowService(db)

            return success(
                data=await workflow_service.get_group_response(
                    tenant_id=current_admin.tenant_id,
                    group_code=group_code,
                ),
                message=_("common.success"),
            )

        @router.put("/groups/{group_code}", summary="更新分组配置")
        @action_update("action.tenant_config.update")
        async def update_group_configs(
            request: Request,
            db: DbSession,
            group_code: str,
            data: ConfigUpdateRequest,
            current_admin: ActiveTenantAdmin,
        ):
            """
            批量更新分组下的配置项 / Batch update config items under a group

            权限 / Permission: tenant_config:update
            """
            workflow_service = TenantConfigWorkflowService(db)
            return success(
                data=await workflow_service.update_group_configs(
                    configs=data.configs,
                    group_code=group_code,
                    tenant_id=current_admin.tenant_id,
                ),
                message=_("config.updated"),
            )

        @router.get("/storage/status", summary="获取企业存储状态")
        @action_read("action.tenant_config.groups")
        async def get_tenant_storage_status(
            request: Request,
            db: DbSession,
            current_admin: ActiveTenantAdmin,
        ):
            """
            获取企业当前存储状态（有效模式、驱动信息、自配置权限等） / Get tenant storage status (effective mode, driver info, self-config permission)

            权限 / Permission: tenant_config:groups
            """
            workflow_service = TenantConfigWorkflowService(db)
            return success(
                data=await workflow_service.get_storage_status(current_admin.tenant_id)
            )

        @router.put("/storage", summary="保存企业存储配置")
        @action_update("action.tenant_config.update")
        async def save_tenant_storage_config(
            request: Request,
            db: DbSession,
            current_admin: ActiveTenantAdmin,
            data: dict = Body(...),
        ):
            """
            企业保存自主存储配置（Mode 3） / Tenant saves self-managed storage config (Mode 3)

            权限 / Permission: tenant_config:update
            """
            workflow_service = TenantConfigWorkflowService(db)
            await workflow_service.save_storage_config(
                data=data,
                tenant_id=current_admin.tenant_id,
            )
            return success(message=_("config.updated"))

        @router.post("/storage/test-connection", summary="测试企业存储连接")
        @action_update("action.tenant_config.update")
        async def test_tenant_storage_connection(
            request: Request,
            db: DbSession,
            current_admin: ActiveTenantAdmin,
            driver: str = Body(..., embed=True),
            root_path: str = Body("", embed=True),
            base_url: str = Body("", embed=True),
            config: dict = Body({}, embed=True),
        ):
            """
            测试企业自主存储连接（Mode 3） / Test tenant self-managed storage connection (Mode 3)

            权限 / Permission: tenant_config:update
            """
            workflow_service = TenantConfigWorkflowService(db)
            return success(
                data=await workflow_service.test_storage_connection(
                    base_url=base_url,
                    config=config,
                    driver=driver,
                    root_path=root_path,
                    tenant_id=current_admin.tenant_id,
                )
            )

        @router.get("/storage/drivers", summary="获取企业允许的存储驱动列表")
        @action_read("action.tenant_config.groups")
        async def list_tenant_storage_drivers(
            request: Request,
            db: DbSession,
            current_admin: ActiveTenantAdmin,
        ):
            """
            获取企业允许选择的存储驱动列表（受平台白名单限制，标记插件启用状态） / Get allowed storage driver list for tenant (restricted by platform whitelist, marks plugin enabled status)

            权限 / Permission: tenant_config:groups
            """
            workflow_service = TenantConfigWorkflowService(db)
            return success(data=await workflow_service.list_storage_drivers())


# 导出路由 / Export router
router = TenantConfigController.get_router()


__all__ = [
    "router",
    "TenantConfigController",
]
