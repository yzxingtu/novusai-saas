"""
企业管理 API / Tenant Management API

提供企业 CRUD 接口（平台管理员专用）
Provides tenant CRUD endpoints (platform admin only).
"""

from fastapi import Body, HTTPException, Query, Request, status

from app.configs.service import ConfigService
from app.core.base_controller import GlobalController
from app.core.deps import ActiveAdmin, DbSession, QueryParams
from app.core.i18n import _
from app.core.logging import ImpersonateLoggerMixin
from app.core.recycle_bin import register_admin_recycle_bin_routes
from app.core.response import build_inline_error_result, success
from app.core.security import (
    IMPERSONATE_TOKEN_EXPIRE_SECONDS,
    TOKEN_SCOPE_TENANT_ADMIN,
    create_impersonate_token,
)
from app.enums import ErrorCode
from app.enums.rbac import PermissionScope
from app.exceptions import BusinessException
from app.rbac.decorators import (
    MenuConfig,
    action_create,
    action_delete,
    action_read,
    action_update,
    permission_action,
    permission_resource,
)
from app.schemas.system import (
    TenantCreateRequest,
    TenantImpersonateRequest,
    TenantImpersonateResponse,
    TenantResetOwnerPasswordRequest,
    TenantResponse,
    TenantStatusRequest,
    TenantUpdateRequest,
)
from app.services.system import TenantService
from app.services.tenant.tenant_role_option_service import TenantAdminReadModelService


# 审计日志辅助类 / Audit log helper class
class _ImpersonateAuditLogger(ImpersonateLoggerMixin):
    """Impersonate 审计日志器 / Impersonate audit logger"""

    pass


_audit_helper = _ImpersonateAuditLogger()


class _TenantStorageAdminFacade:
    """Storage-config workflow facade for admin tenant endpoints."""

    _CONFIG_KEY_MAP = {
        "tenant_storage_mode": "tenant_storage_mode",
        "tenant_storage_driver": "tenant_storage_driver",
        "tenant_storage_root_path": "tenant_storage_root_path",
        "tenant_storage_base_url": "tenant_storage_base_url",
        "tenant_storage_options": "tenant_storage_options",
        "tenant_storage_self_config_enabled": "tenant_storage_self_config_enabled",
    }

    def __init__(self, db: DbSession) -> None:
        self._db = db
        self._config_service = ConfigService(db)

    async def get_tenant_storage_config(self, tenant_id: int) -> dict:
        from app.services.common.storage_config_resolver import StorageConfigResolver

        resolver = StorageConfigResolver(self._db)
        mode = await resolver.get_storage_mode(tenant_id)
        tenant_driver = await self._config_service.get_tenant_config(
            tenant_id, "tenant_storage_driver", default=None
        )
        tenant_root_path = await self._config_service.get_tenant_config(
            tenant_id, "tenant_storage_root_path", default=""
        )
        tenant_base_url = await self._config_service.get_tenant_config(
            tenant_id, "tenant_storage_base_url", default=""
        )
        tenant_options = await self._config_service.get_tenant_config(
            tenant_id, "tenant_storage_options", default={}
        )
        tenant_mode = await self._config_service.get_tenant_config(
            tenant_id, "tenant_storage_mode", default="platform"
        )
        tenant_self_enabled = await self._config_service.get_tenant_config(
            tenant_id, "tenant_storage_self_config_enabled", default=False
        )
        return {
            "tenant_id": tenant_id,
            "effective_mode": mode,
            "tenant_storage_mode": str(tenant_mode),
            "tenant_storage_driver": str(tenant_driver) if tenant_driver else None,
            "tenant_storage_root_path": str(tenant_root_path),
            "tenant_storage_base_url": str(tenant_base_url),
            "tenant_storage_options": tenant_options or {},
            "tenant_storage_self_config_enabled": bool(tenant_self_enabled),
        }

    async def update_tenant_storage_config(self, tenant_id: int, data: dict) -> None:
        mode = data.get("tenant_storage_mode")
        if mode == "admin_override":
            driver = data.get("tenant_storage_driver")
            root_path = data.get("tenant_storage_root_path", "")
            if not driver or not root_path or not str(root_path).strip():
                raise BusinessException(
                    message=_("error.common.invalid_parameter"),
                    code=ErrorCode.INVALID_PARAMETER,
                )
            if driver == "local":
                raise BusinessException(
                    message=_("config.storage.local_not_allowed_for_tenant"),
                    code=ErrorCode.INVALID_PARAMETER,
                )

        for field, config_key in self._CONFIG_KEY_MAP.items():
            if field in data:
                await self._config_service.set_tenant_config(
                    tenant_id=tenant_id,
                    key=config_key,
                    value=data[field],
                )

    async def test_tenant_storage_connection(
        self,
        driver: str,
        root_path: str,
        base_url: str,
        config: dict,
    ) -> dict:
        import io
        import uuid

        from app.storage import storage_manager
        from app.storage.base import StorageConfig

        if driver == "local":
            return build_inline_error_result(
                _("config.storage.local_not_allowed_for_tenant"),
            )

        try:
            sc = StorageConfig(
                driver=driver,
                root_path=root_path or config.get("bucket", "test"),
                base_url=base_url or None,
                options=config,
            )
            drv = storage_manager.get_driver(sc)
            test_key = f".novusai-test/{uuid.uuid4().hex[:8]}.txt"
            test_content = io.BytesIO(b"NovusAI tenant storage test")
            await drv.put(test_key, test_content, mime_type="text/plain")
            exists = await drv.exists(test_key)
            if not exists:
                return build_inline_error_result(_("config.storage.test_file_not_found"))
            await drv.delete(test_key)
            return {"success": True}
        except Exception as exc:
            return build_inline_error_result(
                exc,
                fallback_message=_("common.server_error"),
            )


@permission_resource(
    resource="tenant",
    name="menu.admin.tenant",  # i18n key / 菜单 i18n 键名
    scope=PermissionScope.ADMIN,
    parent_resource="platform_mgmt",
    menu=MenuConfig(
        icon="lucide:store",
        path="/tenant/list",
        component="tenant/List",
        parent="tenant_mgmt",  # 父菜单: 企业管理 / Parent menu: tenant management
        sort_order=10,
    ),
)
class AdminTenantController(GlobalController):
    """
    企业管理控制器 / Tenant Management Controller

    提供企业 CRUD、状态切换等接口
    Provides tenant CRUD, status toggle and other endpoints
    """

    prefix = "/tenants"
    tags = ["Tenant Management"]
    service_class = TenantService

    def _register_routes(self) -> None:
        """注册路由 / Register routes"""
        router = self.router

        # 回收站路由必须在 /{id} 之前注册，避免路径冲突 / Recycle bin routes must be registered before /{id} to avoid path conflicts
        register_admin_recycle_bin_routes(
            router=router,
            service_class=TenantService,
            resource_name="tenant",
        )

        @router.get("/select", summary="获取企业下拉选项")
        @action_read("action.tenant.select")
        async def select_tenants(
            request: Request,
            db: DbSession,
            current_admin: ActiveAdmin,
            search: str = Query("", description=_("api.param.search")),
            is_active: str = Query("", description=_("api.param.is_active")),
            page: int = Query(0, ge=0, description=_("api.param.page")),
            page_size: int = Query(
                20, ge=1, le=100, description=_("api.param.page_size")
            ),
        ):
            """
            获取企业下拉选项 / Get tenant dropdown options

            用于筛选器或表单中的企业选择组件
            Used for tenant selection component in filters or forms

            分页模式： / Pagination modes:
            - page=0: 不分页，返回全部数据（受 limit 限制） / No pagination, returns all data (subject to limit)
            - page>=1: 分页模式，返回分页信息（total, has_more） / Paginated mode, returns pagination info

            权限 / Permission: tenant:select
            """
            # 解析 is_active 参数 / Parse is_active parameter
            active_filter = True  # 默认仅启用 / Default active only
            if is_active.lower() == "false":
                active_filter = False
            elif is_active.lower() == "true":
                active_filter = True

            service = TenantService(db)
            response = await service.get_select_options(
                search=search,
                limit=50,
                is_active=active_filter,
                page=page,
                page_size=page_size,
            )
            return success(
                data=response,
                message=_("common.success"),
            )

        @router.get("", summary="获取企业列表")
        @action_read("action.tenant.list")
        async def list_tenants(
            request: Request,
            db: DbSession,
            spec: QueryParams,
            current_admin: ActiveAdmin,
        ):
            """
            获取所有企业列表 / Get all tenant list

            - 支持通用筛选 / Supports filtering: filter[field][op]=value
            - 支持排序 / Supports sorting: sort=-created_at,name
            - 支持分页 / Supports pagination: page[number]=1&page[size]=20

            权限 / Permission: tenant:list
            """
            service = TenantService(db)
            items, total = await service.query_list(spec, scope="admin")
            read_model_service = TenantAdminReadModelService(db)
            page_data = await read_model_service.build_tenant_list_page(
                items=items,
                total=total,
                page=spec.page,
                page_size=spec.size,
            )

            return success(
                data=page_data,
                message=_("common.success"),
            )

        @router.get("/{tenant_id}", summary="获取企业详情")
        @action_read("action.tenant.detail")
        async def get_tenant(
            request: Request,
            db: DbSession,
            tenant_id: int,
            current_admin: ActiveAdmin,
        ):
            """
            获取企业详情 / Get tenant details

            权限 / Permission: tenant:detail
            """
            service = TenantService(db)
            tenant = await service.get_by_id(tenant_id)

            if tenant is None:
                from fastapi import HTTPException, status

                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=_("tenant.not_found"),
                )

            read_model_service = TenantAdminReadModelService(db)
            data = await read_model_service.build_tenant_detail(tenant)

            return success(
                data=data,
                message=_("common.success"),
            )

        @router.post("", summary="创建企业")
        @action_create("action.tenant.create")
        async def create_tenant(
            request: Request,
            db: DbSession,
            data: TenantCreateRequest,
            current_admin: ActiveAdmin,
        ):
            """
            创建企业 / Create tenant

            - 企业编码由系统自动生成 / Tenant code is auto-generated by system

            权限 / Permission: tenant:create
            """
            service = TenantService(db)
            tenant = await service.create_tenant(
                name=data.name,
                admin_username=data.admin_username,
                admin_email=data.admin_email,
                admin_password=data.admin_password,
                contact_name=data.contact_name,
                contact_phone=data.contact_phone,
                contact_email=data.contact_email,
                plan_id=data.plan_id,
                quota=data.quota,
                expires_at=data.expires_at,
                remark=data.remark,
            )
            await db.commit()

            return success(
                data=TenantResponse.model_validate(tenant, from_attributes=True),
                message=_("tenant.created"),
            )

        @router.put("/{tenant_id}", summary="更新企业")
        @action_update("action.tenant.update")
        async def update_tenant(
            request: Request,
            db: DbSession,
            tenant_id: int,
            data: TenantUpdateRequest,
            current_admin: ActiveAdmin,
        ):
            """
            更新企业信息 / Update tenant info

            权限 / Permission: tenant:update
            """
            service = TenantService(db)

            # 移除 None 值 / Remove None values
            update_data = {k: v for k, v in data.model_dump().items() if v is not None}

            tenant = await service.update_tenant(tenant_id, update_data)
            await db.commit()

            return success(
                data=TenantResponse.model_validate(tenant, from_attributes=True),
                message=_("tenant.updated"),
            )

        @router.delete("/{tenant_id}", summary="删除企业")
        @action_delete("action.tenant.delete")
        async def delete_tenant(
            request: Request,
            db: DbSession,
            tenant_id: int,
            current_admin: ActiveAdmin,
        ):
            """
            删除企业（软删除） / Delete tenant (soft delete)

            **注意**: 删除企业会导致该企业下所有数据不可访问
            **Note**: Deleting a tenant makes all data under it inaccessible

            权限 / Permission: tenant:delete
            """
            service = TenantService(db)

            # 检查企业是否存在 / Check if tenant exists
            tenant = await service.get_by_id(tenant_id)
            if tenant is None:
                from fastapi import HTTPException, status

                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=_("tenant.not_found"),
                )

            await service.delete(tenant_id)
            await db.commit()

            return success(message=_("tenant.deleted"))

        @router.put("/{tenant_id}/status", summary="切换企业状态")
        @action_update("action.tenant.toggle_status")
        async def toggle_tenant_status(
            request: Request,
            db: DbSession,
            tenant_id: int,
            data: TenantStatusRequest,
            current_admin: ActiveAdmin,
        ):
            """
            启用或禁用企业 / Enable or disable tenant

            - 禁用后企业下所有用户无法登录 / All users under the tenant cannot log in after disabling

            权限 / Permission: tenant:update
            """
            service = TenantService(db)
            tenant = await service.toggle_status(tenant_id, data.is_active)
            await db.commit()

            return success(
                data=TenantResponse.model_validate(tenant, from_attributes=True),
                message=_("tenant.status_updated"),
            )

        @router.post("/{tenant_id}/impersonate", summary="一键登录企业后台")
        @permission_action("impersonate", "action.tenant.impersonate")
        async def impersonate_tenant(
            request: Request,
            db: DbSession,
            tenant_id: int,
            current_admin: ActiveAdmin,
            data: TenantImpersonateRequest | None = None,
        ):
            """
            生成一键登录企业后台的 Token / Generate one-click login token for tenant backend

            - Token 60 秒过期，一次性使用 / Token expires in 60 seconds, single-use
            - 可选指定目标角色 role_id / Optionally specify target role_id

            权限 / Permission: tenant:impersonate
            """
            # 获取企业信息 / Get tenant info
            service = TenantService(db)
            tenant = await service.get_by_id(tenant_id)

            if tenant is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=_("tenant.not_found"),
                )

            if not tenant.is_active:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=_("tenant.disabled"),
                )

            # 验证目标角色（如果指定） / Validate target role (if specified)
            role_id = data.role_id if data else None
            if role_id:
                await service.validate_impersonation_role(tenant_id, role_id)

            # 生成 impersonate token / Generate impersonate token
            token = create_impersonate_token(
                admin_id=current_admin.id,
                target_scope=TOKEN_SCOPE_TENANT_ADMIN,
                target_tenant_id=tenant_id,
                target_role_id=role_id,
            )

            # 记录审计日志 / Record audit log
            _audit_helper.logger.info(
                "Admin impersonate initiated | admin_id={} | admin_username={} | "
                "target_tenant_id=%s | target_tenant_code=%s | target_role_id=%s",
                current_admin.id,
                current_admin.username,
                tenant_id,
                tenant.code,
                role_id,
            )

            return success(
                data=TenantImpersonateResponse(
                    impersonate_token=token,
                    tenant_code=tenant.code,
                    tenant_name=tenant.name,
                    expires_in=IMPERSONATE_TOKEN_EXPIRE_SECONDS,
                ),
                message=_("common.success"),
            )

        @router.get("/{tenant_id}/storage-config", summary="获取企业存储配置")
        @action_read("action.tenant.detail")
        async def get_tenant_storage_config(
            request: Request,
            db: DbSession,
            tenant_id: int,
            current_admin: ActiveAdmin,
        ):
            """
            获取企业存储配置（Mode 2: 管理端逐企业指定）
            Get tenant storage config (Mode 2: admin per-tenant override)

            权限 / Permission: tenant:detail
            """
            storage_facade = _TenantStorageAdminFacade(db)
            return success(data=await storage_facade.get_tenant_storage_config(tenant_id))

        @router.put("/{tenant_id}/storage-config", summary="设置企业存储配置")
        @action_update("action.tenant.update")
        async def update_tenant_storage_config(
            request: Request,
            db: DbSession,
            tenant_id: int,
            current_admin: ActiveAdmin,
            data: dict = Body(...),
        ):
            """
            设置企业存储配置（Mode 2: 管理端逐企业指定）
            Set tenant storage config (Mode 2: admin per-tenant override)

            权限 / Permission: tenant:update
            """
            storage_facade = _TenantStorageAdminFacade(db)
            await storage_facade.update_tenant_storage_config(
                tenant_id=tenant_id,
                data=data,
            )
            await db.commit()
            return success(message=_("config.updated"))

        @router.post("/{tenant_id}/storage-config/test", summary="测试企业存储连接")
        @action_update("action.tenant.update")
        async def test_tenant_storage_connection(
            request: Request,
            db: DbSession,
            tenant_id: int,
            current_admin: ActiveAdmin,
            driver: str = Body(..., embed=True),
            root_path: str = Body("", embed=True),
            base_url: str = Body("", embed=True),
            config: dict = Body({}, embed=True),
        ):
            """
            测试企业存储连接 / Test tenant storage connection

            权限 / Permission: tenant:update
            """
            storage_facade = _TenantStorageAdminFacade(db)
            result = await storage_facade.test_tenant_storage_connection(
                driver=driver,
                root_path=root_path,
                base_url=base_url,
                config=config,
            )
            return success(data=result)

        @router.put(
            "/{tenant_id}/reset-owner-password", summary="重置企业超级管理员密码"
        )
        @permission_action("reset_owner_password", "action.tenant.reset_owner_password")
        async def reset_owner_password(
            request: Request,
            db: DbSession,
            tenant_id: int,
            data: TenantResetOwnerPasswordRequest,
            current_admin: ActiveAdmin,
        ):
            """
            重置企业超级管理员（owner）密码 / Reset tenant owner password

            - 用于企业管理员忘记密码或安全事件处理 / For forgotten password or security incident handling

            权限 / Permission: tenant:reset_owner_password
            """
            service = TenantService(db)
            await service.reset_owner_password(tenant_id, data.new_password)
            await db.commit()

            return success(message=_("tenant.owner_password_reset"))


# 导出路由器 / Export router
router = AdminTenantController.get_router()

__all__ = ["router", "AdminTenantController"]
