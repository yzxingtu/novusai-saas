"""
文档解析器模块

支持 PDF、DOCX、TXT、Markdown、CSV、Q&A、URL 七种格式解析
统一输出 ParsedPage 列表供分块器使用
"""

from __future__ import annotations

import csv
import io
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import BinaryIO

from app.core.i18n import _
from app.core.logging import LogManager
from app.exceptions import BusinessException

logger = LogManager.get_logger("ai.rag.parser")


@dataclass
class ParsedPage:
    """解析结果单元（一页/一段/一行）"""
    content: str
    metadata: dict = field(default_factory=dict)


class DocumentParser(ABC):
    """文档解析器基类"""

    @abstractmethod
    async def parse(self, file_content: BinaryIO, file_name: str = "") -> list[ParsedPage]:
        """
        解析文档内容

        Args:
            file_content: 文件二进制流
            file_name: 原始文件名（用于元数据）

        Returns:
            ParsedPage 列表
        """


class PdfParser(DocumentParser):
    """
    PDF 解析器

    使用 PyMuPDF (fitz) 提取文本，保留页码元数据
    """

    async def parse(self, file_content: BinaryIO, file_name: str = "") -> list[ParsedPage]:
        import fitz  # PyMuPDF

        pages: list[ParsedPage] = []
        data = file_content.read()
        doc = fitz.open(stream=data, filetype="pdf")

        try:
            for page_num in range(len(doc)):
                page = doc[page_num]
                text = page.get_text("text").strip()
                if text:
                    pages.append(ParsedPage(
                        content=text,
                        metadata={
                            "page": page_num + 1,
                            "source": file_name,
                        },
                    ))
        finally:
            doc.close()

        logger.info(
            "PDF parsed: %s, pages=%d",
            file_name, len(pages),
        )
        return pages


class DocxParser(DocumentParser):
    """
    DOCX 解析器

    使用 python-docx 提取段落和表格，保留标题层级元数据
    """

    async def parse(self, file_content: BinaryIO, file_name: str = "") -> list[ParsedPage]:
        from docx import Document

        doc = Document(file_content)
        pages: list[ParsedPage] = []
        current_heading: str | None = None
        paragraph_index = 0

        for para in doc.paragraphs:
            text = para.text.strip()
            if not text:
                continue

            # 检测标题
            if para.style and para.style.name and para.style.name.startswith("Heading"):
                current_heading = text

            pages.append(ParsedPage(
                content=text,
                metadata={
                    "heading": current_heading,
                    "paragraph": paragraph_index,
                    "source": file_name,
                },
            ))
            paragraph_index += 1

        # 处理表格：转为 Markdown 格式
        for table_idx, table in enumerate(doc.tables):
            rows_text = []
            for row in table.rows:
                cells = [cell.text.strip() for cell in row.cells]
                rows_text.append("| " + " | ".join(cells) + " |")
            if rows_text:
                # 插入分隔符行
                header_sep = "| " + " | ".join(["---"] * len(table.rows[0].cells)) + " |"
                table_md = rows_text[0] + "\n" + header_sep + "\n" + "\n".join(rows_text[1:])
                pages.append(ParsedPage(
                    content=table_md,
                    metadata={
                        "table_index": table_idx,
                        "source": file_name,
                    },
                ))

        logger.info(
            "DOCX parsed: %s, segments=%d",
            file_name, len(pages),
        )
        return pages


class TxtParser(DocumentParser):
    """
    TXT 解析器

    按空行分段
    """

    async def parse(self, file_content: BinaryIO, file_name: str = "") -> list[ParsedPage]:
        text = file_content.read().decode("utf-8", errors="replace")
        paragraphs = re.split(r"\n\s*\n", text)

        pages: list[ParsedPage] = []
        for idx, para in enumerate(paragraphs):
            content = para.strip()
            if content:
                pages.append(ParsedPage(
                    content=content,
                    metadata={
                        "paragraph": idx,
                        "source": file_name,
                    },
                ))

        logger.info(
            "TXT parsed: %s, paragraphs=%d",
            file_name, len(pages),
        )
        return pages


class MarkdownParser(DocumentParser):
    """
    Markdown 解析器

    按标题层级分段，保留标题作为元数据
    代码块和表格完整保留
    """

    async def parse(self, file_content: BinaryIO, file_name: str = "") -> list[ParsedPage]:
        text = file_content.read().decode("utf-8", errors="replace")
        pages: list[ParsedPage] = []
        current_heading: str | None = None
        current_content: list[str] = []

        def flush():
            """将当前累积内容输出为一个 ParsedPage"""
            nonlocal current_content
            content = "\n".join(current_content).strip()
            if content:
                pages.append(ParsedPage(
                    content=content,
                    metadata={
                        "heading": current_heading,
                        "source": file_name,
                    },
                ))
            current_content = []

        for line in text.split("\n"):
            # 检测标题行
            heading_match = re.match(r"^(#{1,6})\s+(.+)$", line)
            if heading_match:
                flush()
                current_heading = heading_match.group(2).strip()
                current_content.append(line)
            else:
                current_content.append(line)

        flush()

        logger.info(
            "Markdown parsed: %s, sections=%d",
            file_name, len(pages),
        )
        return pages


class CsvParser(DocumentParser):
    """
    CSV 解析器

    使用 pandas 读取，每行转为 "列名: 值" 格式文本
    """

    async def parse(self, file_content: BinaryIO, file_name: str = "") -> list[ParsedPage]:
        import pandas as pd

        df = pd.read_csv(file_content, dtype=str)
        pages: list[ParsedPage] = []
        columns = list(df.columns)

        for row_idx, row in df.iterrows():
            parts = []
            for col in columns:
                val = row.get(col, "")
                if pd.notna(val) and str(val).strip():
                    parts.append(f"{col}: {val}")
            if parts:
                pages.append(ParsedPage(
                    content="\n".join(parts),
                    metadata={
                        "row_index": int(row_idx),
                        "columns": columns,
                        "source": file_name,
                    },
                ))

        logger.info(
            "CSV parsed: %s, rows=%d",
            file_name, len(pages),
        )
        return pages


class QaPairParser:
    """
    Q&A 对解析器

    手动输入的问答对，每对 Q+A 作为一个 ParsedPage
    """

    async def parse_qa(
        self,
        question: str,
        answer: str,
        file_name: str = "Q&A",
    ) -> list[ParsedPage]:
        """
        解析单个 Q&A 对

        Args:
            question: 问题
            answer: 回答
            file_name: 来源名称

        Returns:
            包含单个 ParsedPage 的列表
        """
        content = f"Q: {question}\nA: {answer}"
        return [ParsedPage(
            content=content,
            metadata={
                "type": "qa",
                "question": question,
                "answer": answer,
                "source": file_name,
            },
        )]


class UrlParser(DocumentParser):
    """
    URL 解析器

    使用 httpx + beautifulsoup4 爬取网页，提取正文
    """

    async def parse(self, file_content: BinaryIO, file_name: str = "") -> list[ParsedPage]:
        """
        解析网页内容

        file_content 中存储的是 URL 字符串（UTF-8 编码）
        """
        import httpx
        from bs4 import BeautifulSoup

        url = file_content.read().decode("utf-8").strip()
        if not url:
            raise BusinessException(message=_("knowledge_base.document.error.parse_failed"))

        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            response = await client.get(url)
            response.raise_for_status()

        soup = BeautifulSoup(response.text, "lxml")

        # 移除脚本、样式等非内容标签
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()

        # 提取正文
        pages: list[ParsedPage] = []
        body = soup.find("body")
        if body:
            # 按标题分段
            current_heading: str | None = soup.title.string if soup.title else None
            current_content: list[str] = []

            for element in body.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "td"]):
                text = element.get_text(strip=True)
                if not text:
                    continue

                if element.name and element.name.startswith("h"):
                    # 标题元素：输出之前的内容并开始新段
                    if current_content:
                        pages.append(ParsedPage(
                            content="\n".join(current_content),
                            metadata={
                                "heading": current_heading,
                                "source_url": url,
                                "source": file_name or url,
                            },
                        ))
                        current_content = []
                    current_heading = text
                else:
                    current_content.append(text)

            # 输出最后一段
            if current_content:
                pages.append(ParsedPage(
                    content="\n".join(current_content),
                    metadata={
                        "heading": current_heading,
                        "source_url": url,
                        "source": file_name or url,
                    },
                ))

        logger.info(
            "URL parsed: %s, sections=%d",
            url, len(pages),
        )
        return pages


def get_parser(file_type: str) -> DocumentParser:
    """
    工厂方法：根据文件类型获取解析器

    Args:
        file_type: 文件类型（pdf/docx/txt/md/csv/url）

    Returns:
        对应的解析器实例

    Raises:
        BusinessException: 不支持的文件类型
    """
    parsers: dict[str, type[DocumentParser]] = {
        "pdf": PdfParser,
        "docx": DocxParser,
        "txt": TxtParser,
        "md": MarkdownParser,
        "csv": CsvParser,
        "url": UrlParser,
    }

    parser_cls = parsers.get(file_type)
    if not parser_cls:
        raise BusinessException(
            message=_("knowledge_base.document.error.unsupported_type"),
        )
    return parser_cls()


__all__ = [
    "ParsedPage",
    "DocumentParser",
    "PdfParser",
    "DocxParser",
    "TxtParser",
    "MarkdownParser",
    "CsvParser",
    "QaPairParser",
    "UrlParser",
    "get_parser",
]
