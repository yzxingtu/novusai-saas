"""
租户设置服务

提供租户设置和自定义域名管理的业务逻辑
"""

import secrets
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_service import TenantService
from app.core.config import settings
from app.core.i18n import _
from app.enums import ErrorCode
from app.exceptions import BusinessException, NotFoundException
from app.models import Tenant, TenantDomain
from app.repositories.system.tenant_repository import TenantRepository


class TenantSettingsService(TenantService[Tenant, TenantRepository]):
    """
    租户设置服务
    
    提供：
    - 租户设置读取和更新
    - 自定义域名 CRUD
    - 域名验证
    
    注意：此服务操作 Tenant 和 TenantDomain 两个模型
    """
    
    model = Tenant
    repository_class = TenantRepository
    
    def __init__(self, db: AsyncSession, tenant_id: int):
        """
        初始化服务
        
        Args:
            db: 异步数据库会话
            tenant_id: 租户 ID
        """
        # 注意：这里不调用 super().__init__，因为 TenantRepository 不是 TenantRepository
        # 而是继承自 BaseRepository，不需要 tenant_id
        self.db = db
        self.tenant_id = tenant_id
        self.repo = TenantRepository(db)
    
    # ==================== 租户设置 ====================
    
    async def get_tenant(self) -> Tenant:
        """
        获取当前租户
        
        Returns:
            租户实例
            
        Raises:
            NotFoundException: 租户不存在
        """
        result = await self.db.execute(
            select(Tenant).where(Tenant.id == self.tenant_id)
        )
        tenant = result.scalar_one_or_none()
        
        if not tenant:
            raise NotFoundException(message=_("tenant.not_found"))
        
        return tenant
    
    async def get_settings(self) -> dict[str, Any]:
        """
        获取租户设置
        
        Returns:
            包含租户设置信息的字典
        """
        tenant = await self.get_tenant()
        
        # 统计已绑定域名数量
        domain_count = await self._count_domains()
        
        # 构建子域名 URL
        subdomain_url = f"https://{tenant.code}{settings.TENANT_DOMAIN_SUFFIX}"
        
        return {
            "tenant_id": tenant.id,
            "tenant_code": tenant.code,
            "tenant_name": tenant.name,
            "logo_url": tenant.logo_url,
            "favicon_url": tenant.favicon_url,
            "theme_color": tenant.theme_color,
            "captcha_enabled": tenant.captcha_enabled,
            "login_methods": tenant.login_methods,
            "subdomain": tenant.code,
            "subdomain_url": subdomain_url,
            "max_custom_domains": tenant.max_custom_domains,
            "custom_domain_count": domain_count,
        }
    
    async def update_settings(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        更新租户设置
        
        Args:
            data: 更新数据（logo_url, favicon_url, theme_color, captcha_enabled, login_methods）
        
        Returns:
            更新后的设置信息
        """
        tenant = await self.get_tenant()
        
        # 更新 settings JSON 字段
        current_settings = tenant.settings or {}
        
        if data.get("logo_url") is not None:
            current_settings["logo_url"] = data["logo_url"]
        if data.get("favicon_url") is not None:
            current_settings["favicon_url"] = data["favicon_url"]
        if data.get("theme_color") is not None:
            current_settings["theme_color"] = data["theme_color"]
        if data.get("captcha_enabled") is not None:
            current_settings["captcha_enabled"] = data["captcha_enabled"]
        if data.get("login_methods") is not None:
            current_settings["login_methods"] = data["login_methods"]
        
        tenant.settings = current_settings
        await self.db.flush()
        await self.db.refresh(tenant)
        
        return await self.get_settings()
    
    # ==================== 域名管理 ====================
    
    async def _count_domains(self) -> int:
        """统计已绑定域名数量"""
        result = await self.db.execute(
            select(func.count(TenantDomain.id)).where(
                TenantDomain.tenant_id == self.tenant_id,
                TenantDomain.is_deleted.is_(False),
            )
        )
        return result.scalar() or 0
    
    async def list_domains(self) -> list[TenantDomain]:
        """
        获取域名列表
        
        Returns:
            域名列表
        """
        result = await self.db.execute(
            select(TenantDomain).where(
                TenantDomain.tenant_id == self.tenant_id,
                TenantDomain.is_deleted.is_(False),
            ).order_by(TenantDomain.is_primary.desc(), TenantDomain.created_at)
        )
        return list(result.scalars().all())
    
    async def get_domain(self, domain_id: int) -> TenantDomain:
        """
        获取域名详情
        
        Args:
            domain_id: 域名 ID
            
        Returns:
            域名实例
            
        Raises:
            NotFoundException: 域名不存在
        """
        result = await self.db.execute(
            select(TenantDomain).where(
                TenantDomain.id == domain_id,
                TenantDomain.tenant_id == self.tenant_id,
                TenantDomain.is_deleted.is_(False),
            )
        )
        domain = result.scalar_one_or_none()
        
        if not domain:
            raise NotFoundException(message=_("domain.not_found"))
        
        return domain
    
    async def add_domain(
        self,
        domain: str,
        is_primary: bool = False,
        remark: str | None = None,
    ) -> TenantDomain:
        """
        添加自定义域名
        
        Args:
            domain: 域名
            is_primary: 是否设为主域名
            remark: 备注
            
        Returns:
            创建的域名实例
            
        Raises:
            BusinessException: 配额超限或域名已存在
        """
        tenant = await self.get_tenant()
        
        # 检查是否允许自定义域名
        if not settings.ALLOW_CUSTOM_DOMAIN:
            raise BusinessException(
                message=_("domain.custom_domain_disabled"),
                code=ErrorCode.DOMAIN_CUSTOM_DISABLED,
            )
        
        # 检查配额
        current_count = await self._count_domains()
        if current_count >= tenant.max_custom_domains:
            raise BusinessException(
                message=_("domain.quota_exceeded"),
                code=ErrorCode.DOMAIN_QUOTA_EXCEEDED,
            )
        
        # 检查域名是否已被使用
        existing_result = await self.db.execute(
            select(TenantDomain).where(
                TenantDomain.domain == domain.lower(),
                TenantDomain.is_deleted.is_(False),
            )
        )
        if existing_result.scalar_one_or_none():
            raise BusinessException(
                message=_("domain.already_exists"),
                code=ErrorCode.DOMAIN_ALREADY_EXISTS,
            )
        
        # 如果设为主域名，先取消其他主域名
        if is_primary:
            await self._unset_primary_domain()
        
        # 创建域名
        new_domain = TenantDomain(
            tenant_id=self.tenant_id,
            domain=domain.lower(),
            is_primary=is_primary,
            is_verified=False,
            ssl_status="pending",
            verification_token=secrets.token_urlsafe(32),
            remark=remark,
        )
        
        self.db.add(new_domain)
        await self.db.flush()
        await self.db.refresh(new_domain)
        
        return new_domain
    
    async def update_domain(
        self,
        domain_id: int,
        is_primary: bool | None = None,
        remark: str | None = None,
    ) -> TenantDomain:
        """
        更新域名设置
        
        Args:
            domain_id: 域名 ID
            is_primary: 是否设为主域名
            remark: 备注
            
        Returns:
            更新后的域名实例
        """
        domain = await self.get_domain(domain_id)
        
        # 如果设为主域名，先取消其他主域名
        if is_primary is True:
            await self._unset_primary_domain(exclude_id=domain_id)
            domain.is_primary = True
        elif is_primary is False:
            domain.is_primary = False
        
        if remark is not None:
            domain.remark = remark
        
        await self.db.flush()
        await self.db.refresh(domain)
        
        return domain
    
    async def delete_domain(self, domain_id: int) -> bool:
        """
        删除域名（软删除）
        
        Args:
            domain_id: 域名 ID
            
        Returns:
            是否删除成功
        """
        domain = await self.get_domain(domain_id)
        domain.soft_delete()
        await self.db.flush()
        return True
    
    async def verify_domain(self, domain_id: int) -> TenantDomain:
        """
        验证域名 DNS 配置
        
        Args:
            domain_id: 域名 ID
            
        Returns:
            验证后的域名实例
        """
        domain = await self.get_domain(domain_id)
        tenant = await self.get_tenant()
        
        # TODO: 实际的 DNS 验证逻辑
        # 这里简化处理，实际应该查询 DNS 记录验证 CNAME 指向
        # import dns.resolver
        # try:
        #     answers = dns.resolver.resolve(domain.domain, 'CNAME')
        #     expected = f"{tenant.code}{settings.TENANT_DOMAIN_SUFFIX}"
        #     for rdata in answers:
        #         if str(rdata.target).rstrip('.') == expected:
        #             domain.is_verified = True
        #             domain.verified_at = datetime.now(timezone.utc)
        #             break
        # except Exception:
        #     pass
        
        # 简化实现：假设验证通过
        domain.is_verified = True
        domain.verified_at = datetime.now(timezone.utc)
        domain.ssl_status = "active"  # 实际应该触发 SSL 证书申请
        
        await self.db.flush()
        await self.db.refresh(domain)
        
        return domain
    
    async def _unset_primary_domain(self, exclude_id: int | None = None) -> None:
        """取消所有主域名（除指定 ID 外）"""
        query = (
            TenantDomain.__table__.update()
            .where(
                TenantDomain.tenant_id == self.tenant_id,
                TenantDomain.is_primary.is_(True),
            )
            .values(is_primary=False)
        )
        if exclude_id:
            query = query.where(TenantDomain.id != exclude_id)
        
        await self.db.execute(query)
    
    def get_cname_target(self, tenant: Tenant) -> str:
        """获取 CNAME 目标地址"""
        return f"{tenant.code}{settings.TENANT_DOMAIN_SUFFIX}"


__all__ = ["TenantSettingsService"]
