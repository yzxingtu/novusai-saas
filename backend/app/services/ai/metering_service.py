"""
AI 计量计费服务

实现 Token 计数、费用计算、使用量统计等功能
"""

from datetime import date
from typing import Optional

from app.core.base_service import GlobalService
from app.core.logging import LogManager
from app.core.i18n import _
from app.models.ai import AIModel, UsageStat
from app.repositories.ai.usage_stat_repository import UsageStatRepository


logger = LogManager.get_logger("ai.metering")


class TokenCounter:
    """
    Token 计数器

    提供通用的 Token 计数功能
    """

    @staticmethod
    def count_text_tokens(text: str) -> int:
        """
        估算文本的 Token 数量

        使用简化算法:英文约 4 字符/token,中文约 2 字符/token
        """
        if not text:
            return 0

        chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
        other_chars = len(text) - chinese_chars

        tokens = int(chinese_chars * 0.5 + other_chars / 4)
        return max(1, tokens)

    @staticmethod
    def count_messages_tokens(messages: list[dict]) -> int:
        """
        估算消息列表的 Token 数量
        """
        total = 0
        for message in messages:
            total += 4
            content = message.get("content", "")
            total += TokenCounter.count_text_tokens(content)
            if "name" in message:
                total += TokenCounter.count_text_tokens(message["name"])
        return total

    @staticmethod
    def count_array_tokens(array: list) -> int:
        """
        估算数组的 Token 数量 (用于 embeddings 等)
        """
        return sum(TokenCounter.count_text_tokens(str(item)) for item in array)


class CostCalculator:
    """
    费用计算器

    根据模型定价计算费用
    """

    @staticmethod
    def calculate_cost(
        model: AIModel,
        input_tokens: int,
        output_tokens: int,
    ) -> float:
        """
        计算调用费用
        """
        input_price = float(model.input_price_per_1k or 0)
        output_price = float(model.output_price_per_1k or 0)

        input_cost = (input_tokens / 1000) * input_price
        output_cost = (output_tokens / 1000) * output_price
        total_cost = input_cost + output_cost

        return round(total_cost, 6)


class MeteringService(GlobalService[UsageStat, UsageStatRepository]):
    """
    计量计费服务

    提供统一的计量计费接口
    """

    model = UsageStat
    repository_class = UsageStatRepository

    async def record_usage(
        self,
        tenant_id: int,
        model_id: int,
        request_type: str,
        input_tokens: int,
        output_tokens: int,
        cost: float,
        success: bool = True,
        user_id: Optional[int] = None,
        latency_ms: Optional[int] = None,
    ):
        """
        记录使用量
        """
        stat_date = date.today()

        try:
            tenant_stat = await self.repo.get_or_create_stat(
                tenant_id=tenant_id,
                model_id=model_id,
                request_type=request_type,
                stat_date=stat_date,
                user_id=None,
            )

            tenant_stat.increment(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost=cost,
                success=success,
                latency_ms=latency_ms,
            )

            if user_id:
                user_stat = await self.repo.get_or_create_stat(
                    tenant_id=tenant_id,
                    model_id=model_id,
                    request_type=request_type,
                    stat_date=stat_date,
                    user_id=user_id,
                )

                user_stat.increment(
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    cost=cost,
                    success=success,
                    latency_ms=latency_ms,
                )

            await self.db.flush()

            logger.info(
                _("ai.log.usage_recorded"),
                tenant_id=tenant_id,
                user_id=user_id,
                model_id=model_id,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost=cost,
            )

        except Exception as e:
            logger.error(_("ai.error.record_usage_failed"), error=str(e))
            await self.db.rollback()
            raise

    async def get_tenant_usage(
        self,
        tenant_id: int,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> dict:
        """
        获取租户使用量
        """
        return await self.repo.get_tenant_usage_summary(
            tenant_id=tenant_id,
            start_date=start_date,
            end_date=end_date,
        )

    async def get_user_usage(
        self,
        tenant_id: int,
        user_id: int,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> dict:
        """
        获取用户使用量
        """
        return await self.repo.get_user_usage_summary(
            tenant_id=tenant_id,
            user_id=user_id,
            start_date=start_date,
            end_date=end_date,
        )

    async def get_model_usage(
        self,
        model_id: int,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> dict:
        """
        获取模型使用量
        """
        return await self.repo.get_model_usage_summary(
            model_id=model_id,
            start_date=start_date,
            end_date=end_date,
        )


__all__ = [
    "TokenCounter",
    "CostCalculator",
    "MeteringService",
]
