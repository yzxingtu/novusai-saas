"""Domain-focused intent rules extracted from IntentPlanner."""

from __future__ import annotations

import re
from typing import Any

from app.ai.engine.intent_signal_helpers import (
    _first_position,
    _IntentSignal,
    _tool_families,
)
from app.ai.tools.types import ToolDefinition

_WEATHER_TERMS = ("天气", "气温", "温度", "降雨", "湿度", "weather", "temperature")
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
    "天气",
    "查询天气",
    "调用技能",
    "技能",
    "页面感知",
    "页面操作",
    "执行页面操作",
    "工具",
    "weather",
    "skill",
    "skills",
    "page operation",
    "page operations",
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
_WEB_TERMS = (
    "联网",
    "网上查",
    "网络搜索",
    "官网",
    "链接",
    "url",
    "网址",
    "网页",
    "web search",
    "search online",
    "online search",
    "fetch",
    "高铁票",
    "火车票",
    "12306",
)
_NO_WEB_TERMS = (
    "不要联网",
    "不联网",
    "不用联网",
    "不要搜索",
    "不用搜索",
    "offline",
    "no web",
)
_PAGE_POINTER_TERMS = (
    "这个页面",
    "当前页面",
    "本页面",
    "本页",
    "列表",
    "表格",
    "页面内容",
    "页面里",
    "页面上",
    "这个表格",
    "当前表格",
    "这个列表",
    "当前列表",
    "这个表单",
    "当前表单",
    "这条记录",
    "当前记录",
    "this page",
    "current page",
    "page content",
    "page contents",
    "on this page",
)
_PAGE_SEARCH_TERMS = (
    "搜索记录",
    "查找记录",
    "搜索这个",
    "查找这个",
    "search records",
)
_PAGE_SEARCH_QUALIFIER_TERMS = (
    "记录",
    "列表",
    "表格",
    "筛选",
    "过滤",
    "条件",
    "结果",
    "数据",
    "搜索条件",
    "搜索结果",
    "页内",
    "页面里",
    "页面上",
    "当前页",
    "本页",
    "records",
    "list",
    "table",
    "filter",
)
_GENERIC_WEB_SEARCH_TERMS = (
    "搜索一下",
    "搜索",
    "搜一下",
    "搜一搜",
    "搜搜",
    "查找",
    "look up",
)
_WEB_NOUN_TERMS = (
    "新闻",
    "热点",
    "头条",
    "排行",
    "最新消息",
    "实时新闻",
)
_KNOWLEDGE_TERMS = ("知识库", "文档", "资料", "kb")
_KNOWLEDGE_DEFINITION_PATTERNS = (
    re.compile(
        r"^(?:请|请问|帮我|麻烦|麻烦你|想知道|我想知道|告诉我|给我|能不能|可以)?(?P<subject>.+?)(?:是什么|是啥|是谁|是做什么的|做什么的|是干什么的)[？?]?$",
        re.IGNORECASE,
    ),
    re.compile(
        r"^(?:请|请问|帮我|麻烦|麻烦你|想知道|我想知道|告诉我|给我|能不能|可以)?(?:介绍一下|介绍下|讲讲|说说|科普一下|说明一下)(?P<subject>.+?)[？?]?$",
        re.IGNORECASE,
    ),
    re.compile(
        r"^(?:what is|who is|tell me about)\s+(?P<subject>.+?)[？?]?$",
        re.IGNORECASE,
    ),
)
_KNOWLEDGE_GENERIC_SUBJECTS = (
    "这",
    "这个",
    "那个",
    "它",
    "他",
    "她",
    "ta",
    "this",
    "that",
    "it",
    "这玩意",
    "这个东西",
    "那个东西",
)
_KNOWLEDGE_COURTESY_PREFIXES = (
    "请问",
    "请",
    "帮我",
    "麻烦你",
    "麻烦",
    "我想知道",
    "想知道",
    "告诉我",
    "给我",
)
_KNOWLEDGE_FILLER_SUFFIXES = (
    "一下",
    "下",
    "呢",
    "呀",
    "啊",
    "吧",
)
_MEMORY_SAVE_TERMS = (
    "存入记忆",
    "存到记忆",
    "保存到记忆",
    "记住这个",
    "记住这句",
    "记住这条",
    "帮我记住",
    "请记住",
    "把这个记下来",
    "把这句记下来",
    "记下来",
    "记到记忆",
    "remember this",
    "save to memory",
)
_MEMORY_RECALL_TERMS = (
    "你还记得",
    "还记得我",
    "刚才让你记住",
    "之前让你记住",
    "我刚才说的",
    "回忆一下",
    "代号",
    "codename",
    "remember",
    "recall",
)
_MEMORY_QUERY_HINT_TERMS = (
    "是什么",
    "是啥",
    "还记得",
    "记得吗",
    "记住了没",
    "回忆",
    "remember",
    "recall",
    "what",
    "which",
)
_WEATHER_LOCATION_SUFFIX_RE = re.compile(
    r"[\u4e00-\u9fff]{2,12}(?:市|区|县|州|省|自治区|特别行政区)"
)
_WEATHER_ENGLISH_LOCATION_RE = re.compile(r"\b(?:in|for)\s+([a-z][a-z\s-]{1,40})\b")
_COMMON_WEATHER_LOCATIONS = (
    "北京",
    "上海",
    "广州",
    "深圳",
    "天津",
    "重庆",
    "杭州",
    "南京",
    "苏州",
    "成都",
    "武汉",
    "西安",
    "长沙",
    "郑州",
    "青岛",
    "宁波",
    "厦门",
    "福州",
    "合肥",
    "济南",
    "昆明",
    "大连",
    "沈阳",
    "长春",
    "哈尔滨",
    "无锡",
    "常州",
    "南昌",
    "贵阳",
    "海口",
    "三亚",
    "洛阳",
    "石家庄",
    "太原",
)


class IntentDomainRules:
    """Domain-focused intent classification helpers for tool routing."""

    @staticmethod
    def explicitly_forbids_tool_usage(lowered: str) -> bool:
        return any(term in lowered for term in _NO_TOOL_REQUEST_TERMS)

    @staticmethod
    def looks_like_capability_self_report(lowered: str) -> bool:
        if any(
            term in lowered
            for term in (
                "介绍一下你自己",
                "简单介绍一下你自己",
                "先介绍一下你自己",
                "自我介绍",
                "introduce yourself",
                "who are you",
            )
        ):
            return True
        if not any(term in lowered for term in _CAPABILITY_QUERY_TERMS):
            return False
        return any(term in lowered for term in _CAPABILITY_REFERENCE_TERMS)

    @classmethod
    def looks_like_page_search_request(cls, lowered: str) -> bool:
        explicit_page_search = _first_position(lowered, _PAGE_SEARCH_TERMS) >= 0
        if explicit_page_search:
            return True
        if "搜索" not in lowered and "搜" not in lowered and "查找" not in lowered:
            return False
        has_page_reference = (
            _first_position(lowered, _PAGE_POINTER_TERMS + _PAGE_SEARCH_QUALIFIER_TERMS)
            >= 0
        )
        return has_page_reference

    @classmethod
    def generic_web_search_position(cls, lowered: str) -> int:
        if cls.looks_like_page_search_request(lowered):
            return -1
        if any(
            term in lowered for term in ("天气", "气温", "温度", "weather")
        ) and not any(
            token in lowered for token in (*_WEB_NOUN_TERMS, "官网", "链接", "网址")
        ):
            return -1
        return _first_position(lowered, _GENERIC_WEB_SEARCH_TERMS)

    @classmethod
    def news_like_web_search_position(cls, lowered: str) -> int:
        if cls.looks_like_page_search_request(lowered):
            return -1
        return _first_position(lowered, _WEB_NOUN_TERMS)

    @staticmethod
    def weather_query_has_city(lowered: str) -> bool:
        if not lowered:
            return False
        if _WEATHER_LOCATION_SUFFIX_RE.search(lowered):
            return True
        if _WEATHER_ENGLISH_LOCATION_RE.search(lowered):
            return True
        return any(location in lowered for location in _COMMON_WEATHER_LOCATIONS)

    @staticmethod
    def is_question_like_clause(lowered: str) -> bool:
        if not lowered:
            return False
        return (
            "?" in lowered
            or "？" in lowered
            or any(token in lowered for token in _MEMORY_QUERY_HINT_TERMS)
        )

    @classmethod
    def memory_save_position(cls, lowered: str) -> int:
        pos = _first_position(lowered, _MEMORY_SAVE_TERMS)
        if pos >= 0:
            return pos
        if "记住" in lowered and not cls.is_question_like_clause(lowered):
            return lowered.find("记住")
        if "记下来" in lowered and not cls.is_question_like_clause(lowered):
            return lowered.find("记下来")
        return -1

    @classmethod
    def memory_recall_position(cls, lowered: str) -> int:
        if not lowered:
            return -1
        pos = _first_position(lowered, _MEMORY_RECALL_TERMS)
        if pos >= 0:
            return pos
        if "记得" in lowered and cls.is_question_like_clause(lowered):
            return lowered.find("记得")
        if "记住" in lowered and cls.is_question_like_clause(lowered):
            return lowered.find("记住")
        return -1

    @classmethod
    def has_bound_kb(cls, capability_bundle: Any | None) -> bool:
        sources = getattr(capability_bundle, "context_sources", None) or []
        for source in sources:
            kind = (
                str(source.get("kind") or "").strip()
                if isinstance(source, dict)
                else str(getattr(source, "kind", "") or "").strip()
            )
            if kind == "knowledge_base":
                return True
        return False

    @classmethod
    def normalize_knowledge_subject(cls, subject: str) -> str:
        normalized = re.sub(
            r"\s+",
            " ",
            str(subject or "").strip(" \t\r\n，,。！？?；;：:"),
        )
        if not normalized:
            return ""
        changed = True
        while changed and normalized:
            changed = False
            for prefix in _KNOWLEDGE_COURTESY_PREFIXES:
                if normalized.startswith(prefix):
                    normalized = normalized[len(prefix) :].strip()
                    changed = True
            for suffix in _KNOWLEDGE_FILLER_SUFFIXES:
                if normalized.endswith(suffix):
                    normalized = normalized[: -len(suffix)].strip()
                    changed = True
        return normalized

    @classmethod
    def definition_like_knowledge_query_position(cls, clause: str) -> int:
        text = re.sub(r"\s+", " ", str(clause or "").strip())
        if not text:
            return -1
        lowered = text.lower()
        for pattern in _KNOWLEDGE_DEFINITION_PATTERNS:
            match = pattern.match(text)
            if not match:
                continue
            subject = cls.normalize_knowledge_subject(match.group("subject"))
            subject_lowered = subject.lower()
            if (
                not subject_lowered
                or len(subject_lowered) <= 1
                or subject_lowered in _KNOWLEDGE_GENERIC_SUBJECTS
            ):
                continue
            position = lowered.find(subject_lowered)
            return position if position >= 0 else 0
        return -1

    @classmethod
    def detect_domain_signals(
        cls,
        *,
        clause: str,
        offset: int,
        tools: list[ToolDefinition],
        input_variables: dict[str, Any] | None,
        capability_bundle: Any | None,
        continuation_context: Any | None,
    ) -> list[_IntentSignal]:
        lowered = clause.lower()
        if cls.explicitly_forbids_tool_usage(lowered) or cls.looks_like_capability_self_report(
            lowered
        ):
            return []

        families = _tool_families(tools, input_variables)
        signals: list[_IntentSignal] = []

        memory_recall_position = cls.memory_recall_position(lowered)
        if memory_recall_position >= 0:
            signals.append(
                _IntentSignal(
                    "memory_recall",
                    "memory",
                    "memory_recall",
                    offset + memory_recall_position,
                    requires_tools=False,
                    shortcircuit=True,
                )
            )
        elif (memory_save_position := cls.memory_save_position(lowered)) >= 0:
            signals.append(
                _IntentSignal(
                    "memory_save",
                    "memory",
                    "memory_save",
                    offset + memory_save_position,
                    requires_tools=False,
                    shortcircuit=True,
                )
            )

        weather_position = _first_position(lowered, _WEATHER_TERMS)
        if "weather" in families and weather_position >= 0:
            signals.append(
                _IntentSignal(
                    "weather_query",
                    "weather",
                    "weather",
                    offset + weather_position,
                    shortcircuit=True,
                )
            )

        if "time_ops" in families:
            position = _first_position(lowered, _TIME_TERMS)
            if position >= 0:
                signals.append(
                    _IntentSignal(
                        "time_query",
                        "time_ops",
                        "time",
                        offset + position,
                        shortcircuit=True,
                    )
                )

        no_web = any(term in lowered for term in _NO_WEB_TERMS)
        if not no_web and "web_research" in families:
            if weather_position >= 0 and "weather" not in families:
                signals.append(
                    _IntentSignal(
                        "web_research",
                        "web_research",
                        "weather_web_research",
                        offset + weather_position,
                    )
                )
            position = _first_position(lowered, _WEB_TERMS)
            if position < 0:
                position = cls.news_like_web_search_position(lowered)
            if position < 0:
                position = cls.generic_web_search_position(lowered)
            if position >= 0:
                label = (
                    "rail_search"
                    if any(term in lowered for term in ("高铁票", "火车票", "12306"))
                    else "web_research"
                )
                suppress_generic_weather_fallback = (
                    label == "web_research"
                    and weather_position >= 0
                    and "weather" not in families
                    and not any(term in lowered for term in _WEB_NOUN_TERMS)
                )
                if not suppress_generic_weather_fallback:
                    signals.append(
                        _IntentSignal(
                            "web_research",
                            "web_research",
                            label,
                            offset + position,
                        )
                    )

        if cls.has_bound_kb(capability_bundle):
            has_memory_signal = any(
                signal.kind in {"memory_save", "memory_recall"} for signal in signals
            )
            position = _first_position(lowered, _KNOWLEDGE_TERMS)
            if position < 0:
                position = cls.definition_like_knowledge_query_position(clause)
            if position >= 0 and not has_memory_signal:
                signals.append(
                    _IntentSignal(
                        "knowledge_query",
                        "none",
                        "knowledge_query",
                        offset + position,
                        requires_tools=False,
                    )
                )

        if (
            continuation_context is not None
            and getattr(continuation_context, "active", False)
            and getattr(continuation_context, "family", None) == "web_research"
            and "web_research" in families
            and any(
                term in lowered
                for term in ("那个链接", "那个网页", "上一个结果", "刚才那个链接")
            )
        ):
            signals.append(
                _IntentSignal("web_research", "web_research", "web_research", offset)
            )

        return sorted(signals, key=lambda item: item.position)


__all__ = ["IntentDomainRules"]
