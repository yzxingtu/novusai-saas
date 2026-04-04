"""
Tool Optimizer / 工具优化选择器

Pre-filters the tool list before LLM invocation to prevent passing too many tools
at once, which may confuse the LLM or waste tokens.
在 LLM 调用前对工具列表进行预筛选，防止一次性传入过多工具导致 LLM 混乱或 token 浪费。

Filtering strategies (by priority):
筛选策略（按优先级）：
1. Keyword matching: overlap between user message and tool description keywords
   关键词匹配：用户消息与工具 description 的关键词重叠度
2. History preference: tools successfully called in the same conversation are prioritized
   历史偏好：同一对话中已成功调用过的工具优先保留
3. Type priority: data_query prioritized for data questions, knowledge_base for knowledge Q&A
   类型优先级：data_query 在数据相关问题中优先
"""

from __future__ import annotations

from dataclasses import dataclass

from app.ai.text_semantics import (
    extract_cjk_bigram_and_word_tokens,
    has_forbid_instruction_phrase,
)
from app.ai.tools.semantic_defaults import (
    FAMILY_EXPLICIT_REQUEST_HINTS,
    tool_semantic_family,
    tool_semantic_tags,
)
from app.ai.tools.types import ToolDefinition
from app.core.logging import LogManager

logger = LogManager.get_logger("ai.tool.optimizer")

# Skip optimization when tool count ≤ this value, pass all / 工具数≤此值时跳过优化
MAX_TOOLS_WITHOUT_OPTIMIZATION = 6

# Maximum tools to keep after optimization / 优化后最多保留的工具数
MAX_TOOLS_AFTER_OPTIMIZATION = 8

# Infrastructure tool whitelist: always kept, not subject to optimization / 基础设施工具白名单
PROTECTED_TOOL_NAMES: frozenset[str] = frozenset(
    {
        "get_page_context",
        "invoke_page_operation",
    }
)


def _tool_semantic_family(tool: ToolDefinition) -> str:
    return tool_semantic_family(tool)


def _tool_semantic_tags(tool: ToolDefinition) -> list[str]:
    return tool_semantic_tags(tool)


def _tool_semantic_query_tokens(tool: ToolDefinition) -> set[str]:
    return _tokenize(" ".join(_tool_semantic_tags(tool)))


def _family_query_tokens(tools: list[ToolDefinition], family: str) -> set[str]:
    tokens: set[str] = set()
    for tool in tools:
        if _tool_semantic_family(tool) != family:
            continue
        tokens |= _tool_semantic_query_tokens(tool)
    return tokens


def _query_mentions_family(
    query_text: str,
    query_tokens: set[str],
    family_tokens: set[str],
    family_hints: tuple[str, ...],
) -> bool:
    if family_tokens and query_tokens & family_tokens:
        return True
    return any(len(hint) > 1 and hint in query_text for hint in family_hints)


def _query_forbids_family(
    query_text: str,
    query_tokens: set[str],
    family_tokens: set[str],
    family_hints: tuple[str, ...],
) -> bool:
    if not has_forbid_instruction_phrase(query_text):
        return False
    return _query_mentions_family(query_text, query_tokens, family_tokens, family_hints)


# Dedicated editor tools (pageop_*) and data tools (data_*) are also protected when present
# 专用 editor tools 和 data tools 存在时同样保护
def _is_protected_tool(
    tool: ToolDefinition,
    preferred_family: str | None = None,
) -> bool:
    """Check if tool should be protected from optimization / 工具是否应被保护不被优化"""
    family = _tool_semantic_family(tool)
    if preferred_family:
        if family == preferred_family:
            return True
        if preferred_family == "web_research":
            return tool.name in PROTECTED_TOOL_NAMES
        return False
    if tool.name in PROTECTED_TOOL_NAMES:
        return True
    return family in {"page_ops", "data_ops"}


def _is_explicitly_requested_tool(
    tool: ToolDefinition,
    query_text: str,
) -> bool:
    """Check whether the query explicitly asks for a tool or its semantic capability. / 检查查询是否显式点名工具或其语义能力。"""
    tool_name_lower = tool.name.lower()
    if tool_name_lower in query_text or tool_name_lower.replace("_", " ") in query_text:
        return True

    explicit_hints = [
        str(hint).strip().lower()
        for hint in FAMILY_EXPLICIT_REQUEST_HINTS.get(_tool_semantic_family(tool), ())
        if len(str(hint).strip()) >= 2
    ]
    if any(hint in query_text for hint in explicit_hints):
        return True

    semantic_phrases = [
        str(tag).strip().lower()
        for tag in _tool_semantic_tags(tool)
        if len(str(tag).strip()) >= 4
    ]
    return any(tag in query_text for tag in semantic_phrases)


# Chinese stopwords (high-frequency meaningless words) / 中文停用词
_STOPWORDS_ZH = frozenset(
    {
        "的",
        "了",
        "在",
        "是",
        "我",
        "有",
        "和",
        "就",
        "不",
        "人",
        "都",
        "一",
        "个",
        "上",
        "也",
        "很",
        "到",
        "说",
        "要",
        "去",
        "你",
        "会",
        "着",
        "没有",
        "看",
        "好",
        "自己",
        "这",
        "他",
        "她",
        "它",
        "们",
        "那",
        "些",
        "什么",
        "怎么",
        "哪",
        "为什么",
        "能",
        "请",
        "帮",
        "帮我",
        "一下",
        "吗",
        "呢",
        "吧",
        "啊",
        "嗯",
        "可以",
        "需要",
        "想",
        "能不能",
        "麻烦",
    }
)

# English stopwords / 英文停用词
_STOPWORDS_EN = frozenset(
    {
        "the",
        "a",
        "an",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "have",
        "has",
        "had",
        "do",
        "does",
        "did",
        "will",
        "would",
        "could",
        "should",
        "may",
        "might",
        "can",
        "shall",
        "i",
        "you",
        "he",
        "she",
        "it",
        "we",
        "they",
        "me",
        "him",
        "her",
        "us",
        "them",
        "my",
        "your",
        "his",
        "its",
        "our",
        "their",
        "this",
        "that",
        "these",
        "those",
        "what",
        "which",
        "who",
        "whom",
        "how",
        "why",
        "where",
        "when",
        "and",
        "or",
        "but",
        "if",
        "then",
        "so",
        "than",
        "too",
        "very",
        "just",
        "about",
        "for",
        "with",
        "from",
        "into",
        "to",
        "of",
        "in",
        "on",
        "at",
        "by",
        "not",
        "no",
        "all",
        "some",
        "any",
        "each",
        "please",
        "help",
        "want",
        "need",
    }
)

_STOPWORDS = _STOPWORDS_ZH | _STOPWORDS_EN

@dataclass
class OptimizeResult:
    """Tool optimization result / 工具优化结果"""

    tools: list[ToolDefinition]
    total: int
    selected: int
    skipped: bool = False


def _tokenize(text: str) -> set[str]:
    """Simple tokenization: extract CJK character groups and English words, remove stopwords / 简单分词"""
    return extract_cjk_bigram_and_word_tokens(text, stopwords=_STOPWORDS)


def _score_tool(
    tool: ToolDefinition,
    query_tokens: set[str],
    query_text: str,
    used_tool_names: set[str] | None = None,
    prefer_weather_tools: bool = False,
    preferred_family: str | None = None,
) -> float:
    """
    Score a tool for relevance / 为工具打分

    Args:
        tool: Tool definition / 工具定义
        query_tokens: User query tokenization result / 用户查询分词结果
        query_text: User original query (lowercase) / 用户原始查询
        used_tool_names: Tool names already called in this conversation / 已调用工具名

    Returns:
        Relevance score (higher is more relevant) / 相关性分数
    """
    score = 0.0
    tool_family = _tool_semantic_family(tool)
    semantic_query_tokens = _tool_semantic_query_tokens(tool)
    family_hints = FAMILY_EXPLICIT_REQUEST_HINTS.get(tool_family, ())

    # 1. Keyword overlap between tool name/description and query / 工具名描述与查询的关键词重叠
    tool_text = " ".join(
        [tool.name, tool.description or "", *_tool_semantic_tags(tool)]
    )
    tool_tokens = _tokenize(tool_text)
    overlap = query_tokens & tool_tokens
    if overlap:
        score += len(overlap) * 2.0

    # 2. Tool name appears directly in query / 工具名直接出现在查询中
    tool_name_lower = tool.name.lower()
    if tool_name_lower in query_text or tool_name_lower.replace("_", " ") in query_text:
        score += 10.0

    if _query_mentions_family(
        query_text,
        query_tokens,
        semantic_query_tokens,
        family_hints,
    ):
        score += 4.0

    # 3. Data tool boost / 数据类工具加权
    if (
        tool_family == "data_ops" or tool.tool_type in ("text_to_sql", "crud")
    ) and _query_mentions_family(
        query_text,
        query_tokens,
        semantic_query_tokens,
        family_hints,
    ):
        score += 5.0

    # 4. Knowledge base tools: no fixed vocabulary list — overlap with name/description/tags (steps 1 & 3) already scores relevance.

    # 4.5 Web search tool boost / 联网搜索工具加权
    if tool_family == "web_research" and _query_mentions_family(
        query_text,
        query_tokens,
        semantic_query_tokens,
        family_hints,
    ):
        score += 8.0

    # 4.6 Weather tool boost / 天气工具加权
    if tool_family == "weather" and _query_mentions_family(
        query_text,
        query_tokens,
        semantic_query_tokens,
        family_hints,
    ):
        score += 8.0

    if tool_family == "time_ops" and _query_mentions_family(
        query_text,
        query_tokens,
        semantic_query_tokens,
        family_hints,
    ):
        score += 10.0

    if prefer_weather_tools:
        if tool_family == "weather":
            score += 12.0
        elif tool_family == "web_research":
            score -= 4.0

    # 4.7 Negative preference: user explicitly forbids web search / 用户明确禁止联网搜索时降低联网工具分数
    if tool_family == "web_research" and _query_forbids_family(
        query_text,
        query_tokens,
        semantic_query_tokens,
        family_hints,
    ):
        score -= 20.0

    # 5. History preference: boost previously used tools / 历史偏好加权
    if used_tool_names and tool.name in used_tool_names:
        score += 3.0

    if preferred_family == "web_research":
        if tool_family == "web_research":
            score += 15.0
        elif tool_family == "data_ops":
            score -= 25.0
        elif tool_family == "page_ops":
            score -= 8.0
        elif tool_family in {"weather", "time_ops"}:
            score -= 6.0
    elif preferred_family == "weather":
        if tool_family == "weather":
            score += 15.0
        elif tool_family in {"web_research", "data_ops", "page_ops", "time_ops"}:
            score -= 10.0
    elif preferred_family == "time_ops":
        if tool_family == "time_ops":
            score += 15.0
        elif tool_family in {"web_research", "weather", "data_ops", "page_ops"}:
            score -= 8.0
    elif preferred_family == "data_ops":
        if tool_family == "data_ops":
            score += 15.0
        elif tool_family in {"web_research", "weather", "time_ops", "page_ops"}:
            score -= 8.0
    elif preferred_family == "page_ops":
        if tool_family == "page_ops":
            score += 15.0
        elif tool_family in {"web_research", "weather", "time_ops", "data_ops"}:
            score -= 8.0

    # 6. Base score (ensure minimum score to avoid unstable sorting) / 基础分
    score += 0.1

    return score


def optimize_tools(
    tools: list[ToolDefinition],
    user_query: str,
    used_tool_names: set[str] | None = None,
    preferred_family: str | None = None,
    max_without_optimization: int = MAX_TOOLS_WITHOUT_OPTIMIZATION,
    max_after_optimization: int = MAX_TOOLS_AFTER_OPTIMIZATION,
) -> OptimizeResult:
    """
    Optimize tool list / 优化工具列表

    When tool count exceeds the threshold, filter out the most relevant tool subset
    based on user query content.
    当工具数超过阈值时，根据用户查询内容筛选出最相关的工具子集。

    Args:
        tools: Full tool definition list / 完整工具定义列表
        user_query: User current query text / 用户当前查询文本
        used_tool_names: Tool names successfully called in this conversation / 已调用工具名集合
        max_without_optimization: Skip optimization when count ≤ this / 跳过优化阈值
        max_after_optimization: Max tools to keep after optimization / 优化后最多保留数

    Returns:
        OptimizeResult
    """
    total = len(tools)
    query_text = user_query.lower()
    query_tokens = _tokenize(user_query)

    # Tool count within threshold, skip optimization / 工具数量在阈值内，跳过优化
    if total <= max_without_optimization and not preferred_family:
        return OptimizeResult(
            tools=tools,
            total=total,
            selected=total,
            skipped=True,
        )

    # Separate protected tools and optimizable tools / 分离保护工具与可优化工具
    protected: list[ToolDefinition] = []
    explicitly_requested: list[ToolDefinition] = []
    optimizable: list[ToolDefinition] = []
    for tool in tools:
        if _is_protected_tool(tool, preferred_family=preferred_family):
            protected.append(tool)
            continue

        if _is_explicitly_requested_tool(tool, query_text):
            explicitly_requested.append(tool)
        else:
            optimizable.append(tool)

    # Available budget after deducting protected tools / 扣除保护工具后的可用名额
    budget = max(
        max_after_optimization - len(protected) - len(explicitly_requested),
        0,
    )

    # Optimizable tools within budget, keep all / 可优化工具在名额内，全部保留
    if len(optimizable) <= budget:
        if preferred_family:
            prefer_weather_tools = _query_mentions_family(
                query_text,
                query_tokens,
                _family_query_tokens(tools, "weather"),
                FAMILY_EXPLICIT_REQUEST_HINTS.get("weather", ()),
            ) and any(_tool_semantic_family(tool) == "weather" for tool in tools)
            scored = []
            for idx, tool in enumerate(optimizable):
                score = _score_tool(
                    tool,
                    query_tokens,
                    query_text,
                    used_tool_names,
                    prefer_weather_tools=prefer_weather_tools,
                    preferred_family=preferred_family,
                )
                scored.append((score, idx, tool))
            scored.sort(key=lambda item: (-item[0], item[1]))
            sorted_optimizable = [item[2] for item in scored]
            return OptimizeResult(
                tools=protected + explicitly_requested + sorted_optimizable,
                total=total,
                selected=len(protected)
                + len(explicitly_requested)
                + len(sorted_optimizable),
                skipped=False,
            )
        return OptimizeResult(
            tools=protected + explicitly_requested + optimizable,
            total=total,
            selected=len(protected) + len(explicitly_requested) + len(optimizable),
            skipped=True,
        )

    if budget == 0:
        return OptimizeResult(
            tools=protected + explicitly_requested,
            total=total,
            selected=len(protected) + len(explicitly_requested),
            skipped=False,
        )

    # Score (only optimizable tools) / 打分
    prefer_weather_tools = _query_mentions_family(
        query_text,
        query_tokens,
        _family_query_tokens(tools, "weather"),
        FAMILY_EXPLICIT_REQUEST_HINTS.get("weather", ()),
    ) and any(_tool_semantic_family(tool) == "weather" for tool in tools)
    scored: list[tuple[float, int, ToolDefinition]] = []
    for idx, tool in enumerate(optimizable):
        s = _score_tool(
            tool,
            query_tokens,
            query_text,
            used_tool_names,
            prefer_weather_tools=prefer_weather_tools,
            preferred_family=preferred_family,
        )
        scored.append((s, idx, tool))

    # Sort by score descending (same score keeps original order) / 按分数降序排序
    scored.sort(key=lambda x: (-x[0], x[1]))

    # Take top-N / 取 top-N
    selected_optimizable = [item[2] for item in scored[:budget]]
    selected = protected + explicitly_requested + selected_optimizable

    logger.info(
        "Tool optimizer: {} → {} tools (family={} protected={} explicit={} selected_tool_names={} dropped_tool_names={} query={})",
        total,
        len(selected),
        preferred_family or "none",
        len(protected),
        len(explicitly_requested),
        [tool.name for tool in selected],
        [tool.name for tool in tools if tool not in selected],
        user_query[:50],
    )
    # Loguru 无 isEnabledFor，使用 getattr 兼容 / Loguru has no isEnabledFor, use getattr for compat
    if getattr(logger, "isEnabledFor", lambda _: False)(10):
        for t in protected:
            logger.debug("  [protected] {}", t.name)
        for s, _, t in scored[:budget]:
            logger.debug("  [{}] {}", s, t.name)

    return OptimizeResult(
        tools=selected,
        total=total,
        selected=len(selected),
        skipped=False,
    )


__all__ = [
    "optimize_tools",
    "OptimizeResult",
    "MAX_TOOLS_WITHOUT_OPTIMIZATION",
    "MAX_TOOLS_AFTER_OPTIMIZATION",
    "PROTECTED_TOOL_NAMES",
]
