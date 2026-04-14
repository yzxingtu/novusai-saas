"""
Text Chunker Module / 文本分块器模块

Supports recursive, sentence, semantic, and paragraph chunking.
Unified output as ChunkData list for embedding and storage.
支持递归分割、句子分块、语义分块、段落分块，统一输出 ChunkData 列表供 Embedding 和存储使用。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from app.ai.rag.chunker_support import (
    compute_chunk_hash,
    is_heading_block,
    is_structured_block,
    merge_small_pages,
    prefers_sentence_split,
    split_semantic_units,
    with_overlap_seed,
)
from app.ai.rag.parser import ParsedPage
from app.ai.text_semantics import (
    split_on_blank_lines,
    split_sentences_by_terminal_punctuation,
)
from app.core.logging import LogManager

logger = LogManager.get_logger("ai.rag.chunker")


@dataclass
class ChunkData:
    """Chunk result / 分块结果"""

    content: str
    chunk_index: int
    char_count: int
    content_hash: str
    metadata: dict = field(default_factory=dict)


class BaseChunker(ABC):
    """Base chunker class / 分块器基类"""

    def __init__(self, chunk_size: int = 512, chunk_overlap: int = 50):
        """
        Args:
            chunk_size: Maximum characters per chunk / 每块最大字符数
            chunk_overlap: Overlap characters between chunks / 块间重叠字符数
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    @abstractmethod
    def chunk(self, pages: list[ParsedPage]) -> list[ChunkData]:
        """
        Chunk parsed page list / 将解析页面列表分块

        Args:
            pages: ParsedPage list / ParsedPage 列表

        Returns:
            ChunkData list / ChunkData 列表
        """

    def _build_chunk(self, content: str, index: int, metadata: dict) -> ChunkData:
        """Build a single ChunkData / 构建单个 ChunkData"""
        return ChunkData(
            content=content,
            chunk_index=index,
            char_count=len(content),
            content_hash=compute_chunk_hash(content),
            metadata=metadata,
        )

    def _merge_small_pages(self, pages: list[ParsedPage]) -> list[ParsedPage]:
        """
        Merge adjacent small pages within chunk_size range
        合并相邻小 page 至 chunk_size 范围内

        When Parser outputs many tiny pages (e.g. CSV one page per row),
        chunking each page independently produces fragmented chunks.
        This method merges adjacent small pages into larger ones close to chunk_size,
        preserving semantic coherence.
        当 Parser 输出大量微型 page 时（如 CSV 每行一个 page），
        逐 page 独立分块会产生碎片化 chunk。此方法在分块前将相邻小 page
        合并为接近 chunk_size 的大 page，保留语义连贯性。

        Merge rules / 合并规则：
        - Adjacent pages concatenated (\n\n separated) within chunk_size → merge / 合并
        - Exceeds chunk_size → output accumulated, start new round / 输出，开始新一轮
        - Single page >= chunk_size → output independently / 独立输出

        Returns:
            Merged ParsedPage list / 合并后的 ParsedPage 列表
        """
        return merge_small_pages(pages, chunk_size=self.chunk_size)


class RecursiveChunker(BaseChunker):
    """
    Recursive Splitting Chunker (default strategy)
    递归分割分块器（默认策略）

    Recursively splits by separator priority: \n\n → \n → 。→ ！→ ？→ ；→ space
    Ensures each chunk ≤ chunk_size with chunk_overlap character overlap between chunks.
    按分隔符优先级递归分割：\n\n → \n → 。→ ！→ ？→ ；→ 空格，
    确保每块不超过 chunk_size，块间保留 chunk_overlap 字符重叠。

    Special handling / 特殊处理：
    - Code blocks (```...```) are not split, kept as a whole / 代码块不分割，整体作为一块
    - Heading lines auto-attached to next content block / 标题行自动附带到下一个内容块
    """

    # Separator priority / 分隔符优先级
    SEPARATORS = ["\n\n", "\n", "。", "！", "？", "；", ". ", "! ", "? ", "; ", " "]

    def chunk(self, pages: list[ParsedPage]) -> list[ChunkData]:
        # Pre-merge: merge adjacent small pages to near chunk_size, avoid fragmented chunks
        # 预合并：将相邻小 page 合并至接近 chunk_size，避免碎片化 chunk
        pages = self._merge_small_pages(pages)

        chunks: list[ChunkData] = []
        chunk_index = 0

        for page in pages:
            text = page.content.strip()
            if not text:
                continue

            # Detect code block, do not split / 检测是否为代码块，不分割
            if text.startswith("```") and text.endswith("```"):
                chunks.append(
                    self._build_chunk(text, chunk_index, page.metadata.copy())
                )
                chunk_index += 1
                continue

            # Recursive split / 递归分割
            segments = self._recursive_split(text, 0)

            for segment in segments:
                if not segment.strip():
                    continue
                meta = page.metadata.copy()
                chunks.append(self._build_chunk(segment.strip(), chunk_index, meta))
                chunk_index += 1

        logger.info("RecursiveChunker: {} pages → {} chunks", len(pages), len(chunks))
        return chunks

    def _recursive_split(self, text: str, sep_index: int) -> list[str]:
        """Recursively split text / 递归分割文本"""
        if len(text) <= self.chunk_size:
            return [text]

        if sep_index >= len(self.SEPARATORS):
            # All separators exhausted, hard split / 所有分隔符用尽，硬切
            return self._hard_split(text)

        separator = self.SEPARATORS[sep_index]
        parts = text.split(separator)

        if len(parts) <= 1:
            # Current separator ineffective, try next / 当前分隔符无效，尝试下一个
            return self._recursive_split(text, sep_index + 1)

        result: list[str] = []
        current = ""

        for part in parts:
            candidate = current + separator + part if current else part

            if len(candidate) <= self.chunk_size:
                current = candidate
            else:
                if current:
                    result.append(current)
                    # Keep overlap / 保留重叠
                    if self.chunk_overlap > 0 and len(current) > self.chunk_overlap:
                        overlap_text = current[-self.chunk_overlap :]
                        current = overlap_text + separator + part
                    else:
                        current = part
                else:
                    # Single part exceeds chunk_size, recursively split
                    # 单个 part 超过 chunk_size，递归分割
                    sub_parts = self._recursive_split(part, sep_index + 1)
                    result.extend(sub_parts[:-1])
                    current = sub_parts[-1] if sub_parts else ""

        if current:
            result.append(current)

        return result

    def _hard_split(self, text: str) -> list[str]:
        """Hard split text (last resort) / 硬切文本（最后手段）"""
        result: list[str] = []
        start = 0
        while start < len(text):
            end = min(start + self.chunk_size, len(text))
            result.append(text[start:end])
            start = end - self.chunk_overlap if self.chunk_overlap > 0 else end
        return result


class ParagraphChunker(BaseChunker):
    """
    Paragraph Chunker / 段落分块器

    Splits by natural paragraphs (\n\n), merges small paragraphs,
    recursively splits large ones. Suitable for news, blogs and other
    well-structured documents.
    按自然段落分割（\n\n），小段落合并，大段落用递归分割，
    适用于新闻、博客等段落分明的文档。
    """

    def chunk(self, pages: list[ParsedPage]) -> list[ChunkData]:
        # Pre-merge: merge adjacent small pages to near chunk_size, avoid fragmented chunks
        # 预合并：将相邻小 page 合并至接近 chunk_size，避免碎片化 chunk
        pages = self._merge_small_pages(pages)

        chunks: list[ChunkData] = []
        chunk_index = 0
        recursive = RecursiveChunker(self.chunk_size, self.chunk_overlap)

        for page in pages:
            text = page.content.strip()
            if not text:
                continue

            paragraphs = split_on_blank_lines(text)
            current = ""

            for para in paragraphs:
                para = para.strip()
                if not para:
                    continue

                candidate = current + "\n\n" + para if current else para

                if len(candidate) <= self.chunk_size:
                    current = candidate
                else:
                    if current:
                        chunks.append(
                            self._build_chunk(
                                current, chunk_index, page.metadata.copy()
                            )
                        )
                        chunk_index += 1
                        current = ""

                    if len(para) > self.chunk_size:
                        # Large paragraph, recursively split / 大段落递归分割
                        sub_pages = [
                            ParsedPage(content=para, metadata=page.metadata.copy())
                        ]
                        sub_chunks = recursive.chunk(sub_pages)
                        for sc in sub_chunks:
                            sc.chunk_index = chunk_index
                            chunks.append(sc)
                            chunk_index += 1
                    else:
                        current = para

            if current:
                chunks.append(
                    self._build_chunk(current, chunk_index, page.metadata.copy())
                )
                chunk_index += 1

        logger.info("ParagraphChunker: {} pages → {} chunks", len(pages), len(chunks))
        return chunks


class SentenceChunker(BaseChunker):
    """
    Sentence Chunker / 句子分块器

    Lightweight sentence-boundary chunking for FAQ and short-form text.
    轻量的句边界分块，适合 FAQ 与短文本。
    """

    def chunk(self, pages: list[ParsedPage]) -> list[ChunkData]:
        # Pre-merge: merge adjacent small pages to near chunk_size, avoid fragmented chunks
        # 预合并：将相邻小 page 合并至接近 chunk_size，避免碎片化 chunk
        pages = self._merge_small_pages(pages)

        chunks: list[ChunkData] = []
        chunk_index = 0

        for page in pages:
            text = page.content.strip()
            if not text:
                continue

            # Split by sentences / 按句子分割
            sentences = split_sentences_by_terminal_punctuation(text)

            current = ""
            for sentence in sentences:
                candidate = current + " " + sentence if current else sentence

                if len(candidate) <= self.chunk_size:
                    current = candidate
                else:
                    if current:
                        chunks.append(
                            self._build_chunk(
                                current, chunk_index, page.metadata.copy()
                            )
                        )
                        chunk_index += 1
                        # Overlap / 重叠
                        if self.chunk_overlap > 0 and len(current) > self.chunk_overlap:
                            current = current[-self.chunk_overlap :] + " " + sentence
                        else:
                            current = sentence
                    else:
                        # Single sentence too long, hard split / 单句超长，硬切
                        if len(sentence) > self.chunk_size:
                            start = 0
                            while start < len(sentence):
                                end = min(start + self.chunk_size, len(sentence))
                                chunks.append(
                                    self._build_chunk(
                                        sentence[start:end],
                                        chunk_index,
                                        page.metadata.copy(),
                                    )
                                )
                                chunk_index += 1
                                start = (
                                    end - self.chunk_overlap
                                    if self.chunk_overlap > 0
                                    else end
                                )
                            current = ""
                        else:
                            current = sentence

            if current:
                chunks.append(
                    self._build_chunk(current, chunk_index, page.metadata.copy())
                )
                chunk_index += 1

        logger.info("SentenceChunker: {} pages → {} chunks", len(pages), len(chunks))
        return chunks


class SemanticChunker(BaseChunker):
    """
    Semantic Chunker (structure-aware) / 语义分块器（结构感知）

    Prefers semantic boundaries such as headings, lists, tables and paragraphs,
    then falls back to sentence splitting for oversized blocks.
    优先按标题、列表、表格、段落等结构边界切分，再对超长块回退到句子级拆分。
    """

    def chunk(self, pages: list[ParsedPage]) -> list[ChunkData]:
        pages = self._merge_small_pages(pages)

        chunks: list[ChunkData] = []
        chunk_index = 0
        sentence_chunker = SentenceChunker(self.chunk_size, self.chunk_overlap)
        recursive_chunker = RecursiveChunker(self.chunk_size, self.chunk_overlap)

        for page in pages:
            text = page.content.strip()
            if not text:
                continue

            semantic_units = split_semantic_units(text)
            current = ""
            for unit in semantic_units:
                candidate = current + "\n\n" + unit if current else unit
                if len(candidate) <= self.chunk_size:
                    current = candidate
                    continue

                if current:
                    chunks.append(
                        self._build_chunk(current, chunk_index, page.metadata.copy())
                    )
                    chunk_index += 1

                if len(unit) > self.chunk_size:
                    sub_pages = [
                        ParsedPage(content=unit, metadata=page.metadata.copy())
                    ]
                    splitter = (
                        sentence_chunker
                        if prefers_sentence_split(unit)
                        else recursive_chunker
                    )
                    sub_chunks = splitter.chunk(sub_pages)
                    for sub_chunk in sub_chunks:
                        sub_chunk.chunk_index = chunk_index
                        chunks.append(sub_chunk)
                        chunk_index += 1
                    current = ""
                    continue

                current = with_overlap_seed(
                    current,
                    unit,
                    chunk_overlap=self.chunk_overlap,
                )

            if current:
                chunks.append(
                    self._build_chunk(current, chunk_index, page.metadata.copy())
                )
                chunk_index += 1

        logger.info("SemanticChunker: {} pages → {} chunks", len(pages), len(chunks))
        return chunks

    def _is_heading_block(self, block: str) -> bool:
        return is_heading_block(
            block,
            max_length=max(120, self.chunk_size // 3),
        )

    def _is_structured_block(self, block: str) -> bool:
        return is_structured_block(block)

    def _prefers_sentence_split(self, block: str) -> bool:
        return prefers_sentence_split(block)

    def _with_overlap_seed(self, current: str, next_unit: str) -> str:
        return with_overlap_seed(
            current,
            next_unit,
            chunk_overlap=self.chunk_overlap,
        )


def get_chunker(
    strategy: str, chunk_size: int = 512, chunk_overlap: int = 50
) -> BaseChunker:
    """
    Factory method: get chunker by strategy / 工厂方法：根据策略获取分块器

    Args:
        strategy: Chunking strategy (recursive/sentence/semantic/paragraph) / 分块策略
        chunk_size: Maximum characters per chunk / 每块最大字符数
        chunk_overlap: Overlap characters between chunks / 块间重叠字符数

    Returns:
        Corresponding chunker instance / 对应的分块器实例
    """
    chunkers: dict[str, type[BaseChunker]] = {
        "recursive": RecursiveChunker,
        "sentence": SentenceChunker,
        "semantic": SemanticChunker,
        "paragraph": ParagraphChunker,
    }
    chunker_cls = chunkers.get(strategy, RecursiveChunker)
    return chunker_cls(chunk_size, chunk_overlap)


__all__ = [
    "ChunkData",
    "BaseChunker",
    "RecursiveChunker",
    "SentenceChunker",
    "SemanticChunker",
    "ParagraphChunker",
    "get_chunker",
]
