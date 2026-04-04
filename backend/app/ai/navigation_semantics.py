"""
Semantic menu navigation helpers / 语义菜单导航辅助工具。

Keeps backend navigation intent checks aligned with frontend semantic menu
matching so planner and router can recognize target pages from menu metadata.
让后端的导航意图判断与前端的语义菜单匹配保持一致，使 planner 与路由器
能基于菜单元数据识别目标页面。
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from app.ai.text_semantics import collapse_whitespace, contains_any_phrase

_QUERY_FILLER_TERMS = (
    "帮我",
    "请帮我",
    "请",
    "麻烦",
    "我想",
    "想要",
    "我要",
    "能不能",
    "可以帮我",
    "给我",
    "一下",
    "一个",
    "一条",
    "一份",
    "新增",
    "添加",
    "新建",
    "创建",
    "打开",
    "进入",
    "跳转",
    "切到",
    "前往",
    "go to",
    "navigate to",
    "switch to",
    "jump to",
    "open",
    "create",
    "add",
    "new",
)
_NAVIGATION_ACTION_TERMS = (
    "添加",
    "新增",
    "新建",
    "创建",
    "打开",
    "进入",
    "跳转",
    "切到",
    "前往",
    "管理",
    "配置",
    "go to",
    "open",
    "navigate",
    "switch to",
    "jump to",
    "create",
    "add",
    "new",
)
_SPACE_EQUIVALENT_CHARS = frozenset({" ", "\t", "\r", "\n", "/", "_", "-"})
_PUNCTUATION_CHARS = frozenset(
    set("()[]{}.,:;!?'\"`~@#$%^&*+=|<>\\")
)


def _replace_chars_with_space(text: str, chars: frozenset[str]) -> str:
    return "".join(" " if char in chars else char for char in text)


def _strip_terms(text: str, phrases: Sequence[str]) -> str:
    normalized = collapse_whitespace(text).lower()
    for phrase in sorted(
        {collapse_whitespace(item).lower() for item in phrases if item},
        key=len,
        reverse=True,
    ):
        while phrase and phrase in normalized:
            normalized = normalized.replace(phrase, " ")
    return collapse_whitespace(normalized)


def _is_compact_subsequence(needle: str, haystack: str) -> bool:
    if not needle or not haystack:
        return False
    cursor = 0
    for char in haystack:
        if char == needle[cursor]:
            cursor += 1
            if cursor >= len(needle):
                return True
    return False


def normalize_navigation_text(value: Any) -> str:
    """Normalize free-form text for semantic matching / 规范化语义匹配文本。"""
    text = str(value or "").strip().lower()
    if not text:
        return ""
    text = _replace_chars_with_space(text, _SPACE_EQUIVALENT_CHARS)
    text = _replace_chars_with_space(text, _PUNCTUATION_CHARS)
    return collapse_whitespace(text)


def compact_navigation_text(value: Any) -> str:
    """Normalize and remove spaces / 规范化后移除空格。"""
    return normalize_navigation_text(value).replace(" ", "")


def _normalize_string_list(values: Any) -> list[str]:
    if not isinstance(values, Sequence) or isinstance(values, (str, bytes)):
        return []
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value or "").strip()
        normalized = normalize_navigation_text(text)
        if not normalized or normalized in seen:
            continue
        result.append(text)
        seen.add(normalized)
    return result


def strip_navigation_fillers(value: str) -> str:
    """Remove action/filler phrases to expose target nouns / 去掉动作和口头填充词。"""
    return _strip_terms(normalize_navigation_text(value), _QUERY_FILLER_TERMS).strip()


def build_navigation_query_variants(query: str) -> list[str]:
    """Build normalized query variants without a local menu synonym catalog. / 构建不依赖本地菜单同义词词典的查询变体。"""
    variants: list[str] = []
    seen: set[str] = set()

    def _add(value: Any) -> None:
        normalized = normalize_navigation_text(value)
        if not normalized or normalized in seen:
            return
        variants.append(normalized)
        seen.add(normalized)

    normalized_query = normalize_navigation_text(query)
    stripped_query = strip_navigation_fillers(query)

    _add(normalized_query)
    _add(stripped_query)

    return variants


def extract_available_menu_entries(
    page_context: Mapping[str, Any] | None,
) -> list[dict[str, Any]]:
    """Extract semantic menu entries from page context / 从页面上下文提取语义菜单条目。"""
    if not isinstance(page_context, Mapping):
        return []
    page_data = page_context.get("page_data")
    if not isinstance(page_data, Mapping):
        return []
    raw_entries = page_data.get("available_menus")
    if not isinstance(raw_entries, list):
        return []

    entries: list[dict[str, Any]] = []
    for item in raw_entries:
        if not isinstance(item, Mapping):
            continue
        title = str(item.get("title") or "").strip()
        path = str(item.get("path") or "").strip()
        page_key = str(item.get("page_key") or "").strip()
        if not (title or path or page_key):
            continue
        entries.append(
            {
                "title": title,
                "path": path,
                "page_key": page_key,
                "description": str(item.get("description") or "").strip(),
                "category": str(item.get("category") or "").strip(),
                "keywords": _normalize_string_list(item.get("keywords")),
                "capabilities": _normalize_string_list(item.get("capabilities")),
                "breadcrumb": _normalize_string_list(item.get("breadcrumb")),
            }
        )
    return entries


def score_navigation_entry(entry: Mapping[str, Any], query: str) -> int:
    """Score a semantic menu entry against user query / 计算菜单条目与用户查询的语义匹配分数。"""
    variants = build_navigation_query_variants(query)
    if not variants:
        return 0

    path = normalize_navigation_text(entry.get("path"))
    page_key = normalize_navigation_text(entry.get("page_key"))
    title = normalize_navigation_text(entry.get("title"))
    description = normalize_navigation_text(entry.get("description"))
    category = normalize_navigation_text(entry.get("category"))
    breadcrumb = normalize_navigation_text(
        " / ".join(_normalize_string_list(entry.get("breadcrumb")))
    )
    keywords = [
        normalize_navigation_text(keyword)
        for keyword in _normalize_string_list(entry.get("keywords"))
    ]
    capabilities = [
        normalize_navigation_text(capability)
        for capability in _normalize_string_list(entry.get("capabilities"))
    ]
    endpoint_adjusted_path = normalize_navigation_text(
        str(entry.get("path") or "").replace("/admin/", "/").replace("/tenant/", "/")
    )
    haystacks = [
        value
        for value in (
            title,
            breadcrumb,
            path,
            page_key,
            endpoint_adjusted_path,
            description,
            category,
            *keywords,
            *capabilities,
        )
        if value
    ]
    compact_haystacks = [compact_navigation_text(value) for value in haystacks]
    compact_title = compact_navigation_text(title)
    compact_breadcrumb = compact_navigation_text(breadcrumb)
    compact_keywords = [compact_navigation_text(keyword) for keyword in keywords]
    compact_capabilities = [
        compact_navigation_text(capability) for capability in capabilities
    ]

    best_score = 0

    for variant in variants:
        compact_variant = compact_navigation_text(variant)
        if not compact_variant:
            continue

        if path == variant or endpoint_adjusted_path == variant:
            best_score = max(best_score, 1000)
            continue
        if page_key == variant:
            best_score = max(best_score, 980)
            continue
        if title == variant:
            best_score = max(best_score, 960)
            continue
        if variant in keywords:
            best_score = max(best_score, 950)
            continue
        if variant in capabilities:
            best_score = max(best_score, 930)
            continue
        if breadcrumb == variant:
            best_score = max(best_score, 920)
            continue
        if compact_variant == compact_title:
            best_score = max(best_score, 910)
            continue
        if compact_variant in compact_keywords:
            best_score = max(best_score, 900)
            continue
        if compact_variant in compact_capabilities:
            best_score = max(best_score, 880)
            continue
        if compact_variant == compact_breadcrumb:
            best_score = max(best_score, 870)
            continue

        if variant and variant in title:
            best_score = max(best_score, 890)
        if any(variant and variant in keyword for keyword in keywords):
            best_score = max(best_score, 880)
        if variant and variant in description:
            best_score = max(best_score, 860)
        if any(variant and variant in capability for capability in capabilities):
            best_score = max(best_score, 840)
        if variant and variant in breadcrumb:
            best_score = max(best_score, 830)
        if variant and variant in page_key:
            best_score = max(best_score, 810)
        if variant and (variant in path or variant in endpoint_adjusted_path):
            best_score = max(best_score, 790)
        if category and category == variant:
            best_score = max(best_score, 770)

        if any(compact_variant in haystack for haystack in compact_haystacks):
            best_score = max(best_score, 720)

        if any(_is_compact_subsequence(compact_variant, haystack) for haystack in compact_haystacks):
            best_score = max(best_score, 640)

        tokens = [token for token in variant.split(" ") if token]
        if len(tokens) > 1 and any(
            all(token in haystack for token in tokens) for haystack in haystacks
        ):
            best_score = max(best_score, 600)

    return best_score


def search_navigation_entries(
    entries: Sequence[Mapping[str, Any]],
    query: str,
) -> list[tuple[Mapping[str, Any], int]]:
    """Return semantic navigation matches sorted by score / 返回按分数排序的语义匹配结果。"""
    scored = [
        (entry, score_navigation_entry(entry, query))
        for entry in entries
    ]
    return sorted(
        [item for item in scored if item[1] > 0],
        key=lambda item: item[1],
        reverse=True,
    )


def has_semantic_navigation_target(
    query: str,
    entries: Sequence[Mapping[str, Any]],
    *,
    min_score: int = 760,
) -> bool:
    """Check whether query maps to an accessible menu / 判断查询是否映射到可访问菜单。"""
    matches = search_navigation_entries(entries, query)
    if not matches:
        return False
    top_entry, top_score = matches[0]
    second_score = matches[1][1] if len(matches) > 1 else 0
    if top_score < min_score:
        return False
    if second_score >= top_score - 40 and top_score < 920:
        return False
    return bool(top_entry)


def has_navigation_intent(
    query: str,
    page_context: Mapping[str, Any] | None = None,
) -> bool:
    """Detect cross-page navigation intent with a shared rule set / 用共享规则检测跨页导航意图。"""
    normalized_query = normalize_navigation_text(query)
    if not normalized_query:
        return False

    has_action = contains_any_phrase(normalized_query, _NAVIGATION_ACTION_TERMS)
    if not has_action:
        return False

    menu_entries = extract_available_menu_entries(page_context)
    return bool(
        menu_entries and has_semantic_navigation_target(normalized_query, menu_entries)
    )


__all__ = [
    "build_navigation_query_variants",
    "compact_navigation_text",
    "extract_available_menu_entries",
    "has_navigation_intent",
    "has_semantic_navigation_target",
    "normalize_navigation_text",
    "score_navigation_entry",
    "search_navigation_entries",
    "strip_navigation_fillers",
]
