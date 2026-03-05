"""
配额服务

提供租户配额检查功能
"""

from dataclasses import dataclass
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.i18n import _
from app.models.tenant.tenant import Tenant
from app.models.tenant.tenant_admin import TenantAdmin
from app.models.tenant.tenant_domain import TenantDomain
from app.models.tenant.tenant_user import TenantUser


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

    async def _lock_tenant_row(self) -> None:
        """
        对租户行加排他锁，序列化同一租户的并发配额检查。

        在同一事务中先锁定再 COUNT，确保 CHECK → INSERT 之间
        不会有其他事务插入同类资源，消除 TOCTOU 竞态。
        锁在事务提交/回滚后自动释放。
        """
        await self.db.execute(
            select(Tenant.id)
            .where(Tenant.id == self.tenant.id)
            .with_for_update()
        )

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

    async def check_storage_quota(
        self,
        additional_bytes: int = 0,
        current_bytes: int | None = None,
    ) -> QuotaCheckResult:
        """
        检查存储配额

        Args:
            additional_bytes: 额外需要的字节数
            current_bytes: 当前已使用字节数（为空则使用默认值）

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
                message=_("quota.no_limit"),
            )

        # 使用传入的存储使用量，未传入则使用默认值
        current_bytes = current_bytes or 0

        limit_bytes = limit_gb * 1024 * 1024 * 1024
        remaining = limit_bytes - current_bytes

        allowed = (current_bytes + additional_bytes) <= limit_bytes

        return QuotaCheckResult(
            allowed=allowed,
            current=int(current_bytes / (1024 * 1024 * 1024)),  # 转为 GB
            limit=limit_gb,
            remaining=max(0, int(remaining / (1024 * 1024 * 1024))),
            message=None if allowed else _("quota.storage_exceeded", current=f"{current_bytes / (1024 * 1024 * 1024):.2f}", limit=limit_gb),
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
                message=_("quota.no_limit"),
            )

        # 锁定租户行，防止并发超额
        await self._lock_tenant_row()

        # 统计当前用户数
        query = select(func.count(TenantUser.id)).where(
            TenantUser.tenant_id == self.tenant.id,
            TenantUser.is_deleted.is_(False),
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
            message=None if allowed else _("quota.users_exceeded", limit=limit),
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
                message=_("quota.no_limit"),
            )

        # 锁定租户行，防止并发超额
        await self._lock_tenant_row()

        # 统计当前管理员数
        query = select(func.count(TenantAdmin.id)).where(
            TenantAdmin.tenant_id == self.tenant.id,
            TenantAdmin.is_deleted.is_(False),
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
            message=None if allowed else _("quota.admins_exceeded", limit=limit),
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
                message=_("quota.custom_domain_not_supported"),
            )

        limit = self.get_quota_value("max_custom_domains", 0)

        # 0 表示无限制
        if limit == 0:
            return QuotaCheckResult(
                allowed=True,
                current=0,
                limit=0,
                remaining=0,
                message=_("quota.no_limit"),
            )

        # 锁定租户行，防止并发超额
        await self._lock_tenant_row()

        # 统计当前自定义域名数（排除主域名/子域名）
        query = select(func.count(TenantDomain.id)).where(
            TenantDomain.tenant_id == self.tenant.id,
            TenantDomain.is_deleted.is_(False),
            TenantDomain.is_primary.is_(False),  # 仅统计自定义域名
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
            message=None if allowed else _("quota.domains_exceeded", limit=limit),
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
                message=_("quota.no_limit"),
            )

        # 从 AI 调用日志统计当月调用次数
        from app.core.base_model import utc_now
        now = utc_now()
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        from app.models.ai.call_log import AICallLog
        query = select(func.count(AICallLog.id)).where(
            AICallLog.tenant_id == self.tenant.id,
            AICallLog.created_at >= month_start,
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
            message=None if allowed else _("quota.api_calls_exceeded", limit=limit),
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
                message=_("quota.no_limit"),
            )

        file_size_mb = file_size_bytes / (1024 * 1024)
        allowed = file_size_mb <= limit_mb

        return QuotaCheckResult(
            allowed=allowed,
            current=int(file_size_mb),
            limit=limit_mb,
            remaining=max(0, int(limit_mb - file_size_mb)),
            message=None if allowed else _("quota.file_size_exceeded", limit=limit_mb),
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


    @classmethod
    async def check_api_quota_for_tenant_id(
        cls,
        db: AsyncSession,
        tenant_id: int,
    ) -> "QuotaCheckResult":
        """
        通过 tenant_id 检查月 API 调用次数配额（内部加载 Tenant + Plan）

        专供 ExecutionDispatcher 等无法预加载 Tenant 的调用方使用，
        避免在 Dispatcher 层写内联 SQL。

        Args:
            db: 数据库会话
            tenant_id: 租户 ID

        Returns:
            QuotaCheckResult（无限制时 allowed=True）
        """
        from sqlalchemy.orm import selectinload

        from app.models.tenant.tenant import Tenant

        tenant_obj = (
            await db.execute(
                select(Tenant)
                .options(selectinload(Tenant.tenant_plan))
                .where(Tenant.id == tenant_id)
            )
        ).scalar_one_or_none()

        if not tenant_obj:
            return QuotaCheckResult(allowed=True, current=0, limit=0, remaining=0)

        svc = cls(db, tenant_obj)
        return await svc.check_api_calls_quota()


__all__ = ["QuotaService", "QuotaCheckResult"]
