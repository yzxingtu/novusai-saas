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

    def test_medium_chinese_keyword_analyze(self, classifier, ComplexityLevel):
        """含中文「分析」关键词 → MEDIUM / 「 」 → MEDIUM"""
        messages = [_user("请分析这段代码的性能问题。")]
        result = classifier.classify(messages)
        assert result == ComplexityLevel.MEDIUM

    def test_medium_english_keyword_analyze(self, classifier, ComplexityLevel):
        """含英文 analyze 关键词 → MEDIUM / analyze → MEDIUM"""
        messages = [_user("Can you analyze this SQL query for me?")]
        result = classifier.classify(messages)
        assert result == ComplexityLevel.MEDIUM

    def test_medium_attachment_elevates_simple(self, classifier, ComplexityLevel):
        """有图片附件时，即使评分为 SIMPLE 也自动升为 MEDIUM / ， SIMPLE MEDI..."""
        messages = [_user("这是什么？")]
        result = classifier.classify(messages, has_attachments=True)
        assert result == ComplexityLevel.MEDIUM

    def test_medium_attachment_does_not_lower_complex(self, classifier, ComplexityLevel):
        """有附件时 COMPLEX 不会被降级 / COMPLEX"""
        # 11 轮消息 + 含「分析」关键词 → 2+2=4分 → COMPLEX
        msgs = [_user("你好"), _assistant("好的")]  * 5 + [_user("请分析并对比这两个方案的区别")]
        result = classifier.classify(msgs, has_attachments=True)
        assert result == ComplexityLevel.COMPLEX

    def test_complex_long_multi_turn_conversation(self, classifier, ComplexityLevel):
        """多轮（>10）长对话 → COMPLEX / （>10） → COMPLEX"""
        # 构建 11 轮对话：2分（轮数>10）+ 1分（长消息）= 3分... 还需要1分
        # 让第12条消息包含「推理」关键词 → 3+2=5分 → COMPLEX
        msgs = []
        for i in range(11):
            msgs.append(_user(f"这是第{i + 1}轮问题，内容比较普通"))
            msgs.append(_assistant(f"第{i + 1}轮回答"))
        msgs.append(_user("请对这11轮对话进行推理分析"))
        result = classifier.classify(msgs)
        assert result == ComplexityLevel.COMPLEX

    def test_complex_many_tools(self, classifier, ComplexityLevel):
        """6个工具 + 长消息 → COMPLEX / 6 + → COMPLEX"""
        tools = [{"name": f"tool_{i}"} for i in range(6)]
        long_content = "请" + "帮我实现一个复杂的数据处理管道，" * 30  # > 500 chars
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

    def test_medium_english_reasoning_keyword(self, classifier, ComplexityLevel):
        """英文 reasoning 关键词 → MEDIUM / reasoning → MEDIUM"""
        messages = [_user("Let me explain my reasoning for this approach.")]
        result = classifier.classify(messages)
        assert result == ComplexityLevel.MEDIUM

    def test_complex_very_long_multi_turn_and_keywords(self, classifier, ComplexityLevel):
        """>20轮对话 + 关键词 → COMPLEX（额外1分） / >20 + → COMPLEX（ 1 ）"""
        msgs = []
        for _ in range(21):
            msgs.append(_user("普通问题"))
            msgs.append(_assistant("回答"))
        msgs.append(_user("请分析并实现"))  # +2 关键词（分析+实现各算一次）
        result = classifier.classify(msgs)
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
        # evaluate → +1(score_1) + 2(tools>5) = 3 → MEDIUM
        assert result == ComplexityLevel.MEDIUM

    def test_only_assistant_messages(self, classifier, ComplexityLevel):
        """只有 assistant 消息，无 user 消息 → SIMPLE / assistant ， user → SI..."""
        msgs = [_assistant("你好") for _ in range(15)]
        result = classifier.classify(msgs)
        assert result == ComplexityLevel.SIMPLE
