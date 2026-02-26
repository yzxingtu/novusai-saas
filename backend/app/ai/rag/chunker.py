"""
文本分块器模块

支持递归分割、语义分块、段落分块三种策略
统一输出 ChunkData 列表供 Embedding 和存储使用
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
    """分块结果"""
    content: str
    chunk_index: int
    char_count: int
    content_hash: str
    metadata: dict = field(default_factory=dict)


def _compute_hash(text: str) -> str:
    """计算文本 MD5 哈希"""
    return hashlib.md5(text.encode("utf-8")).hexdigest()


class BaseChunker(ABC):
    """分块器基类"""

    def __init__(self, chunk_size: int = 512, chunk_overlap: int = 50):
        """
        Args:
            chunk_size: 每块最大字符数
            chunk_overlap: 块间重叠字符数
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    @abstractmethod
    def chunk(self, pages: list[ParsedPage]) -> list[ChunkData]:
        """
        将解析页面列表分块

        Args:
            pages: ParsedPage 列表

        Returns:
            ChunkData 列表
        """

    def _build_chunk(self, content: str, index: int, metadata: dict) -> ChunkData:
        """构建单个 ChunkData"""
        return ChunkData(
            content=content,
            chunk_index=index,
            char_count=len(content),
            content_hash=_compute_hash(content),
            metadata=metadata,
        )

    def _merge_small_pages(self, pages: list[ParsedPage]) -> list[ParsedPage]:
        """
        合并相邻小 page 至 chunk_size 范围内

        当 Parser 输出大量微型 page 时（如 CSV 每行一个 page），
        逐 page 独立分块会产生碎片化 chunk。此方法在分块前将相邻小 page
        合并为接近 chunk_size 的大 page，保留语义连贯性。

        合并规则：
        - 相邻 page 内容拼接（\\n\\n 分隔）不超过 chunk_size → 合并
        - 超过 chunk_size → 当前累积 page 输出，开始新一轮
        - 单个 page 已 >= chunk_size → 独立输出，不与其他 page 合并

        Returns:
            合并后的 ParsedPage 列表
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

            # 单个 page 已达 chunk_size，独立输出
            if len(text) >= self.chunk_size:
                # 先输出缓冲区
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

            # 计算合并后长度
            new_len = buf_len + (sep_len if buf_parts else 0) + len(text)

            if new_len <= self.chunk_size:
                buf_parts.append(text)
                buf_len = new_len
                if not buf_metadata:
                    buf_metadata = page.metadata.copy()
            else:
                # 超出：输出缓冲区，开始新一轮
                if buf_parts:
                    merged.append(ParsedPage(
                        content=separator.join(buf_parts),
                        metadata=buf_metadata,
                    ))
                buf_parts = [text]
                buf_len = len(text)
                buf_metadata = page.metadata.copy()

        # 输出剩余
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
    递归分割分块器（默认策略）

    按分隔符优先级递归分割：\\n\\n → \\n → 。→ ！→ ？→ ；→ 空格
    确保每块不超过 chunk_size，块间保留 chunk_overlap 字符重叠

    特殊处理：
    - 代码块（```...```）不分割，整体作为一块
    - 标题行自动附带到下一个内容块
    """

    # 分隔符优先级
    SEPARATORS = ["\n\n", "\n", "。", "！", "？", "；", ". ", "! ", "? ", "; ", " "]

    def chunk(self, pages: list[ParsedPage]) -> list[ChunkData]:
        # 预合并：将相邻小 page 合并至接近 chunk_size，避免碎片化 chunk
        pages = self._merge_small_pages(pages)

        chunks: list[ChunkData] = []
        chunk_index = 0

        for page in pages:
            text = page.content.strip()
            if not text:
                continue

            # 检测是否为代码块，不分割
            if text.startswith("```") and text.endswith("```"):
                chunks.append(self._build_chunk(text, chunk_index, page.metadata.copy()))
                chunk_index += 1
                continue

            # 递归分割
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
        """递归分割文本"""
        if len(text) <= self.chunk_size:
            return [text]

        if sep_index >= len(self.SEPARATORS):
            # 所有分隔符用尽，硬切
            return self._hard_split(text)

        separator = self.SEPARATORS[sep_index]
        parts = text.split(separator)

        if len(parts) <= 1:
            # 当前分隔符无效，尝试下一个
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
                    # 保留重叠
                    if self.chunk_overlap > 0 and len(current) > self.chunk_overlap:
                        overlap_text = current[-self.chunk_overlap:]
                        current = overlap_text + separator + part
                    else:
                        current = part
                else:
                    # 单个 part 超过 chunk_size，递归分割
                    sub_parts = self._recursive_split(part, sep_index + 1)
                    result.extend(sub_parts[:-1])
                    current = sub_parts[-1] if sub_parts else ""

        if current:
            result.append(current)

        return result

    def _hard_split(self, text: str) -> list[str]:
        """硬切文本（最后手段）"""
        result: list[str] = []
        start = 0
        while start < len(text):
            end = min(start + self.chunk_size, len(text))
            result.append(text[start:end])
            start = end - self.chunk_overlap if self.chunk_overlap > 0 else end
        return result


class ParagraphChunker(BaseChunker):
    """
    段落分块器

    按自然段落分割（\\n\\n），小段落合并，大段落用递归分割
    适用于新闻、博客等段落分明的文档
    """

    def chunk(self, pages: list[ParsedPage]) -> list[ChunkData]:
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
                        # 大段落递归分割
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
    语义分块器（高级策略）

    先按句子分割，然后在语义转折点切分
    由于语义分块需要额外 Embedding 计算，此处简化为基于句子边界的分块
    后续 T9 可增强为真正的 Embedding 相似度分块
    """

    # 中英文句子分隔符
    SENTENCE_SEPARATORS = re.compile(r"(?<=[。！？.!?])\s*")

    def chunk(self, pages: list[ParsedPage]) -> list[ChunkData]:
        # 预合并：将相邻小 page 合并至接近 chunk_size，避免碎片化 chunk
        pages = self._merge_small_pages(pages)

        chunks: list[ChunkData] = []
        chunk_index = 0

        for page in pages:
            text = page.content.strip()
            if not text:
                continue

            # 按句子分割
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
                        # 重叠
                        if self.chunk_overlap > 0 and len(current) > self.chunk_overlap:
                            current = current[-self.chunk_overlap:] + " " + sentence
                        else:
                            current = sentence
                    else:
                        # 单句超长，硬切
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
    工厂方法：根据策略获取分块器

    Args:
        strategy: 分块策略（recursive/semantic/paragraph）
        chunk_size: 每块最大字符数
        chunk_overlap: 块间重叠字符数

    Returns:
        对应的分块器实例
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
