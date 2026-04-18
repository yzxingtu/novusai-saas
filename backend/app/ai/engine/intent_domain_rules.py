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
    def explicit_url_position(clause: str) -> int:
        match = _EXPLICIT_WEB_URL_RE.search(str(clause or "").strip())
        return match.start() if match else -1

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
        tools_forbidden = cls.explicitly_forbids_tool_usage(lowered)
        if cls.looks_like_capability_self_report(lowered):
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
                position = cls.explicit_url_position(clause)
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

        if tools_forbidden:
            signals = [signal for signal in signals if not signal.requires_tools]

        return sorted(signals, key=lambda item: item.position)


__all__ = ["IntentDomainRules"]
