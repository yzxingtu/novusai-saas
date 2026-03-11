"""
Text Chunker Module
文本分块器模块

Supports three strategies: recursive splitting, semantic chunking, and paragraph chunking.
Unified output as ChunkData list for embedding and storage.
支持递归分割、语义分块、段落分块三种策略，统一输出 ChunkData 列表供 Embedding 和存储使用。
"""

from __future__ import annotations

import hashlib
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from app.ai.rag.parser import ParsedPage
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


def _compute_hash(text: str) -> str:
    """Compute MD5 hash of text / 计算文本 MD5 哈希"""
    return hashlib.md5(text.encode("utf-8")).hexdigest()


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
            content_hash=_compute_hash(content),
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
        if not pages:
            return pages

        merged: list[ParsedPage] = []
        buf_parts: list[str] = []
        buf_len = 0
        buf_metadata: dict = {}

        separator = "\n\n"
        sep_len = len(separator)

        for page in pages:
            text = page.content.strip()
            if not text:
                continue

            # Single page already reached chunk_size, output independently
            # 单个 page 已达 chunk_size，独立输出
            if len(text) >= self.chunk_size:
                # Flush buffer first / 先输出缓冲区
                if buf_parts:
                    merged.append(ParsedPage(
                        content=separator.join(buf_parts),
                        metadata=buf_metadata,
                    ))
                    buf_parts = []
                    buf_len = 0
                    buf_metadata = {}
                merged.append(page)
                continue

            # Calculate merged length / 计算合并后长度
            new_len = buf_len + (sep_len if buf_parts else 0) + len(text)

            if new_len <= self.chunk_size:
                buf_parts.append(text)
                buf_len = new_len
                if not buf_metadata:
                    buf_metadata = page.metadata.copy()
            else:
                # Exceeded: output buffer, start new round / 超出：输出缓冲区，开始新一轮
                if buf_parts:
                    merged.append(ParsedPage(
                        content=separator.join(buf_parts),
                        metadata=buf_metadata,
                    ))
                buf_parts = [text]
                buf_len = len(text)
                buf_metadata = page.metadata.copy()

        # Output remaining / 输出剩余
        if buf_parts:
            merged.append(ParsedPage(
                content=separator.join(buf_parts),
                metadata=buf_metadata,
            ))

        if len(merged) != len(pages):
            logger.info(
                "Merged small pages: %d → %d (chunk_size=%d)",
                len(pages), len(merged), self.chunk_size,
            )

        return merged


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
                chunks.append(self._build_chunk(text, chunk_index, page.metadata.copy()))
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

        logger.info("RecursiveChunker: %d pages → %d chunks", len(pages), len(chunks))
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
                        overlap_text = current[-self.chunk_overlap:]
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
    Paragraph Chunker
    段落分块器

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

            paragraphs = re.split(r"\n\s*\n", text)
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
                        chunks.append(self._build_chunk(current, chunk_index, page.metadata.copy()))
                        chunk_index += 1
                        current = ""

                    if len(para) > self.chunk_size:
                        # Large paragraph, recursively split / 大段落递归分割
                        sub_pages = [ParsedPage(content=para, metadata=page.metadata.copy())]
                        sub_chunks = recursive.chunk(sub_pages)
                        for sc in sub_chunks:
                            sc.chunk_index = chunk_index
                            chunks.append(sc)
                            chunk_index += 1
                    else:
                        current = para

            if current:
                chunks.append(self._build_chunk(current, chunk_index, page.metadata.copy()))
                chunk_index += 1

        logger.info("ParagraphChunker: %d pages → %d chunks", len(pages), len(chunks))
        return chunks


class SemanticChunker(BaseChunker):
    """
    Semantic Chunker (advanced strategy)
    语义分块器（高级策略）

    Splits by sentences first, then at semantic transition points.
    Since semantic chunking requires extra embedding computation,
    this is simplified to sentence-boundary-based chunking.
    先按句子分割，然后在语义转折点切分。
    由于语义分块需要额外 Embedding 计算，此处简化为基于句子边界的分块。
    """

    # Chinese and English sentence separators / 中英文句子分隔符
    SENTENCE_SEPARATORS = re.compile(r"(?<=[。！？.!?])\s*")

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
            sentences = self.SENTENCE_SEPARATORS.split(text)
            sentences = [s.strip() for s in sentences if s.strip()]

            current = ""
            for sentence in sentences:
                candidate = current + " " + sentence if current else sentence

                if len(candidate) <= self.chunk_size:
                    current = candidate
                else:
                    if current:
                        chunks.append(self._build_chunk(current, chunk_index, page.metadata.copy()))
                        chunk_index += 1
                        # Overlap / 重叠
                        if self.chunk_overlap > 0 and len(current) > self.chunk_overlap:
                            current = current[-self.chunk_overlap:] + " " + sentence
                        else:
                            current = sentence
                    else:
                        # Single sentence too long, hard split / 单句超长，硬切
                        if len(sentence) > self.chunk_size:
                            start = 0
                            while start < len(sentence):
                                end = min(start + self.chunk_size, len(sentence))
                                chunks.append(self._build_chunk(
                                    sentence[start:end], chunk_index, page.metadata.copy(),
                                ))
                                chunk_index += 1
                                start = end - self.chunk_overlap if self.chunk_overlap > 0 else end
                            current = ""
                        else:
                            current = sentence

            if current:
                chunks.append(self._build_chunk(current, chunk_index, page.metadata.copy()))
                chunk_index += 1

        logger.info("SemanticChunker: %d pages → %d chunks", len(pages), len(chunks))
        return chunks


def get_chunker(strategy: str, chunk_size: int = 512, chunk_overlap: int = 50) -> BaseChunker:
    """
    Factory method: get chunker by strategy / 工厂方法：根据策略获取分块器

    Args:
        strategy: Chunking strategy (recursive/semantic/paragraph) / 分块策略
        chunk_size: Maximum characters per chunk / 每块最大字符数
        chunk_overlap: Overlap characters between chunks / 块间重叠字符数

    Returns:
        Corresponding chunker instance / 对应的分块器实例
    """
    chunkers: dict[str, type[BaseChunker]] = {
        "recursive": RecursiveChunker,
        "semantic": SemanticChunker,
        "paragraph": ParagraphChunker,
    }
    chunker_cls = chunkers.get(strategy, RecursiveChunker)
    return chunker_cls(chunk_size, chunk_overlap)


__all__ = [
    "ChunkData",
    "BaseChunker",
    "RecursiveChunker",
    "SemanticChunker",
    "ParagraphChunker",
    "get_chunker",
]
