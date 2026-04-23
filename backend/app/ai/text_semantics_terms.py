"""Phrase and reply semantics helpers for AI runtime flows."""

from __future__ import annotations

from collections.abc import Iterable

_MODEL_FC_BLOCK_MARKERS = (
    ("<｜DSML｜function_calls>", "</｜DSML｜function_calls>"),
    ("<｜DSML｜tool_calls>", "</｜DSML｜tool_calls>"),
)
_MODEL_FC_TAG_PREFIXES = ("<｜", "</｜")

_TRAILING_REPLY_PUNCTUATION = frozenset({"!", ".", "?", "！", "。", "？", "…"})
_CONFIRMATION_REPLIES = frozenset(
    {
        "确认执行",
        "确认",
        "执行",
        "好的",
        "好",
        "好吧",
        "是",
        "是的",
        "是吧",
        "可以",
        "行",
        "嗯",
        "没问题",
        "妥了",
        "confirm",
        "yes",
        "ok",
        "okay",
        "sure",
        "yep",
        "yeah",
        "go ahead",
        "proceed",
    }
)
_REJECTION_REPLIES = frozenset(
    {
        "取消",
        "拒绝",
        "不执行",
        "不要",
        "不要了",
        "不",
        "算了",
        "别",
        "甭",
        "cancel",
        "no",
        "reject",
        "abort",
        "stop",
        "nope",
    }
)
_QUESTION_INDICATORS = (
    "为什么",
    "怎么样",
    "怎么办",
    "怎么回事",
    "怎么",
    "如何",
    "啥",
    "哪个",
    "哪样",
    "哪里",
    "哪些",
    "哪种",
    "是不是",
    "对吗",
    "对不对",
    "咋样",
    "咋办",
    "咋",
    "几个",
    "几点",
    "几号",
    "几时",
    "多少",
    "多大",
    "多长",
    "多久",
)
_CAPABILITY_DENIAL_TERMS = (
    "无法",
    "不能",
    "不可以",
    "做不到",
    "没法",
    "没有",
    "没有权限",
    "不具备",
    "缺少权限",
    "只读",
    "read only",
    "readonly",
    "lacking",
    "lack",
    "can't",
    "cannot",
    "unable",
    "no access",
    "not able",
    "don't have",
    "do not have",
    "doesn't have",
)
_TOOL_PLANNING_LEAK_TERMS = (
    "to fulfill the user's request",
    "to fulfill the users request",
    "according to workflow",
    "first call ",
    "calling ",
    "invoking ",
    "invoke ",
    "正在调用",
    "调用 ",
    "then ",
    "<｜dsml｜tool_calls>",
    "<｜dsml｜invoke",
)
_FORBID_INSTRUCTION_TERMS = (
    "不要",
    "别",
    "不用",
    "无需",
    "勿",
    "甭",
    "dont",
    "don't",
    "do not",
    "without",
    "no need",
)
_WEATHER_TERMS = (
    "天气",
    "气温",
    "温度",
    "气候",
    "降雨",
    "湿度",
    "weather",
    "temperature",
)
_RAIL_TICKET_TERMS = (
    "高铁票",
    "动车票",
    "火车票",
    "车票",
    "12306",
    "列车票",
    "高铁",
)
_PAGE_SUMMARY_TERMS = (
    "本页面",
    "当前页面",
    "页面里有什么",
    "页面上有什么",
    "页面都有什么",
    "阅读页面",
    "读一下页面",
    "看看页面",
    "页面有什么内容",
)
_PAGE_DETAIL_OPERATION_TERMS = (
    "创建",
    "新增",
    "添加",
    "绑定",
    "授权",
    "编辑",
    "修改",
    "删除",
    "提交",
    "填写",
    "表单",
    "搜索",
    "筛选",
    "刷新",
    "截图",
    "截屏",
    "可见行",
    "可见记录",
    "列表明细",
    "表格明细",
    "ui_click",
    "ui_open_surface",
    "ui_read_region",
    "ui_read_table",
    "bind",
    "grant",
    "ui_fill_form",
    "ui_submit_form",
    "ui_get_form_",
)
_WEB_SEARCH_PREFIXES = ("search results for:",)
_FETCH_URL_PREFIXES = ("content from http://", "content from https://")


def collapse_whitespace(text: str | None) -> str:
    return " ".join((text or "").split())


def normalize_match_text(text: str | None) -> str:
    return collapse_whitespace(text).strip().lower()


def contains_any_phrase(text: str | None, phrases: Iterable[str]) -> bool:
    normalized = normalize_match_text(text)
    return any(str(phrase or "").lower() in normalized for phrase in phrases if phrase)


def strip_trailing_reply_punctuation(text: str | None) -> str:
    normalized = collapse_whitespace(text).strip()
    while normalized and normalized[-1] in _TRAILING_REPLY_PUNCTUATION:
        normalized = normalized[:-1].rstrip()
    return normalized


def is_confirmation_reply(text: str | None) -> bool:
    normalized = normalize_match_text(strip_trailing_reply_punctuation(text))
    return bool(normalized and normalized in _CONFIRMATION_REPLIES)


def is_rejection_reply(text: str | None) -> bool:
    normalized = normalize_match_text(strip_trailing_reply_punctuation(text))
    return bool(normalized and normalized in _REJECTION_REPLIES)


def has_question_indicator(text: str | None) -> bool:
    return contains_any_phrase(text, _QUESTION_INDICATORS)


def has_capability_denial_phrase(text: str | None) -> bool:
    return contains_any_phrase(text, _CAPABILITY_DENIAL_TERMS)


def has_tool_planning_leak_phrase(text: str | None) -> bool:
    return contains_any_phrase(text, _TOOL_PLANNING_LEAK_TERMS)


def has_forbid_instruction_phrase(text: str | None) -> bool:
    return contains_any_phrase(text, _FORBID_INSTRUCTION_TERMS)


def mentions_weather(text: str | None) -> bool:
    return contains_any_phrase(text, _WEATHER_TERMS)


def mentions_rail_ticket(text: str | None) -> bool:
    return contains_any_phrase(text, _RAIL_TICKET_TERMS)


def mentions_page_summary(text: str | None) -> bool:
    return contains_any_phrase(text, _PAGE_SUMMARY_TERMS)


def mentions_page_detail_operation(text: str | None) -> bool:
    return contains_any_phrase(text, _PAGE_DETAIL_OPERATION_TERMS)


def strip_model_function_call_markup(text: str | None) -> str:
    raw = text or ""
    if "｜" not in raw:
        return raw

    cleaned = raw
    for block_start, block_end in _MODEL_FC_BLOCK_MARKERS:
        while True:
            start = cleaned.find(block_start)
            if start < 0:
                break
            end = cleaned.find(block_end, start + len(block_start))
            if end < 0:
                cleaned = cleaned[:start]
                break
            cleaned = cleaned[:start] + cleaned[end + len(block_end) :]

    result: list[str] = []
    idx = 0
    length = len(cleaned)
    while idx < length:
        if cleaned.startswith(_MODEL_FC_TAG_PREFIXES[0], idx) or cleaned.startswith(
            _MODEL_FC_TAG_PREFIXES[1],
            idx,
        ):
            close = cleaned.find(">", idx)
            if close < 0:
                break
            idx = close + 1
            continue
        result.append(cleaned[idx])
        idx += 1
    return "".join(result)


def extract_textual_tool_call_names(
    text: str | None,
    *,
    alias_to_tool_name: dict[str, str],
    known_tool_names: set[str] | None = None,
) -> list[str]:
    normalized = collapse_whitespace(text)
    lowered = normalized.lower()
    if not lowered:
        return []

    matched: list[str] = []

    def _append(candidate: str) -> None:
        actual = alias_to_tool_name.get(candidate, candidate)
        if (
            actual
            and (known_tool_names is None or actual in known_tool_names)
            and actual not in matched
        ):
            matched.append(actual)

    for alias, actual in alias_to_tool_name.items():
        alias_key = normalize_match_text(alias)
        if not alias_key:
            continue
        markers = (
            f"functions.{alias_key}",
            f"{alias_key}(",
            f"call {alias_key}",
            f"calling {alias_key}",
            f"invoking {alias_key}",
            f"invoke {alias_key}",
            f'invoke name="{alias_key}"',
            f"invoke name='{alias_key}'",
            f'invoke name=“{alias_key}”',
            f"invoke name=‘{alias_key}’",
            f'name="{alias_key}"',
            f"name='{alias_key}'",
            f'name=“{alias_key}”',
            f"name=‘{alias_key}’",
            f'"name":"{alias_key}"',
            f"'name':'{alias_key}'",
            f"正在调用{alias_key}",
            f"正在调用 {alias_key}",
            f"调用{alias_key}",
            f"调用 {alias_key}",
            f"then {alias_key}",
            f"next {alias_key}",
        )
        if any(marker in lowered for marker in markers):
            _append(actual)

    if any(lowered.startswith(prefix) for prefix in _WEB_SEARCH_PREFIXES):
        _append("web_search")
    if any(lowered.startswith(prefix) for prefix in _FETCH_URL_PREFIXES):
        _append("fetch_url")
    if "candidate url" in lowered and "fetch_url" in lowered:
        _append("fetch_url")

    return matched


__all__ = [
    "collapse_whitespace",
    "contains_any_phrase",
    "extract_textual_tool_call_names",
    "has_capability_denial_phrase",
    "has_forbid_instruction_phrase",
    "has_question_indicator",
    "has_tool_planning_leak_phrase",
    "is_confirmation_reply",
    "is_rejection_reply",
    "mentions_page_detail_operation",
    "mentions_page_summary",
    "mentions_rail_ticket",
    "mentions_weather",
    "normalize_match_text",
    "strip_model_function_call_markup",
    "strip_trailing_reply_punctuation",
]
