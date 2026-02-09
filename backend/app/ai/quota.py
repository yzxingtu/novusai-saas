"""
AI 调用配额管理服务

管理租户的 Token 配额、月度预算和使用量追踪
"""

from typing import Optional
from datetime import date, datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.core.redis import get_redis
from app.core.logging import LogManager
from app.core.i18n import _
from app.services.ai import MeteringService
from app.models.ai.tenant_quota import TenantQuota
from app.enums.ai import QuotaTypeEnum, QuotaPeriodEnum


logger = LogManager.get_logger("ai.quota")


class QuotaExceeded(Exception):
    """配额超出异常"""
    pass


class UsageTracker:
    """
    使用量追踪器
    
    使用 Redis 实时追踪 Token 使用量,防止超额
    """
    
    PREFIX_DAILY = "ai:usage:daily:"
    PREFIX_MONTHLY = "ai:usage:monthly:"
    
    @staticmethod
    def _get_key(prefix: str, tenant_id: int, model_id: int, date_key: str) -> str:
        """生成 Redis 键"""
        return f"{prefix}{tenant_id}:{model_id}:{date_key}"
    
    @staticmethod
    async def get_daily_usage(
        tenant_id: int,
        model_id: int,
        stat_date: Optional[date] = None
    ) -> int:
        """
        获取当日 Token 使用量
        
        Args:
            tenant_id: 租户 ID
            model_id: 模型 ID
            stat_date: 统计日期,默认今天
            
        Returns:
            Token 使用量
        """
        redis = await get_redis()
        stat_date = stat_date or date.today()
        key = UsageTracker._get_key(UsageTracker.PREFIX_DAILY, tenant_id, model_id, stat_date.isoformat())
        
        value = await redis.get(key)
        return int(value) if value else 0
    
    @staticmethod
    async def get_monthly_usage(
        tenant_id: int,
        model_id: int,
        year: Optional[int] = None,
        month: Optional[int] = None
    ) -> int:
        """
        获取当月 Token 使用量
        
        Args:
            tenant_id: 租户 ID
            model_id: 模型 ID
            year: 年份,默认当前年
            month: 月份,默认当前月
            
        Returns:
            Token 使用量
        """
        redis = await get_redis()
        today = date.today()
        year = year or today.year
        month = month or today.month
        
        key = UsageTracker._get_key(
            UsageTracker.PREFIX_MONTHLY,
            tenant_id,
            model_id,
            f"{year}-{month:02d}"
        )
        
        value = await redis.get(key)
        return int(value) if value else 0
    
    @staticmethod
    async def record_usage(
        tenant_id: int,
        model_id: int,
        tokens: int,
        stat_date: Optional[date] = None
    ):
        """
        记录 Token 使用量
        
        Args:
            tenant_id: 租户 ID
            model_id: 模型 ID
            tokens: Token 数量
            stat_date: 统计日期
        """
        redis = await get_redis()
        stat_date = stat_date or date.today()
        
        # 记录每日使用量
        daily_key = UsageTracker._get_key(
            UsageTracker.PREFIX_DAILY,
            tenant_id,
            model_id,
            stat_date.isoformat()
        )
        await redis.incrby(daily_key, tokens)
        await redis.expire(daily_key, 86400 * 2)  # 保留 2 天
        
        # 记录每月使用量
        monthly_key = UsageTracker._get_key(
            UsageTracker.PREFIX_MONTHLY,
            tenant_id,
            model_id,
            f"{stat_date.year}-{stat_date.month:02d}"
        )
        await redis.incrby(monthly_key, tokens)
        await redis.expire(monthly_key, 86400 * 35)  # 保留 35 天


class QuotaManager:
    """
    配额管理器
    
    检查和执行租户配额限制
    """
    
    def __init__(self, db: AsyncSession):
        """
        初始化配额管理器
        
        Args:
            db: 数据库会话
        """
        self.db = db
        self.metering = MeteringService(db)
    
    async def check_quota(
        self,
        tenant_id: int,
        model_id: int,
        estimated_tokens: int = 0
    ) -> bool:
        """
        检查配额
        
        Args:
            tenant_id: 租户 ID
            model_id: 模型 ID
            estimated_tokens: 预估 Token 数量
            
        Returns:
            True 表示允许调用
            
        Raises:
            QuotaExceeded: 配额超出
        """
        # 获取租户配额配置
        quota = await self._get_tenant_quota(tenant_id, model_id)
        
        if not quota or not quota.is_active:
            # 没有配置配额或配额未激活,允许调用
            return True
        
        # 检查硬限制
        if quota.quota_type == QuotaTypeEnum.HARD.value:
            # 获取当前使用量
            current_usage = await self._get_usage(
                tenant_id,
                model_id,
                quota.period
            )
            
            # 检查是否超出
            if current_usage + estimated_tokens > quota.limit:
                logger.warning(
                    _("ai.log.quota_exceeded"),
                    tenant_id=tenant_id,
                    model_id=model_id,
                    current=current_usage,
                    limit=quota.limit,
                    period=quota.period
                )
                raise QuotaExceeded(
                    _("ai.error.quota_exceeded").format(
                        current=current_usage + estimated_tokens,
                        limit=quota.limit,
                        period=quota.period
                    )
                )
        
        # 检查软限制 - 记录但允许超额
        elif quota.quota_type == QuotaTypeEnum.SOFT.value:
            current_usage = await self._get_usage(
                tenant_id,
                model_id,
                quota.period
            )
            
            if current_usage + estimated_tokens > quota.limit:
                logger.warning(
                    _("ai.log.quota_exceeded_soft"),
                    tenant_id=tenant_id,
                    model_id=model_id,
                    current=current_usage,
                    limit=quota.limit,
                    period=quota.period
                )
                # 软限制允许超额,但记录警告
                # TODO: 发送通知给租户
        
        return True
    
    async def record_usage(
        self,
        tenant_id: int,
        model_id: int,
        tokens: int,
        stat_date: Optional[date] = None
    ):
        """
        记录使用量
        
        Args:
            tenant_id: 租户 ID
            model_id: 模型 ID
            tokens: Token 数量
            stat_date: 统计日期
        """
        await UsageTracker.record_usage(tenant_id, model_id, tokens, stat_date)
    
    async def _get_tenant_quota(
        self,
        tenant_id: int,
        model_id: int
    ) -> Optional[TenantQuota]:
        """
        获取租户配额配置
        
        Args:
            tenant_id: 租户 ID
            model_id: 模型 ID
            
        Returns:
            TenantQuota 实例
        """
        stmt = select(TenantQuota).where(
            and_(
                TenantQuota.tenant_id == tenant_id,
                TenantQuota.model_id == model_id,
                TenantQuota.is_active == True,
                TenantQuota.is_deleted == False,
            )
        ).order_by(TenantQuota.created_at.desc())
        
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()
    
    async def _get_usage(
        self,
        tenant_id: int,
        model_id: int,
        period: str
    ) -> int:
        """
        获取使用量
        
        Args:
            tenant_id: 租户 ID
            model_id: 模型 ID
            period: 周期(daily/monthly)
            
        Returns:
            Token 使用量
        """
        today = date.today()
        
        if period == QuotaPeriodEnum.DAILY.value:
            return await UsageTracker.get_daily_usage(tenant_id, model_id, today)
        elif period == QuotaPeriodEnum.MONTHLY.value:
            return await UsageTracker.get_monthly_usage(
                tenant_id,
                model_id,
                today.year,
                today.month
            )
        else:
            return 0


__all__ = [
    "UsageTracker",
    "QuotaManager",
    "QuotaExceeded",
]
