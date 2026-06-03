"""Shared parser contracts for RAG document parsing."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import BinaryIO


@dataclass
class ParsedPage:
    """Parsed result unit (one page/paragraph/row) / 解析结果单元（一页/一段/一行）"""

    content: str
    metadata: dict = field(default_factory=dict)


class DocumentParser(ABC):
    """Document parser base class / 文档解析器基类"""

    @abstractmethod
    async def parse(
        self, file_content: BinaryIO, file_name: str = ""
    ) -> list[ParsedPage]:
        """
        Parse document content / 解析文档内容

        Args:
            file_content: File binary stream / 文件二进制流
            file_name: Original file name (for metadata) / 原始文件名（用于元数据）

        Returns:
            ParsedPage list / ParsedPage 列表
        """


class QaPairParser:
    """Q&A pair parser / Q&A 对解析器。"""

    async def parse_qa(
        self,
        question: str,
        answer: str,
        file_name: str = "Q&A",
    ) -> list[ParsedPage]:
        content = f"Q: {question}\nA: {answer}"
        return [
            ParsedPage(
                content=content,
                metadata={
                    "type": "qa",
                    "question": question,
                    "answer": answer,
                    "source": file_name,
                },
            )
        ]


__all__ = ["ParsedPage", "DocumentParser", "QaPairParser"]
