"""Domain-focused intent rules extracted from IntentPlanner."""

from __future__ import annotations

import re
from typing import Any

from app.ai.engine.intent_domain_rules_terms import (
    _CAPABILITY_QUERY_TERMS,
    _CAPABILITY_REFERENCE_TERMS,
    _COMMON_WEATHER_LOCATIONS,
    _KNOWLEDGE_COURTESY_PREFIXES,
    _KNOWLEDGE_DEFINITION_PATTERNS,
    _KNOWLEDGE_FILLER_SUFFIXES,
    _KNOWLEDGE_GENERIC_SUBJECTS,
    _MEMORY_QUERY_HINT_TERMS,
    _MEMORY_RECALL_TERMS,
    _MEMORY_SAVE_TERMS,
    _NO_TOOL_REQUEST_TERMS,
    _TIME_TERMS,
    _WEATHER_ENGLISH_LOCATION_RE,
    _WEATHER_LOCATION_SUFFIX_RE,
)
from app.ai.engine.intent_signal_helpers import (
    _first_position,
    _IntentSignal,
    _semantic_profile_position,
    _tool_families,
)
from app.ai.text_semantics import has_question_indicator, mentions_weather
from app.ai.tools.types import ToolDefinition

_CN_LOCAL_TIME_RE = re.compile(r"(?:当前|现在)?[\u4e00-\u9fff]{1,12}(?:时间|时区)")
_EN_LOCAL_TIME_RE = re.compile(
    r"\b(?:current|now)?\s*[a-z][a-z\s-]{1,40}\s+time\b",
    re.IGNORECASE,
)
_TIME_FORMAT_HINT_TERMS = ("hh:mm", "h:mm")
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
_WEATHER_SHORTCIRCUIT_TERMS = (
    "天气",
    "weather",
    "气温",
    "温度",
)
_KNOWLEDGE_QUERY_PROFILE = (
    "what is explain introduce tell me about knowledge base document policy definition",
    "是什么 介绍一下 讲讲 说说 说明一下 科普一下 文档 资料 政策",
)
_EXPLICIT_KB_REFERENCE_RE = re.compile(
    r"(?:知识库|knowledge base|\bkb\b)",
    re.IGNORECASE,
)
_KNOWLEDGE_EXPLICIT_REFERENCE_TERMS = (
    "根据",
    "基于",
    "结合",
    "参考",
    "引用",
    "概括",
    "总结",
    "归纳",
    "summarize",
    "summary",
    "based on",
    "using",
    "from the knowledge base",
)
_KNOWLEDGE_WEB_PREFIX_RE = re.compile(
    r"^(?:联网|上网)?\s*(?:查一下|查下|搜索一下|搜索|搜一下|搜一搜|搜搜|look up|search(?: online)?)\s*",
    re.IGNORECASE,
)
_GENERIC_KNOWLEDGE_QUESTION_PATTERNS = tuple(
    re.compile(
        rf"^{re.escape(subject)}\s*(?:是什么|是啥|是谁|what is|who is|tell me about)\b",
        re.IGNORECASE,
    )
    for subject in _KNOWLEDGE_GENERIC_SUBJECTS
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
            for token in (
                "current",
                "now",
                "what time",
                "time",
                *_TIME_FORMAT_HINT_TERMS,
            )
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
        return has_question_indicator(lowered) or any(
            token in lowered for token in _MEMORY_QUERY_HINT_TERMS
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
            question_like = cls.is_question_like_clause(lowered)
            if (not has_save_cues or question_like) and (
                question_like
                or any(token in lowered for token in _MEMORY_RECALL_CONTEXT_TERMS)
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
    def knowledge_query_position(cls, clause: str) -> int:
        position = cls.definition_like_knowledge_query_position(clause)
        if position >= 0:
            return position

        lowered = str(clause or "").strip().lower()
        kb_reference = _EXPLICIT_KB_REFERENCE_RE.search(lowered)
        if kb_reference and (
            any(term in lowered for term in _KNOWLEDGE_EXPLICIT_REFERENCE_TERMS)
            or _semantic_profile_position(
                lowered,
                _KNOWLEDGE_QUERY_PROFILE,
                min_score=1,
            )
            >= 0
        ):
            return kb_reference.start()

        cleaned = _KNOWLEDGE_WEB_PREFIX_RE.sub("", str(clause or "").strip())
        if cleaned != str(clause or "").strip():
            position = cls.definition_like_knowledge_query_position(cleaned)
            if position >= 0:
                lowered_original = str(clause or "").strip().lower()
                lowered_cleaned = cleaned.lower()
                matched = lowered_cleaned[position:]
                mapped = lowered_original.find(matched)
                return mapped if mapped >= 0 else position

        if not lowered or not cls.is_question_like_clause(lowered):
            return -1
        normalized_question = re.sub(r"[\s？?!.。]+", "", lowered)
        if any(
            pattern.match(normalized_question)
            for pattern in _GENERIC_KNOWLEDGE_QUESTION_PATTERNS
        ):
            return -1
        return _semantic_profile_position(
            lowered,
            _KNOWLEDGE_QUERY_PROFILE,
            min_score=2,
        )

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
        _ = continuation_context
        lowered = clause.lower()
        tools_forbidden = cls.explicitly_forbids_tool_usage(lowered)
        if cls.looks_like_capability_self_report(lowered):
            return []
        if cls.looks_like_tool_invocation_assertion(lowered):
            return []

        families = _tool_families(tools, input_variables)
        signals: list[_IntentSignal] = []

        # SHORTCIRCUIT: memory recall/save is explicit and should bypass semantic routing.
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
                    metadata={"routing_mode": "deterministic_shortcircuit"},
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
                    metadata={"routing_mode": "deterministic_shortcircuit"},
                )
            )

        # SHORTCIRCUIT: weather stays bounded to explicit weather/time-style asks.
        weather_position = (
            _first_position(lowered, _WEATHER_SHORTCIRCUIT_TERMS)
            if mentions_weather(lowered)
            else -1
        )
        if "weather" in families and weather_position >= 0:
            signals.append(
                _IntentSignal(
                    "weather_query",
                    "weather",
                    "weather",
                    offset + weather_position,
                    shortcircuit=True,
                    metadata={"routing_mode": "deterministic_shortcircuit"},
                )
            )

        # SHORTCIRCUIT: direct clock/date prompts should not depend on broader semantics.
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
                        metadata={"routing_mode": "deterministic_shortcircuit"},
                    )
                )

        knowledge_query_position = (
            cls.knowledge_query_position(clause)
            if cls.has_bound_kb(capability_bundle)
            else -1
        )

        if cls.has_bound_kb(capability_bundle):
            has_memory_signal = any(
                signal.kind in {"memory_save", "memory_recall"} for signal in signals
            )
            position = knowledge_query_position
            if position >= 0 and not has_memory_signal:
                signals.append(
                    _IntentSignal(
                        "knowledge_query",
                        "none",
                        "knowledge_query",
                        offset + position,
                        requires_tools=False,
                        metadata={"routing_mode": "structured_semantic"},
                    )
                )

        if tools_forbidden:
            signals = [signal for signal in signals if not signal.requires_tools]

        return sorted(signals, key=lambda item: item.position)


__all__ = ["IntentDomainRules"]
