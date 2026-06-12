"""Term and pattern buckets used by IntentDomainRules."""

from __future__ import annotations

_CAPABILITY_QUERY_TERMS = (
    "是否能",
    "能否",
    "会不会",
    "能不能",
    "可以做什么",
    "有哪些能力",
    "能力边界",
    "what can you do",
    "whether you can",
    "what are you capable of",
)
_CAPABILITY_REFERENCE_TERMS = (
    "调用技能",
    "技能",
    "工具",
    "skill",
    "skills",
    "tool",
    "tools",
)
_NO_TOOL_REQUEST_TERMS = (
    "不要调用任何工具",
    "不要调用工具",
    "不要使用任何工具",
    "不要使用工具",
    "不需要调用工具",
    "无需调用工具",
    "do not call any tools",
    "don't call any tools",
    "without calling any tools",
    "without using tools",
)
_TIME_TERMS = (
    "现在几点",
    "现在是几点",
    "现在时间",
    "当前时间",
    "北京时间",
    "现在的北京时间",
    "北京时间几点",
    "北京时间是几点",
    "今天几号",
    "当前日期",
    "今天星期几",
    "今天周几",
    "今天是几号",
    "星期几",
    "周几",
    "几号",
    "time now",
    "current time",
    "beijing time",
    "beijing time now",
    "what day is it",
    "what date is it",
)
__all__ = [
    "_CAPABILITY_QUERY_TERMS",
    "_CAPABILITY_REFERENCE_TERMS",
    "_NO_TOOL_REQUEST_TERMS",
    "_TIME_TERMS",
]
