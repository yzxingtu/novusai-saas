"""Structured intent planning for multi-intent chat turns."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

from app.ai.navigation_semantics import has_navigation_intent
from app.ai.tools.semantic_defaults import tool_semantic_family
from app.ai.tools.types import ToolDefinition
from app.ai.types import ChatMessage
from app.schemas.ai.agent_chat import PAGE_CONTEXT_KEY

from .types import IntentPlan

_CLAUSE_SEPARATORS = (
    "，然后",
    "，再",
    "，顺便",
    "，并且",
    "然后",
    "再帮我",
    "顺便",
    "对了",
    "另外",
    "并且",
    "以及",
    "同时",
    "；",
    ";",
    ", then",
    " and then ",
)
_WEATHER_TERMS = ("天气", "气温", "温度", "降雨", "湿度", "weather", "temperature")
_TIME_TERMS = (
    "现在几点",
    "当前时间",
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
_PAGE_SUMMARY_TERMS = (
    "读取页面",
    "分析页面",
    "查看页面",
    "读一下页面",
    "总结页面",
    "页面有什么内容",
    "看看页面",
    "看看本页面",
    "阅读一下当前页面",
    "read this page",
    "read the page",
    "analyze this page",
    "summarize this page",
    "what is on this page",
    "what's on this page",
    "what does this page contain",
)
_PAGE_FORM_WRITE_TERMS = (
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
    "创建记录",
    "新增记录",
    "编辑记录",
    "填写表单",
    "提交表单",
    "保存表单",
    "create",
    "add",
    "edit",
    "update",
    "delete",
    "submit",
    "save",
    "fill",
)
_PAGE_FORM_READ_TERMS = (
    "表单状态",
    "表单选项",
    "读取表单",
    "查看表单",
    "当前表单",
    "form state",
    "form options",
    "read form",
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
_PAGE_SEARCH_TERMS = (
    "搜索记录",
    "搜索列表",
    "在页面里搜索",
    "查找记录",
    "清空搜索",
    "清除搜索",
    "清空筛选",
    "清除筛选",
    "刷新列表",
    "刷新表格",
    "筛选",
    "过滤",
    "search records",
    "search the list",
    "clear search",
    "clear filter",
    "refresh list",
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
_PAGE_SCREENSHOT_TERMS = (
    "截图",
    "截屏",
    "屏幕截图",
    "页面截图",
    "capture screenshot",
    "take a screenshot",
    "screenshot this page",
)
_PAGE_EDITOR_READ_TERMS = (
    "编辑器内容",
    "读取编辑器",
    "查看编辑器",
    "富文本内容",
    "editor content",
    "editor html",
    "editor text",
    "read editor",
)
_PAGE_EDITOR_WRITE_TERMS = (
    "改写正文",
    "替换正文",
    "替换内容",
    "追加内容",
    "追加",
    "插入内容",
    "更新标题",
    "修改标题",
    "标题",
    "正文",
    "替换章节",
    "rewrite section",
    "replace content",
    "append content",
    "insert content",
    "update title",
)
_PAGE_ROW_DETAIL_TERMS = (
    "明细",
    "详情",
    "查看详情",
    "这条记录",
    "可见记录",
    "可见行",
    "row detail",
    "visible rows",
    "read row detail",
)
_PAGE_PAGINATION_TERMS = (
    "下一页",
    "上一页",
    "翻页",
    "分页",
    "每页",
    "page size",
    "next page",
    "prev page",
    "previous page",
    "go to page",
)
_PAGE_CAPABILITY_TERMS = ("页面感知能力", "页面能力", "页面操作能力", "页面操作")
_KNOWLEDGE_TERMS = ("知识库", "文档", "资料", "kb")
_WEATHER_LOCATION_SUFFIX_RE = re.compile(
    r"[\u4e00-\u9fff]{2,12}(?:市|区|县|州|省|自治区|特别行政区)"
)
_WEATHER_ENGLISH_LOCATION_RE = re.compile(
    r"\b(?:in|for)\s+([a-z][a-z\s-]{1,40})\b"
)
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


@dataclass(frozen=True)
class _IntentSignal:
    kind: str
    family: str
    label: str
    position: int
    requires_tools: bool = True
    shortcircuit: bool = False


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
    def _page_operation_names(input_variables: dict[str, Any] | None) -> set[str]:
        if not isinstance(input_variables, dict):
            return set()
        page_context = input_variables.get(PAGE_CONTEXT_KEY)
        if not isinstance(page_context, dict):
            return set()
        page_data = page_context.get("page_data")
        raw_operations = (
            page_data.get("available_operations")
            if isinstance(page_data, dict)
            else page_context.get("available_operations")
        )
        if not isinstance(raw_operations, list):
            return set()
        return {
            str(item.get("name") or "").strip()
            for item in raw_operations
            if isinstance(item, dict) and item.get("name")
        }

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

    @staticmethod
    def _looks_like_page_jump_request(lowered: str) -> bool:
        return any(token in lowered for token in _PAGE_PAGINATION_TERMS) or (
            "页" in lowered
            and any(token in lowered for token in ("第", "上一", "下一", "每页"))
        )

    @classmethod
    def _looks_like_page_search_request(cls, lowered: str) -> bool:
        explicit_page_search = cls._first_position(lowered, _PAGE_SEARCH_TERMS) >= 0
        if explicit_page_search:
            return True
        if "搜索" not in lowered and "搜" not in lowered and "查找" not in lowered:
            return False
        has_page_reference = cls._first_position(
            lowered,
            _PAGE_POINTER_TERMS + _PAGE_SEARCH_QUALIFIER_TERMS,
        ) >= 0
        return has_page_reference

    @classmethod
    def _generic_web_search_position(cls, lowered: str) -> int:
        if cls._looks_like_page_search_request(lowered):
            return -1
        if any(term in lowered for term in ("天气", "气温", "温度", "weather")) and not any(
            token in lowered
            for token in (*_WEB_NOUN_TERMS, "官网", "链接", "网址")
        ):
            return -1
        return cls._first_position(lowered, _GENERIC_WEB_SEARCH_TERMS)

    @classmethod
    def _news_like_web_search_position(cls, lowered: str) -> int:
        if cls._looks_like_page_search_request(lowered):
            return -1
        return cls._first_position(lowered, _WEB_NOUN_TERMS)

    @staticmethod
    def _weather_query_has_city(lowered: str) -> bool:
        if not lowered:
            return False
        if _WEATHER_LOCATION_SUFFIX_RE.search(lowered):
            return True
        if _WEATHER_ENGLISH_LOCATION_RE.search(lowered):
            return True
        return any(location in lowered for location in _COMMON_WEATHER_LOCATIONS)

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
    def _detect_page_signal(
        cls,
        *,
        clause: str,
        offset: int,
        input_variables: dict[str, Any] | None,
    ) -> _IntentSignal | None:
        lowered = clause.lower()
        page_context_present = cls._has_page_context(input_variables)
        if not page_context_present:
            return None

        page_position = cls._first_position(
            lowered,
            _PAGE_POINTER_TERMS
            + _PAGE_SUMMARY_TERMS
            + _PAGE_FORM_READ_TERMS
            + _PAGE_FORM_WRITE_TERMS
            + _PAGE_NAV_TERMS
            + _PAGE_SEARCH_TERMS
            + _PAGE_SCREENSHOT_TERMS
            + _PAGE_EDITOR_READ_TERMS
            + _PAGE_EDITOR_WRITE_TERMS
            + _PAGE_ROW_DETAIL_TERMS
            + _PAGE_CAPABILITY_TERMS,
        )
        if page_position < 0 and not any(
            token in lowered
            for token in (
                "搜索",
                "查找",
                "刷新",
                "筛选",
                "截图",
                "编辑器",
                "表单",
                "分页",
                "上一页",
                "下一页",
                "翻页",
                "每页",
                "详情",
            )
        ):
            return None

        page_context = (
            input_variables.get(PAGE_CONTEXT_KEY)
            if isinstance(input_variables, dict)
            else None
        )
        navigation_request = has_navigation_intent(clause, page_context)
        candidates: list[tuple[int, int, _IntentSignal]] = []

        def add_candidate(kind: str, label: str, position: int, priority: int) -> None:
            if position < 0:
                return
            candidates.append(
                (
                    position,
                    priority,
                    _IntentSignal(
                        kind,
                        "page_ops",
                        label,
                        offset + position,
                        shortcircuit=(kind == "page_summary"),
                    ),
                )
            )

        nav_position = cls._first_position(lowered, _PAGE_NAV_TERMS)
        if navigation_request or nav_position >= 0:
            add_candidate(
                "page_navigation",
                "page_navigation",
                nav_position if nav_position >= 0 else max(page_position, 0),
                0,
            )

        add_candidate(
            "page_screenshot",
            "page_screenshot",
            cls._first_position(lowered, _PAGE_SCREENSHOT_TERMS),
            1,
        )
        editor_anchor = lowered.find("编辑器")
        editor_write_position = cls._first_position(lowered, _PAGE_EDITOR_WRITE_TERMS)
        if editor_anchor >= 0 and any(
            token in lowered
            for token in ("修改", "改写", "优化", "润色", "追加", "插入", "标题", "正文")
        ):
            editor_write_position = (
                editor_anchor
                if editor_write_position < 0
                else min(editor_anchor, editor_write_position)
            )
        add_candidate(
            "page_editor_write",
            "page_editor_write",
            editor_write_position,
            2,
        )
        editor_read_position = cls._first_position(lowered, _PAGE_EDITOR_READ_TERMS)
        if editor_anchor >= 0 and any(
            token in lowered for token in ("什么", "内容", "html", "文本")
        ):
            editor_read_position = (
                editor_anchor
                if editor_read_position < 0
                else min(editor_anchor, editor_read_position)
            )
        add_candidate(
            "page_editor_read",
            "page_editor_read",
            editor_read_position,
            3,
        )
        form_write_position = cls._first_position(lowered, _PAGE_FORM_WRITE_TERMS)
        if not (editor_anchor >= 0 and editor_write_position >= 0):
            add_candidate(
                "page_form_write",
                "page_form_write",
                form_write_position,
                4,
            )
        add_candidate(
            "page_form_read",
            "page_form_read",
            cls._first_position(lowered, _PAGE_FORM_READ_TERMS),
            5,
        )

        search_position = cls._first_position(lowered, _PAGE_SEARCH_TERMS)
        if search_position < 0 and cls._looks_like_page_search_request(lowered):
            search_position = lowered.find("搜索")
        add_candidate("page_search", "page_search", search_position, 6)

        pagination_position = (
            cls._first_position(lowered, _PAGE_PAGINATION_TERMS)
            if cls._looks_like_page_jump_request(lowered)
            else -1
        )
        add_candidate(
            "page_pagination",
            "page_pagination",
            pagination_position,
            7,
        )
        add_candidate(
            "page_row_detail",
            "page_row_detail",
            cls._first_position(lowered, _PAGE_ROW_DETAIL_TERMS),
            8,
        )

        if not candidates:
            summary_position = cls._first_position(
                lowered,
                _PAGE_SUMMARY_TERMS + _PAGE_POINTER_TERMS + _PAGE_CAPABILITY_TERMS,
            )
            add_candidate(
                "page_summary",
                "page_summary",
                summary_position if summary_position >= 0 else page_position,
                9,
            )

        if not candidates:
            return None
        return min(candidates, key=lambda item: (item[0], item[1]))[2]

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
        signals: list[_IntentSignal] = []

        if "weather" in families:
            position = cls._first_position(lowered, _WEATHER_TERMS)
            if position >= 0:
                signals.append(
                    _IntentSignal(
                        "weather_query",
                        "weather",
                        "weather",
                        offset + position,
                        shortcircuit=True,
                    )
                )

        if "time_ops" in families:
            position = cls._first_position(lowered, _TIME_TERMS)
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

        if cls._has_page_context(input_variables) and "page_ops" in families:
            page_signal = cls._detect_page_signal(
                clause=clause,
                offset=offset,
                input_variables=input_variables,
            )
            if page_signal is not None:
                signals.append(page_signal)

        no_web = any(term in lowered for term in _NO_WEB_TERMS)
        if not no_web and "web_research" in families:
            position = cls._first_position(lowered, _WEB_TERMS)
            if position < 0:
                position = cls._news_like_web_search_position(lowered)
            if position < 0:
                position = cls._generic_web_search_position(lowered)
            if position >= 0:
                label = (
                    "rail_search"
                    if any(term in lowered for term in ("高铁票", "火车票", "12306"))
                    else "web_research"
                )
                signals.append(
                    _IntentSignal(
                        "web_research",
                        "web_research",
                        label,
                        offset + position,
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
                    shortcircuit=True,
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
            metadata: dict[str, Any] = {}
            allow_text_response = False
            if signal.kind == "weather_query" and not cls._weather_query_has_city(
                user_text.lower()
            ):
                allow_text_response = True
                metadata["missing_args"] = ["city"]
            plans.append(
                IntentPlan(
                    intent_id=f"intent-{index}",
                    kind=signal.kind,
                    family=signal.family,
                    order=index,
                    user_visible_label=signal.label,
                    source_text=user_text,
                    requires_tools=signal.requires_tools,
                    allow_text_response=allow_text_response,
                    shortcircuit=signal.shortcircuit,
                    metadata=metadata,
                )
            )
        return plans


__all__ = ["IntentPlanner"]
