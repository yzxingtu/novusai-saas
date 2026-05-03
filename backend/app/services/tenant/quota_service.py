"""
配额服务 / Quota Service

提供企业配额检查功能
Provides tenant quota checking functionality.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.configs.service import ConfigService
from app.core.base_model import utc_now
from app.core.config import settings
from app.core.i18n import _
from app.core.redis import get_redis
from app.models.tenant.tenant import Tenant
from app.models.tenant.tenant_admin import TenantAdmin
from app.models.tenant.tenant_domain import TenantDomain
from app.models.tenant.tenant_user import TenantUser


@dataclass
class QuotaCheckResult:
    """配额检查结果 / Quota check result."""

    allowed: bool
    """是否允许 / Whether allowed."""

    current: int
    """当前使用量 / Current usage."""

    limit: int
    """限制值（0 表示无限制，-1 表示不可用） / Limit (0=unlimited, -1=unavailable)."""

    remaining: int
    """剩余配额 / Remaining quota."""

    message: str | None = None
    """提示信息 / Message."""


class QuotaService:
    """
    配额服务 / Quota service.

    提供企业运行时配额检查功能；配额优先级：企业覆盖 > 套餐默认。
    Provides tenant runtime quota checks; priority: tenant override > plan default.
    """

    API_CALLS_MONTHLY_PREFIX = "quota:api_calls:monthly:"
    _API_CALLS_CHECK_AND_RECORD_LUA = """
    local current = tonumber(redis.call('GET', KEYS[1]) or '0')
    if current + tonumber(ARGV[1]) > tonumber(ARGV[2]) then
        return current
    end
    redis.call('INCRBY', KEYS[1], ARGV[1])
    redis.call('EXPIRE', KEYS[1], tonumber(ARGV[3]))
    return -1
    """

    def __init__(self, db: AsyncSession, tenant: Tenant):
        """
        初始化配额服务 / Initialize quota service.

        Args:
            db: 异步数据库会话
            tenant: 企业实例（需要已加载 tenant_plan 关系）
        """
        self.db = db
        self.tenant = tenant

    @classmethod
    def _build_api_calls_month_key(cls, tenant_id: int, now: datetime) -> str:
        return f"{cls.API_CALLS_MONTHLY_PREFIX}{tenant_id}:{now.year}-{now.month:02d}"

    @staticmethod
    def _build_api_calls_month_ttl(now: datetime) -> int:
        next_month = (now.replace(day=28) + timedelta(days=4)).replace(
            day=1,
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
        )
        return max(int((next_month - now).total_seconds()) + 86400, 86400)

    async def _count_current_month_api_calls_from_db(
        self, month_start: datetime
    ) -> int:
        from app.models.ai.call_log import AICallLog

        query = select(func.count(AICallLog.id)).where(
            AICallLog.tenant_id == self.tenant.id,
            AICallLog.created_at >= month_start,
        )
        result = await self.db.execute(query)
        return int(result.scalar() or 0)

    async def _get_or_seed_api_calls_counter(
        self,
        *,
        now: datetime,
    ) -> tuple[Any, str, int, int]:
        redis = await get_redis()
        key = self._build_api_calls_month_key(self.tenant.id, now)
        ttl_seconds = self._build_api_calls_month_ttl(now)
        raw = await redis.get(key)
        if raw is not None:
            return redis, key, int(raw), ttl_seconds

        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        seeded_count = await self._count_current_month_api_calls_from_db(month_start)
        created = await redis.setnx(key, seeded_count)
        if created:
            await redis.expire(key, ttl_seconds)
            return redis, key, seeded_count, ttl_seconds

        raw_after = await redis.get(key)
        return (
            redis,
            key,
            int(raw_after) if raw_after is not None else seeded_count,
            ttl_seconds,
        )

    async def _get_domain_suffix(self) -> str:
        """
        获取平台域名后缀 / Get platform domain suffix.

        优先从平台配置读取，回退到环境变量
        """
        config_svc = ConfigService(self.db)
        suffix = await config_svc.get_platform_config(
            "tenant_domain_suffix",
            default=settings.TENANT_DOMAIN_SUFFIX,
        )
        return suffix or settings.TENANT_DOMAIN_SUFFIX

    async def _lock_tenant_row(self) -> None:
        """
        对企业行加排他锁，序列化同一企业的并发配额检查 / Lock tenant row for exclusive quota check.

        在同一事务中先锁定再 COUNT，确保 CHECK → INSERT 之间
        不会有其他事务插入同类资源，消除 TOCTOU 竞态。
        锁在事务提交/回滚后自动释放。
        """
        await self.db.execute(
            select(Tenant.id).where(Tenant.id == self.tenant.id).with_for_update()
        )

    def get_quota_value(self, key: str, default: int | bool | None = None) -> Any:
        """
        获取企业有效配额值 / Get effective quota value for tenant.

        优先级：企业覆盖 > 套餐默认

        Args:
            key: 配额键名
            default: 默认值

        Returns:
            配额值
        """
        return self.tenant.get_quota_value(key, default)

    def _has_active_plan(self) -> bool:
        """Whether this tenant has an active subscription plan loaded."""
        has_active_plan = getattr(self.tenant, "has_active_plan", None)
        if isinstance(has_active_plan, bool):
            return has_active_plan
        if not bool(getattr(self.tenant, "is_active", True)):
            return False
        if bool(getattr(self.tenant, "is_deleted", False)):
            return False
        plan_id = getattr(self.tenant, "plan_id", None)
        plan = getattr(self.tenant, "tenant_plan", None)
        return (
            plan_id is not None
            and plan is not None
            and bool(getattr(plan, "is_active", False))
        )

    @staticmethod
    def _plan_unavailable_result() -> QuotaCheckResult:
        return QuotaCheckResult(
            allowed=False,
            current=0,
            limit=-1,
            remaining=0,
            message=_("tenant_plan.not_found"),
        )

    def get_feature(self, key: str, default: bool = False) -> bool:
        """
        获取特性开关 / Get feature flag.

        Args:
            key: 特性键名
            default: 默认值

        Returns:
            特性是否启用
        """
        if not self._has_active_plan():
            return False
        # 优先从企业级 quota 获取（特性也可以存在 quota 中）
        if self.tenant.quota and key in self.tenant.quota:
            return bool(self.tenant.quota.get(key, default))
        # 其次从套餐 features 获取
        if self.tenant.tenant_plan:
            return self.tenant.tenant_plan.get_feature(key, default)
        return default

    def can_use_feature(self, feature_key: str) -> bool:
        """
        检查是否可用某功能 / Check if feature is enabled.

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
        检查存储配额 / Check storage quota.

        Args:
            additional_bytes: 额外需要的字节数
            current_bytes: 当前已使用字节数（为空则使用默认值）

        Returns:
            配额检查结果
        """
        if not self._has_active_plan():
            return self._plan_unavailable_result()

        limit_gb = self.get_quota_value("storage_limit_gb", 0)

        # 0 表示无限制 / Zero means unlimited
        if limit_gb == 0:
            return QuotaCheckResult(
                allowed=True,
                current=0,
                limit=0,
                remaining=0,
                message=_("quota.no_limit"),
            )

        # 使用传入的存储使用量，未传入则使用默认值 / Use passed storage usage; default if omitted
        current_bytes = current_bytes or 0

        limit_bytes = limit_gb * 1024 * 1024 * 1024
        remaining = limit_bytes - current_bytes

        allowed = (current_bytes + additional_bytes) <= limit_bytes

        return QuotaCheckResult(
            allowed=allowed,
            current=int(current_bytes / (1024 * 1024 * 1024)),  # 转为 GB
            limit=limit_gb,
            remaining=max(0, int(remaining / (1024 * 1024 * 1024))),
            message=None
            if allowed
            else _(
                "quota.storage_exceeded",
                current=f"{current_bytes / (1024 * 1024 * 1024):.2f}",
                limit=limit_gb,
            ),
        )

    async def check_user_quota(self, additional: int = 1) -> QuotaCheckResult:
        """
        检查用户数配额 / Check user count quota.

        Args:
            additional: 额外需要添加的用户数

        Returns:
            配额检查结果
        """
        if not self._has_active_plan():
            return self._plan_unavailable_result()

        limit = self.get_quota_value("max_users", 0)

        # 0 表示无限制 / Zero means unlimited
        if limit == 0:
            return QuotaCheckResult(
                allowed=True,
                current=0,
                limit=0,
                remaining=0,
                message=_("quota.no_limit"),
            )

        # 锁定企业行，防止并发超额 / Lock tenant row to prevent concurrent over-allot
        await self._lock_tenant_row()

        # 统计当前用户数 / Count current users
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
        检查管理员数配额 / Check admin count quota.

        Args:
            additional: 额外需要添加的管理员数

        Returns:
            配额检查结果
        """
        if not self._has_active_plan():
            return self._plan_unavailable_result()

        limit = self.get_quota_value("max_admins", 0)

        # 0 表示无限制 / Zero means unlimited
        if limit == 0:
            return QuotaCheckResult(
                allowed=True,
                current=0,
                limit=0,
                remaining=0,
                message=_("quota.no_limit"),
            )

        # 锁定企业行，防止并发超额 / Lock tenant row to prevent concurrent over-allot
        await self._lock_tenant_row()

        # 统计当前管理员数 / Count current admins
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
        检查自定义域名数配额 / Check custom domain count quota.

        Args:
            additional: 额外需要添加的域名数

        Returns:
            配额检查结果
        """
        if not self._has_active_plan():
            return self._plan_unavailable_result()

        # 先检查是否允许自定义域名 / Check custom domain allowed first
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

        # 0 表示无限制 / Zero means unlimited
        if limit == 0:
            return QuotaCheckResult(
                allowed=True,
                current=0,
                limit=0,
                remaining=0,
                message=_("quota.no_limit"),
            )

        # 锁定企业行，防止并发超额 / Lock tenant row to prevent concurrent over-allot
        await self._lock_tenant_row()

        # 获取平台域名后缀，用于区分默认域名和自定义域名 / Fetch platform domain suffix to tell default vs custom
        suffix = await self._get_domain_suffix()

        # 统计当前自定义域名数（排除默认域名，按后缀判断） / Count custom domains (exclude default by suffix)
        query = select(func.count(TenantDomain.id)).where(
            TenantDomain.tenant_id == self.tenant.id,
            TenantDomain.is_deleted.is_(False),
            ~TenantDomain.domain.endswith(suffix),
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
        检查 API 调用次数配额 / Check API calls quota.

        Args:
            additional: 额外需要的调用次数

        Returns:
            配额检查结果
        """
        if not self._has_active_plan():
            return self._plan_unavailable_result()

        limit = self.get_quota_value("api_calls_per_month", 0)

        # 0 表示无限制 / Zero means unlimited
        if limit == 0:
            return QuotaCheckResult(
                allowed=True,
                current=0,
                limit=0,
                remaining=0,
                message=_("quota.no_limit"),
            )

        now = utc_now()
        redis, key, current, ttl_seconds = await self._get_or_seed_api_calls_counter(
            now=now
        )

        if additional <= 0:
            remaining = limit - current
            return QuotaCheckResult(
                allowed=current <= limit,
                current=current,
                limit=limit,
                remaining=max(0, remaining),
                message=None
                if current <= limit
                else _("quota.api_calls_exceeded", limit=limit),
            )

        result = await redis.eval(
            self._API_CALLS_CHECK_AND_RECORD_LUA,
            1,
            key,
            str(additional),
            str(limit),
            str(ttl_seconds),
        )
        allowed = int(result) < 0
        if not allowed:
            current = int(result)

        remaining = limit - current

        return QuotaCheckResult(
            allowed=allowed,
            current=current,
            limit=limit,
            remaining=max(0, remaining),
            message=None if allowed else _("quota.api_calls_exceeded", limit=limit),
        )

    def check_file_size(self, file_size_bytes: int) -> QuotaCheckResult:
        """
        检查文件大小限制 / Check file size limit.

        Args:
            file_size_bytes: 文件大小（字节）

        Returns:
            配额检查结果
        """
        if not self._has_active_plan():
            return self._plan_unavailable_result()

        limit_mb = self.get_quota_value("max_file_size_mb", 0)

        # 0 表示无限制 / Zero means unlimited
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
        获取所有配额配置 / Get all quota config.

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
        获取所有特性开关 / Get all feature flags.

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
        通过 tenant_id 检查月 API 调用次数配额（内部加载 Tenant + Plan）/ Check monthly API quota by tenant_id (loads Tenant + Plan internally).

        专供 ExecutionDispatcher 等无法预加载 Tenant 的调用方使用，
        避免在 Dispatcher 层写内联 SQL。

        Args:
            db: 数据库会话
            tenant_id: 企业 ID

        Returns:
            QuotaCheckResult（无限制时 allowed=True）
        """
        from sqlalchemy.orm import selectinload

        from app.models.tenant.tenant import Tenant

        tenant_obj = (
            await db.execute(
                select(Tenant)
                .options(selectinload(Tenant.tenant_plan))
                .where(
                    Tenant.id == tenant_id,
                    Tenant.is_active.is_(True),
                    Tenant.is_deleted.is_(False),
                )
            )
        ).scalar_one_or_none()

        if not tenant_obj:
            return cls._plan_unavailable_result()

        svc = cls(db, tenant_obj)
        return await svc.check_api_calls_quota()


__all__ = ["QuotaService", "QuotaCheckResult"]
