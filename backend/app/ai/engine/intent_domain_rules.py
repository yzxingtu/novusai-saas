"""Domain-focused intent rules extracted from IntentPlanner."""

from __future__ import annotations

import re
from typing import Any

from app.ai.engine.intent_domain_rules_terms import (
    _CAPABILITY_QUERY_TERMS,
    _CAPABILITY_REFERENCE_TERMS,
    _COMMON_WEATHER_LOCATIONS,
    _GENERIC_WEB_SEARCH_TERMS,
    _KNOWLEDGE_COURTESY_PREFIXES,
    _KNOWLEDGE_DEFINITION_PATTERNS,
    _KNOWLEDGE_FILLER_SUFFIXES,
    _KNOWLEDGE_GENERIC_SUBJECTS,
    _KNOWLEDGE_TERMS,
    _MEMORY_QUERY_HINT_TERMS,
    _MEMORY_RECALL_TERMS,
    _MEMORY_SAVE_TERMS,
    _NO_TOOL_REQUEST_TERMS,
    _NO_WEB_TERMS,
    _PAGE_POINTER_TERMS,
    _PAGE_SEARCH_QUALIFIER_TERMS,
    _PAGE_SEARCH_TERMS,
    _TIME_TERMS,
    _WEATHER_ENGLISH_LOCATION_RE,
    _WEATHER_LOCATION_SUFFIX_RE,
    _WEATHER_TERMS,
    _WEB_NOUN_TERMS,
    _WEB_TERMS,
)
from app.ai.engine.intent_signal_helpers import (
    _first_position,
    _IntentSignal,
    _tool_families,
)
from app.ai.tools.types import ToolDefinition

_EXPLICIT_WEB_URL_RE = re.compile(r"https?://[^\s<>()\[\]\"']+", re.IGNORECASE)
_SEARCH_ONLY_NO_WEB_RE = re.compile(
    r"(?:不要|别|不用|不必|无需)\s*(?:联网)?(?:搜索|搜|查找|search)"
    r"|do not (?:web )?search"
    r"|don't (?:web )?search"
    r"|no web search",
    re.IGNORECASE,
)
_ALL_WEB_FORBIDDEN_RE = re.compile(
    r"(?:不要|别|不用|不必|无需)\s*联网(?!搜索|搜|查找|search)"
    r"|offline"
    r"|no web",
    re.IGNORECASE,
)
_CN_LOCAL_TIME_RE = re.compile(r"(?:当前|现在)?[\u4e00-\u9fff]{1,12}(?:时间|时区)")
_EN_LOCAL_TIME_RE = re.compile(
    r"\b(?:current|now)?\s*[a-z][a-z\s-]{1,40}\s+time\b",
    re.IGNORECASE,
)
_TIME_FORMAT_HINT_TERMS = ("hh:mm", "h:mm")
_FETCH_URL_DIRECTIVE_TERMS = ("fetch_url", "抓取", "fetch", "读取网页", "读取链接")
_TOOL_INVOCATION_ASSERTION_TERMS = (
    "若没实际调用",
    "若没有实际调用",
    "如果没实际调用",
    "如果没有实际调用",
    "没实际调用",
    "没有实际调用",
    "未实际调用",
)
_TOOL_INVOCATION_ASSERTION_TOOL_TERMS = (
    "fetch_url",
    "web_search",
    "get_current_time",
    "调用工具",
    "实际调用工具",
)
_MEMORY_SAVE_PHRASES = (
    "写入长期记忆",
    "写入记忆",
    "写进长期记忆",
    "写进记忆",
    "写到长期记忆",
    "写到记忆",
)
_MEMORY_CODEWORD_TERMS = ("代号", "暗号", "codeword", "codename")
_MEMORY_RECALL_CONTEXT_TERMS = (
    "之前",
    "刚才",
    "先前",
    "还记得",
    "告诉我",
    "回答我",
    "是什么",
    "是啥",
    "哪个",
    "哪一个",
    "what",
    "which",
    "recall",
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

    @staticmethod
    def looks_like_tool_invocation_assertion(lowered: str) -> bool:
        if not lowered:
            return False
        normalized = str(lowered or "").strip()
        return any(
            normalized.startswith(term) for term in _TOOL_INVOCATION_ASSERTION_TERMS
        ) and any(tool in lowered for tool in _TOOL_INVOCATION_ASSERTION_TOOL_TERMS)

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
    def explicit_url(clause: str) -> str | None:
        match = _EXPLICIT_WEB_URL_RE.search(str(clause or "").strip())
        if not match:
            return None
        url = str(match.group(0) or "").strip()
        return url or None

    @staticmethod
    def explicit_url_position(clause: str) -> int:
        match = _EXPLICIT_WEB_URL_RE.search(str(clause or "").strip())
        return match.start() if match else -1

    @classmethod
    def explicitly_forbids_web_search(cls, lowered: str) -> bool:
        if not lowered:
            return False
        if _SEARCH_ONLY_NO_WEB_RE.search(lowered):
            return True
        return any(
            term in lowered
            for term in (
                "不要联网搜索",
                "不联网搜索",
                "不用联网搜索",
                "无需联网搜索",
                "不要搜索",
                "不用搜索",
            )
        )

    @classmethod
    def explicitly_forbids_all_web_access(cls, lowered: str) -> bool:
        if not lowered:
            return False
        if _ALL_WEB_FORBIDDEN_RE.search(lowered):
            return True
        for term in _NO_WEB_TERMS:
            normalized = str(term or "").strip().lower()
            if not normalized:
                continue
            if any(token in normalized for token in ("搜索", "search")):
                continue
            position = lowered.find(normalized)
            if position < 0:
                continue
            suffix = lowered[position + len(normalized) :]
            if normalized.endswith("联网") and suffix.startswith(
                ("搜索", "搜", "查找", "search")
            ):
                continue
            return True
        return False

    @classmethod
    def explicit_fetch_url_request(
        cls,
        lowered: str,
        *,
        explicit_url: str | None = None,
    ) -> bool:
        if not lowered:
            return False
        if any(term in lowered for term in _FETCH_URL_DIRECTIVE_TERMS):
            return True
        return bool(explicit_url) and any(
            token in lowered for token in ("打开", "抓取", "概括", "总结", "摘要")
        )

    @classmethod
    def time_query_position(cls, lowered: str) -> int:
        position = _first_position(lowered, _TIME_TERMS)
        if position >= 0:
            return position

        direct_tool_position = lowered.find("get_current_time")
        if direct_tool_position >= 0:
            return direct_tool_position

        cn_match = _CN_LOCAL_TIME_RE.search(lowered)
        if cn_match and any(
            token in lowered
            for token in ("当前", "现在", "几点", "只回答", *_TIME_FORMAT_HINT_TERMS)
        ):
            return cn_match.start()

        en_match = _EN_LOCAL_TIME_RE.search(lowered)
        if en_match and any(
            token in lowered
            for token in ("current", "now", "what time", "time", *_TIME_FORMAT_HINT_TERMS)
        ):
            return en_match.start()

        return -1

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
        positions = [
            position
            for position in (
                _first_position(lowered, _MEMORY_SAVE_TERMS),
                *[lowered.find(phrase) for phrase in _MEMORY_SAVE_PHRASES],
            )
            if position >= 0
        ]
        if positions:
            return min(positions)
        if "记住" in lowered and not cls.is_question_like_clause(lowered):
            return lowered.find("记住")
        if "记下来" in lowered and not cls.is_question_like_clause(lowered):
            return lowered.find("记下来")
        return -1

    @classmethod
    def memory_recall_position(cls, lowered: str) -> int:
        if not lowered:
            return -1
        recall_terms = tuple(
            term for term in _MEMORY_RECALL_TERMS if term not in _MEMORY_CODEWORD_TERMS
        )
        pos = _first_position(lowered, recall_terms)
        if pos >= 0:
            return pos
        codeword_positions = [
            lowered.find(term)
            for term in _MEMORY_CODEWORD_TERMS
            if lowered.find(term) >= 0
        ]
        if codeword_positions:
            has_save_cues = any(
                token in lowered
                for token in (
                    *_MEMORY_SAVE_PHRASES,
                    "长期记忆",
                    "记忆",
                    "记住",
                    "记下来",
                    "保存",
                    "存入",
                    "写入",
                    "写进",
                    "写到",
                )
            )
            if not has_save_cues or cls.is_question_like_clause(lowered):
                if cls.is_question_like_clause(lowered) or any(
                    token in lowered for token in _MEMORY_RECALL_CONTEXT_TERMS
                ):
                    return min(codeword_positions)
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
        tools_forbidden = cls.explicitly_forbids_tool_usage(lowered)
        if cls.looks_like_capability_self_report(lowered):
            return []
        if cls.looks_like_tool_invocation_assertion(lowered):
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
            position = cls.time_query_position(lowered)
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

        explicit_url = cls.explicit_url(clause)
        explicit_url_position = cls.explicit_url_position(clause)
        forbids_web_search = cls.explicitly_forbids_web_search(lowered)
        forbids_all_web_access = cls.explicitly_forbids_all_web_access(lowered)
        explicit_fetch_url_request = cls.explicit_fetch_url_request(
            lowered,
            explicit_url=explicit_url,
        )
        fetch_only_request = bool(explicit_url) or explicit_fetch_url_request
        if not forbids_all_web_access and "web_research" in families:
            if weather_position >= 0 and "weather" not in families:
                signals.append(
                    _IntentSignal(
                        "web_research",
                        "web_research",
                        "weather_web_research",
                        offset + weather_position,
                    )
                )
            position_candidates = [
                candidate
                for candidate in (
                    _first_position(lowered, _WEB_TERMS),
                    lowered.find("fetch_url"),
                    explicit_url_position,
                    cls.news_like_web_search_position(lowered),
                    cls.generic_web_search_position(lowered),
                )
                if candidate >= 0
            ]
            position = min(position_candidates) if position_candidates else -1
            if forbids_web_search and not fetch_only_request:
                position = -1
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
                    metadata: dict[str, Any] = {}
                    if explicit_url:
                        metadata["explicit_url"] = explicit_url
                        metadata["prefer_fetch_url"] = True
                        metadata["fetch_only"] = True
                    elif explicit_fetch_url_request:
                        metadata["prefer_fetch_url"] = True
                        metadata["fetch_only"] = True
                    if forbids_web_search:
                        metadata["web_search_forbidden"] = True
                    signals.append(
                        _IntentSignal(
                            "web_research",
                            "web_research",
                            label,
                            offset + position,
                            metadata=metadata,
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

        if tools_forbidden:
            signals = [signal for signal in signals if not signal.requires_tools]

        return sorted(signals, key=lambda item: item.position)


__all__ = ["IntentDomainRules"]
