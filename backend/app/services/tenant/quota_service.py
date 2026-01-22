"""
配额服务

提供租户配额检查功能
"""

from dataclasses import dataclass
from typing import Any

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tenant.tenant import Tenant
from app.models.tenant.tenant_admin import TenantAdmin
from app.models.tenant.tenant_domain import TenantDomain


@dataclass
class QuotaCheckResult:
    """配额检查结果"""
    
    allowed: bool
    """是否允许"""
    
    current: int
    """当前使用量"""
    
    limit: int
    """限制值（0 表示无限制，-1 表示不可用）"""
    
    remaining: int
    """剩余配额"""
    
    message: str | None = None
    """提示信息"""


class QuotaService:
    """
    配额服务
    
    提供租户运行时配额检查功能
    配额优先级：租户覆盖 > 套餐默认
    """
    
    def __init__(self, db: AsyncSession, tenant: Tenant):
        """
        初始化配额服务
        
        Args:
            db: 异步数据库会话
            tenant: 租户实例（需要已加载 tenant_plan 关系）
        """
        self.db = db
        self.tenant = tenant
    
    def get_quota_value(self, key: str, default: int | bool | None = None) -> Any:
        """
        获取租户有效配额值
        
        优先级：租户覆盖 > 套餐默认
        
        Args:
            key: 配额键名
            default: 默认值
        
        Returns:
            配额值
        """
        return self.tenant.get_quota_value(key, default)
    
    def get_feature(self, key: str, default: bool = False) -> bool:
        """
        获取特性开关
        
        Args:
            key: 特性键名
            default: 默认值
        
        Returns:
            特性是否启用
        """
        # 优先从租户级 quota 获取（特性也可以存在 quota 中）
        if self.tenant.quota and key in self.tenant.quota:
            return bool(self.tenant.quota.get(key, default))
        # 其次从套餐 features 获取
        if self.tenant.tenant_plan:
            return self.tenant.tenant_plan.get_feature(key, default)
        return default
    
    def can_use_feature(self, feature_key: str) -> bool:
        """
        检查是否可用某功能
        
        Args:
            feature_key: 功能键名（如 ai_enabled, advanced_analytics）
        
        Returns:
            是否可用
        """
        return self.get_feature(feature_key, False)
    
    async def check_storage_quota(self, additional_bytes: int = 0) -> QuotaCheckResult:
        """
        检查存储配额
        
        Args:
            additional_bytes: 额外需要的字节数
        
        Returns:
            配额检查结果
        """
        limit_gb = self.get_quota_value("storage_limit_gb", 0)
        
        # 0 表示无限制
        if limit_gb == 0:
            return QuotaCheckResult(
                allowed=True,
                current=0,
                limit=0,
                remaining=0,
                message="无存储限制",
            )
        
        # TODO: 从文件服务获取当前存储使用量
        current_bytes = 0  # 需要实现实际的存储统计
        
        limit_bytes = limit_gb * 1024 * 1024 * 1024
        additional_gb = additional_bytes / (1024 * 1024 * 1024)
        remaining = limit_bytes - current_bytes
        
        allowed = (current_bytes + additional_bytes) <= limit_bytes
        
        return QuotaCheckResult(
            allowed=allowed,
            current=int(current_bytes / (1024 * 1024 * 1024)),  # 转为 GB
            limit=limit_gb,
            remaining=max(0, int(remaining / (1024 * 1024 * 1024))),
            message=None if allowed else f"存储空间不足，当前已使用 {current_bytes / (1024 * 1024 * 1024):.2f}GB，限制 {limit_gb}GB",
        )
    
    async def check_user_quota(self, additional: int = 1) -> QuotaCheckResult:
        """
        检查用户数配额
        
        Args:
            additional: 额外需要添加的用户数
        
        Returns:
            配额检查结果
        """
        limit = self.get_quota_value("max_users", 0)
        
        # 0 表示无限制
        if limit == 0:
            return QuotaCheckResult(
                allowed=True,
                current=0,
                limit=0,
                remaining=0,
                message="无用户数限制",
            )
        
        # 统计当前用户数（需要有 TenantUser 模型）
        # TODO: 实现实际的用户统计
        current = 0
        
        remaining = limit - current
        allowed = (current + additional) <= limit
        
        return QuotaCheckResult(
            allowed=allowed,
            current=current,
            limit=limit,
            remaining=max(0, remaining),
            message=None if allowed else f"用户数已达上限 {limit}",
        )
    
    async def check_admin_quota(self, additional: int = 1) -> QuotaCheckResult:
        """
        检查管理员数配额
        
        Args:
            additional: 额外需要添加的管理员数
        
        Returns:
            配额检查结果
        """
        limit = self.get_quota_value("max_admins", 0)
        
        # 0 表示无限制
        if limit == 0:
            return QuotaCheckResult(
                allowed=True,
                current=0,
                limit=0,
                remaining=0,
                message="无管理员数限制",
            )
        
        # 统计当前管理员数
        query = select(func.count(TenantAdmin.id)).where(
            TenantAdmin.tenant_id == self.tenant.id,
            TenantAdmin.is_deleted == False,
        )
        result = await self.db.execute(query)
        current = result.scalar() or 0
        
        remaining = limit - current
        allowed = (current + additional) <= limit
        
        return QuotaCheckResult(
            allowed=allowed,
            current=current,
            limit=limit,
            remaining=max(0, remaining),
            message=None if allowed else f"管理员数已达上限 {limit}",
        )
    
    async def check_domain_quota(self, additional: int = 1) -> QuotaCheckResult:
        """
        检查自定义域名数配额
        
        Args:
            additional: 额外需要添加的域名数
        
        Returns:
            配额检查结果
        """
        # 先检查是否允许自定义域名
        allow_custom = self.get_quota_value("allow_custom_domain", False)
        if not allow_custom:
            return QuotaCheckResult(
                allowed=False,
                current=0,
                limit=-1,
                remaining=0,
                message="当前套餐不支持自定义域名",
            )
        
        limit = self.get_quota_value("max_custom_domains", 0)
        
        # 0 表示无限制
        if limit == 0:
            return QuotaCheckResult(
                allowed=True,
                current=0,
                limit=0,
                remaining=0,
                message="无域名数限制",
            )
        
        # 统计当前自定义域名数（排除主域名/子域名）
        query = select(func.count(TenantDomain.id)).where(
            TenantDomain.tenant_id == self.tenant.id,
            TenantDomain.is_deleted == False,
            TenantDomain.is_primary == False,  # 仅统计自定义域名
        )
        result = await self.db.execute(query)
        current = result.scalar() or 0
        
        remaining = limit - current
        allowed = (current + additional) <= limit
        
        return QuotaCheckResult(
            allowed=allowed,
            current=current,
            limit=limit,
            remaining=max(0, remaining),
            message=None if allowed else f"自定义域名数已达上限 {limit}",
        )
    
    async def check_api_calls_quota(self, additional: int = 1) -> QuotaCheckResult:
        """
        检查 API 调用次数配额
        
        Args:
            additional: 额外需要的调用次数
        
        Returns:
            配额检查结果
        """
        limit = self.get_quota_value("api_calls_per_month", 0)
        
        # 0 表示无限制
        if limit == 0:
            return QuotaCheckResult(
                allowed=True,
                current=0,
                limit=0,
                remaining=0,
                message="无 API 调用限制",
            )
        
        # TODO: 从计数服务获取当前月份调用次数
        current = 0
        
        remaining = limit - current
        allowed = (current + additional) <= limit
        
        return QuotaCheckResult(
            allowed=allowed,
            current=current,
            limit=limit,
            remaining=max(0, remaining),
            message=None if allowed else f"本月 API 调用次数已达上限 {limit}",
        )
    
    def check_file_size(self, file_size_bytes: int) -> QuotaCheckResult:
        """
        检查文件大小限制
        
        Args:
            file_size_bytes: 文件大小（字节）
        
        Returns:
            配额检查结果
        """
        limit_mb = self.get_quota_value("max_file_size_mb", 0)
        
        # 0 表示无限制
        if limit_mb == 0:
            return QuotaCheckResult(
                allowed=True,
                current=0,
                limit=0,
                remaining=0,
                message="无文件大小限制",
            )
        
        file_size_mb = file_size_bytes / (1024 * 1024)
        allowed = file_size_mb <= limit_mb
        
        return QuotaCheckResult(
            allowed=allowed,
            current=int(file_size_mb),
            limit=limit_mb,
            remaining=max(0, int(limit_mb - file_size_mb)),
            message=None if allowed else f"文件大小超出限制 {limit_mb}MB",
        )
    
    def get_all_quotas(self) -> dict[str, Any]:
        """
        获取所有配额配置
        
        Returns:
            配额配置字典
        """
        quota_keys = [
            "storage_limit_gb",
            "max_users",
            "max_admins",
            "max_custom_domains",
            "allow_custom_domain",
            "api_calls_per_month",
            "max_file_size_mb",
        ]
        
        result = {}
        for key in quota_keys:
            result[key] = self.get_quota_value(key, 0)
        
        return result
    
    def get_all_features(self) -> dict[str, bool]:
        """
        获取所有特性开关
        
        Returns:
            特性开关字典
        """
        feature_keys = [
            "ai_enabled",
            "advanced_analytics",
            "white_label",
            "priority_support",
        ]
        
        result = {}
        for key in feature_keys:
            result[key] = self.get_feature(key, False)
        
        return result


__all__ = ["QuotaService", "QuotaCheckResult"]
