"""
租户域名服务

提供租户域名的业务逻辑（平台级，非租户隔离）
"""

import secrets
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.configs.service import ConfigService
from app.core.base_service import GlobalService
from app.core.config import settings
from app.core.i18n import _
from app.enums import ErrorCode
from app.exceptions import BusinessException, NotFoundException
from app.models.tenant.tenant import Tenant
from app.models.tenant.tenant_domain import TenantDomain
from app.repositories.tenant.tenant_domain_repository import TenantDomainRepository

# 配置键名
_CONFIG_KEY_DOMAIN_SUFFIX = "tenant_domain_suffix"
_CONFIG_KEY_VERIFICATION_PREFIX = "domain_verification_prefix"


class TenantDomainService(GlobalService[TenantDomain, TenantDomainRepository]):
    """
    租户域名服务
    
    提供域名特有的业务方法
    注意：域名管理是平台级操作，不做租户隔离
    """
    
    model = TenantDomain
    repository_class = TenantDomainRepository
    
    async def _get_domain_suffix(self) -> str:
        """
        获取租户默认域名后缀
        
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
        获取租户及其套餐信息
        """
        result = await self.db.execute(
            select(Tenant)
            .where(Tenant.id == tenant_id, Tenant.is_deleted == False)
            .options(selectinload(Tenant.tenant_plan))
        )
        return result.scalar_one_or_none()
    
    async def _check_custom_domain_allowed(self, tenant_id: int) -> tuple[bool, int]:
        """
        检查租户是否允许添加自定义域名
        
        Args:
            tenant_id: 租户 ID
            
        Returns:
            (is_allowed, max_custom_domains) 元组
        """
        tenant = await self._get_tenant_with_plan(tenant_id)
        if not tenant:
            return False, 0
        
        # 从租户/套餐配额获取是否允许自定义域名
        allow_custom_domain = tenant.get_quota_value("allow_custom_domain", False)
        if not allow_custom_domain:
            return False, 0
        
        # 获取最大自定义域名数量
        max_custom_domains = tenant.get_quota_value("max_custom_domains", 0)
        return True, max_custom_domains
    
    async def create_default_domain(
        self,
        tenant_id: int,
        tenant_code: str,
    ) -> TenantDomain:
        """
        创建租户默认域名
        
        默认域名格式: {tenant_code}{suffix}
        后缀从平台配置读取（tenant_domain_suffix）
        自动标记为主域名、已验证
        
        Args:
            tenant_id: 租户 ID
            tenant_code: 租户编码
        
        Returns:
            创建的默认域名
        """
        # 从平台配置获取域名后缀
        suffix = await self._get_domain_suffix()
        
        # 构建默认域名
        domain = f"{tenant_code}{suffix}"
        
        # 检查域名是否已存在（理论上不应该存在）
        if await self.repo.domain_exists(domain):
            raise BusinessException(
                message=_("tenant_domain.already_exists"),
                code=ErrorCode.DUPLICATE_ENTRY,
            )
        
        # 创建默认域名
        data = {
            "tenant_id": tenant_id,
            "domain": domain,
            "is_verified": True,  # 默认域名自动验证
            "verified_at": datetime.now(timezone.utc),
            "is_primary": True,  # 默认域名是主域名
            "ssl_status": "active",  # 默认域名 SSL 已配置
            "remark": _("tenant_domain.default_domain_remark"),
        }
        
        return await self.create(data)
    
    async def add_custom_domain(
        self,
        tenant_id: int,
        domain: str,
        remark: str | None = None,
    ) -> TenantDomain:
        """
        添加自定义域名
        
        自定义域名需要 DNS 验证后才能使用
        
        Args:
            tenant_id: 租户 ID
            domain: 域名
            remark: 备注
        
        Returns:
            创建的域名
        
        Raises:
            BusinessException: 域名已存在、配额超限或套餐不允许自定义域名
        """
        # 检查套餐是否允许自定义域名
        is_allowed, max_domains = await self._check_custom_domain_allowed(tenant_id)
        if not is_allowed:
            raise BusinessException(
                message=_("domain.custom_domain_disabled"),
                code=ErrorCode.FORBIDDEN,
            )
        
        # 检查域名配额
        current_count = await self.repo.count_tenant_domains(tenant_id)
        # 扣除默认域名，只统计自定义域名
        suffix = await self._get_domain_suffix()
        domains = await self.repo.get_tenant_domains(tenant_id)
        custom_count = sum(1 for d in domains if not d.domain.endswith(suffix))
        
        if max_domains > 0 and custom_count >= max_domains:
            raise BusinessException(
                message=_("domain.quota_exceeded"),
                code=ErrorCode.QUOTA_EXCEEDED,
            )
        
        # 检查域名是否已存在
        if await self.repo.domain_exists(domain):
            raise BusinessException(
                message=_("tenant_domain.already_exists"),
                code=ErrorCode.DUPLICATE_ENTRY,
            )
        
        # 生成验证 Token
        verification_token = self._generate_verification_token()
        
        # 创建域名记录
        data = {
            "tenant_id": tenant_id,
            "domain": domain,
            "is_verified": False,  # 自定义域名需要验证
            "is_primary": False,  # 默认不是主域名
            "ssl_status": "pending",  # SSL 待配置
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
        
        # 获取域名后缀配置
        suffix = await self._get_domain_suffix()
        
        # 检查是否是默认域名（域名以配置的后缀结尾）
        if domain_obj.domain.endswith(suffix):
            raise BusinessException(
                message=_("tenant_domain.cannot_delete_default"),
                code=ErrorCode.FORBIDDEN,
            )
        
        # 检查是否是主域名
        if domain_obj.is_primary:
            raise BusinessException(
                message=_("tenant_domain.cannot_delete_primary"),
                code=ErrorCode.FORBIDDEN,
            )
        
        return await self.delete(domain_id)
    
    async def set_primary_domain(
        self,
        tenant_id: int,
        domain_id: int,
    ) -> TenantDomain:
        """
        设置主域名
        
        每个租户只能有一个主域名
        
        Args:
            tenant_id: 租户 ID
            domain_id: 域名 ID
        
        Returns:
            设置后的域名
        
        Raises:
            NotFoundException: 域名不存在
            BusinessException: 域名不属于该租户或未验证
        """
        domain = await self.get_by_id(domain_id)
        if not domain:
            raise NotFoundException(
                message=_("tenant_domain.not_found"),
            )
        
        # 检查域名是否属于该租户
        if domain.tenant_id != tenant_id:
            raise BusinessException(
                message=_("tenant_domain.not_found"),
                code=ErrorCode.FORBIDDEN,
            )
        
        # 检查域名是否已验证
        if not domain.is_verified:
            raise BusinessException(
                message=_("tenant_domain.not_verified"),
                code=ErrorCode.VALIDATION_ERROR,
            )
        
        # 清除现有主域名标记
        await self.repo.clear_primary_flag(tenant_id)
        
        # 设置新的主域名
        result = await self.update(domain_id, {"is_primary": True})
        if not result:
            raise NotFoundException(message=_("tenant_domain.not_found"))
        return result
    
    async def verify_domain(self, domain_id: int) -> TenantDomain:
        """
        验证域名
        
        实际的 DNS 验证逻辑需要另外实现（检查 TXT 记录）
        此方法用于手动标记域名为已验证
        
        Args:
            domain_id: 域名 ID
        
        Returns:
            验证后的域名
        
        Raises:
            NotFoundException: 域名不存在
            BusinessException: 域名已验证
        """
        domain = await self.get_by_id(domain_id)
        if not domain:
            raise NotFoundException(
                message=_("tenant_domain.not_found"),
            )
        
        # 检查是否已验证
        if domain.is_verified:
            raise BusinessException(
                message=_("tenant_domain.already_verified"),
                code=ErrorCode.VALIDATION_ERROR,
            )
        
        # 标记为已验证
        result = await self.update(domain_id, {
            "is_verified": True,
            "verified_at": datetime.now(timezone.utc),
            "ssl_status": "provisioning",  # SSL 开始配置
        })
        if not result:
            raise NotFoundException(message=_("tenant_domain.not_found"))
        return result
    
    async def get_tenant_domains(self, tenant_id: int) -> list[TenantDomain]:
        """
        获取租户所有域名
        
        Args:
            tenant_id: 租户 ID
        
        Returns:
            域名列表，主域名排在前面
        """
        return await self.repo.get_tenant_domains(tenant_id)
    
    async def get_primary_domain(self, tenant_id: int) -> TenantDomain | None:
        """
        获取租户主域名
        
        Args:
            tenant_id: 租户 ID
        
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


__all__ = ["TenantDomainService"]
