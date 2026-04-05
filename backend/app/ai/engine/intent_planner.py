"""Structured intent planning for multi-intent chat turns."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.ai.navigation_semantics import has_navigation_intent
from app.ai.tools.semantic_defaults import tool_semantic_family
from app.ai.tools.types import ToolDefinition
from app.ai.types import ChatMessage
from app.schemas.ai.agent_chat import PAGE_CONTEXT_KEY

from .types import IntentPlan

_CLAUSE_SEPARATORS = (
    "，然后",
    "然后",
    "再帮我",
    "并且",
    "以及",
    "同时",
    ", then",
    " and then ",
)
_WEATHER_TERMS = ("天气", "气温", "温度", "降雨", "湿度", "weather", "temperature")
_TIME_TERMS = (
    "现在几点",
    "当前时间",
    "今天几号",
    "当前日期",
    "time now",
    "current time",
)
_WEB_TERMS = (
    "联网",
    "搜索",
    "搜一下",
    "网上查",
    "网络搜索",
    "官网",
    "链接",
    "url",
    "网页",
    "web search",
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
    "页面内容",
    "页面里",
    "页面上",
    "这个表格",
    "这个表单",
    "这条记录",
    "this page",
    "current page",
    "page content",
    "page contents",
    "on this page",
)
_PAGE_READ_TERMS = (
    "读取页面",
    "分析页面",
    "查看页面",
    "读一下页面",
    "总结页面",
    "页面有什么内容",
    "看看页面",
    "read this page",
    "read the page",
    "analyze this page",
    "summarize this page",
    "what is on this page",
    "what's on this page",
    "what does this page contain",
)
_PAGE_WRITE_TERMS = (
    "创建",
    "新增",
    "添加",
    "修改",
    "编辑",
    "删除",
    "填写",
    "提交",
    "保存",
    "更新",
    "操作",
    "create",
    "add",
    "edit",
    "update",
    "delete",
    "submit",
    "save",
    "fill",
)
_PAGE_NAV_TERMS = (
    "打开",
    "前往",
    "跳转",
    "进入",
    "导航",
    "去到",
    "切换到",
    "新页面",
    "新的页面",
    "open",
    "go to",
    "navigate",
    "switch to",
)
_PAGE_CAPABILITY_TERMS = ("页面感知能力", "页面能力", "页面操作能力", "页面操作")
_KNOWLEDGE_TERMS = ("知识库", "文档", "资料", "kb")


@dataclass(frozen=True)
class _IntentSignal:
    kind: str
    family: str
    label: str
    position: int
    requires_tools: bool = True


class IntentPlanner:
    @staticmethod
    def _last_user_text(messages: list[ChatMessage]) -> str:
        for message in reversed(messages):
            if message.role == "user":
                return (message.content or "").strip()
        return ""

    @staticmethod
    def _has_page_context(input_variables: dict[str, Any] | None) -> bool:
        if not isinstance(input_variables, dict):
            return False
        page_context = input_variables.get(PAGE_CONTEXT_KEY)
        return isinstance(page_context, dict) and bool(
            str(page_context.get("page_key") or "").strip()
        )

    @staticmethod
    def _tool_families(
        tools: list[ToolDefinition],
        input_variables: dict[str, Any] | None,
    ) -> set[str]:
        return {
            tool_semantic_family(tool, input_variables)
            for tool in tools
            if tool_semantic_family(tool, input_variables) != "none"
        }

    @staticmethod
    def _first_position(text: str, candidates: tuple[str, ...]) -> int:
        positions = [
            text.find(item) for item in candidates if item and text.find(item) >= 0
        ]
        return min(positions) if positions else -1

    @classmethod
    def _split_clauses(cls, text: str) -> list[tuple[int, str]]:
        if not text:
            return []
        lowered = text.lower()
        start = 0
        idx = 0
        clauses: list[tuple[int, str]] = []
        while idx < len(lowered):
            separator = next(
                (
                    token
                    for token in _CLAUSE_SEPARATORS
                    if lowered.startswith(token, idx)
                ),
                None,
            )
            if separator is None:
                idx += 1
                continue
            chunk = text[start:idx].strip(" ，,。；;、")
            if chunk:
                clauses.append((start, chunk))
            idx += len(separator)
            start = idx
        tail = text[start:].strip(" ，,。；;、")
        if tail:
            clauses.append((start, tail))
        return clauses or [(0, text.strip())]

    @classmethod
    def _has_bound_kb(cls, capability_bundle: Any | None) -> bool:
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
    def _detect_clause_signals(
        cls,
        clause: str,
        *,
        offset: int,
        tools: list[ToolDefinition],
        input_variables: dict[str, Any] | None,
        capability_bundle: Any | None,
        continuation_context: Any | None,
    ) -> list[_IntentSignal]:
        lowered = clause.lower()
        families = cls._tool_families(tools, input_variables)
        page_context_present = cls._has_page_context(input_variables)
        signals: list[_IntentSignal] = []

        if "weather" in families:
            position = cls._first_position(lowered, _WEATHER_TERMS)
            if position >= 0:
                signals.append(
                    _IntentSignal(
                        "weather_query", "weather", "weather", offset + position
                    )
                )

        if "time_ops" in families:
            position = cls._first_position(lowered, _TIME_TERMS)
            if position >= 0:
                signals.append(
                    _IntentSignal("time_query", "time_ops", "time", offset + position)
                )

        no_web = any(term in lowered for term in _NO_WEB_TERMS)
        if not no_web and "web_research" in families:
            position = cls._first_position(lowered, _WEB_TERMS)
            if position >= 0:
                label = (
                    "rail_search"
                    if any(term in lowered for term in ("高铁票", "火车票", "12306"))
                    else "web_research"
                )
                signals.append(
                    _IntentSignal(
                        "web_research", "web_research", label, offset + position
                    )
                )

        if page_context_present and "page_ops" in families:
            page_position = cls._first_position(
                lowered,
                _PAGE_POINTER_TERMS
                + _PAGE_READ_TERMS
                + _PAGE_WRITE_TERMS
                + _PAGE_NAV_TERMS
                + _PAGE_CAPABILITY_TERMS,
            )
            navigation_request = has_navigation_intent(
                clause,
                input_variables.get(PAGE_CONTEXT_KEY)
                if isinstance(input_variables, dict)
                else None,
            )
            if page_position >= 0 or navigation_request:
                nav_position = cls._first_position(lowered, _PAGE_NAV_TERMS)
                write_position = cls._first_position(lowered, _PAGE_WRITE_TERMS)
                read_position = cls._first_position(
                    lowered,
                    _PAGE_READ_TERMS + _PAGE_POINTER_TERMS + _PAGE_CAPABILITY_TERMS,
                )
                if navigation_request or nav_position >= 0:
                    signals.append(
                        _IntentSignal(
                            "page_navigation",
                            "page_ops",
                            "page_navigation",
                            offset
                            + (
                                nav_position
                                if nav_position >= 0
                                else max(page_position, 0)
                            ),
                        )
                    )
                elif write_position >= 0:
                    signals.append(
                        _IntentSignal(
                            "page_write",
                            "page_ops",
                            "page_write",
                            offset + write_position,
                        )
                    )
                else:
                    signals.append(
                        _IntentSignal(
                            "page_read",
                            "page_ops",
                            "page_read",
                            offset
                            + (
                                read_position
                                if read_position >= 0
                                else max(page_position, 0)
                            ),
                        )
                    )

        if cls._has_bound_kb(capability_bundle):
            position = cls._first_position(lowered, _KNOWLEDGE_TERMS)
            if position >= 0:
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

    @classmethod
    def plan_turn(
        cls,
        *,
        messages: list[ChatMessage],
        tools: list[ToolDefinition],
        input_variables: dict[str, Any] | None,
        continuation_context: Any | None,
        capability_bundle: Any | None = None,
    ) -> list[IntentPlan]:
        user_text = cls._last_user_text(messages)
        if not user_text:
            return []

        detected: list[_IntentSignal] = []
        for offset, clause in cls._split_clauses(user_text):
            detected.extend(
                cls._detect_clause_signals(
                    clause,
                    offset=offset,
                    tools=tools,
                    input_variables=input_variables,
                    capability_bundle=capability_bundle,
                    continuation_context=continuation_context,
                )
            )

        if not detected:
            return [
                IntentPlan(
                    intent_id="intent-1",
                    kind="direct_reply",
                    family="none",
                    order=1,
                    user_visible_label="direct_reply",
                    source_text=user_text,
                    requires_tools=False,
                )
            ]

        plans: list[IntentPlan] = []
        seen: set[tuple[str, str, int]] = set()
        for index, signal in enumerate(
            sorted(detected, key=lambda item: item.position), start=1
        ):
            key = (signal.kind, signal.family, signal.position)
            if key in seen:
                continue
            seen.add(key)
            plans.append(
                IntentPlan(
                    intent_id=f"intent-{index}",
                    kind=signal.kind,  # type: ignore[arg-type]
                    family=signal.family,
                    order=index,
                    user_visible_label=signal.label,
                    source_text=user_text,
                    requires_tools=signal.requires_tools,
                )
            )
        return plans


__all__ = ["IntentPlanner"]
