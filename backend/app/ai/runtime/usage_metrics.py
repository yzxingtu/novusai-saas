"""
AI usage metrics utilities / AI 用量指标工具

Runtime-shared helpers for token estimation and pricing.
运行时共享的 Token 估算与计费辅助。
"""

from __future__ import annotations

from app.models.ai import AIModel


class TokenCounter:
    """
    Token counter / Token 计数器.

    Uses a lightweight heuristic suitable for quota pre-deduction and routing.
    使用轻量级估算，适用于配额预扣与路由阶段。
    """

    @staticmethod
    def count_text_tokens(text: str) -> int:
        """Estimate token count for text / 估算文本 Token 数量."""
        if not text:
            return 0

        chinese_chars = sum(1 for c in text if "\u4e00" <= c <= "\u9fff")
        other_chars = len(text) - chinese_chars
        tokens = int(chinese_chars * 0.5 + other_chars / 4)
        return max(1, tokens)

    @staticmethod
    def count_messages_tokens(messages: list[dict]) -> int:
        """Estimate token count for message list / 估算消息列表 Token 数量."""
        total = 0
        for message in messages:
            total += 4
            total += TokenCounter.count_text_tokens(str(message.get("content", "")))
            if "name" in message:
                total += TokenCounter.count_text_tokens(str(message["name"]))
        return total

    @staticmethod
    def count_array_tokens(array: list) -> int:
        """Estimate token count for array payloads / 估算数组载荷 Token 数量."""
        return sum(TokenCounter.count_text_tokens(str(item)) for item in array)


class CostCalculator:
    """
    Cost calculator / 费用计算器.
    """

    @staticmethod
    def calculate_cost(
        model: AIModel,
        input_tokens: int,
        output_tokens: int,
    ) -> float:
        """Calculate request cost / 计算调用费用."""
        input_price = float(model.input_price_per_1k or 0)
        output_price = float(model.output_price_per_1k or 0)
        input_cost = (input_tokens / 1000) * input_price
        output_cost = (output_tokens / 1000) * output_price
        return round(input_cost + output_cost, 6)


__all__ = ["TokenCounter", "CostCalculator"]
