"""
企业域名管理 API / Tenant Domain Management API

提供企业域名 CRUD 接口（平台管理员专用）
Provides tenant domain CRUD endpoints (platform admin only)
"""

from fastapi import HTTPException, Request, status

from app.core.base_controller import GlobalController
from app.core.base_schema import PageResponse
from app.core.deps import ActiveAdmin, DbSession, QueryParams
from app.core.i18n import _
from app.core.response import success
from app.enums.rbac import PermissionScope
from app.rbac.decorators import (
    action_create,
    action_delete,
    action_read,
    action_update,
    permission_action,
    permission_resource,
)
from app.schemas.common.query import FilterOp, FilterRule
from app.schemas.tenant import (
    DevHostMutationResponse,
    DevHostsStatusResponse,
    DevHostsSyncAllResponse,
    SslAutoRenewRequest,
    SslCertificateResponse,
    SslCertificateUploadRequest,
    SslReplaceRequest,
    TenantDomainCreateRequest,
    TenantDomainResponse,
    TenantDomainUpdateRequest,
    TenantDomainVerificationInfo,
)
from app.services.system import TenantDomainService, TenantService
from app.services.system.ssl_certificate_service import SslCertificateService


@permission_resource(
    resource="tenant_domain",
    name="menu.admin.tenant_domain",  # i18n key / 菜单 i18n 键名
    scope=PermissionScope.ADMIN,
    parent_resource="tenant",  # 操作权限挂载到企业管理菜单下 / Permissions mounted under tenant management menu
)
class AdminTenantDomainController(GlobalController):
    """
    企业域名管理控制器 / Tenant Domain Management Controller

    提供企业域名 CRUD、验证、主域名设置等接口
    Provides tenant domain CRUD, verification, primary domain setting endpoints
    """

    prefix = "/tenants/{tenant_id}/domains"
    tags = ["Tenant Domain Management"]
    service_class = TenantDomainService

    def _register_routes(self) -> None:
        """注册路由 / Register routes"""
        router = self.router

        async def _verify_tenant_exists(
            db: DbSession,
            tenant_id: int,
        ) -> None:
            """验证企业是否存在 / Verify tenant exists"""
            tenant_service = TenantService(db)
            tenant = await tenant_service.get_by_id(tenant_id)
            if tenant is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=_("tenant.not_found"),
                )

        @router.get("", summary="获取企业域名列表")
        @action_read("action.tenant_domain.list")
        async def list_domains(
            request: Request,
            db: DbSession,
            spec: QueryParams,
            current_admin: ActiveAdmin,
            tenant_id: int,
        ):
            """
            获取企业域名列表 / Get tenant domain list

            - 支持通用筛选 / Supports filtering: filter[field][op]=value
            - 支持排序 / Supports sorting: sort=-created_at,domain
            - 支持分页 / Supports pagination: page[number]=1&page[size]=20

            权限 / Permission: tenant_domain:list
            """
            await _verify_tenant_exists(db, tenant_id)

            # 强制添加企业 ID 筛选 / Force add tenant ID filter
            spec.filters.append(
                FilterRule(field="tenant_id", op=FilterOp.eq, value=tenant_id)
            )

            service = TenantDomainService(db)
            items, total = await service.query_list(spec, scope="admin")

            # 计算 CNAME 目标（一次查询，复用） / Calculate CNAME target (single query, reuse)
            cname_target = await service.get_cname_target(tenant_id)

            # 为每个域名添加验证信息 / Add verification info for each domain
            domain_responses = []
            for item in items:
                resp = TenantDomainResponse.model_validate(item, from_attributes=True)
                resp.cname_target = cname_target
                # 未验证的域名添加验证 DNS 信息 / Add verification DNS info for unverified domains
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

        @router.post("", summary="为企业添加自定义域名")
        @action_create("action.tenant_domain.create")
        async def create_domain(
            request: Request,
            db: DbSession,
            data: TenantDomainCreateRequest,
            current_admin: ActiveAdmin,
            tenant_id: int,
        ):
            """
            为企业添加自定义域名 / Add custom domain for tenant

            - 新域名需要 DNS 验证后才能使用 / New domain requires DNS verification before use

            权限 / Permission: tenant_domain:create
            """
            await _verify_tenant_exists(db, tenant_id)

            service = TenantDomainService(db)
            domain = await service.add_custom_domain(
                tenant_id=tenant_id,
                domain=data.domain,
                remark=data.remark,
            )

            # 如果请求设为主域名，且域名已验证 / If requested as primary domain and domain is verified
            if data.is_primary and domain.is_verified:
                domain = await service.set_primary_domain(tenant_id, domain.id)

            await db.commit()

            # 添加验证 DNS 信息 + CNAME 目标 / Add verification DNS info + CNAME target
            resp = TenantDomainResponse.model_validate(domain, from_attributes=True)
            resp.cname_target = await service.get_cname_target(tenant_id)
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
            获取域名详情 / Get domain details

            权限 / Permission: tenant_domain:detail
            """
            await _verify_tenant_exists(db, tenant_id)

            service = TenantDomainService(db)
            domain = await service.get_by_id(domain_id)

            if domain is None or domain.tenant_id != tenant_id:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=_("tenant_domain.not_found"),
                )

            # 添加验证 DNS 信息 + CNAME 目标 / Add verification DNS info + CNAME target
            resp = TenantDomainResponse.model_validate(domain, from_attributes=True)
            resp.cname_target = await service.get_cname_target(tenant_id)
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
            更新域名信息 / Update domain info

            - 仅可更新备注 / Only remark can be updated
            - 设置主域名请使用专用接口 / Use dedicated endpoint for setting primary domain

            权限 / Permission: tenant_domain:update
            """
            await _verify_tenant_exists(db, tenant_id)

            service = TenantDomainService(db)

            # 验证域名存在且属于该企业 / Verify domain exists and belongs to this tenant
            existing = await service.get_by_id(domain_id)
            if existing is None or existing.tenant_id != tenant_id:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=_("tenant_domain.not_found"),
                )

            # 更新备注 / Update remark
            domain = await service.update_domain(
                domain_id=domain_id,
                remark=data.remark,
            )

            # 如果请求设为主域名 / If requested as primary domain
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
            删除域名 / Delete domain

            **注意 / Note**:
            - 不能删除主域名 / Cannot delete primary domain
            - 不能删除默认域名 / Cannot delete default domain

            权限 / Permission: tenant_domain:delete
            """
            await _verify_tenant_exists(db, tenant_id)

            service = TenantDomainService(db)

            # 验证域名存在且属于该企业 / Verify domain exists and belongs to this tenant
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
            验证域名 / Verify domain

            - 检查 DNS TXT 记录是否正确配置 / Check if DNS TXT record is correctly configured
            - 验证成功后域名可设为主域名 / Domain can be set as primary after successful verification

            权限 / Permission: tenant_domain:verify
            """
            await _verify_tenant_exists(db, tenant_id)

            service = TenantDomainService(db)

            # 验证域名存在且属于该企业 / Verify domain exists and belongs to this tenant
            existing = await service.get_by_id(domain_id)
            if existing is None or existing.tenant_id != tenant_id:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=_("tenant_domain.not_found"),
                )

            # 执行 DNS TXT 记录验证 / Execute DNS TXT record verification
            domain = await service.verify_domain(domain_id)
            await db.commit()
            auto_provisioned = await service.maybe_auto_start_ssl_after_verify(
                domain_id
            )
            if auto_provisioned:
                await db.commit()
                domain = auto_provisioned

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
            设置为主域名 / Set as primary domain

            - 每个企业只能有一个主域名 / Each tenant can only have one primary domain
            - 域名必须已验证 / Domain must be verified

            权限 / Permission: tenant_domain:set_primary
            """
            await _verify_tenant_exists(db, tenant_id)

            service = TenantDomainService(db)
            domain = await service.set_primary_domain(tenant_id, domain_id)
            await db.commit()

            return success(
                data=TenantDomainResponse.model_validate(domain, from_attributes=True),
                message=_("tenant_domain.primary_set"),
            )

        @router.get("/dev-hosts/status", summary="获取 Dev Hosts 状态总览")
        @permission_action("hosts_status", "action.tenant_domain.hosts_status")
        async def get_dev_hosts_status(
            request: Request,
            db: DbSession,
            tenant_id: int,
            current_admin: ActiveAdmin,
        ):
            """
            获取当前企业全部域名的 Dev Hosts 状态 / Get Dev Hosts status for all domains of the current tenant

            - 仅管理端可见 / Admin-only
            - 返回运行时信息和每个域名的 hosts 状态 / Returns runtime info and per-domain hosts state

            权限 / Permission: tenant_domain:hosts_status
            """
            await _verify_tenant_exists(db, tenant_id)

            service = TenantDomainService(db)
            result = await service.get_dev_hosts_status(tenant_id)

            return success(
                data=DevHostsStatusResponse.model_validate(result),
                message=_("common.success"),
            )

        @router.post("/{domain_id}/dev-hosts/sync", summary="同步单个域名的 Dev Hosts")
        @permission_action("hosts_sync", "action.tenant_domain.hosts_sync")
        async def sync_dev_host(
            request: Request,
            db: DbSession,
            tenant_id: int,
            domain_id: int,
            current_admin: ActiveAdmin,
        ):
            """
            同步单个域名的 Dev Hosts 条目 / Sync the Dev Hosts entry for a single domain

            - 已有手动条目时不会重复写入 / Does not duplicate when a manual entry already exists
            - 未验证域名不参与同步 / Unverified domains are not eligible for sync

            权限 / Permission: tenant_domain:hosts_sync
            """
            await _verify_tenant_exists(db, tenant_id)

            service = TenantDomainService(db)
            result = await service.sync_dev_host(tenant_id, domain_id)

            return success(
                data=DevHostMutationResponse.model_validate(result),
                message=_("common.success"),
            )

        @router.delete(
            "/{domain_id}/dev-hosts", summary="移除单个域名的 Dev Hosts 托管条目"
        )
        @permission_action("hosts_remove", "action.tenant_domain.hosts_remove")
        async def remove_dev_host(
            request: Request,
            db: DbSession,
            tenant_id: int,
            domain_id: int,
            current_admin: ActiveAdmin,
        ):
            """
            移除单个域名的 Dev Hosts 托管条目 / Remove the managed Dev Hosts entry for a single domain

            - 仅删除系统托管条目 / Only removes system-managed entries
            - 手动 hosts 条目不会被系统误删 / Manual hosts entries will not be deleted by the system

            权限 / Permission: tenant_domain:hosts_remove
            """
            await _verify_tenant_exists(db, tenant_id)

            service = TenantDomainService(db)
            result = await service.remove_dev_host(tenant_id, domain_id)

            return success(
                data=DevHostMutationResponse.model_validate(result),
                message=_("common.success"),
            )

        @router.post("/dev-hosts/sync-all", summary="批量同步企业全部 Dev Hosts 条目")
        @permission_action("hosts_sync_all", "action.tenant_domain.hosts_sync_all")
        async def sync_all_dev_hosts(
            request: Request,
            db: DbSession,
            tenant_id: int,
            current_admin: ActiveAdmin,
        ):
            """
            批量同步企业全部可用域名的 Dev Hosts 条目 / Batch sync Dev Hosts entries for all eligible tenant domains

            - 默认域名和已验证自定义域名参与同步 / Default domains and verified custom domains are synced
            - 未验证域名自动跳过 / Unverified domains are skipped automatically

            权限 / Permission: tenant_domain:hosts_sync_all
            """
            await _verify_tenant_exists(db, tenant_id)

            service = TenantDomainService(db)
            result = await service.sync_all_dev_hosts(tenant_id)

            return success(
                data=DevHostsSyncAllResponse.model_validate(result),
                message=_("common.success"),
            )

        # ==================== SSL 证书管理端点 / SSL Certificate Management Endpoints ====================

        async def _verify_domain_ownership(
            db: DbSession,
            tenant_id: int,
            domain_id: int,
        ):
            """验证域名属于指定企业 / Verify domain belongs to specified tenant"""
            service = TenantDomainService(db)
            domain = await service.get_by_id(domain_id)
            if not domain or domain.tenant_id != tenant_id:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=_("tenant_domain.not_found"),
                )
            return domain

        @router.get("/{domain_id}/ssl", summary="获取域名 SSL 证书详情")
        @permission_action("ssl_detail", "action.tenant_domain.ssl_detail")
        async def get_ssl_detail(
            request: Request,
            db: DbSession,
            tenant_id: int,
            domain_id: int,
            current_admin: ActiveAdmin,
        ):
            """获取域名 SSL 证书详情 / Get domain SSL certificate details"""
            await _verify_tenant_exists(db, tenant_id)
            await _verify_domain_ownership(db, tenant_id, domain_id)

            ssl_service = SslCertificateService(db)
            cert = await ssl_service.get_cert_detail(domain_id)
            if not cert:
                return success(data=None, message=_("ssl_certificate.not_found"))
            return success(data=SslCertificateResponse.from_model(cert))

        @router.post("/{domain_id}/ssl/provision", summary="为企业签发 SSL 证书")
        @permission_action("ssl_provision", "action.tenant_domain.ssl_provision")
        async def provision_ssl(
            request: Request,
            db: DbSession,
            tenant_id: int,
            domain_id: int,
            current_admin: ActiveAdmin,
        ):
            """
            手动触发 ACME SSL 证书签发（通过 Celery 队列异步执行）/ Manually trigger ACME SSL provisioning (async via Celery).
            """
            await _verify_tenant_exists(db, tenant_id)

            service = TenantDomainService(db)
            domain = await service.get_by_id(domain_id)
            if not domain or domain.tenant_id != tenant_id:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=_("tenant_domain.not_found"),
                )
            if not domain.is_verified:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=_("ssl_certificate.domain_not_verified"),
                )

            await service.start_ssl_provision(domain_id)
            await db.commit()

            return success(message=_("ssl_certificate.provision_started"))

        @router.post("/{domain_id}/ssl/renew", summary="为企业展期/续期 SSL 证书")
        @permission_action("ssl_renew", "action.tenant_domain.ssl_renew")
        async def renew_ssl(
            request: Request,
            db: DbSession,
            tenant_id: int,
            domain_id: int,
            current_admin: ActiveAdmin,
        ):
            """
            手动续期已有平台证书（通过 Celery 队列异步执行）/ Manually renew platform cert (async via Celery). 仅 platform 类型证书可续期。
            """
            await _verify_tenant_exists(db, tenant_id)
            domain = await _verify_domain_ownership(db, tenant_id, domain_id)
            await TenantDomainService(db).ensure_custom_domain_entitled(
                tenant_id, domain
            )

            ssl_service = SslCertificateService(db)
            cert = await ssl_service.get_cert_detail(domain_id)
            if not cert:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=_("ssl_certificate.not_found"),
                )

            from app.enums.domain import SslCertType

            if cert.cert_type != SslCertType.PLATFORM.value:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=_("ssl_certificate.custom_cert_no_renew"),
                )

            from app.services.system.dns_provider import ensure_dns_provider_ready

            await ensure_dns_provider_ready(db)
            from app.celery_app import celery_app

            celery_app.send_task(
                "app.tasks.ssl_tasks.task_renew_ssl",
                kwargs={"cert_id": cert.id},
                queue="default",
            )

            return success(message=_("ssl_certificate.renew_started"))

        @router.post("/{domain_id}/ssl/upload", summary="为企业上传自定义 SSL 证书")
        @permission_action("ssl_upload", "action.tenant_domain.ssl_upload")
        async def upload_ssl(
            request: Request,
            db: DbSession,
            tenant_id: int,
            domain_id: int,
            data: SslCertificateUploadRequest,
            current_admin: ActiveAdmin,
        ):
            """
            管理员为企业上传自定义证书 / Admin upload custom cert for tenant. 自动设置 cert_type=custom, auto_renew=False。
            Auto-sets cert_type=custom, auto_renew=False
            """
            await _verify_tenant_exists(db, tenant_id)
            domain = await _verify_domain_ownership(db, tenant_id, domain_id)
            await TenantDomainService(db).ensure_custom_domain_entitled(
                tenant_id, domain
            )

            ssl_service = SslCertificateService(db)
            cert = await ssl_service.upload_custom_cert(
                domain_id=domain_id,
                tenant_id=tenant_id,
                cert_pem=data.certificate,
                key_pem=data.private_key,
                chain_pem=data.certificate_chain,
                check_quota=True,
            )
            await db.commit()

            return success(
                data=SslCertificateResponse.from_model(cert),
                message=_("ssl_certificate.upload_success"),
            )

        @router.post("/{domain_id}/ssl/replace", summary="强制替换企业 SSL 证书")
        @permission_action("ssl_replace", "action.tenant_domain.ssl_replace")
        async def replace_ssl(
            request: Request,
            db: DbSession,
            tenant_id: int,
            domain_id: int,
            data: SslReplaceRequest,
            current_admin: ActiveAdmin,
        ):
            """
            管理员强制替换证书（Admin 独有） / Admin force replace certificate (Admin exclusive)
            mode=platform: 重新触发 ACME 签发 / Re-trigger ACME provisioning
            mode=custom: 上传新的自定义证书 / Upload new custom certificate
            """
            await _verify_tenant_exists(db, tenant_id)
            domain = await _verify_domain_ownership(db, tenant_id, domain_id)

            if data.mode == "platform":
                service = TenantDomainService(db)
                await service.start_ssl_provision(domain_id)
                await db.commit()
                return success(message=_("ssl_certificate.provision_started"))
            else:
                if not data.certificate or not data.private_key:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=_("ssl_certificate.invalid_cert_format"),
                    )

                await TenantDomainService(db).ensure_custom_domain_entitled(
                    tenant_id, domain
                )
                ssl_service = SslCertificateService(db)
                cert = await ssl_service.upload_custom_cert(
                    domain_id=domain_id,
                    tenant_id=tenant_id,
                    cert_pem=data.certificate,
                    key_pem=data.private_key,
                    chain_pem=data.certificate_chain,
                    check_quota=True,
                )
                await db.commit()
                return success(
                    data=SslCertificateResponse.from_model(cert),
                    message=_("ssl_certificate.replace_success"),
                )

        @router.delete("/{domain_id}/ssl", summary="删除企业 SSL 证书")
        @permission_action("ssl_delete", "action.tenant_domain.ssl_delete")
        async def delete_ssl(
            request: Request,
            db: DbSession,
            tenant_id: int,
            domain_id: int,
            current_admin: ActiveAdmin,
        ):
            """删除域名 SSL 证书，ssl_status 重置为 none / Delete domain SSL certificate, reset ssl_status to none"""
            await _verify_tenant_exists(db, tenant_id)
            await _verify_domain_ownership(db, tenant_id, domain_id)

            ssl_service = SslCertificateService(db)
            await ssl_service.delete_cert(domain_id)
            await db.commit()

            return success(message=_("ssl_certificate.delete_success"))

        @router.put("/{domain_id}/ssl/auto-renew", summary="设置 SSL 自动续期开关")
        @permission_action("ssl_auto_renew", "action.tenant_domain.ssl_auto_renew")
        async def toggle_ssl_auto_renew(
            request: Request,
            db: DbSession,
            tenant_id: int,
            domain_id: int,
            data: SslAutoRenewRequest,
            current_admin: ActiveAdmin,
        ):
            """开启/关闭 SSL 自动续期（仅 platform 类型可开启） / Toggle SSL auto-renew (only platform type can enable)"""
            await _verify_tenant_exists(db, tenant_id)
            domain = await _verify_domain_ownership(db, tenant_id, domain_id)
            if data.auto_renew:
                await TenantDomainService(db).ensure_custom_domain_entitled(
                    tenant_id, domain
                )

            ssl_service = SslCertificateService(db)
            cert = await ssl_service.toggle_auto_renew(domain_id, data.auto_renew)
            await db.commit()

            return success(
                data=SslCertificateResponse.from_model(cert),
                message=_("ssl_certificate.auto_renew_updated"),
            )

        @router.post("/ssl/batch-provision", summary="批量签发企业所有域名 SSL")
        @permission_action(
            "ssl_batch_provision", "action.tenant_domain.ssl_batch_provision"
        )
        async def batch_provision_ssl(
            request: Request,
            db: DbSession,
            tenant_id: int,
            current_admin: ActiveAdmin,
        ):
            """
            批量为企业所有已验证但无 SSL 的域名触发签发（Admin 独有）
            Batch provision SSL for all verified domains without SSL (Admin exclusive)
            每个域名一个 Celery 任务 / One Celery task per domain
            """
            await _verify_tenant_exists(db, tenant_id)

            service = TenantDomainService(db)
            triggered = await service.batch_provision_ssl(tenant_id)
            await db.commit()

            return success(
                data={"triggered": triggered, "skipped": 0},
                message=_("ssl_certificate.batch_provision_started"),
            )


# 导出路由器 / Export router
router = AdminTenantDomainController.get_router()

__all__ = ["router", "AdminTenantDomainController"]
