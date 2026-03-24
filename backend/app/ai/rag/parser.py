"""
Document Parser Module / 文档解析器模块

Supports 11 formats: PDF, DOCX, TXT, Markdown, CSV, XLSX, HTML, Q&A, URL, PPTX, Image (JPG/PNG/WebP/GIF).
Unified output as ParsedPage list for chunker consumption.
支持 PDF、DOCX、TXT、Markdown、CSV、XLSX、HTML、Q&A、URL、PPTX、图片（JPG/PNG/WebP/GIF）十一种格式解析，
统一输出 ParsedPage 列表供分块器使用。
"""

from __future__ import annotations

import io
import mimetypes
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, BinaryIO

if TYPE_CHECKING:
    from app.ai.rag.audio_describer import AudioDescriber
    from app.ai.rag.video_describer import VideoDescriber
    from app.ai.rag.vision_describer import VisionDescriber
    from app.models.ai.knowledge_base import KnowledgeBase

from app.core.i18n import _
from app.core.logging import LogManager
from app.exceptions import BusinessException

logger = LogManager.get_logger("ai.rag.parser")


@dataclass
class ParsedPage:
    """Parsed result unit (one page/paragraph/row) / 解析结果单元（一页/一段/一行）"""
    content: str
    metadata: dict = field(default_factory=dict)


class DocumentParser(ABC):
    """Document parser base class / 文档解析器基类"""

    @abstractmethod
    async def parse(self, file_content: BinaryIO, file_name: str = "") -> list[ParsedPage]:
        """
        Parse document content / 解析文档内容

        Args:
            file_content: File binary stream / 文件二进制流
            file_name: Original file name (for metadata) / 原始文件名（用于元数据）

        Returns:
            ParsedPage list / ParsedPage 列表
        """


class PdfParser(DocumentParser):
    """
    PDF Parser / PDF 解析器

    Uses PyMuPDF (fitz) to extract text, preserving page number metadata.
    When knowledge_base.extract_images=True and VisionDescriber is injected,
    also extracts embedded images and calls Vision model to generate descriptions.
    使用 PyMuPDF (fitz) 提取文本，保留页码元数据。
    当 knowledge_base.extract_images=True 且注入了 VisionDescriber 时，
    同时提取内嵌图片并调用 Vision 模型生成图片描述追加到页面列表。

    Image filter: images smaller than 4KB (noise/decoration) are skipped.
    图片过滤规则：小于 4KB（噪点/装饰图）的图片跳过。
    """

    # Skip images below this size (avoid processing logos, separators, etc.) / 跳过小于此大小的图片（避免处理 logo、分隔线等装饰图片）
    _MIN_IMAGE_BYTES = 4 * 1024

    def __init__(
        self,
        vision_describer: VisionDescriber | None = None,
        knowledge_base: KnowledgeBase | None = None,
    ) -> None:
        self._vision_describer = vision_describer
        self._knowledge_base = knowledge_base

    async def parse(self, file_content: BinaryIO, file_name: str = "") -> list[ParsedPage]:
        import fitz  # PyMuPDF / PDF 解析库

        pages: list[ParsedPage] = []
        data = file_content.read()
        doc = fitz.open(stream=data, filetype="pdf")

        extract_images: bool = (
            self._vision_describer is not None
            and self._knowledge_base is not None
            and getattr(self._knowledge_base, "extract_images", False)
        )

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

                if not extract_images:
                    continue

                for img_idx, img_info in enumerate(page.get_images(full=True)):
                    xref = img_info[0]
                    try:
                        base_image = doc.extract_image(xref)
                    except Exception:
                        continue
                    if not base_image:
                        continue

                    image_bytes: bytes = base_image.get("image", b"")
                    if not image_bytes or len(image_bytes) < self._MIN_IMAGE_BYTES:
                        continue

                    ext: str = base_image.get("ext", "png")
                    mime_type = "image/jpeg" if ext in ("jpg", "jpeg") else f"image/{ext}"

                    description = await self._vision_describer.describe_image(  # type: ignore[union-attr]  # 可选依赖 / optional
                        image_bytes=image_bytes,
                        mime_type=mime_type,
                        knowledge_base=self._knowledge_base,  # type: ignore[arg-type]  # 可选依赖 / optional
                    )
                    if description:
                        pages.append(ParsedPage(
                            content=description,
                            metadata={
                                "page": page_num + 1,
                                "image_index": img_idx,
                                "source": file_name,
                                "type": "image",
                            },
                        ))
        finally:
            doc.close()

        logger.info(
            "PDF parsed: {}, pages={} (extract_images={})",
            file_name, len(pages), extract_images,
        )
        return pages


class DocxParser(DocumentParser):
    """
    DOCX Parser / DOCX 解析器

    Uses python-docx to extract paragraphs and tables, preserving heading hierarchy metadata.
    使用 python-docx 提取段落和表格，保留标题层级元数据。
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

            # Detect heading / 检测标题
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

        # Process tables: convert to Markdown format / 处理表格：转为 Markdown 格式
        for table_idx, table in enumerate(doc.tables):
            rows_text = []
            for row in table.rows:
                cells = [cell.text.strip() for cell in row.cells]
                rows_text.append("| " + " | ".join(cells) + " |")
            if rows_text:
                # Insert separator row / 插入分隔符行
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
            "DOCX parsed: {}, segments={}",
            file_name, len(pages),
        )
        return pages


class TxtParser(DocumentParser):
    """
    TXT Parser / TXT 解析器

    Splits by blank lines into paragraphs.
    按空行分段。
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
            "TXT parsed: {}, paragraphs={}",
            file_name, len(pages),
        )
        return pages


class MarkdownParser(DocumentParser):
    """
    Markdown Parser / Markdown 解析器

    Splits by heading hierarchy, preserving headings as metadata.
    Code blocks and tables are kept intact.
    按标题层级分段，保留标题作为元数据。
    代码块和表格完整保留。
    """

    async def parse(self, file_content: BinaryIO, file_name: str = "") -> list[ParsedPage]:
        text = file_content.read().decode("utf-8", errors="replace")
        pages: list[ParsedPage] = []
        current_heading: str | None = None
        current_content: list[str] = []

        def flush():
            """Flush accumulated content as a ParsedPage / 将当前累积内容输出为一个 ParsedPage"""
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
            # Detect heading line / 检测标题行
            heading_match = re.match(r"^(#{1,6})\s+(.+)$", line)
            if heading_match:
                flush()
                current_heading = heading_match.group(2).strip()
                current_content.append(line)
            else:
                current_content.append(line)

        flush()

        logger.info(
            "Markdown parsed: {}, sections={}",
            file_name, len(pages),
        )
        return pages


class CsvParser(DocumentParser):
    """
    CSV Parser / CSV 解析器

    Uses pandas to read, each row converted to "column_name: value" format text.
    使用 pandas 读取，每行转为 "列名: 值" 格式文本。
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
            "CSV parsed: {}, rows={}",
            file_name, len(pages),
        )
        return pages


class XlsxParser(DocumentParser):
    """
    Excel (.xlsx) Parser / Excel (.xlsx) 解析器

    Uses openpyxl to read, supports multiple sheets, each row converted to "column_name: value" format text.
    使用 openpyxl 读取，支持多 Sheet，每行转为 "列名: 值" 格式文本。
    """

    async def parse(self, file_content: BinaryIO, file_name: str = "") -> list[ParsedPage]:
        from openpyxl import load_workbook

        wb = load_workbook(file_content, read_only=True, data_only=True)
        pages: list[ParsedPage] = []

        try:
            for sheet_name in wb.sheetnames:
                ws = wb[sheet_name]
                rows = list(ws.iter_rows(values_only=True))
                if not rows:
                    continue

                # First row as column names / 第一行作为列名
                headers = [
                    str(h).strip() if h is not None else f"col_{i}"
                    for i, h in enumerate(rows[0])
                ]

                for row_idx, row in enumerate(rows[1:], start=1):
                    parts = []
                    for col_idx, val in enumerate(row):
                        if val is not None and str(val).strip():
                            col_name = headers[col_idx] if col_idx < len(headers) else f"col_{col_idx}"
                            parts.append(f"{col_name}: {val}")
                    if parts:
                        pages.append(ParsedPage(
                            content="\n".join(parts),
                            metadata={
                                "sheet": sheet_name,
                                "row_index": row_idx,
                                "columns": headers,
                                "source": file_name,
                            },
                        ))
        finally:
            wb.close()

        logger.info(
            "XLSX parsed: {}, sheets={}, rows={}",
            file_name, len(wb.sheetnames), len(pages),
        )
        return pages


class QaPairParser:
    """
    Q&A Pair Parser / Q&A 对解析器

    Manually input Q&A pairs, each Q+A pair as one ParsedPage.
    手动输入的问答对，每对 Q+A 作为一个 ParsedPage。
    """

    async def parse_qa(
        self,
        question: str,
        answer: str,
        file_name: str = "Q&A",
    ) -> list[ParsedPage]:
        """
        Parse a single Q&A pair / 解析单个 Q&A 对

        Args:
            question: Question / 问题
            answer: Answer / 回答
            file_name: Source name / 来源名称

        Returns:
            List containing a single ParsedPage / 包含单个 ParsedPage 的列表
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


class HtmlParser(DocumentParser):
    """
    HTML File Parser / HTML 文件解析器

    Uses BeautifulSoup to extract body content, filtering out script/style and other non-content tags.
    使用 BeautifulSoup 提取正文，过滤 script/style 等非内容标签。
    """

    async def parse(self, file_content: BinaryIO, file_name: str = "") -> list[ParsedPage]:
        from bs4 import BeautifulSoup

        html_text = file_content.read().decode("utf-8", errors="replace")
        soup = BeautifulSoup(html_text, "lxml")

        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()

        pages: list[ParsedPage] = []
        body = soup.find("body") or soup
        current_heading: str | None = soup.title.string if soup.title else None
        current_content: list[str] = []

        for element in body.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "td"]):
            text = element.get_text(strip=True)
            if not text:
                continue

            if element.name and element.name.startswith("h"):
                if current_content:
                    pages.append(ParsedPage(
                        content="\n".join(current_content),
                        metadata={
                            "heading": current_heading,
                            "source": file_name,
                        },
                    ))
                    current_content = []
                current_heading = text
            else:
                current_content.append(text)

        if current_content:
            pages.append(ParsedPage(
                content="\n".join(current_content),
                metadata={
                    "heading": current_heading,
                    "source": file_name,
                },
            ))

        logger.info(
            "HTML parsed: {}, sections={}",
            file_name, len(pages),
        )
        return pages


class UrlParser(DocumentParser):
    """
    URL Parser / URL 解析器

    Uses httpx + beautifulsoup4 to fetch web pages and extract body content.
    使用 httpx + beautifulsoup4 爬取网页，提取正文。
    """

    async def parse(self, file_content: BinaryIO, file_name: str = "") -> list[ParsedPage]:
        """
        Parse web page content / 解析网页内容

        file_content stores URL string (UTF-8 encoded).
        file_content 中存储的是 URL 字符串（UTF-8 编码）。
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

        # Remove script, style and other non-content tags / 移除脚本、样式等非内容标签
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()

        # Extract body content / 提取正文
        pages: list[ParsedPage] = []
        body = soup.find("body")
        if body:
            # Split by heading / 按标题分段
            current_heading: str | None = soup.title.string if soup.title else None
            current_content: list[str] = []

            for element in body.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "td"]):
                text = element.get_text(strip=True)
                if not text:
                    continue

                if element.name and element.name.startswith("h"):
                    # Heading element: output previous content and start new section / 标题元素：输出之前的内容并开始新段
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

            # Output last section / 输出最后一段
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
            "URL parsed: {}, sections={}",
            url, len(pages),
        )
        return pages


class ImageParser(DocumentParser):
    """
    Image File Parser (jpg/jpeg/png/webp/gif) / 图片文件解析器（jpg/jpeg/png/webp/gif）

    Calls VisionDescriber to generate text descriptions for images, returns a single ParsedPage.
    If vision_describer is None or description is empty, returns ParsedPage with content=""
    (processor layer is responsible for filtering empty ParsedPage).
    调用 VisionDescriber 生成图片的文字描述，返回单个 ParsedPage。
    若 vision_describer 为 None 或描述为空，返回 content="" 的 ParsedPage
    （processor 层负责过滤空 ParsedPage）。
    """

    def __init__(
        self,
        vision_describer: VisionDescriber | None = None,
        knowledge_base: KnowledgeBase | None = None,
    ) -> None:
        self._vision_describer = vision_describer
        self._knowledge_base = knowledge_base

    async def parse(self, file_content: BinaryIO, file_name: str = "") -> list[ParsedPage]:
        image_bytes = file_content.read()

        if not self._vision_describer or not self._knowledge_base or not image_bytes:
            return [ParsedPage(content="", metadata={"source": file_name})]

        # Infer MIME type from filename, fallback to image/jpeg / MIME 类型从文件名推断，fallback 到 image/jpeg
        mime_type, _ = mimetypes.guess_type(file_name or "image.jpg")
        if not mime_type or not mime_type.startswith("image/"):
            mime_type = "image/jpeg"

        description = await self._vision_describer.describe_image(
            image_bytes=image_bytes,
            mime_type=mime_type,
            knowledge_base=self._knowledge_base,
        )

        logger.info(
            "Image parsed via Vision: {}, description_len={}",
            file_name,
            len(description),
        )
        return [ParsedPage(
            content=description,
            metadata={
                "source": file_name,
                "mime_type": mime_type,
            },
        )]


class AudioParser(DocumentParser):
    """
    Audio File Parser / 音频文件解析器

    Uses AudioDescriber to transcribe audio to text for embedding.
    If describer is None or returns "", returns empty ParsedPage (filtered by processor).
    使用 AudioDescriber 将音频转写为文本供 embedding。无 describer 或返回 "" 时返回空 ParsedPage（由 processor 过滤）。
    """

    def __init__(
        self,
        audio_describer: AudioDescriber | None = None,
        knowledge_base: KnowledgeBase | None = None,
    ) -> None:
        self._audio_describer = audio_describer
        self._knowledge_base = knowledge_base

    async def parse(self, file_content: BinaryIO, file_name: str = "") -> list[ParsedPage]:
        audio_bytes = file_content.read()
        if not self._audio_describer or not audio_bytes:
            return [ParsedPage(content="", metadata={"source": file_name})]
        mime_type, _ = mimetypes.guess_type(file_name or "audio.mp3")
        if not mime_type or not mime_type.startswith("audio/"):
            mime_type = "audio/mpeg"
        description = await self._audio_describer.describe_audio(
            audio_bytes=audio_bytes,
            mime_type=mime_type,
            knowledge_base=self._knowledge_base,
        )
        logger.info("Audio parsed: {}, description_len={}", file_name, len(description))
        return [ParsedPage(
            content=description,
            metadata={"source": file_name, "mime_type": mime_type},
        )]


class VideoParser(DocumentParser):
    """
    Video File Parser / 视频文件解析器

    Uses VideoDescriber to get text description for embedding.
    If describer is None or returns "", returns empty ParsedPage (filtered by processor).
    使用 VideoDescriber 得到文本描述供 embedding。无 describer 或返回 "" 时返回空 ParsedPage（由 processor 过滤）。
    """

    def __init__(
        self,
        video_describer: VideoDescriber | None = None,
        knowledge_base: KnowledgeBase | None = None,
    ) -> None:
        self._video_describer = video_describer
        self._knowledge_base = knowledge_base

    async def parse(self, file_content: BinaryIO, file_name: str = "") -> list[ParsedPage]:
        video_bytes = file_content.read()
        if not self._video_describer or not video_bytes:
            return [ParsedPage(content="", metadata={"source": file_name})]
        mime_type, _ = mimetypes.guess_type(file_name or "video.mp4")
        if not mime_type or not mime_type.startswith("video/"):
            mime_type = "video/mp4"
        description = await self._video_describer.describe_video(
            video_bytes=video_bytes,
            mime_type=mime_type,
            knowledge_base=self._knowledge_base,
        )
        logger.info("Video parsed: {}, description_len={}", file_name, len(description))
        return [ParsedPage(
            content=description,
            metadata={"source": file_name, "mime_type": mime_type},
        )]


class PptxParser(DocumentParser):
    """
    PPTX Parser / PPTX 解析器

    Uses python-pptx to extract per-slide:
    - Text box/placeholder content
    - Tables (Markdown format)
    - Slide title (metadata.heading)
    - Slide notes (if any)
    使用 python-pptx 按幻灯片提取：
    - 文字框/占位符内容
    - 表格（Markdown 格式）
    - 幻灯片标题（metadata.heading）
    - 幻灯片备注（若有）

    Each slide → 1 ParsedPage (blank slides are skipped).
    每张幻灯片 → 1个 ParsedPage（空白幻灯片跳过）。
    """

    async def parse(self, file_content: BinaryIO, file_name: str = "") -> list[ParsedPage]:
        from pptx import Presentation  # python-pptx / PPT 解析库

        data = file_content.read()
        prs = Presentation(io.BytesIO(data))
        pages: list[ParsedPage] = []

        for slide_num, slide in enumerate(prs.slides, start=1):
            parts: list[str] = []
            title_text: str | None = None

            for shape in slide.shapes:
                # Extract text box/placeholder content / 提取文字框/占位符内容
                if shape.has_text_frame:
                    text = shape.text_frame.text.strip()
                    if not text:
                        continue
                    # Detect title placeholder / 识别标题占位符
                    if shape.shape_id == 1 or (
                        hasattr(shape, "placeholder_format")
                        and shape.placeholder_format is not None
                        and shape.placeholder_format.idx == 0
                    ):
                        title_text = text
                    parts.append(text)

                # Extract tables / 提取表格
                if shape.has_table:
                    rows_text = []
                    for row in shape.table.rows:
                        cells = [cell.text.strip() for cell in row.cells]
                        rows_text.append("| " + " | ".join(cells) + " |")
                    if rows_text:
                        header_sep = "| " + " | ".join(["---"] * len(shape.table.columns)) + " |"
                        table_md = rows_text[0] + "\n" + header_sep + "\n" + "\n".join(rows_text[1:])
                        parts.append(table_md)

            # Extract slide notes / 提取幻灯片备注
            if slide.has_notes_slide:
                notes_text = slide.notes_slide.notes_text_frame.text.strip()
                if notes_text:
                    parts.append(notes_text)

            content = "\n\n".join(parts).strip()
            if not content:
                continue

            pages.append(ParsedPage(
                content=content,
                metadata={
                    "slide": slide_num,
                    "heading": title_text,
                    "source": file_name,
                },
            ))

        logger.info(
            "PPTX parsed: {}, slides={}",
            file_name, len(pages),
        )
        return pages


_IMAGE_TYPES: frozenset[str] = frozenset({"image", "jpg", "jpeg", "png", "webp", "gif"})
_AUDIO_TYPES: frozenset[str] = frozenset({"audio", "mp3", "wav", "m4a", "flac", "aac"})
_VIDEO_TYPES: frozenset[str] = frozenset({"video", "mp4", "webm", "mov", "avi", "mkv"})


def get_parser(
    file_type: str,
    vision_describer: VisionDescriber | None = None,
    audio_describer: AudioDescriber | None = None,
    video_describer: VideoDescriber | None = None,
    knowledge_base: KnowledgeBase | None = None,
) -> DocumentParser:
    """
    Factory method: get parser by file type
    工厂方法：根据文件类型获取解析器

    Args:
        file_type: File type (pdf/docx/txt/md/csv/url/pptx/image/audio/video...) / 文件类型
        vision_describer: Vision description service for ImageParser and enhanced PdfParser
                          图片描述服务，供 ImageParser 和增强版 PdfParser 使用
        audio_describer: Audio-to-text service for AudioParser / 音频转文本服务，供 AudioParser 使用
        video_describer: Video-to-text service for VideoParser / 视频转文本服务，供 VideoParser 使用
        knowledge_base: KB object for image/audio/video parsers / 知识库对象，供图片/音频/视频解析器使用

    Returns:
        Corresponding parser instance / 对应的解析器实例

    Raises:
        BusinessException: Unsupported file type / 不支持的文件类型
    """
    if file_type == "pdf":
        return PdfParser(
            vision_describer=vision_describer,
            knowledge_base=knowledge_base,
        )

    text_parsers: dict[str, type[DocumentParser]] = {
        "docx": DocxParser,
        "txt": TxtParser,
        "md": MarkdownParser,
        "csv": CsvParser,
        "xlsx": XlsxParser,
        "html": HtmlParser,
        "url": UrlParser,
        "pptx": PptxParser,
    }

    if file_type in text_parsers:
        return text_parsers[file_type]()

    if file_type in _IMAGE_TYPES:
        return ImageParser(
            vision_describer=vision_describer,
            knowledge_base=knowledge_base,
        )

    if file_type in _AUDIO_TYPES:
        return AudioParser(
            audio_describer=audio_describer,
            knowledge_base=knowledge_base,
        )

    if file_type in _VIDEO_TYPES:
        return VideoParser(
            video_describer=video_describer,
            knowledge_base=knowledge_base,
        )

    raise BusinessException(
        message=_("knowledge_base.document.error.unsupported_type"),
    )


__all__ = [
    "ParsedPage",
    "DocumentParser",
    "PdfParser",
    "DocxParser",
    "TxtParser",
    "MarkdownParser",
    "CsvParser",
    "XlsxParser",
    "HtmlParser",
    "QaPairParser",
    "UrlParser",
    "PptxParser",
    "ImageParser",
    "AudioParser",
    "VideoParser",
    "get_parser",
]
