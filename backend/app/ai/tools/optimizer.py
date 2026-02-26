"""
工具优化选择器（Tool Optimizer）

在 LLM 调用前对工具列表进行预筛选，防止一次性传入过多工具导致 LLM 混乱或 token 浪费。

筛选策略（按优先级）：
1. 关键词匹配：用户消息与工具 description 的关键词重叠度
2. 历史偏好：同一对话中已成功调用过的工具优先保留
3. 类型优先级：data_query 在数据相关问题中优先，knowledge_base 在知识问答中优先
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from app.ai.tools.types import ToolDefinition
from app.core.logging import LogManager

logger = LogManager.get_logger("ai.tool.optimizer")

# 工具数 ≤ 此值时跳过优化，直接全部传入
MAX_TOOLS_WITHOUT_OPTIMIZATION = 6

# 优化后最多保留的工具数
MAX_TOOLS_AFTER_OPTIMIZATION = 8

# 中文分词用的停用词（高频无意义词）
_STOPWORDS_ZH = frozenset({
    "的", "了", "在", "是", "我", "有", "和", "就", "不", "人",
    "都", "一", "个", "上", "也", "很", "到", "说", "要", "去",
    "你", "会", "着", "没有", "看", "好", "自己", "这", "他", "她",
    "它", "们", "那", "些", "什么", "怎么", "哪", "为什么", "能",
    "请", "帮", "帮我", "一下", "吗", "呢", "吧", "啊", "嗯",
    "可以", "需要", "想", "能不能", "麻烦",
})

# 英文停用词
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

# 数据相关关键词 → data_* 工具加权
_DATA_KEYWORDS = frozenset({
    "数据", "查询", "统计", "记录", "表", "创建", "修改", "删除",
    "更新", "新增", "编辑", "添加", "搜索", "筛选", "过滤", "排序",
    "data", "query", "record", "table", "create", "update", "delete",
    "insert", "search", "filter", "sort", "count", "statistics",
    "report", "list", "find", "show", "display",
})

# 知识/文档相关关键词 → knowledge_base 工具加权
_KB_KEYWORDS = frozenset({
    "知识", "文档", "资料", "说明", "手册", "指南", "规范", "政策",
    "制度", "流程", "标准", "参考", "介绍", "解释", "含义", "定义",
    "knowledge", "document", "manual", "guide", "reference", "policy",
    "explain", "definition", "meaning", "describe", "about",
})

# 联网搜索相关关键词 → web_search/fetch_url 工具加权
_WEB_KEYWORDS = frozenset({
    "联网", "搜索", "搜一下", "查一下", "查阅", "上网", "网上",
    "最新", "实时", "新闻", "百科", "维基", "天气", "今天",
    "谁是", "生日", "简介", "官网", "网址", "链接", "网页",
    "search", "internet", "web", "online", "latest", "news",
    "wiki", "wikipedia", "weather", "today", "website", "url",
    "browse", "lookup", "fetch",
})

# 中文字符正则
_CJK_RE = re.compile(r"[\u4e00-\u9fff]+")
# 英文单词正则
_WORD_RE = re.compile(r"[a-zA-Z]{2,}")


@dataclass
class OptimizeResult:
    """工具优化结果"""

    tools: list[ToolDefinition]
    total: int
    selected: int
    skipped: bool = False


def _tokenize(text: str) -> set[str]:
    """简单分词：提取中文字符组和英文单词，去停用词"""
    tokens: set[str] = set()

    for match in _CJK_RE.finditer(text):
        chars = match.group()
        # 中文按 bigram 拆分
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
    为工具打分

    Args:
        tool: 工具定义
        query_tokens: 用户查询分词结果
        query_text: 用户原始查询（小写）
        used_tool_names: 本次对话中已成功调用过的工具名

    Returns:
        相关性分数（越高越相关）
    """
    score = 0.0

    # 1. 工具名/描述与查询的关键词重叠
    tool_text = f"{tool.name} {tool.description or ''}"
    tool_tokens = _tokenize(tool_text)
    overlap = query_tokens & tool_tokens
    if overlap:
        score += len(overlap) * 2.0

    # 2. 工具名直接出现在查询中
    tool_name_lower = tool.name.lower()
    if tool_name_lower in query_text or tool_name_lower.replace("_", " ") in query_text:
        score += 10.0

    # 3. 数据类工具加权
    if tool.name.startswith("data_") or tool.tool_type in ("text_to_sql", "crud"):
        if query_tokens & _DATA_KEYWORDS:
            score += 5.0

    # 4. 知识库工具加权
    if "knowledge" in tool_name_lower or "kb" in tool_name_lower:
        if query_tokens & _KB_KEYWORDS:
            score += 5.0

    # 4.5 联网搜索工具加权
    if "search" in tool_name_lower or "fetch" in tool_name_lower or "web" in tool_name_lower:
        if query_tokens & _WEB_KEYWORDS:
            score += 8.0

    # 5. 历史偏好：已使用过的工具加权
    if used_tool_names and tool.name in used_tool_names:
        score += 3.0

    # 6. 基础分（确保每个工具至少有个最小分数，避免全0排序不稳定）
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
    优化工具列表

    当工具数超过阈值时，根据用户查询内容筛选出最相关的工具子集。

    Args:
        tools: 完整工具定义列表
        user_query: 用户当前查询文本
        used_tool_names: 本次对话中已成功调用过的工具名集合
        max_without_optimization: 工具数 ≤ 此值时跳过优化
        max_after_optimization: 优化后最多保留的工具数

    Returns:
        OptimizeResult
    """
    total = len(tools)

    # 工具数量在阈值内，跳过优化
    if total <= max_without_optimization:
        return OptimizeResult(
            tools=tools,
            total=total,
            selected=total,
            skipped=True,
        )

    # 分词
    query_text = user_query.lower()
    query_tokens = _tokenize(user_query)

    # 打分
    scored: list[tuple[float, int, ToolDefinition]] = []
    for idx, tool in enumerate(tools):
        s = _score_tool(tool, query_tokens, query_text, used_tool_names)
        scored.append((s, idx, tool))

    # 按分数降序排序（分数相同按原始顺序）
    scored.sort(key=lambda x: (-x[0], x[1]))

    # 取 top-N
    selected = [item[2] for item in scored[:max_after_optimization]]

    logger.info(
        "Tool optimizer: %d → %d tools (query=%s)",
        total,
        len(selected),
        user_query[:50],
    )
    if logger.isEnabledFor(10):  # DEBUG
        for s, _, t in scored[:max_after_optimization]:
            logger.debug("  [%.1f] %s", s, t.name)

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
]
