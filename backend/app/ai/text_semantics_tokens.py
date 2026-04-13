"""Tokenization and identifier helpers for AI runtime flows."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from app.ai.text_semantics_terms import collapse_whitespace


def safe_positive_int(raw: Any) -> int | None:
    if isinstance(raw, int):
        return raw if raw > 0 else None
    text = str(raw or "").strip()
    if not text or not text.isdigit():
        return None
    value = int(text)
    return value if value > 0 else None


def slugify_ascii_identifier(
    text: str | None,
    *,
    lowercase: bool = True,
    max_length: int | None = None,
) -> str:
    source = str(text or "").strip()
    if lowercase:
        source = source.lower()

    pieces: list[str] = []
    last_was_sep = False
    for ch in source:
        if (
            ("a" <= ch <= "z")
            or ("0" <= ch <= "9")
            or (not lowercase and ("A" <= ch <= "Z"))
        ):
            pieces.append(ch)
            last_was_sep = False
            continue
        if ch == "_" or ch == "-":
            if pieces and not last_was_sep:
                pieces.append("_")
                last_was_sep = True
            continue
        if pieces and not last_was_sep:
            pieces.append("_")
            last_was_sep = True

    result = "".join(pieces).strip("_")
    if max_length is not None and max_length > 0:
        return result[:max_length]
    return result


def split_on_any_delimiter(text: str | None, delimiters: str) -> list[str]:
    if not text:
        return []
    parts: list[str] = []
    current: list[str] = []
    delimiter_set = set(delimiters)
    for ch in str(text):
        if ch in delimiter_set:
            if current:
                parts.append("".join(current))
                current = []
            continue
        current.append(ch)
    if current:
        parts.append("".join(current))
    return parts


def split_mixed_alnum_tokens(text: str | None) -> list[str]:
    raw = str(text or "")
    tokens: list[str] = []
    current: list[str] = []
    current_kind: str | None = None

    def _flush() -> None:
        nonlocal current, current_kind
        if current:
            tokens.append("".join(current))
        current = []
        current_kind = None

    for ch in raw:
        if "0" <= ch <= "9":
            kind = "digit"
        elif ("a" <= ch <= "z") or ("A" <= ch <= "Z"):
            kind = "alpha"
        else:
            _flush()
            continue
        if current_kind is None or current_kind == kind:
            current.append(ch)
            current_kind = kind
            continue
        _flush()
        current.append(ch)
        current_kind = kind

    _flush()
    return tokens


def split_on_blank_lines(text: str | None) -> list[str]:
    raw = str(text or "")
    blocks: list[str] = []
    current: list[str] = []
    for line in raw.splitlines():
        if line.strip():
            current.append(line)
            continue
        if current:
            blocks.append("\n".join(current))
            current = []
    if current:
        blocks.append("\n".join(current))
    return blocks


def split_sentences_by_terminal_punctuation(text: str | None) -> list[str]:
    raw = str(text or "")
    if not raw:
        return []

    sentences: list[str] = []
    current: list[str] = []
    terminal = {"。", "！", "？", ".", "!", "?"}
    length = len(raw)

    for idx, ch in enumerate(raw):
        current.append(ch)
        if ch not in terminal:
            continue
        next_char = raw[idx + 1] if idx + 1 < length else ""
        if next_char and not next_char.isspace() and next_char not in terminal:
            continue
        sentence = "".join(current).strip()
        if sentence:
            sentences.append(sentence)
        current = []

    tail = "".join(current).strip()
    if tail:
        sentences.append(tail)
    return sentences


def parse_markdown_heading(line: str | None) -> tuple[int, str] | None:
    raw = str(line or "")
    idx = 0
    length = len(raw)
    while idx < length and raw[idx] == "#":
        idx += 1
    if idx == 0 or idx > 6:
        return None
    if idx >= length or not raw[idx].isspace():
        return None
    heading = raw[idx:].strip()
    if not heading:
        return None
    return idx, heading


def build_semver_sort_key(version: str | None) -> tuple[tuple[int, int | str], ...]:
    normalized = str(version or "").strip()
    if not normalized:
        return ()
    if normalized.startswith(("v", "V")):
        normalized = normalized[1:]

    key: list[tuple[int, int | str]] = []
    for part in split_on_any_delimiter(normalized, ".+-"):
        for token in split_mixed_alnum_tokens(part):
            if token.isdigit():
                key.append((0, int(token)))
            else:
                key.append((1, token.lower()))
    return tuple(key)


def extract_cjk_bigram_and_word_tokens(
    text: str | None,
    *,
    stopwords: set[str] | frozenset[str] | None = None,
) -> set[str]:
    raw = str(text or "")
    blocked = stopwords or set()
    tokens: set[str] = set()

    def _append(token: str) -> None:
        normalized = token.lower()
        if normalized and normalized not in blocked:
            tokens.add(normalized)

    idx = 0
    length = len(raw)
    while idx < length:
        ch = raw[idx]
        code = ord(ch)
        if 0x4E00 <= code <= 0x9FFF:
            start = idx
            while idx < length and 0x4E00 <= ord(raw[idx]) <= 0x9FFF:
                idx += 1
            segment = raw[start:idx]
            for seg_idx, seg_ch in enumerate(segment):
                if seg_ch not in blocked:
                    tokens.add(seg_ch)
                if seg_idx < len(segment) - 1:
                    bigram = segment[seg_idx : seg_idx + 2]
                    if bigram not in blocked:
                        tokens.add(bigram)
            continue

        if ("a" <= ch <= "z") or ("A" <= ch <= "Z"):
            start = idx
            idx += 1
            while idx < length and (
                ("a" <= raw[idx] <= "z") or ("A" <= raw[idx] <= "Z")
            ):
                idx += 1
            token = raw[start:idx]
            if len(token) >= 2:
                _append(token)
            continue

        idx += 1

    return tokens


def extract_memory_keywords(text: str | None, *, limit: int = 12) -> list[str]:
    normalized = collapse_whitespace(text).lower()
    if not normalized:
        return []

    seen: set[str] = set()
    keywords: list[str] = []
    length = len(normalized)
    idx = 0
    while idx < length and len(keywords) < limit:
        ch = normalized[idx]
        code = ord(ch)
        if 0x4E00 <= code <= 0x9FFF:
            start = idx
            while idx < length and 0x4E00 <= ord(normalized[idx]) <= 0x9FFF:
                idx += 1
            token = normalized[start:idx]
            if len(token) >= 2 and token not in seen:
                seen.add(token)
                keywords.append(token)
            continue

        if ("a" <= ch <= "z") or ("0" <= ch <= "9"):
            start = idx
            idx += 1
            while idx < length:
                nxt = normalized[idx]
                if ("a" <= nxt <= "z") or ("0" <= nxt <= "9") or nxt in {"_", "-"}:
                    idx += 1
                    continue
                break
            token = normalized[start:idx]
            if len(token) >= 2 and token not in seen:
                seen.add(token)
                keywords.append(token[:32])
            continue

        idx += 1

    return keywords


def parse_index_score_pair(line: str | None) -> tuple[int, float] | None:
    cleaned = str(line or "").strip()
    if not cleaned:
        return None
    while cleaned and cleaned[0] in {"[", "("}:
        cleaned = cleaned[1:].lstrip()
    index_chars: list[str] = []
    position = 0
    while position < len(cleaned) and cleaned[position].isdigit():
        index_chars.append(cleaned[position])
        position += 1
    if not index_chars:
        return None
    while position < len(cleaned) and cleaned[position] in {"]", ")", " ", "\t"}:
        position += 1
    if position >= len(cleaned) or cleaned[position] not in {":", "="}:
        return None
    position += 1
    while position < len(cleaned) and cleaned[position] in {" ", "\t"}:
        position += 1
    score_chars: list[str] = []
    dot_used = False
    while position < len(cleaned):
        ch = cleaned[position]
        if ch.isdigit():
            score_chars.append(ch)
        elif ch == "." and not dot_used:
            score_chars.append(ch)
            dot_used = True
        else:
            break
        position += 1
    if not score_chars:
        return None
    return int("".join(index_chars)), float("".join(score_chars))


def split_last_suffix(
    text: str | None,
    *,
    separator: str = "-",
    allowed_suffixes: Iterable[str],
) -> tuple[str, str | None]:
    raw = str(text or "").strip()
    if not raw:
        return "", None
    suffixes = {str(item).strip().lower() for item in allowed_suffixes if item}
    head, sep, tail = raw.rpartition(separator)
    if not sep or tail.lower() not in suffixes:
        return raw, None
    return head, tail.lower()


__all__ = [
    "build_semver_sort_key",
    "extract_cjk_bigram_and_word_tokens",
    "extract_memory_keywords",
    "parse_index_score_pair",
    "parse_markdown_heading",
    "safe_positive_int",
    "slugify_ascii_identifier",
    "split_last_suffix",
    "split_mixed_alnum_tokens",
    "split_on_any_delimiter",
    "split_on_blank_lines",
    "split_sentences_by_terminal_punctuation",
]
