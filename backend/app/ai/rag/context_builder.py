"""
RAG Context Builder / RAG 上下文构建器

Assembles retrieved chunks into LLM-usable context text,
with precise context length control based on token budget.
将检索到的分块拼接为 LLM 可用的上下文文本，基于 Token 预算精确控制上下文长度。
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

from app.ai.rag.retriever import ChunkSearchResult
from app.ai.utils.token_estimator import estimate_tokens
from app.core.i18n import _
from app.core.logging import LogManager

logger = LogManager.get_logger("ai.rag.context_builder")

# Default token budget parameters / 默认 Token 预算参数
DEFAULT_CONTEXT_TOKEN_RATIO = 0.6  # RAG context ratio of remaining space / RAG 上下文占剩余空间的比例
DEFAULT_OUTPUT_RESERVE = 500  # Minimum tokens reserved for LLM generation / 至少预留给 LLM 生成的 token 数

# RAG context footer (header obtained at runtime via _()) / RAG 上下文拼接后缀（前缀在运行时通过 _() 获取）
RAG_CONTEXT_FOOTER = "\n---\n"


@dataclass
class SourceReference:
    """
    Source Reference / 引用来源

    Used for SSE event rag_sources push to frontend.
    用于 SSE 事件 rag_sources 推送给前端。
    """

    doc_name: str
    doc_id: int
    chunk_id: int
    score: float
    snippet: str
    page: int | None = None
    heading: str | None = None
    chunk_index: int = 0

    def to_dict(self) -> dict:
        """Serialize / 序列化"""
        return asdict(self)


@dataclass
class RAGContext:
    """RAG build result / RAG 构建结果"""

    rag_text: str  # Assembled context text / 拼接后的上下文文本
    sources: list[SourceReference]  # Source reference list / 引用来源列表
    token_count: int  # Token count consumed by context / 上下文消耗的 token 数
    chunk_count: int  # Actual number of chunks included / 实际纳入的分块数


class RAGContextBuilder:
    """
    RAG Context Builder / RAG 上下文构建器

    Core responsibilities / 核心职责：
    1. Add chunks from highest to lowest score within token budget / 按 Token 预算从高分到低分逐块添加
    2. Generate context text with reference numbers / 生成带引用编号的上下文文本
    3. Output SourceReference for SSE push / 输出 SourceReference 供 SSE 推送
    """

    def __init__(
        self,
        context_token_ratio: float = DEFAULT_CONTEXT_TOKEN_RATIO,
        output_reserve: int = DEFAULT_OUTPUT_RESERVE,
    ):
        """
        Args:
            context_token_ratio: RAG context ratio of remaining space / RAG 上下文占剩余空间的比例
            output_reserve: Tokens reserved for LLM generation / 预留给 LLM 生成的 token 数
        """
        self.context_token_ratio = context_token_ratio
        self.output_reserve = output_reserve

    def calculate_rag_budget(
        self,
        max_context_tokens: int,
        system_prompt_tokens: int,
        max_tokens: int | None = None,
    ) -> tuple[int, int]:
        """
        Calculate token budgets for RAG context and conversation history
        计算 RAG 上下文和对话历史的 Token 预算

        Strategy / 策略：
        1. Deduct system_prompt and output reserve from total budget / 从总预算中扣除 system_prompt 和输出预留
        2. Allocate remaining space to RAG by context_token_ratio / 剩余空间按 context_token_ratio 分配给 RAG
        3. Allocate rest to conversation history / 其余分配给对话历史

        Args:
            max_context_tokens: Model total context window tokens / 模型总上下文窗口 token 数
            system_prompt_tokens: Tokens consumed by system_prompt / system_prompt 消耗的 token 数
            max_tokens: LLM max_tokens parameter / LLM max_tokens 参数

        Returns:
            (rag_budget, history_budget): Token budgets for RAG and history / RAG 和对话历史的 token 预算
        """
        output_reserve = max(max_tokens or 0, self.output_reserve)
        remaining = max_context_tokens - system_prompt_tokens - output_reserve
        remaining = max(remaining, 0)

        rag_budget = int(remaining * self.context_token_ratio)
        history_budget = remaining - rag_budget

        return rag_budget, history_budget

    def build_rag_context(
        self,
        chunks: list[ChunkSearchResult],
        token_budget: int,
    ) -> RAGContext:
        """
        Build RAG context / 构建 RAG 上下文

        Adds chunks from highest to lowest score until token budget is exhausted.
        按 score 从高到低逐块添加，直到 token 预算耗尽。

        Args:
            chunks: Retrieval result list (sorted by score desc) / 检索结果列表（已按 score 降序排列）
            token_budget: Available token budget / 可用的 token 预算

        Returns:
            RAGContext with assembled text, sources, and actual token count
            RAGContext 包含拼接文本、来源列表、实际 token 数
        """
        if not chunks or token_budget <= 0:
            return RAGContext(rag_text="", sources=[], token_count=0, chunk_count=0)

        # Get i18n header at runtime / 运行时获取 i18n header
        rag_header = _("ai.rag.context_header") + "\n"

        # Pre-deduct header/footer overhead / 预扣 header/footer 开销
        header_tokens = estimate_tokens(rag_header)
        footer_tokens = estimate_tokens(RAG_CONTEXT_FOOTER)
        available = token_budget - header_tokens - footer_tokens

        if available <= 0:
            return RAGContext(rag_text="", sources=[], token_count=0, chunk_count=0)

        parts: list[str] = []
        sources: list[SourceReference] = []
        used_tokens = 0
        ref_index = 1

        for chunk in chunks:
            # Build single chunk text / 构建单块文本
            source_info = self._format_source_info(chunk)
            line = f"[{ref_index}] {chunk.content}"
            if source_info:
                line += f" — {source_info}"

            line_tokens = estimate_tokens(line)

            # Check if over budget / 检查是否超预算
            if used_tokens + line_tokens > available:
                # If first chunk already exceeds, truncate and add
                # 如果是第一块就超了，截断后添加
                if ref_index == 1:
                    truncated = self._truncate_to_budget(line, available)
                    if truncated:
                        parts.append(truncated)
                        used_tokens += estimate_tokens(truncated)
                        sources.append(self._build_source_ref(chunk, ref_index))
                break

            parts.append(line)
            used_tokens += line_tokens
            sources.append(self._build_source_ref(chunk, ref_index))
            ref_index += 1

        if not parts:
            return RAGContext(rag_text="", sources=[], token_count=0, chunk_count=0)

        rag_text = rag_header + "\n".join(parts) + RAG_CONTEXT_FOOTER
        total_tokens = used_tokens + header_tokens + footer_tokens

        logger.info(
            "RAG context built: %d chunks, %d tokens (budget=%d)",
            len(sources), total_tokens, token_budget,
        )

        return RAGContext(
            rag_text=rag_text,
            sources=sources,
            token_count=total_tokens,
            chunk_count=len(sources),
        )

    @staticmethod
    def _format_source_info(chunk: ChunkSearchResult) -> str:
        """Format source info / 格式化来源信息"""
        parts = []
        if chunk.document_name:
            parts.append(_("ai.rag.source_label", name=chunk.document_name))

        if chunk.metadata:
            page = chunk.metadata.get("page")
            if page is not None:
                parts.append(_("ai.rag.page_label", page=page))

            heading = chunk.metadata.get("heading")
            if heading:
                parts.append(heading)

        return ", ".join(parts)

    @staticmethod
    def _build_source_ref(
        chunk: ChunkSearchResult,
        ref_index: int,
    ) -> SourceReference:
        """Build SourceReference from retrieval result / 从检索结果构建 SourceReference"""
        _ = ref_index
        page = None
        heading = None
        if chunk.metadata:
            page = chunk.metadata.get("page")
            heading = chunk.metadata.get("heading")

        return SourceReference(
            doc_name=chunk.document_name,
            doc_id=chunk.document_id,
            chunk_id=chunk.chunk_id,
            score=chunk.score,
            snippet=RAGContextBuilder._extract_snippet(chunk.content),
            page=page,
            heading=heading,
            chunk_index=chunk.chunk_index,
        )

    @staticmethod
    def _extract_snippet(content: str, max_tokens: int = 80) -> str:
        """
        Smart snippet extraction: truncate at natural boundaries, not hard-coded char count.
        智能提取 snippet：按自然边界截取，而非硬编码字符数。

        Strategy / 策略：
        - Content within token budget → return full text / 内容在 token 预算内 → 直接返回全文
        - Exceeds budget → truncate at natural boundary (period/newline/semicolon/comma)
          超出预算 → 按自然边界（句号/换行/分号/逗号）截断
        - Ensure no mid-word truncation, append ellipsis / 确保不在词中间截断，末尾加省略号

        Args:
            content: Chunk raw text / chunk 原始文本
            max_tokens: Snippet token budget (default 80, ~120-160 Chinese chars)
                        snippet 的 token 预算（默认 80，约 120-160 中文字）
        """
        if not content:
            return ""

        content = content.strip()

        if estimate_tokens(content) <= max_tokens:
            return content

        # Find rough truncation point by token budget (char-level binary search)
        # 按 token 预算找到粗略截断点（字符级二分）
        low, high = 0, len(content)
        while low < high:
            mid = (low + high + 1) // 2
            if estimate_tokens(content[:mid]) <= max_tokens:
                low = mid
            else:
                high = mid - 1

        rough_end = low
        if rough_end <= 0:
            return content[:20] + "..."

        # Find best natural boundary near rough point (priority: period > newline > semicolon > comma)
        # 在粗截断点附近寻找最佳自然边界（优先级：句号 > 换行 > 分号 > 逗号）
        candidates = []
        for sep in ("。", "\n", "；", ". ", "; ", "，", ", "):
            pos = content.rfind(sep, 0, rough_end)
            if pos > rough_end * 0.3:  # 至少保留 30% 内容
                candidates.append((pos + len(sep), sep))

        if candidates:
            best_pos = max(candidates, key=lambda x: x[0])[0]
            snippet = content[:best_pos].rstrip()
        else:
            # No natural boundary: truncate at space/char boundary
            # 无自然边界：按空格/字边界截断
            snippet = content[:rough_end].rstrip()

        return snippet + "..." if len(snippet) < len(content) else snippet

    @staticmethod
    def _truncate_to_budget(text: str, budget: int) -> str:
        """Truncate text to specified token budget / 截断文本到指定 token 预算"""
        if estimate_tokens(text) <= budget:
            return text

        # Binary search for truncation point / 二分查找截断点
        low, high = 0, len(text)
        while low < high:
            mid = (low + high + 1) // 2
            if estimate_tokens(text[:mid]) <= budget:
                low = mid
            else:
                high = mid - 1

        return text[:low] + "..." if low > 0 else ""


__all__ = [
    "RAGContextBuilder",
    "RAGContext",
    "SourceReference",
]
