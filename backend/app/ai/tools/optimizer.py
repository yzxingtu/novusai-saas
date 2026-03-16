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

import re
from dataclasses import dataclass

from app.ai.tools.types import ToolDefinition
from app.core.logging import LogManager

logger = LogManager.get_logger("ai.tool.optimizer")

# Skip optimization when tool count ≤ this value, pass all / 工具数≤此值时跳过优化
MAX_TOOLS_WITHOUT_OPTIMIZATION = 6

# Maximum tools to keep after optimization / 优化后最多保留的工具数
MAX_TOOLS_AFTER_OPTIMIZATION = 8

# Infrastructure tool whitelist: always kept, not subject to optimization / 基础设施工具白名单
_PROTECTED_TOOL_NAMES: frozenset[str] = frozenset({
    "get_page_context",
    "invoke_page_operation",
})

# Dedicated editor tools (pageop_*) are also protected when present
# 专用 editor tools 存在时同样保护
def _is_protected_tool(name: str) -> bool:
    """Check if tool should be protected from optimization / 工具是否应被保护不被优化"""
    return name in _PROTECTED_TOOL_NAMES or name.startswith("pageop_")

# Chinese stopwords (high-frequency meaningless words) / 中文停用词
_STOPWORDS_ZH = frozenset({
    "的", "了", "在", "是", "我", "有", "和", "就", "不", "人",
    "都", "一", "个", "上", "也", "很", "到", "说", "要", "去",
    "你", "会", "着", "没有", "看", "好", "自己", "这", "他", "她",
    "它", "们", "那", "些", "什么", "怎么", "哪", "为什么", "能",
    "请", "帮", "帮我", "一下", "吗", "呢", "吧", "啊", "嗯",
    "可以", "需要", "想", "能不能", "麻烦",
})

# English stopwords / 英文停用词
_STOPWORDS_EN = frozenset({
    "the", "a", "an", "is", "are", "was", "were", "be", "been",
    "being", "have", "has", "had", "do", "does", "did", "will",
    "would", "could", "should", "may", "might", "can", "shall",
    "i", "you", "he", "she", "it", "we", "they", "me", "him",
    "her", "us", "them", "my", "your", "his", "its", "our",
    "their", "this", "that", "these", "those", "what", "which",
    "who", "whom", "how", "why", "where", "when", "and", "or",
    "but", "if", "then", "so", "than", "too", "very", "just",
    "about", "for", "with", "from", "into", "to", "of", "in",
    "on", "at", "by", "not", "no", "all", "some", "any", "each",
    "please", "help", "want", "need",
})

_STOPWORDS = _STOPWORDS_ZH | _STOPWORDS_EN

# Data-related keywords → boost data_* tools / 数据相关关键词
_DATA_KEYWORDS = frozenset({
    "数据", "查询", "统计", "记录", "表", "创建", "修改", "删除",
    "更新", "新增", "编辑", "添加", "搜索", "筛选", "过滤", "排序",
    "data", "query", "record", "table", "create", "update", "delete",
    "insert", "search", "filter", "sort", "count", "statistics",
    "report", "list", "find", "show", "display",
})

# Knowledge/document keywords → boost knowledge_base tools / 知识文档关键词
_KB_KEYWORDS = frozenset({
    "知识", "文档", "资料", "说明", "手册", "指南", "规范", "政策",
    "制度", "流程", "标准", "参考", "介绍", "解释", "含义", "定义",
    "knowledge", "document", "manual", "guide", "reference", "policy",
    "explain", "definition", "meaning", "describe", "about",
})

# Web search keywords → boost web_search/fetch_url tools / 联网搜索关键词
_WEB_KEYWORDS = frozenset({
    "联网", "搜索", "搜一下", "查一下", "查阅", "上网", "网上",
    "最新", "实时", "新闻", "百科", "维基", "天气", "今天",
    "谁是", "生日", "简介", "官网", "网址", "链接", "网页",
    "search", "internet", "web", "online", "latest", "news",
    "wiki", "wikipedia", "weather", "today", "website", "url",
    "browse", "lookup", "fetch",
})

# Chinese character regex / 中文字符正则
_CJK_RE = re.compile(r"[\u4e00-\u9fff]+")
# English word regex / 英文单词正则
_WORD_RE = re.compile(r"[a-zA-Z]{2,}")


@dataclass
class OptimizeResult:
    """Tool optimization result / 工具优化结果"""

    tools: list[ToolDefinition]
    total: int
    selected: int
    skipped: bool = False


def _tokenize(text: str) -> set[str]:
    """Simple tokenization: extract CJK character groups and English words, remove stopwords / 简单分词"""
    tokens: set[str] = set()

    for match in _CJK_RE.finditer(text):
        chars = match.group()
        # Split Chinese by bigram / 中文按 bigram 拆分
        for i in range(len(chars)):
            char = chars[i]
            if char not in _STOPWORDS:
                tokens.add(char)
            if i < len(chars) - 1:
                bigram = chars[i:i + 2]
                if bigram not in _STOPWORDS:
                    tokens.add(bigram)

    for match in _WORD_RE.finditer(text):
        word = match.group().lower()
        if word not in _STOPWORDS:
            tokens.add(word)

    return tokens


def _score_tool(
    tool: ToolDefinition,
    query_tokens: set[str],
    query_text: str,
    used_tool_names: set[str] | None = None,
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

    # 1. Keyword overlap between tool name/description and query / 工具名描述与查询的关键词重叠
    tool_text = f"{tool.name} {tool.description or ''}"
    tool_tokens = _tokenize(tool_text)
    overlap = query_tokens & tool_tokens
    if overlap:
        score += len(overlap) * 2.0

    # 2. Tool name appears directly in query / 工具名直接出现在查询中
    tool_name_lower = tool.name.lower()
    if tool_name_lower in query_text or tool_name_lower.replace("_", " ") in query_text:
        score += 10.0

    # 3. Data tool boost / 数据类工具加权
    if (
        (tool.name.startswith("data_") or tool.tool_type in ("text_to_sql", "crud"))
        and query_tokens & _DATA_KEYWORDS
    ):
        score += 5.0

    # 4. Knowledge base tool boost / 知识库工具加权
    if ("knowledge" in tool_name_lower or "kb" in tool_name_lower) and query_tokens & _KB_KEYWORDS:
        score += 5.0

    # 4.5 Web search tool boost / 联网搜索工具加权
    if (
        ("search" in tool_name_lower or "fetch" in tool_name_lower or "web" in tool_name_lower)
        and query_tokens & _WEB_KEYWORDS
    ):
        score += 8.0

    # 5. History preference: boost previously used tools / 历史偏好加权
    if used_tool_names and tool.name in used_tool_names:
        score += 3.0

    # 6. Base score (ensure minimum score to avoid unstable sorting) / 基础分
    score += 0.1

    return score


def optimize_tools(
    tools: list[ToolDefinition],
    user_query: str,
    used_tool_names: set[str] | None = None,
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

    # Tool count within threshold, skip optimization / 工具数量在阈值内，跳过优化
    if total <= max_without_optimization:
        return OptimizeResult(
            tools=tools,
            total=total,
            selected=total,
            skipped=True,
        )

    # Separate protected tools and optimizable tools / 分离保护工具与可优化工具
    protected: list[ToolDefinition] = []
    optimizable: list[ToolDefinition] = []
    for tool in tools:
        if _is_protected_tool(tool.name):
            protected.append(tool)
        else:
            optimizable.append(tool)

    # Available budget after deducting protected tools / 扣除保护工具后的可用名额
    budget = max(max_after_optimization - len(protected), 1)

    # Optimizable tools within budget, keep all / 可优化工具在名额内，全部保留
    if len(optimizable) <= budget:
        return OptimizeResult(
            tools=protected + optimizable,
            total=total,
            selected=len(protected) + len(optimizable),
            skipped=True,
        )

    # Tokenize / 分词
    query_text = user_query.lower()
    query_tokens = _tokenize(user_query)

    # Score (only optimizable tools) / 打分
    scored: list[tuple[float, int, ToolDefinition]] = []
    for idx, tool in enumerate(optimizable):
        s = _score_tool(tool, query_tokens, query_text, used_tool_names)
        scored.append((s, idx, tool))

    # Sort by score descending (same score keeps original order) / 按分数降序排序
    scored.sort(key=lambda x: (-x[0], x[1]))

    # Take top-N / 取 top-N
    selected_optimizable = [item[2] for item in scored[:budget]]
    selected = protected + selected_optimizable

    logger.info(
        "Tool optimizer: {} → {} tools ({} protected, query={})",
        total,
        len(selected),
        len(protected),
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
