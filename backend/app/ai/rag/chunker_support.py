"""Chunker support helpers for structure-aware text splitting."""

from __future__ import annotations

import hashlib

from app.ai.rag.parser import ParsedPage
from app.ai.text_semantics import (
    parse_markdown_heading,
    split_on_blank_lines,
    split_sentences_by_terminal_punctuation,
)
from app.core.logging import LogManager

logger = LogManager.get_logger("ai.rag.chunker")

_CJK_OUTLINE_NUMERALS = frozenset("一二三四五六七八九十百零")


def compute_chunk_hash(text: str) -> str:
    """Compute MD5 hash of text / 计算文本 MD5 哈希"""
    return hashlib.md5(text.encode("utf-8"), usedforsecurity=False).hexdigest()


def looks_like_outline_heading(line: str) -> bool:
    stripped = (line or "").strip()
    if not stripped:
        return False
    if parse_markdown_heading(stripped) is not None:
        return True

    if stripped.startswith("第"):
        idx = 1
        while idx < len(stripped) and (
            stripped[idx].isdigit() or stripped[idx] in _CJK_OUTLINE_NUMERALS
        ):
            idx += 1
        if idx > 1 and idx < len(stripped) and stripped[idx] in "章节部分篇条款、.．":
            return bool(stripped[idx + 1 :].strip())

    idx = 0
    while idx < len(stripped) and stripped[idx] in _CJK_OUTLINE_NUMERALS:
        idx += 1
    if idx > 0 and idx < len(stripped) and stripped[idx] in "、.．":
        return bool(stripped[idx + 1 :].strip())

    idx = 0
    while idx < len(stripped) and stripped[idx].isdigit():
        idx += 1
    if idx > 0 and idx < len(stripped) and stripped[idx] in ".)、．":
        return bool(stripped[idx + 1 :].strip())

    if len(stripped) >= 3 and stripped[0].isalpha() and stripped[1] in ".)":
        return bool(stripped[2:].strip())

    return False


def looks_like_list_item(line: str) -> bool:
    stripped = (line or "").strip()
    if not stripped:
        return False
    if stripped[0] in {"-", "*", "•"}:
        return (
            len(stripped) > 1 and stripped[1].isspace() and bool(stripped[2:].strip())
        )

    idx = 0
    while idx < len(stripped) and stripped[idx].isdigit():
        idx += 1
    if idx > 0 and idx < len(stripped) and stripped[idx] in ".)、．":
        return bool(stripped[idx + 1 :].strip())
    return False


def merge_small_pages(
    pages: list[ParsedPage],
    *,
    chunk_size: int,
) -> list[ParsedPage]:
    """Merge adjacent small pages into larger semantic pages."""
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

        if len(text) >= chunk_size:
            if buf_parts:
                merged.append(
                    ParsedPage(
                        content=separator.join(buf_parts),
                        metadata=buf_metadata,
                    )
                )
                buf_parts = []
                buf_len = 0
                buf_metadata = {}
            merged.append(page)
            continue

        new_len = buf_len + (sep_len if buf_parts else 0) + len(text)
        if new_len <= chunk_size:
            buf_parts.append(text)
            buf_len = new_len
            if not buf_metadata:
                buf_metadata = page.metadata.copy()
            continue

        if buf_parts:
            merged.append(
                ParsedPage(
                    content=separator.join(buf_parts),
                    metadata=buf_metadata,
                )
            )
        buf_parts = [text]
        buf_len = len(text)
        buf_metadata = page.metadata.copy()

    if buf_parts:
        merged.append(
            ParsedPage(
                content=separator.join(buf_parts),
                metadata=buf_metadata,
            )
        )

    if len(merged) != len(pages):
        logger.info(
            "Merged small pages: {} → {} (chunk_size={})",
            len(pages),
            len(merged),
            chunk_size,
        )

    return merged


def split_semantic_units(text: str) -> list[str]:
    blocks = [block.strip() for block in split_on_blank_lines(text) if block.strip()]
    if not blocks:
        return []

    units: list[str] = []
    pending_heading = ""
    for block in blocks:
        if pending_heading:
            block = pending_heading + "\n" + block
            pending_heading = ""

        if is_heading_block(block):
            pending_heading = block
            continue

        if is_structured_block(block):
            units.append(block)
            continue

        normalized = [
            sentence.strip()
            for sentence in split_sentences_by_terminal_punctuation(block)
            if sentence.strip()
        ]
        if normalized:
            units.extend(normalized)
        else:
            units.append(block)

    if pending_heading:
        units.append(pending_heading)

    return units


def is_heading_block(block: str, *, max_length: int = 120) -> bool:
    return (
        "\n" not in block
        and len(block) <= max_length
        and looks_like_outline_heading(block)
    )


def is_structured_block(block: str) -> bool:
    if block.startswith("```") and block.endswith("```"):
        return True
    if block.count("|") >= 4 or "\t" in block:
        return True
    lines = [line.strip() for line in block.splitlines() if line.strip()]
    return len(lines) >= 2 and all(looks_like_list_item(line) for line in lines)


def prefers_sentence_split(block: str) -> bool:
    return "。" in block or "！" in block or "？" in block or ". " in block


def with_overlap_seed(current: str, next_unit: str, *, chunk_overlap: int) -> str:
    if not current or chunk_overlap <= 0:
        return next_unit
    tail = current[-chunk_overlap:]
    return f"{tail}\n{next_unit}"
