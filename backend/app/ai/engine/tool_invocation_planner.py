"""
Deterministic planner for deciding whether a turn should use tools.
确定性工具调用规划器：判断当前轮是否应该调用工具。
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import re
from typing import Any

from app.ai.tools.semantic_defaults import tool_family_from_name, tool_semantic_family
from app.ai.tools.types import ToolDefinition
from app.ai.types import ChatMessage
from app.schemas.ai.agent_chat import PAGE_CONTEXT_KEY

_PAGE_POINTER_RE = re.compile(
    r"(这个页面|当前页面|这个表格|这个表单|这个按钮|这条记录|这里|页面(的)?内容|本页面|本页|page|form|table|record)",
    re.IGNORECASE,
)
_PAGE_ACTION_RE = re.compile(
    r"(看看这个页面|看到这个页面|读取页面|分析页面|查看页面|当前页|页面里|页面上|读一下页面|看看本页面|看一下本页面|本页面的内容)",
    re.IGNORECASE,
)
_PAGE_CAPABILITY_RE = re.compile(
    r"(页面感知能力|页面感知交互|页面能力|页面操作能力|通过页面感知能力|通过页面感知交互|通过页面能力|用页面能力|使用页面能力|通过页面操作)",
    re.IGNORECASE,
)
_WEB_RESEARCH_RE = re.compile(
    r"(联网|搜一下|查一下|最新|最近|新闻|官网|链接|url|网页|web|search|fetch)",
    re.IGNORECASE,
)
_WEB_RESULT_ANCHOR_RE = re.compile(
    r"(刚才那个链接|上面那个结果|那篇文章|那个网页|这个链接|刚才查到的|上一个结果)",
    re.IGNORECASE,
)
_DATA_QUERY_RE = re.compile(
    r"(数据|记录|表\b|查询|筛选|排序|统计|数据库|id\b|字段|明细|列表)",
    re.IGNORECASE,
)
_DATA_STRONG_RE = re.compile(
    r"(数据|记录|数据库|字段|明细|列表|筛选|排序|统计|\btable\b|\brecord\b|\bsql\b|\bid\b|报表)",
    re.IGNORECASE,
)
_DATA_ANCHOR_RE = re.compile(
    r"(这条数据|这条记录|上一条记录|这个字段|这个id|这行数据|上一行)",
    re.IGNORECASE,
)
_SMALLTALK_RE = re.compile(
    r"(你真聪明|真聪明|谢谢|多谢|好厉害|好棒|哈哈|哈哈哈|好久不见|你好呀|你好|早上好|晚上好|晚安|可爱)",
    re.IGNORECASE,
)
_EMOTION_RE = re.compile(
    r"(我不开心|我难受|我焦虑|我伤心|我紧张|我害怕|今天心情不好|安慰我|抱抱我)",
    re.IGNORECASE,
)
_HEALTH_RE = re.compile(
    r"(我肚子疼|胃疼|头疼|头晕|发烧|咳嗽|难受|不舒服|身体怎么样|身体不舒服)",
    re.IGNORECASE,
)
_THANKS_RE = re.compile(r"^(谢谢|多谢|thanks|thank you)[!！。~ ]*$", re.IGNORECASE)

_WEATHER_INTENT_RE = re.compile(r"(天气|气温|温度|气候|降雨|湿度|weather|temperature)", re.IGNORECASE)


@dataclass(frozen=True)
class ToolInvocationPlan:
    intent: str = "direct_reply"
    family: str = "none"
    allow_no_tool: bool = True
    allow_family_continuation: bool = False
    reason: str = "default_no_tool"
    confidence_band: str = "medium"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ToolInvocationPlanner:
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
    def _is_explicit_data_request(user_text: str) -> bool:
        text = (user_text or "").strip()
        if not text:
            return False
        if not _DATA_QUERY_RE.search(text):
            return False
        if _DATA_STRONG_RE.search(text):
            return True
        # "查询" alone is ambiguous; when web intent is explicit, avoid false data_ops mix.
        return not bool(_WEB_RESEARCH_RE.search(text))

    @staticmethod
    def _is_explicit_page_request(
        user_text: str,
        *,
        page_context_present: bool,
    ) -> bool:
        if not page_context_present:
            return False
        text = (user_text or "").strip()
        if not text:
            return False
        return bool(
            _PAGE_POINTER_RE.search(text)
            or _PAGE_ACTION_RE.search(text)
            or _PAGE_CAPABILITY_RE.search(text)
        )

    @staticmethod
    def _recent_successful_tool_names(messages: list[ChatMessage]) -> list[str]:
        names: list[str] = []
        seen: set[str] = set()
        for message in reversed(messages):
            if message.role == "assistant" and message.tool_calls:
                for tool_call in reversed(message.tool_calls):
                    if tool_call.get("success") is not True:
                        continue
                    tool_name = str(
                        (tool_call.get("function") or {}).get("name")
                        or tool_call.get("name")
                        or ""
                    ).strip()
                    if tool_name and tool_name not in seen:
                        names.append(tool_name)
                        seen.add(tool_name)
            if len(names) >= 3:
                break
        return names[:3]

    @staticmethod
    def _has_unresolved_page_flow(messages: list[ChatMessage]) -> bool:
        for message in reversed(messages):
            metadata = message.metadata or {}
            pending_confirmation = metadata.get("pending_confirmation")
            if isinstance(pending_confirmation, dict) and not pending_confirmation.get(
                "resolved"
            ):
                return True
            pending_consent = metadata.get("pending_consent")
            if isinstance(pending_consent, dict) and not pending_consent.get(
                "resolved"
            ):
                tool_name = str(pending_consent.get("tool_name") or "").strip()
                if tool_family_from_name(tool_name) == "page_ops":
                    return True
            for tool_call in message.tool_calls or []:
                nested_pending = tool_call.get("pending_confirmation")
                if isinstance(nested_pending, dict) and not nested_pending.get(
                    "resolved"
                ):
                    return True
        return False

    @classmethod
    def explicit_requested_families(
        cls,
        *,
        messages: list[ChatMessage],
        tools: list[ToolDefinition],
        input_variables: dict[str, Any] | None,
    ) -> list[str]:
        user_text = cls._last_user_text(messages)
        if not user_text or not tools:
            return []

        page_context_present = cls._has_page_context(input_variables)
        families_with_pos: list[tuple[int, str]] = []

        def _record(match: re.Match[str] | None, family: str) -> None:
            if match is None:
                return
            families_with_pos.append((match.start(), family))

        page_match = None
        if cls._is_explicit_page_request(
            user_text,
            page_context_present=page_context_present,
        ):
            page_match = (
                _PAGE_CAPABILITY_RE.search(user_text)
                or _PAGE_ACTION_RE.search(user_text)
                or _PAGE_POINTER_RE.search(user_text)
            )
        _record(page_match, "page_ops")

        _record(_WEB_RESEARCH_RE.search(user_text), "web_research")
        if cls._is_explicit_data_request(user_text):
            _record(_DATA_QUERY_RE.search(user_text), "data_ops")

        has_weather_tools = any(
            tool_semantic_family(tool, input_variables) == "weather" for tool in tools
        )
        if has_weather_tools:
            _record(_WEATHER_INTENT_RE.search(user_text), "weather")

        has_time_tools = any(
            tool_semantic_family(tool, input_variables) == "time_ops" for tool in tools
        )
        if has_time_tools:
            _record(
                re.search(
                    r"(现在几点|当前时间|今天几号|当前日期|time now|current time)",
                    user_text,
                    re.IGNORECASE,
                ),
                "time_ops",
            )

        ordered: list[str] = []
        for _, family in sorted(families_with_pos, key=lambda item: item[0]):
            if family not in ordered:
                ordered.append(family)
        return ordered

    @classmethod
    def plan(
        cls,
        *,
        messages: list[ChatMessage],
        tools: list[ToolDefinition],
        input_variables: dict[str, Any] | None,
        continuation_context: Any | None,
    ) -> ToolInvocationPlan:
        user_text = cls._last_user_text(messages)
        if not user_text or not tools:
            return ToolInvocationPlan()

        page_context_present = cls._has_page_context(input_variables)
        recent_successful_tool_names = cls._recent_successful_tool_names(messages[:-1])
        latest_tool_name = recent_successful_tool_names[0] if recent_successful_tool_names else ""
        latest_family = tool_family_from_name(latest_tool_name, input_variables)
        unresolved_page_flow = cls._has_unresolved_page_flow(messages[:-1])

        explicit_page = cls._is_explicit_page_request(
            user_text,
            page_context_present=page_context_present,
        )
        explicit_web = bool(_WEB_RESEARCH_RE.search(user_text))
        explicit_data = cls._is_explicit_data_request(user_text)
        web_anchor = bool(_WEB_RESULT_ANCHOR_RE.search(user_text))
        data_anchor = bool(_DATA_ANCHOR_RE.search(user_text))
        page_anchor = page_context_present and bool(_PAGE_POINTER_RE.search(user_text))
        has_weather_tools = any(
            tool_semantic_family(tool, input_variables) == "weather" for tool in tools
        )
        explicit_weather = has_weather_tools and bool(_WEATHER_INTENT_RE.search(user_text))
        explicit_time = any(
            tool_semantic_family(tool, input_variables) == "time_ops" for tool in tools
        ) and bool(
            re.search(
                r"(现在几点|当前时间|今天几号|当前日期|time now|current time)",
                user_text,
                re.IGNORECASE,
            )
        )
        health_or_emotion = bool(_HEALTH_RE.search(user_text) or _EMOTION_RE.search(user_text))
        smalltalk = bool(_SMALLTALK_RE.search(user_text) or _THANKS_RE.match(user_text))

        if (smalltalk or health_or_emotion) and not (
            explicit_page or explicit_web or explicit_data or explicit_weather or explicit_time
        ):
            return ToolInvocationPlan(
                intent="direct_reply",
                family="none",
                allow_no_tool=True,
                allow_family_continuation=False,
                reason="smalltalk_or_support_no_tool",
                confidence_band="high",
            )

        if (
            continuation_context
            and getattr(continuation_context, "active", False)
            and getattr(continuation_context, "family", None) == "web_research"
            and (
                web_anchor
                or int(getattr(continuation_context, "fetched_url_count", 0) or 0) == 0
            )
        ):
            return ToolInvocationPlan(
                intent="web_research",
                family="web_research",
                allow_no_tool=False,
                allow_family_continuation=True,
                reason="anchored_or_unfinished_web_continuation",
                confidence_band="medium",
            )

        if latest_family == "page_ops" and (page_anchor or unresolved_page_flow):
            return ToolInvocationPlan(
                intent="page_question",
                family="page_ops",
                allow_no_tool=False,
                allow_family_continuation=True,
                reason="anchored_or_pending_page_continuation",
                confidence_band="medium",
            )

        if latest_family == "data_ops" and data_anchor:
            return ToolInvocationPlan(
                intent="data_query",
                family="data_ops",
                allow_no_tool=False,
                allow_family_continuation=True,
                reason="anchored_data_continuation",
                confidence_band="medium",
            )

        if explicit_page:
            return ToolInvocationPlan(
                intent="page_question",
                family="page_ops",
                allow_no_tool=False,
                allow_family_continuation=bool(page_anchor or unresolved_page_flow),
                reason="explicit_page_request",
                confidence_band="high",
            )

        if explicit_web:
            return ToolInvocationPlan(
                intent="web_research",
                family="web_research",
                allow_no_tool=False,
                allow_family_continuation=False,
                reason="explicit_web_request",
                confidence_band="high",
            )

        if explicit_data:
            return ToolInvocationPlan(
                intent="data_query",
                family="data_ops",
                allow_no_tool=False,
                allow_family_continuation=False,
                reason="explicit_data_request",
                confidence_band="high",
            )

        if explicit_time:
            return ToolInvocationPlan(
                intent="time_question",
                family="time_ops",
                allow_no_tool=False,
                allow_family_continuation=False,
                reason="explicit_time_request",
                confidence_band="high",
            )

        if explicit_weather:
            return ToolInvocationPlan(
                intent="weather_question",
                family="weather",
                allow_no_tool=False,
                allow_family_continuation=False,
                reason="explicit_weather_request",
                confidence_band="high",
            )

        return ToolInvocationPlan()


__all__ = ["ToolInvocationPlan", "ToolInvocationPlanner"]
