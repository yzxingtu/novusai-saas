"""Domain-focused intent rules extracted from IntentPlanner."""

from __future__ import annotations

import re
from typing import Any

from app.ai.engine.intent_domain_rules_terms import (
    _CAPABILITY_QUERY_TERMS,
    _CAPABILITY_REFERENCE_TERMS,
    _NO_TOOL_REQUEST_TERMS,
    _TIME_TERMS,
)
from app.ai.engine.intent_signal_helpers import (
    _first_position,
    _IntentSignal,
    _tool_families,
)
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
        _ = capability_bundle, continuation_context
        lowered = clause.lower()
        tools_forbidden = cls.explicitly_forbids_tool_usage(lowered)
        if cls.looks_like_capability_self_report(lowered):
            return []
        if cls.looks_like_tool_invocation_assertion(lowered):
            return []

        families = _tool_families(tools, input_variables)
        signals: list[_IntentSignal] = []

        # Memory and knowledge retrieval are exposed as system context tools.
        # The LLM now decides whether to call them via function calling instead
        # of this keyword planner synthesizing memory_* or knowledge_query intents.

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

        if tools_forbidden:
            signals = [signal for signal in signals if not signal.requires_tools]

        return sorted(signals, key=lambda item: item.position)


__all__ = ["IntentDomainRules"]
