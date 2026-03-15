"""
Conversation Complexity Classifier / 对话复杂度分类器

Pure synchronous computation logic, no I/O operations, no AI calls, call time < 1ms.
Used for request classification in multi-model routing strategies.
纯同步计算逻辑，无 IO 操作，无 AI 调用，调用时间 < 1ms
用于多模型路由策略中的请求分级
"""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING

from app.core.logging import LogManager

if TYPE_CHECKING:
    from app.ai.types import ChatMessage

logger = LogManager.get_logger("ai.routing")

# ==================== Keyword Scoring Rules / 关键词评分规则 ====================

_KEYWORDS_SCORE_2: frozenset[str] = frozenset({
    "分析", "推理", "规划", "代码", "编写", "实现", "设计", "对比",
    "analyze", "analysis", "reasoning", "planning", "code", "implement",
    "design", "compare",
})

_KEYWORDS_SCORE_1: frozenset[str] = frozenset({
    "综合", "总结多", "评估", "证明", "数学", "公式",
    "synthesize", "summarize", "evaluate", "prove", "math", "formula",
    "complex", "sophisticated",
})

_TURNS_THRESHOLD_MEDIUM = 10
_TURNS_THRESHOLD_COMPLEX = 20
_LONG_MESSAGE_CHARS = 500
_TOOLS_THRESHOLD = 5
_TOOLS_SCORE = 2


class ComplexityLevel(str, Enum):
    """Conversation complexity level / 对话复杂度级别"""

    SIMPLE = "simple"
    MEDIUM = "medium"
    COMPLEX = "complex"


class ComplexityClassifier:
    """
    Conversation Complexity Classifier
    对话复杂度分类器

    Evaluates conversation complexity based on message turns, message length, keywords, tool count, and attachments.
    基于消息轮数、消息长度、关键词、工具数量和附件评估对话复杂度。

    Scoring rules / 评分规则：
    - Message turns > 10: +2 / 消息轮数 > 10：+2 分
    - Latest user message > 500 chars: +1 / 最新用户消息 > 500 字符：+1 分
    - Message contains +2 keywords (analyze/reasoning/code/...): +2
      消息含 +2 关键词（分析/推理/代码/analyze/reasoning/...）：+2 分
    - Message contains +1 keywords (synthesize/evaluate/math/...): +1
      消息含 +1 关键词（综合/评估/数学/synthesize/evaluate/...）：+1 分
    - Tool count > 5: +2 / 工具数量 > 5：+2 分
    - Message turns > 20: additional +1 / 消息轮数 > 20：额外 +1 分
    - Has attachments (images, etc.): auto-elevated to MEDIUM or higher
      有附件（图片等）：自动升为 MEDIUM 及以上

    Levels: 0-1 → SIMPLE, 2-3 → MEDIUM, 4+ → COMPLEX
    分级：0-1 → SIMPLE，2-3 → MEDIUM，4+ → COMPLEX
    """

    def classify(
        self,
        messages: list[ChatMessage],
        tools: list | None = None,
        has_attachments: bool = False,
    ) -> ComplexityLevel:
        """
        Classify conversation complexity
        对话复杂度分类

        Args:
            messages: List of chat messages / 对话消息列表
            tools: List of available tools (optional) / 可用工具列表（可选）
            has_attachments: Whether there are attachments (images, etc.) / 是否含附件（图片等）

        Returns:
            ComplexityLevel enum value / ComplexityLevel 枚举值
        """
        score = self._compute_score(messages, tools)
        level = self._score_to_level(score)

        if has_attachments:
            level = self._elevate_for_attachments(level)

        logger.debug(
            "ComplexityClassifier: score=%d level=%s turns=%d tools=%d attachments=%s",
            score,
            level.value,
            len(messages),
            len(tools) if tools else 0,
            has_attachments,
        )

        return level

    # ==================== Internal Scoring Logic / 内部评分逻辑 ====================

    def _compute_score(
        self,
        messages: list[ChatMessage],
        tools: list | None,
    ) -> int:
        score = 0
        turn_count = self._get_turn_count(messages)

        if turn_count > _TURNS_THRESHOLD_MEDIUM:
            score += 2

        if turn_count > _TURNS_THRESHOLD_COMPLEX:
            score += 1

        latest_user_content = self._get_latest_user_content(messages)
        if len(latest_user_content) > _LONG_MESSAGE_CHARS:
            score += 1

        all_content = self._get_all_user_content(messages)
        content_lower = all_content.lower()

        if self._contains_any(content_lower, all_content, _KEYWORDS_SCORE_2):
            score += 2

        if self._contains_any(content_lower, all_content, _KEYWORDS_SCORE_1):
            score += 1

        if tools and len(tools) > _TOOLS_THRESHOLD:
            score += _TOOLS_SCORE

        return score

    @staticmethod
    def _score_to_level(score: int) -> ComplexityLevel:
        if score >= 4:
            return ComplexityLevel.COMPLEX
        if score >= 2:
            return ComplexityLevel.MEDIUM
        return ComplexityLevel.SIMPLE

    @staticmethod
    def _elevate_for_attachments(level: ComplexityLevel) -> ComplexityLevel:
        """Elevate to at least MEDIUM when attachments are present / 有附件时至少升为 MEDIUM"""
        if level == ComplexityLevel.SIMPLE:
            return ComplexityLevel.MEDIUM
        return level

    @staticmethod
    def _get_latest_user_content(messages: list[ChatMessage]) -> str:
        for msg in reversed(messages):
            if msg.role == "user":
                return msg.content or ""
        return ""

    @staticmethod
    def _get_turn_count(messages: list[ChatMessage]) -> int:
        """Count conversation turns only when user intent exists. / 仅在用户意图存在时计算对话轮数。"""
        if not any(msg.role == "user" for msg in messages):
            return 0
        return len(messages)

    @staticmethod
    def _get_all_user_content(messages: list[ChatMessage]) -> str:
        return " ".join(
            msg.content or ""
            for msg in messages
            if msg.role == "user"
        )

    @staticmethod
    def _contains_any(
        content_lower: str,
        content_original: str,
        keywords: frozenset[str],
    ) -> bool:
        for kw in keywords:
            if kw.isascii():
                if kw in content_lower:
                    return True
            else:
                if kw in content_original:
                    return True
        return False


__all__ = ["ComplexityClassifier", "ComplexityLevel"]
