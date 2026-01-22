"""
租户域名管理 API

提供租户域名 CRUD 接口（平台管理员专用）
"""

from fastapi import HTTPException, Request, status

from app.core.base_controller import GlobalController
from app.core.base_schema import PageResponse
from app.core.deps import DbSession, QueryParams, ActiveAdmin
from app.core.i18n import _
from app.core.response import success
from app.enums.rbac import PermissionScope
from app.schemas.common.query import FilterRule, FilterOp
from app.rbac.decorators import (
    permission_resource,
    permission_action,
    action_read,
    action_create,
    action_update,
    action_delete,
)
from app.schemas.tenant import (
    TenantDomainResponse,
    TenantDomainVerificationInfo,
    TenantDomainCreateRequest,
    TenantDomainUpdateRequest,
)
from app.services.system import TenantService
from app.services.tenant import TenantDomainService


@permission_resource(
    resource="tenant_domain",
    name="menu.admin.tenant_domain",  # i18n key
    scope=PermissionScope.ADMIN,
    parent_resource="tenant",  # 操作权限挂载到租户管理菜单下
)
class AdminTenantDomainController(GlobalController):
    """
    租户域名管理控制器
    
    提供租户域名 CRUD、验证、主域名设置等接口
    """
    
    prefix = "/tenants/{tenant_id}/domains"
    tags = ["租户域名管理"]
    service_class = TenantDomainService
    
    def _register_routes(self) -> None:
        """注册路由"""
        router = self.router
        
        async def _verify_tenant_exists(
            db: DbSession,
            tenant_id: int,
        ) -> None:
            """验证租户是否存在"""
            tenant_service = TenantService(db)
            tenant = await tenant_service.get_by_id(tenant_id)
            if tenant is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=_("tenant.not_found"),
                )
        
        @router.get("", summary="获取租户域名列表")
        @action_read("action.tenant_domain.list")
        async def list_domains(
            request: Request,
            db: DbSession,
            spec: QueryParams,
            current_admin: ActiveAdmin,
            tenant_id: int,
        ):
            """
            获取租户域名列表
            
            - 支持通用筛选: filter[field][op]=value
            - 支持排序: sort=-created_at,domain
            - 支持分页: page[number]=1&page[size]=20
            
            权限: tenant_domain:list
            """
            await _verify_tenant_exists(db, tenant_id)
            
            # 强制添加租户 ID 筛选
            spec.filters.append(FilterRule(field="tenant_id", op=FilterOp.eq, value=tenant_id))
            
            service = TenantDomainService(db)
            items, total = await service.query_list(spec, scope="admin")
            
            # 为每个域名添加验证信息
            domain_responses = []
            for item in items:
                resp = TenantDomainResponse.model_validate(item, from_attributes=True)
                # 未验证的域名添加验证 DNS 信息
                if not item.is_verified and item.verification_token:
                    verification_record = await service.get_verification_record(item)
                    resp.verification_info = TenantDomainVerificationInfo(
                        dns_type=verification_record["type"],
                        dns_name=verification_record["name"],
                        dns_value=verification_record["value"],
                    )
                domain_responses.append(resp)
            
            return success(
                data=PageResponse.create(
                    items=domain_responses,
                    total=total,
                    page=spec.page,
                    page_size=spec.size,
                ),
                message=_("common.success"),
            )
        
        @router.post("", summary="为租户添加自定义域名")
        @action_create("action.tenant_domain.create")
        async def create_domain(
            request: Request,
            db: DbSession,
            data: TenantDomainCreateRequest,
            current_admin: ActiveAdmin,
            tenant_id: int,
        ):
            """
            为租户添加自定义域名
            
            - 新域名需要 DNS 验证后才能使用
            
            权限: tenant_domain:create
            """
            await _verify_tenant_exists(db, tenant_id)
            
            service = TenantDomainService(db)
            domain = await service.add_custom_domain(
                tenant_id=tenant_id,
                domain=data.domain,
                remark=data.remark,
            )
            
            # 如果请求设为主域名，且域名已验证
            if data.is_primary and domain.is_verified:
                domain = await service.set_primary_domain(tenant_id, domain.id)
            
            await db.commit()
            
            # 添加验证 DNS 信息
            resp = TenantDomainResponse.model_validate(domain, from_attributes=True)
            if not domain.is_verified and domain.verification_token:
                verification_record = await service.get_verification_record(domain)
                resp.verification_info = TenantDomainVerificationInfo(
                    dns_type=verification_record["type"],
                    dns_name=verification_record["name"],
                    dns_value=verification_record["value"],
                )
            
            return success(
                data=resp,
                message=_("tenant_domain.created"),
            )
        
        @router.get("/{domain_id}", summary="获取域名详情")
        @action_read("action.tenant_domain.detail")
        async def get_domain(
            request: Request,
            db: DbSession,
            tenant_id: int,
            domain_id: int,
            current_admin: ActiveAdmin,
        ):
            """
            获取域名详情
            
            权限: tenant_domain:detail
            """
            await _verify_tenant_exists(db, tenant_id)
            
            service = TenantDomainService(db)
            domain = await service.get_by_id(domain_id)
            
            if domain is None or domain.tenant_id != tenant_id:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=_("tenant_domain.not_found"),
                )
            
            # 添加验证 DNS 信息
            resp = TenantDomainResponse.model_validate(domain, from_attributes=True)
            if not domain.is_verified and domain.verification_token:
                verification_record = await service.get_verification_record(domain)
                resp.verification_info = TenantDomainVerificationInfo(
                    dns_type=verification_record["type"],
                    dns_name=verification_record["name"],
                    dns_value=verification_record["value"],
                )
            
            return success(
                data=resp,
                message=_("common.success"),
            )
        
        @router.put("/{domain_id}", summary="更新域名信息")
        @action_update("action.tenant_domain.update")
        async def update_domain(
            request: Request,
            db: DbSession,
            tenant_id: int,
            domain_id: int,
            data: TenantDomainUpdateRequest,
            current_admin: ActiveAdmin,
        ):
            """
            更新域名信息
            
            - 仅可更新备注
            - 设置主域名请使用专用接口
            
            权限: tenant_domain:update
            """
            await _verify_tenant_exists(db, tenant_id)
            
            service = TenantDomainService(db)
            
            # 验证域名存在且属于该租户
            existing = await service.get_by_id(domain_id)
            if existing is None or existing.tenant_id != tenant_id:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=_("tenant_domain.not_found"),
                )
            
            # 更新备注
            domain = await service.update_domain(
                domain_id=domain_id,
                remark=data.remark,
            )
            
            # 如果请求设为主域名
            if data.is_primary is True:
                domain = await service.set_primary_domain(tenant_id, domain_id)
            
            await db.commit()
            
            return success(
                data=TenantDomainResponse.model_validate(domain, from_attributes=True),
                message=_("tenant_domain.updated"),
            )
        
        @router.delete("/{domain_id}", summary="删除域名")
        @action_delete("action.tenant_domain.delete")
        async def delete_domain(
            request: Request,
            db: DbSession,
            tenant_id: int,
            domain_id: int,
            current_admin: ActiveAdmin,
        ):
            """
            删除域名
            
            **注意**:
            - 不能删除主域名
            - 不能删除默认域名
            
            权限: tenant_domain:delete
            """
            await _verify_tenant_exists(db, tenant_id)
            
            service = TenantDomainService(db)
            
            # 验证域名存在且属于该租户
            existing = await service.get_by_id(domain_id)
            if existing is None or existing.tenant_id != tenant_id:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=_("tenant_domain.not_found"),
                )
            
            await service.remove_domain(domain_id)
            await db.commit()
            
            return success(message=_("tenant_domain.deleted"))
        
        @router.post("/{domain_id}/verify", summary="验证域名")
        @permission_action("verify", "action.tenant_domain.verify")
        async def verify_domain(
            request: Request,
            db: DbSession,
            tenant_id: int,
            domain_id: int,
            current_admin: ActiveAdmin,
        ):
            """
            验证域名
            
            - 检查 DNS TXT 记录是否正确配置
            - 验证成功后域名可设为主域名
            
            权限: tenant_domain:verify
            """
            await _verify_tenant_exists(db, tenant_id)
            
            service = TenantDomainService(db)
            
            # 验证域名存在且属于该租户
            existing = await service.get_by_id(domain_id)
            if existing is None or existing.tenant_id != tenant_id:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=_("tenant_domain.not_found"),
                )
            
            # 执行 DNS TXT 记录验证
            domain = await service.verify_domain(domain_id)
            await db.commit()
            
            return success(
                data=TenantDomainResponse.model_validate(domain, from_attributes=True),
                message=_("tenant_domain.verified"),
            )
        
        @router.put("/{domain_id}/primary", summary="设置为主域名")
        @permission_action("set_primary", "action.tenant_domain.set_primary")
        async def set_primary_domain(
            request: Request,
            db: DbSession,
            tenant_id: int,
            domain_id: int,
            current_admin: ActiveAdmin,
        ):
            """
            设置为主域名
            
            - 每个租户只能有一个主域名
            - 域名必须已验证
            
            权限: tenant_domain:set_primary
            """
            await _verify_tenant_exists(db, tenant_id)
            
            service = TenantDomainService(db)
            domain = await service.set_primary_domain(tenant_id, domain_id)
            await db.commit()
            
            return success(
                data=TenantDomainResponse.model_validate(domain, from_attributes=True),
                message=_("tenant_domain.primary_set"),
            )


# 导出路由器
router = AdminTenantDomainController.get_router()

__all__ = ["router", "AdminTenantDomainController"]
