"""JSON-like text extraction helpers for AI runtime flows."""

from __future__ import annotations

import json
from typing import Any

from app.ai.text_semantics_terms import normalize_match_text


def remove_trailing_json_commas(text: str) -> str:
    chars = list(text)
    result: list[str] = []
    in_string = False
    escape_next = False
    length = len(chars)
    idx = 0
    while idx < length:
        ch = chars[idx]
        if in_string:
            result.append(ch)
            if escape_next:
                escape_next = False
            elif ch == "\\":
                escape_next = True
            elif ch == '"':
                in_string = False
            idx += 1
            continue

        if ch == '"':
            in_string = True
            result.append(ch)
            idx += 1
            continue

        if ch == ",":
            look_ahead = idx + 1
            while look_ahead < length and chars[look_ahead] in {" ", "\t", "\r", "\n"}:
                look_ahead += 1
            if look_ahead < length and chars[look_ahead] in {"}", "]"}:
                idx += 1
                continue

        result.append(ch)
        idx += 1
    return "".join(result)


def extract_fenced_json_block(text: str | None) -> str | None:
    raw = text or ""
    start = 0
    while True:
        fence = raw.find("```", start)
        if fence < 0:
            return None
        header_end = raw.find("\n", fence + 3)
        if header_end < 0:
            return None
        header = raw[fence + 3 : header_end].strip().lower()
        if header in {"", "json"}:
            close = raw.find("```", header_end + 1)
            if close < 0:
                return None
            return raw[header_end + 1 : close].strip()
        start = header_end + 1


def extract_first_json_object(text: str | None) -> dict[str, Any] | None:
    raw = text or ""
    for candidate in iter_json_objects(raw):
        try:
            parsed = json.loads(candidate)
        except (json.JSONDecodeError, TypeError, ValueError):
            continue
        if isinstance(parsed, dict):
            return parsed
    return None


def extract_first_json_array(text: str | None) -> list[Any] | None:
    raw = text or ""
    for candidate in iter_json_arrays(raw):
        try:
            parsed = json.loads(candidate)
        except (json.JSONDecodeError, TypeError, ValueError):
            continue
        if isinstance(parsed, list):
            return parsed
    return None


def extract_first_json_object_with_key(
    text: str | None,
    required_key: str,
) -> dict[str, Any] | None:
    raw = text or ""
    for candidate in iter_json_objects(raw):
        try:
            parsed = json.loads(candidate)
        except (json.JSONDecodeError, TypeError, ValueError):
            continue
        if isinstance(parsed, dict) and required_key in parsed:
            return parsed
    return None


def iter_json_objects(text: str | None) -> list[str]:
    raw = text or ""
    results: list[str] = []
    start: int | None = None
    depth = 0
    in_string = False
    escape_next = False

    for idx, ch in enumerate(raw):
        if in_string:
            if escape_next:
                escape_next = False
            elif ch == "\\":
                escape_next = True
            elif ch == '"':
                in_string = False
            continue

        if ch == '"':
            in_string = True
            continue

        if ch == "{":
            if depth == 0:
                start = idx
            depth += 1
            continue

        if ch == "}" and depth > 0:
            depth -= 1
            if depth == 0 and start is not None:
                results.append(raw[start : idx + 1])
                start = None

    return results


def iter_json_arrays(text: str | None) -> list[str]:
    raw = text or ""
    results: list[str] = []
    start: int | None = None
    depth = 0
    in_string = False
    escape_next = False

    for idx, ch in enumerate(raw):
        if in_string:
            if escape_next:
                escape_next = False
            elif ch == "\\":
                escape_next = True
            elif ch == '"':
                in_string = False
            continue

        if ch == '"':
            in_string = True
            continue

        if ch == "[":
            if depth == 0:
                start = idx
            depth += 1
            continue

        if ch == "]" and depth > 0:
            depth -= 1
            if depth == 0 and start is not None:
                results.append(raw[start : idx + 1])
                start = None

    return results


def extract_named_field_value(
    text: str | None,
    field_name: str,
) -> str | None:
    target = normalize_match_text(field_name)
    if not target:
        return None
    for line in (text or "").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        for separator in (":", "："):
            if separator not in stripped:
                continue
            head, tail = stripped.split(separator, 1)
            if normalize_match_text(head) == target:
                value = tail.strip()
                if value:
                    return value
    return None


def extract_data_url_payload(
    url: str | None,
    *,
    media_prefix: str,
) -> str | None:
    raw = str(url or "").strip()
    prefix = f"data:{media_prefix}/"
    if not raw.startswith(prefix):
        return None
    comma_idx = raw.find(",")
    if comma_idx < 0:
        return None
    metadata = raw[len("data:") : comma_idx].lower()
    if ";base64" not in metadata:
        return None
    return raw[comma_idx + 1 :]


def extract_double_brace_placeholders(text: str | None) -> list[str]:
    raw = str(text or "")
    placeholders: list[str] = []
    seen: set[str] = set()
    idx = 0
    length = len(raw)

    while idx < length:
        start = raw.find("{{", idx)
        if start < 0:
            break
        end = raw.find("}}", start + 2)
        if end < 0:
            break
        name = raw[start + 2 : end].strip()
        if name and all(ch.isalnum() or ch == "_" for ch in name) and name not in seen:
            seen.add(name)
            placeholders.append(name)
        idx = end + 2

    return placeholders


def extract_braced_identifiers(
    text: str | None,
    *,
    opening: str = "{",
    closing: str = "}",
) -> list[str]:
    raw = str(text or "")
    identifiers: list[str] = []
    seen: set[str] = set()
    idx = 0
    length = len(raw)

    while idx < length:
        start = raw.find(opening, idx)
        if start < 0:
            break
        end = raw.find(closing, start + len(opening))
        if end < 0:
            break
        name = raw[start + len(opening) : end].strip()
        if name and all(ch.isalnum() or ch == "_" for ch in name) and name not in seen:
            seen.add(name)
            identifiers.append(name)
        idx = end + len(closing)

    return identifiers


__all__ = [
    "extract_braced_identifiers",
    "extract_data_url_payload",
    "extract_double_brace_placeholders",
    "extract_fenced_json_block",
    "extract_first_json_array",
    "extract_first_json_object",
    "extract_first_json_object_with_key",
    "extract_named_field_value",
    "iter_json_arrays",
    "iter_json_objects",
    "remove_trailing_json_commas",
]
