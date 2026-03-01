"""
租户域名管理 API

提供租户端域名管理 CRUD、验证、主域名设置等接口
"""

from fastapi import HTTPException, Request, status

from app.core.base_controller import TenantController
from app.core.base_schema import PageResponse
from app.core.deps import DbSession, QueryParams, ActiveTenantAdmin
from app.core.i18n import _
from app.core.response import success
from app.enums.rbac import PermissionScope
from app.exceptions import BusinessException, NotFoundException
from app.rbac.decorators import (
    permission_resource,
    MenuConfig,
    action_read,
    action_create,
    action_update,
    action_delete,
    permission_action,
)
from app.schemas.tenant.domain import (
    TenantDomainResponse,
    TenantDomainVerificationInfo,
    TenantDomainCreateRequest,
    TenantDomainUpdateRequest,
)
from app.schemas.tenant.ssl import (
    SslCertificateResponse,
    SslCertificateUploadRequest,
    SslAutoRenewRequest,
)
from app.services.system.tenant_domain_service import TenantDomainTenantService
from app.services.system.ssl_certificate_service import SslCertificateService


@permission_resource(
    resource="tenant_domain",
    name="menu.tenant.domain",  # i18n key
    scope=PermissionScope.ALL_TENANTS,
    menu=MenuConfig(
        icon="lucide:globe",
        path="/system-mgmt/domains",
        component="tenant/system-mgmt/domains/index",
        parent="system_mgmt",  # 父菜单: 系统管理
        sort_order=10,
    ),
)
class TenantDomainController(TenantController):
    """
    租户域名管理控制器

    提供租户域名 CRUD、验证、主域名设置等接口
    """

    prefix = "/domains"
    tags = ["Tenant Domain Management"]
    service_class = TenantDomainTenantService

    def _register_routes(self) -> None:
        """注册路由"""
        router = self.router

        # 域名列表接口
        @router.get("", summary="获取域名列表")
        @action_read("action.tenant_domain.list")
        async def list_domains(
            request: Request,
            db: DbSession,
            spec: QueryParams,
            current_admin: ActiveTenantAdmin,
        ):
            """
            获取租户域名列表

            - 支持通用筛选: filter[field][op]=value
            - 支持排序: sort=-created_at,domain
            - 支持分页: page[number]=1&page[size]=20

            权限: tenant_domain:list
            """
            service = self.get_service(db, current_admin.tenant_id)
            items, total = await service.query_list(spec, scope="tenant")

            # 计算 CNAME 目标（一次查询，复用）
            cname_target = await service.get_cname_target(current_admin.tenant_id)

            # 为每个域名添加验证信息
            domain_responses = []
            for item in items:
                resp = TenantDomainResponse.model_validate(item, from_attributes=True)
                resp.cname_target = cname_target
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

        # 域名详情接口
        @router.get("/{domain_id}", summary="获取域名详情")
        @action_read("action.tenant_domain.detail")
        async def get_domain(
            request: Request,
            db: DbSession,
            domain_id: int,
            current_admin: ActiveTenantAdmin,
        ):
            """
            获取域名详情

            权限: tenant_domain:detail
            """
            service = self.get_service(db, current_admin.tenant_id)
            domain = await service.get_by_id(domain_id)

            if domain is None or domain.tenant_id != current_admin.tenant_id:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=_("tenant_domain.not_found"),
                )

            # 添加验证 DNS 信息 + CNAME 目标
            resp = TenantDomainResponse.model_validate(domain, from_attributes=True)
            resp.cname_target = await service.get_cname_target(current_admin.tenant_id)
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

        # 添加域名接口
        @router.post("", summary="添加域名")
        @action_create("action.tenant_domain.create")
        async def create_domain(
            request: Request,
            db: DbSession,
            data: TenantDomainCreateRequest,
            current_admin: ActiveTenantAdmin,
        ):
            """
            添加自定义域名

            - 新域名需要 DNS 验证后才能使用

            权限: tenant_domain:create
            """
            # 检查自定义域名配额（allow_custom_domain + max_custom_domains）
            from sqlalchemy import select
            from sqlalchemy.orm import selectinload
            from app.models.tenant.tenant import Tenant
            from app.services.tenant.quota_service import QuotaService
            from app.enums import ErrorCode
            from app.exceptions import BusinessException
            tenant_obj = (await db.execute(
                select(Tenant)
                .options(selectinload(Tenant.tenant_plan))
                .where(Tenant.id == current_admin.tenant_id)
            )).scalar_one_or_none()
            if tenant_obj:
                quota_svc = QuotaService(db, tenant_obj)
                domain_check = await quota_svc.check_domain_quota()
                if not domain_check.allowed:
                    raise BusinessException(
                        message=domain_check.message or _("quota.custom_domain_not_supported"),
                        code=ErrorCode.CONFLICT,
                    )

            service = self.get_service(db, current_admin.tenant_id)
            domain = await service.add_custom_domain(
                tenant_id=current_admin.tenant_id,
                domain=data.domain,
                remark=data.remark,
            )

            # 如果请求设为主域名，且域名已验证
            if data.is_primary and domain.is_verified:
                domain = await service.set_primary_domain(current_admin.tenant_id, domain.id)

            await db.commit()

            # 添加验证 DNS 信息 + CNAME 目标
            resp = TenantDomainResponse.model_validate(domain, from_attributes=True)
            resp.cname_target = await service.get_cname_target(current_admin.tenant_id)
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

        # 更新域名接口
        @router.put("/{domain_id}", summary="更新域名")
        @action_update("action.tenant_domain.update")
        async def update_domain(
            request: Request,
            db: DbSession,
            domain_id: int,
            data: TenantDomainUpdateRequest,
            current_admin: ActiveTenantAdmin,
        ):
            """
            更新域名信息

            - 仅可更新备注
            - 设置主域名请使用专用接口

            权限: tenant_domain:update
            """
            service = self.get_service(db, current_admin.tenant_id)

            # 验证域名存在且属于当前租户
            existing = await service.get_by_id(domain_id)
            if existing is None or existing.tenant_id != current_admin.tenant_id:
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
                domain = await service.set_primary_domain(current_admin.tenant_id, domain_id)

            await db.commit()

            return success(
                data=TenantDomainResponse.model_validate(domain, from_attributes=True),
                message=_("tenant_domain.updated"),
            )

        # 删除域名接口
        @router.delete("/{domain_id}", summary="删除域名")
        @action_delete("action.tenant_domain.delete")
        async def delete_domain(
            request: Request,
            db: DbSession,
            domain_id: int,
            current_admin: ActiveTenantAdmin,
        ):
            """
            删除域名

            **注意**:
            - 不能删除主域名
            - 不能删除默认域名

            权限: tenant_domain:delete
            """
            service = self.get_service(db, current_admin.tenant_id)

            # 验证域名存在且属于当前租户
            existing = await service.get_by_id(domain_id)
            if existing is None or existing.tenant_id != current_admin.tenant_id:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=_("tenant_domain.not_found"),
                )

            await service.remove_domain(domain_id)
            await db.commit()

            return success(message=_("tenant_domain.deleted"))

        # 验证域名接口
        @router.post("/{domain_id}/verify", summary="验证域名")
        @permission_action("verify", "action.tenant_domain.verify")
        async def verify_domain(
            request: Request,
            db: DbSession,
            domain_id: int,
            current_admin: ActiveTenantAdmin,
        ):
            """
            验证域名

            - 检查 DNS TXT 记录是否正确配置
            - 验证成功后域名可设为主域名

            权限: tenant_domain:verify
            """
            service = self.get_service(db, current_admin.tenant_id)

            # 验证域名存在且属于当前租户
            existing = await service.get_by_id(domain_id)
            if existing is None or existing.tenant_id != current_admin.tenant_id:
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

        # 设置主域名接口
        @router.put("/{domain_id}/primary", summary="设置为主域名")
        @permission_action("set_primary", "action.tenant_domain.set_primary")
        async def set_primary_domain(
            request: Request,
            db: DbSession,
            domain_id: int,
            current_admin: ActiveTenantAdmin,
        ):
            """
            设置为主域名

            - 每个租户只能有一个主域名
            - 域名必须已验证

            权限: tenant_domain:set_primary
            """
            service = self.get_service(db, current_admin.tenant_id)
            domain = await service.set_primary_domain(current_admin.tenant_id, domain_id)
            await db.commit()

            return success(
                data=TenantDomainResponse.model_validate(domain, from_attributes=True),
                message=_("tenant_domain.primary_set"),
            )

        # ==================== SSL 证书管理端点 ====================

        @router.get("/{domain_id}/ssl", summary="获取域名 SSL 证书详情")
        @permission_action("ssl_detail", "action.tenant_domain.ssl_detail")
        async def get_ssl_detail(
            request: Request,
            db: DbSession,
            domain_id: int,
            current_admin: ActiveTenantAdmin,
        ):
            """获取域名 SSL 证书详情（租户隔离）"""
            service = self.get_service(db, current_admin.tenant_id)
            domain = await service.get_by_id(domain_id)
            if not domain or domain.tenant_id != current_admin.tenant_id:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_("tenant_domain.not_found"))

            ssl_service = SslCertificateService(db)
            cert = await ssl_service.get_cert_detail(domain_id)
            if not cert:
                return success(data=None, message=_("ssl_certificate.not_found"))
            return success(data=SslCertificateResponse.from_model(cert))

        @router.post("/{domain_id}/ssl/provision", summary="手动触发 SSL 签发")
        @permission_action("ssl_provision", "action.tenant_domain.ssl_provision")
        async def provision_ssl(
            request: Request,
            db: DbSession,
            domain_id: int,
            current_admin: ActiveTenantAdmin,
        ):
            """手动触发 ACME SSL 证书签发（Celery 队列异步执行）"""
            service = self.get_service(db, current_admin.tenant_id)
            domain = await service.get_by_id(domain_id)
            if not domain or domain.tenant_id != current_admin.tenant_id:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_("tenant_domain.not_found"))
            if not domain.is_verified:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=_("ssl_certificate.domain_not_verified"))

            from app.enums.domain import DomainSslStatus
            await service.update(domain_id, {"ssl_status": DomainSslStatus.PROVISIONING.value})
            await db.commit()

            from app.celery_app import celery_app
            celery_app.send_task("app.tasks.ssl_tasks.task_provision_ssl", args=[domain_id], queue="default")

            return success(message=_("ssl_certificate.provision_started"))

        @router.post("/{domain_id}/ssl/renew", summary="手动续期 SSL 证书")
        @permission_action("ssl_renew", "action.tenant_domain.ssl_renew")
        async def renew_ssl(
            request: Request,
            db: DbSession,
            domain_id: int,
            current_admin: ActiveTenantAdmin,
        ):
            """手动续期平台证书（Celery 队列异步执行），仅 platform 类型"""
            service = self.get_service(db, current_admin.tenant_id)
            domain = await service.get_by_id(domain_id)
            if not domain or domain.tenant_id != current_admin.tenant_id:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_("tenant_domain.not_found"))

            ssl_service = SslCertificateService(db)
            cert = await ssl_service.get_cert_detail(domain_id)
            if not cert:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_("ssl_certificate.not_found"))

            from app.enums.domain import SslCertType
            if cert.cert_type != SslCertType.PLATFORM.value:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=_("ssl_certificate.custom_cert_no_renew"))

            from app.celery_app import celery_app
            celery_app.send_task("app.tasks.ssl_tasks.task_renew_ssl", kwargs={"cert_id": cert.id}, queue="default")

            return success(message=_("ssl_certificate.renew_started"))

        @router.post("/{domain_id}/ssl/upload", summary="上传自定义 SSL 证书")
        @permission_action("ssl_upload", "action.tenant_domain.ssl_upload")
        async def upload_ssl(
            request: Request,
            db: DbSession,
            domain_id: int,
            data: SslCertificateUploadRequest,
            current_admin: ActiveTenantAdmin,
        ):
            """
            上传自定义证书（需套餐 allow_custom_ssl）
            自动设置 cert_type=custom, auto_renew=False
            """
            service = self.get_service(db, current_admin.tenant_id)
            domain = await service.get_by_id(domain_id)
            if not domain or domain.tenant_id != current_admin.tenant_id:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_("tenant_domain.not_found"))

            # 套餐权限检查
            from app.models.tenant.tenant import Tenant
            from sqlalchemy import select
            from sqlalchemy.orm import selectinload
            tenant_result = await db.execute(
                select(Tenant).where(Tenant.id == current_admin.tenant_id).options(selectinload(Tenant.tenant_plan))
            )
            tenant = tenant_result.scalar_one_or_none()
            if tenant and not tenant.get_quota_value("allow_custom_ssl", False):
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=_("ssl_certificate.custom_ssl_not_allowed"))

            ssl_service = SslCertificateService(db)
            cert = await ssl_service.upload_custom_cert(
                domain_id=domain_id,
                tenant_id=current_admin.tenant_id,
                cert_pem=data.certificate,
                key_pem=data.private_key,
                chain_pem=data.certificate_chain,
            )
            await db.commit()

            return success(
                data=SslCertificateResponse.from_model(cert),
                message=_("ssl_certificate.upload_success"),
            )

        @router.delete("/{domain_id}/ssl", summary="删除 SSL 证书")
        @permission_action("ssl_delete", "action.tenant_domain.ssl_delete")
        async def delete_ssl(
            request: Request,
            db: DbSession,
            domain_id: int,
            current_admin: ActiveTenantAdmin,
        ):
            """删除域名 SSL 证书，ssl_status 重置为 none"""
            service = self.get_service(db, current_admin.tenant_id)
            domain = await service.get_by_id(domain_id)
            if not domain or domain.tenant_id != current_admin.tenant_id:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_("tenant_domain.not_found"))

            ssl_service = SslCertificateService(db)
            await ssl_service.delete_cert(domain_id)
            await db.commit()

            return success(message=_("ssl_certificate.delete_success"))

        @router.put("/{domain_id}/ssl/auto-renew", summary="设置 SSL 自动续期开关")
        @permission_action("ssl_auto_renew", "action.tenant_domain.ssl_auto_renew")
        async def toggle_ssl_auto_renew(
            request: Request,
            db: DbSession,
            domain_id: int,
            data: SslAutoRenewRequest,
            current_admin: ActiveTenantAdmin,
        ):
            """开启/关闭 SSL 自动续期（仅 platform 类型可开启）"""
            service = self.get_service(db, current_admin.tenant_id)
            domain = await service.get_by_id(domain_id)
            if not domain or domain.tenant_id != current_admin.tenant_id:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_("tenant_domain.not_found"))

            ssl_service = SslCertificateService(db)
            cert = await ssl_service.toggle_auto_renew(domain_id, data.auto_renew)
            await db.commit()

            return success(
                data=SslCertificateResponse.from_model(cert),
                message=_("ssl_certificate.auto_renew_updated"),
            )


# 导出路由器
router = TenantDomainController.get_router()

__all__ = ["router", "TenantDomainController"]
