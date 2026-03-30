"""ComplexityClassifier 单元测试 / Test.

验证对话复杂度分级逻辑（SIMPLE/MEDIUM/COMPLEX）"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import pytest

# ==================== 轻量 ChatMessage stub ====================


@dataclass
class _Msg:
    """测试用轻量消息对象（避免引入 SQLAlchemy 上下文） / Test."""

    role: Literal["system", "user", "assistant", "tool"]
    content: str
    attachments: list[dict] | None = None


def _user(content: str) -> _Msg:
    return _Msg(role="user", content=content)


def _assistant(content: str) -> _Msg:
    return _Msg(role="assistant", content=content)


# ==================== 测试用例 ====================


@pytest.fixture
def classifier():
    from app.ai.routing.complexity_classifier import ComplexityClassifier
    return ComplexityClassifier()


@pytest.fixture
def ComplexityLevel():
    from app.ai.routing.complexity_classifier import ComplexityLevel as _CL
    return _CL


class TestComplexityClassifierBasic:
    """基础分类用例 / Description."""

    def test_simple_greeting(self, classifier, ComplexityLevel):
        """简单问候 → SIMPLE / → SIMPLE"""
        messages = [_user("你好，今天天气怎么样？")]
        result = classifier.classify(messages)
        assert result == ComplexityLevel.SIMPLE

    def test_simple_short_question(self, classifier, ComplexityLevel):
        """单条短问题 → SIMPLE / → SIMPLE"""
        messages = [_user("什么是机器学习？")]
        result = classifier.classify(messages)
        assert result == ComplexityLevel.SIMPLE

    def test_medium_from_many_user_turns(self, classifier, ComplexityLevel):
        """>10 轮用户消息 → 结构分 +2 → MEDIUM"""
        messages: list = []
        for i in range(11):
            messages.append(_user(f"第{i}问"))
            messages.append(_assistant(f"答{i}"))
        result = classifier.classify(messages)
        assert result == ComplexityLevel.MEDIUM

    def test_simple_single_message_no_structure_boost(self, classifier, ComplexityLevel):
        """单条消息无轮次/长度/工具加成 → SIMPLE"""
        messages = [_user("Can you analyze this SQL query for me?")]
        result = classifier.classify(messages)
        assert result == ComplexityLevel.SIMPLE

    def test_medium_attachment_elevates_simple(self, classifier, ComplexityLevel):
        """有图片附件时，即使评分为 SIMPLE 也自动升为 MEDIUM / ， SIMPLE MEDI..."""
        messages = [_user("这是什么？")]
        result = classifier.classify(messages, has_attachments=True)
        assert result == ComplexityLevel.MEDIUM

    def test_medium_attachment_does_not_lower_complex(self, classifier, ComplexityLevel):
        """有附件时 COMPLEX 不会被降级 / COMPLEX"""
        # 11 user turns (+2) + 6 tools (+2) + long last user msg (+1) = 5 → COMPLEX
        msgs = [_user("你好"), _assistant("好的")] * 10
        long_last = "请详细说明" + "x" * 520
        msgs.append(_user(long_last))
        tools = [{"name": f"t{i}"} for i in range(6)]
        result = classifier.classify(msgs, tools=tools, has_attachments=True)
        assert result == ComplexityLevel.COMPLEX

    def test_complex_long_multi_turn_conversation(self, classifier, ComplexityLevel):
        """多轮（>10）+ 长消息 + 多工具 → COMPLEX"""
        msgs = []
        for i in range(11):
            msgs.append(_user(f"这是第{i + 1}轮问题，内容比较普通"))
            msgs.append(_assistant(f"第{i + 1}轮回答"))
        msgs.append(_user("请总结" + "y" * 520))
        tools = [{"name": f"t{i}"} for i in range(6)]
        result = classifier.classify(msgs, tools=tools)
        assert result == ComplexityLevel.COMPLEX

    def test_complex_many_tools(self, classifier, ComplexityLevel):
        """6个工具 + 超长用户消息（结构分：长消息 + 累积超长）→ COMPLEX"""
        tools = [{"name": f"tool_{i}"} for i in range(6)]
        long_content = "请" + "x" * 8500  # >500 且累积 >8000
        messages = [_user(long_content)]
        result = classifier.classify(messages, tools=tools)
        assert result == ComplexityLevel.COMPLEX

    def test_simple_no_keywords_short_few_turns(self, classifier, ComplexityLevel):
        """3轮短对话、无关键词 → SIMPLE / 3 、 → SIMPLE"""
        msgs = [
            _user("你好"),
            _assistant("您好"),
            _user("今天天气如何"),
        ]
        result = classifier.classify(msgs)
        assert result == ComplexityLevel.SIMPLE

    def test_complex_very_long_multi_turn_and_keywords(self, classifier, ComplexityLevel):
        """>20 轮用户 + 超额轮次加分 → COMPLEX"""
        msgs = []
        for _ in range(21):
            msgs.append(_user("普通问题"))
            msgs.append(_assistant("回答"))
        msgs.append(_user("收尾"))
        # 22 user turns: >20 → +2 +1 = 3; need 4+ → add 6 tools +2 → 5
        tools = [{"name": f"t{i}"} for i in range(6)]
        result = classifier.classify(msgs, tools=tools)
        assert result == ComplexityLevel.COMPLEX


class TestComplexityClassifierEdgeCases:
    """边界用例 / Description."""

    def test_empty_messages(self, classifier, ComplexityLevel):
        """空消息列表 → SIMPLE / → SIMPLE"""
        result = classifier.classify([])
        assert result == ComplexityLevel.SIMPLE

    def test_zero_tools(self, classifier, ComplexityLevel):
        """空工具列表不影响分级 / Description."""
        result = classifier.classify([_user("Hello")], tools=[])
        assert result == ComplexityLevel.SIMPLE

    def test_exactly_threshold_tools(self, classifier, ComplexityLevel):
        """恰好5个工具（不超过阈值）→ 不加分 / 5 （ ）→"""
        tools = [{"name": f"tool_{i}"} for i in range(5)]
        result = classifier.classify([_user("帮我做点事")], tools=tools)
        assert result == ComplexityLevel.SIMPLE

    def test_six_tools_over_threshold(self, classifier, ComplexityLevel):
        """恰好6个工具（超过阈值）→ +2分 / 6 （ ）→ +2"""
        tools = [{"name": f"tool_{i}"} for i in range(6)]
        result = classifier.classify([_user("evaluate this")], tools=tools)
        assert result == ComplexityLevel.MEDIUM

    def test_only_assistant_messages(self, classifier, ComplexityLevel):
        """只有 assistant 消息，无 user 消息 → SIMPLE / assistant ， user → SI..."""
        msgs = [_assistant("你好") for _ in range(15)]
        result = classifier.classify(msgs)
        assert result == ComplexityLevel.SIMPLE

    def test_non_user_messages_do_not_inflate_turn_count(self, classifier, ComplexityLevel):
        """system/tool/assistant 不应抬高轮次评分 / system/tool/assistant must not inflate turn scoring."""
        msgs = [
            _Msg(role="system", content="你是助手"),
            *[_assistant(f"第{i}轮回答") for i in range(12)],
            *[_Msg(role="tool", content=f"tool-{i}") for i in range(12)],
            _user("你好"),
        ]
        result = classifier.classify(msgs)
        assert result == ComplexityLevel.SIMPLE
