"""
企业域名服务 / Tenant Domain Service

提供企业域名的业务逻辑（平台级，非企业隔离）
Provides tenant domain business logic (platform-level, no tenant isolation).
"""

import secrets

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.configs.service import ConfigService
from app.core.base_model import utc_now
from app.core.base_service import GlobalService, TenantService
from app.core.config import settings
from app.core.hosts_helper import (
    async_add_host_entry,
    async_get_domain_entry_status,
    async_get_runtime_info,
    async_remove_host_entry,
    is_dev_local,
)
from app.core.i18n import _
from app.enums import ErrorCode
from app.enums.domain import DomainSslStatus
from app.exceptions import BusinessException, NotFoundException
from app.models.tenant.tenant import Tenant
from app.models.tenant.tenant_domain import TenantDomain
from app.repositories.system.tenant_domain_repository import TenantDomainRepository
from app.repositories.tenant.tenant_domain_tenant_repository import (
    TenantDomainTenantRepository,
)

_CONFIG_KEY_DOMAIN_SUFFIX = "tenant_domain_suffix"
_CONFIG_KEY_VERIFICATION_PREFIX = "domain_verification_prefix"


class TenantDomainService(GlobalService[TenantDomain, TenantDomainRepository]):
    """
    企业域名服务

    提供域名特有的业务方法
    注意：域名管理是平台级操作，不做企业隔离
    """

    model = TenantDomain
    repository_class = TenantDomainRepository

    async def _get_domain_suffix(self) -> str:
        """
        获取企业默认域名后缀

        优先从平台配置读取，回退到环境变量
        """
        config_service = ConfigService(self.db)
        suffix = await config_service.get_platform_config(
            _CONFIG_KEY_DOMAIN_SUFFIX,
            default=settings.TENANT_DOMAIN_SUFFIX,
        )
        return suffix or settings.TENANT_DOMAIN_SUFFIX

    async def _get_verification_prefix(self) -> str:
        """
        获取域名验证 DNS 前缀

        优先从平台配置读取，回退到环境变量
        """
        config_service = ConfigService(self.db)
        prefix = await config_service.get_platform_config(
            _CONFIG_KEY_VERIFICATION_PREFIX,
            default=settings.DOMAIN_VERIFICATION_PREFIX,
        )
        return prefix or settings.DOMAIN_VERIFICATION_PREFIX

    async def _get_tenant_with_plan(self, tenant_id: int) -> Tenant | None:
        """
        获取企业及其套餐信息
        """
        result = await self.db.execute(
            select(Tenant)
            .where(Tenant.id == tenant_id, Tenant.is_deleted.is_(False))
            .options(selectinload(Tenant.tenant_plan))
        )
        return result.scalar_one_or_none()

    async def _check_custom_domain_allowed(self, tenant_id: int) -> tuple[bool, int]:
        """
        检查企业是否允许添加自定义域名

        Args:
            tenant_id: 企业 ID

        Returns:
            (is_allowed, max_custom_domains) 元组
        """
        tenant = await self._get_tenant_with_plan(tenant_id)
        if not tenant:
            return False, 0

        allow_custom_domain = tenant.get_quota_value("allow_custom_domain", False)
        if not allow_custom_domain:
            return False, 0

        max_custom_domains = tenant.get_quota_value("max_custom_domains", 0)
        return True, max_custom_domains

    async def create_default_domain(
        self,
        tenant_id: int,
        tenant_code: str,
    ) -> TenantDomain:
        """
        创建企业默认域名

        默认域名格式: {tenant_code}{suffix}
        后缀从平台配置读取（tenant_domain_suffix）
        自动标记为主域名、已验证

        Args:
            tenant_id: 企业 ID
            tenant_code: 企业编码

        Returns:
            创建的默认域名
        """
        suffix = await self._get_domain_suffix()
        domain = f"{tenant_code}{suffix}"

        if await self.repo.domain_exists(domain):
            raise BusinessException(
                message=_("tenant_domain.already_exists"),
                code=ErrorCode.DUPLICATE_ENTRY,
            )

        data = {
            "tenant_id": tenant_id,
            "domain": domain,
            "is_verified": True,
            "verified_at": utc_now(),
            "is_primary": True,
            "ssl_status": DomainSslStatus.ACTIVE.value,
            "remark": _("tenant_domain.default_domain_remark"),
        }

        result = await self.create(data)

        # ⚠️  LOCAL DEV ENVIRONMENT: auto-inject default domain into hosts file
        if self._should_inject_hosts() and is_dev_local():
            await async_add_host_entry(domain)

        return result

    async def add_custom_domain(
        self,
        tenant_id: int,
        domain: str,
        remark: str | None = None,
        *,
        skip_quota_check: bool = False,
    ) -> TenantDomain:
        """
        添加自定义域名

        自定义域名需要 DNS 验证后才能使用

        Args:
            tenant_id: 企业 ID
            domain: 域名
            remark: 备注
            skip_quota_check: 跳过配额检查（Admin 端使用）

        Returns:
            创建的域名

        Raises:
            BusinessException: 域名已存在、配额超限或套餐不允许自定义域名
        """
        if not skip_quota_check:
            is_allowed, max_domains = await self._check_custom_domain_allowed(tenant_id)
            if not is_allowed:
                raise BusinessException(
                    message=_("tenant_domain.custom_domain_disabled"),
                    code=ErrorCode.FORBIDDEN,
                )

            suffix = await self._get_domain_suffix()
            domains = await self.repo.get_tenant_domains(tenant_id)
            custom_count = sum(1 for d in domains if not d.domain.endswith(suffix))

            if max_domains > 0 and custom_count >= max_domains:
                raise BusinessException(
                    message=_("tenant_domain.quota_exceeded"),
                    code=ErrorCode.DOMAIN_QUOTA_EXCEEDED,
                )

        if await self.repo.domain_exists(domain):
            raise BusinessException(
                message=_("tenant_domain.already_exists"),
                code=ErrorCode.DUPLICATE_ENTRY,
            )

        verification_token = self._generate_verification_token()

        data = {
            "tenant_id": tenant_id,
            "domain": domain,
            "is_verified": False,
            "is_primary": False,
            "ssl_status": DomainSslStatus.PENDING.value,
            "verification_token": verification_token,
            "remark": remark,
        }

        return await self.create(data)

    async def remove_domain(self, domain_id: int) -> bool:
        """
        删除域名

        Args:
            domain_id: 域名 ID

        Returns:
            是否删除成功

        Raises:
            NotFoundException: 域名不存在
            BusinessException: 不能删除主域名或默认域名
        """
        domain_obj = await self.get_by_id(domain_id)
        if not domain_obj:
            raise NotFoundException(
                message=_("tenant_domain.not_found"),
            )

        suffix = await self._get_domain_suffix()

        if domain_obj.domain.endswith(suffix):
            raise BusinessException(
                message=_("tenant_domain.cannot_delete_default"),
                code=ErrorCode.FORBIDDEN,
            )

        if domain_obj.is_primary:
            raise BusinessException(
                message=_("tenant_domain.cannot_delete_primary"),
                code=ErrorCode.FORBIDDEN,
            )

        domain_str = domain_obj.domain
        deleted = await self.delete(domain_id)

        # ⚠️  LOCAL DEV ENVIRONMENT: remove deleted custom domain from hosts file
        if deleted and self._should_inject_hosts() and is_dev_local():
            await async_remove_host_entry(domain_str)

        return deleted

    async def set_primary_domain(
        self,
        tenant_id: int,
        domain_id: int,
    ) -> TenantDomain:
        """
        设置主域名

        每个企业只能有一个主域名

        Args:
            tenant_id: 企业 ID
            domain_id: 域名 ID

        Returns:
            设置后的域名

        Raises:
            NotFoundException: 域名不存在
            BusinessException: 域名不属于该企业或未验证
        """
        domain = await self.get_by_id(domain_id)
        if not domain:
            raise NotFoundException(
                message=_("tenant_domain.not_found"),
            )

        if domain.tenant_id != tenant_id:
            raise BusinessException(
                message=_("tenant_domain.not_found"),
                code=ErrorCode.FORBIDDEN,
            )

        if not domain.is_verified:
            raise BusinessException(
                message=_("tenant_domain.not_verified"),
                code=ErrorCode.VALIDATION_ERROR,
            )

        await self.repo.clear_primary_flag(tenant_id)

        result = await self.update(domain_id, {"is_primary": True})
        if not result:
            raise NotFoundException(message=_("tenant_domain.not_found"))
        return result

    async def verify_domain(self, domain_id: int) -> TenantDomain:
        """
        验证域名

        查询 DNS TXT 记录验证域名所有权

        Args:
            domain_id: 域名 ID

        Returns:
            验证后的域名

        Raises:
            NotFoundException: 域名不存在
            BusinessException: 域名已验证或验证失败
        """
        domain = await self.get_by_id(domain_id)
        if not domain:
            raise NotFoundException(
                message=_("tenant_domain.not_found"),
            )

        if domain.is_verified:
            raise BusinessException(
                message=_("tenant_domain.already_verified"),
                code=ErrorCode.VALIDATION_ERROR,
            )

        # 开发模式跳过 DNS 验证
        if settings.DEBUG:
            is_valid = True
        else:
            is_valid = await self._verify_dns_txt_record(domain)

        if not is_valid:
            raise BusinessException(
                message=_("tenant_domain.verify_failed"),
                code=ErrorCode.VALIDATION_ERROR,
            )

        result = await self.update(domain_id, {
            "is_verified": True,
            "verified_at": utc_now(),
            "ssl_status": DomainSslStatus.PROVISIONING.value,
        })
        if not result:
            raise NotFoundException(message=_("tenant_domain.not_found"))

        # ⚠️  LOCAL DEV ENVIRONMENT: auto-inject verified custom domain into hosts file
        if self._should_inject_hosts() and is_dev_local():
            await async_add_host_entry(domain.domain)

        # ⚠️  LOCAL DEV ENVIRONMENT: skip SSL provisioning for local domains
        # (.app.local / .localhost cannot obtain public CA certificates)
        if not settings.DEBUG:
            from app.celery_app import celery_app
            celery_app.send_task(
                "app.tasks.ssl_tasks.task_provision_ssl",
                args=[domain_id],
                queue="default",
            )

        return result

    async def _verify_dns_txt_record(self, domain: TenantDomain) -> bool:
        """
        验证 DNS TXT 记录

        Args:
            domain: 域名实例

        Returns:
            验证是否通过
        """
        import asyncio

        import dns.resolver

        prefix = await self._get_verification_prefix()

        txt_record_name = f"{prefix}.{domain.domain}"
        expected_value = domain.verification_token

        try:
            answers = await asyncio.to_thread(
                dns.resolver.resolve, txt_record_name, "TXT"
            )

            for rdata in answers:
                txt_value = str(rdata).strip('"').strip()
                if txt_value == expected_value:
                    return True

            return False

        except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer,
                dns.resolver.NoNameservers, Exception):
            return False

    async def get_tenant_domains(self, tenant_id: int) -> list[TenantDomain]:
        """
        获取企业所有域名

        Args:
            tenant_id: 企业 ID

        Returns:
            域名列表，主域名排在前面
        """
        return await self.repo.get_tenant_domains(tenant_id)

    async def get_primary_domain(self, tenant_id: int) -> TenantDomain | None:
        """
        获取企业主域名

        Args:
            tenant_id: 企业 ID

        Returns:
            主域名或 None
        """
        return await self.repo.get_primary_domain(tenant_id)

    async def get_by_domain(self, domain: str) -> TenantDomain | None:
        """
        根据域名获取记录

        Args:
            domain: 域名

        Returns:
            域名实例或 None
        """
        return await self.repo.get_by_domain(domain)

    async def update_domain(
        self,
        domain_id: int,
        remark: str | None = None,
    ) -> TenantDomain:
        """
        更新域名信息

        Args:
            domain_id: 域名 ID
            remark: 备注

        Returns:
            更新后的域名

        Raises:
            NotFoundException: 域名不存在
        """
        domain = await self.get_by_id(domain_id)
        if not domain:
            raise NotFoundException(
                message=_("tenant_domain.not_found"),
            )

        data = {}
        if remark is not None:
            data["remark"] = remark

        if not data:
            return domain

        result = await self.update(domain_id, data)
        if not result:
            raise NotFoundException(message=_("tenant_domain.not_found"))
        return result

    def _generate_verification_token(self) -> str:
        """
        生成域名验证 Token

        Returns:
            32 位随机字符串
        """
        return secrets.token_hex(16)

    async def get_cname_target(self, tenant_id: int) -> str:
        """
        获取企业的 CNAME 解析目标

        Args:
            tenant_id: 企业 ID

        Returns:
            CNAME 目标（如 tenant_code.novusai.com）
        """
        tenant = await self._get_tenant_with_plan(tenant_id)
        if not tenant:
            return ""
        suffix = await self._get_domain_suffix()
        return f"{tenant.code}{suffix}"

    async def get_verification_record(self, domain_obj: TenantDomain) -> dict:
        """
        获取 DNS 验证记录信息

        Args:
            domain_obj: 域名实例

        Returns:
            验证记录信息
        """
        prefix = await self._get_verification_prefix()
        return {
            "type": "TXT",
            "name": f"{prefix}.{domain_obj.domain}",
            "value": domain_obj.verification_token,
        }

    async def _get_owned_domain(self, tenant_id: int, domain_id: int) -> TenantDomain:
        """获取指定企业拥有的域名，不存在则抛错 / Get a domain owned by the specified tenant, or raise when not found"""
        domain = await self.get_by_id(domain_id)
        if not domain or domain.tenant_id != tenant_id:
            raise NotFoundException(message=_("tenant_domain.not_found"))
        return domain

    def _build_dev_host_domain_status(self, domain_obj: TenantDomain, runtime: dict, entry_status: dict) -> dict:
        """构建单个域名的 Dev Hosts 状态响应 / Build the Dev Hosts status response for a single domain"""
        eligible = bool(domain_obj.is_verified)
        if not eligible:
            return {
                "domain_id": domain_obj.id,
                "domain": domain_obj.domain,
                "eligible": False,
                "status": "not_required",
                "managed": False,
                "matched_ip": None,
                "reason": "unverified",
            }

        reason = None
        if entry_status["status"] == "unsupported":
            reason = "unsupported_platform"
        elif not runtime["enabled"]:
            reason = "dev_hosts_disabled"

        return {
            "domain_id": domain_obj.id,
            "domain": domain_obj.domain,
            "eligible": True,
            "status": entry_status["status"],
            "managed": entry_status["managed"],
            "matched_ip": entry_status["matched_ip"],
            "reason": reason,
        }

    async def get_dev_hosts_status(self, tenant_id: int) -> dict:
        """获取企业全部域名的 Dev Hosts 状态 / Get Dev Hosts status for all domains of the tenant"""
        runtime = await async_get_runtime_info()
        domains = await self.repo.get_tenant_domains(tenant_id)

        domain_statuses = []
        for domain_obj in domains:
            entry_status = await async_get_domain_entry_status(domain_obj.domain)
            domain_statuses.append(self._build_dev_host_domain_status(domain_obj, runtime, entry_status))

        return {
            "runtime": runtime,
            "domains": domain_statuses,
        }

    async def sync_dev_host(self, tenant_id: int, domain_id: int) -> dict:
        """同步单个域名到 Dev Hosts / Sync a single domain into Dev Hosts"""
        domain = await self._get_owned_domain(tenant_id, domain_id)
        if not domain.is_verified:
            raise BusinessException(
                message=_("tenant_domain.not_verified"),
                code=ErrorCode.VALIDATION_ERROR,
            )

        if self._should_inject_hosts():
            await async_add_host_entry(domain.domain)

        runtime = await async_get_runtime_info()
        entry_status = await async_get_domain_entry_status(domain.domain)
        return {
            "runtime": runtime,
            "domain": self._build_dev_host_domain_status(domain, runtime, entry_status),
        }

    async def remove_dev_host(self, tenant_id: int, domain_id: int) -> dict:
        """移除单个域名的托管 Dev Hosts 条目 / Remove the managed Dev Hosts entry for a single domain"""
        domain = await self._get_owned_domain(tenant_id, domain_id)

        if self._should_inject_hosts():
            await async_remove_host_entry(domain.domain)

        runtime = await async_get_runtime_info()
        entry_status = await async_get_domain_entry_status(domain.domain)
        return {
            "runtime": runtime,
            "domain": self._build_dev_host_domain_status(domain, runtime, entry_status),
        }

    async def sync_all_dev_hosts(self, tenant_id: int) -> dict:
        """批量同步企业全部可写入的 Dev Hosts 条目 / Batch sync all eligible Dev Hosts entries for the tenant"""
        domains = await self.repo.get_tenant_domains(tenant_id)
        synced = 0
        skipped = 0

        if self._should_inject_hosts():
            for domain_obj in domains:
                if not domain_obj.is_verified:
                    skipped += 1
                    continue
                await async_add_host_entry(domain_obj.domain)
                synced += 1
        else:
            skipped = len(domains)

        overview = await self.get_dev_hosts_status(tenant_id)
        overview["synced"] = synced
        overview["skipped"] = skipped
        return overview

    def _should_inject_hosts(self) -> bool:
        """
        是否允许在当前服务上下文中注入 hosts

        管理端（TenantDomainService）返回 True；
        企业端（TenantDomainTenantService）覆盖返回 False，防止误写入。
        """
        return True

    def get_cname_record(self, domain: TenantDomain) -> dict:
        """
        获取 CNAME 记录信息

        Args:
            domain: 域名实例

        Returns:
            CNAME 记录信息
        """
        return {
            "type": "CNAME",
            "name": domain.domain,
            "value": domain.cname_target,
        }


    async def batch_provision_ssl(self, tenant_id: int) -> int:
        """
        批量为企业所有已验证但无 SSL 的域名触发签发

        Args:
            tenant_id: 企业 ID

        Returns:
            触发签发的域名数量
        """
        from app.enums.domain import DomainSslStatus

        result = await self.db.execute(
            select(TenantDomain).where(
                TenantDomain.tenant_id == tenant_id,
                TenantDomain.is_verified.is_(True),
                TenantDomain.ssl_status.in_([
                    DomainSslStatus.NONE.value,
                    DomainSslStatus.FAILED.value,
                    DomainSslStatus.EXPIRED.value,
                ]),
                TenantDomain.is_deleted.is_(False),
            )
        )
        domains = list(result.scalars().all())

        triggered = 0
        # ⚠️  LOCAL DEV ENVIRONMENT: skip SSL provisioning in DEBUG mode
        if not settings.DEBUG:
            from app.celery_app import celery_app
            for domain in domains:
                await self.update(domain.id, {"ssl_status": DomainSslStatus.PROVISIONING.value})
                celery_app.send_task(
                    "app.tasks.ssl_tasks.task_provision_ssl",
                    args=[domain.id],
                    queue="default",
                )
                triggered += 1

        return triggered


class TenantDomainTenantService(TenantDomainService, TenantService[TenantDomain, TenantDomainTenantRepository]):
    model = TenantDomain
    repository_class = TenantDomainTenantRepository

    def __init__(self, db, tenant_id: int):
        TenantService.__init__(self, db, tenant_id)

    def _should_inject_hosts(self) -> bool:
        """企业端禁止 hosts 注入，防止非预期写入本地系统文件"""
        return False

    async def verify_domain(self, domain_id: int) -> TenantDomain:
        """
        企业端域名验证 — 永远执行真实 DNS 验证，不受 DEBUG 模式影响

        安全原则：企业端不应因 DEBUG=true 而绕过 DNS 验证，
        防止企业在开发/测试环境中意外验证不属于自己的域名。
        """
        domain = await self.get_by_id(domain_id)
        if not domain:
            raise NotFoundException(
                message=_("tenant_domain.not_found"),
            )

        if domain.is_verified:
            raise BusinessException(
                message=_("tenant_domain.already_verified"),
                code=ErrorCode.VALIDATION_ERROR,
            )

        # 企业端始终执行真实 DNS 验证，不跳过
        is_valid = await self._verify_dns_txt_record(domain)

        if not is_valid:
            raise BusinessException(
                message=_("tenant_domain.verify_failed"),
                code=ErrorCode.VALIDATION_ERROR,
            )

        result = await self.update(domain_id, {
            "is_verified": True,
            "verified_at": utc_now(),
            "ssl_status": DomainSslStatus.PROVISIONING.value,
        })
        if not result:
            raise NotFoundException(message=_("tenant_domain.not_found"))

        # 触发 SSL 证书签发（企业端不跳过，SSL 是真实需要的）
        from app.celery_app import celery_app
        celery_app.send_task(
            "app.tasks.ssl_tasks.task_provision_ssl",
            args=[domain_id],
            queue="default",
        )

        return result


__all__ = ["TenantDomainService", "TenantDomainTenantService"]
