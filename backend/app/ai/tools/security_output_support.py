"""Output sanitization helpers for tool execution security."""

from __future__ import annotations

_SENSITIVE_FIELD_TERMS = (
    "apikey",
    "token",
    "secret",
    "password",
    "passwd",
    "authorization",
)
_SENSITIVE_VALUE_CHARS = frozenset(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-/."
)
_KEY_PREFIXES = ("sk-", "pk-", "ak-", "sk_", "pk_", "ak_")


def sanitize_output(output: str, *, max_size: int = 10000) -> tuple[str, bool]:
    """Mask sensitive strings and truncate overly large output."""
    sanitized = _mask_inline_secret_assignments(output)
    sanitized = _mask_bearer_tokens(sanitized)
    sanitized = _mask_prefixed_keys(sanitized)

    truncated = False
    if len(sanitized) > max_size:
        sanitized = sanitized[:max_size] + "\n...[truncated]"
        truncated = True

    return sanitized, truncated


def _mask_inline_secret_assignments(text: str) -> str:
    lines: list[str] = []
    for line in text.splitlines():
        lines.append(_mask_secret_assignment_line(line))
    return "\n".join(lines)


def _mask_secret_assignment_line(line: str) -> str:
    separator_index = _find_first_assignment_separator(line)
    if separator_index < 0:
        return line

    separator = line[separator_index]
    head = line[:separator_index]
    key = head.strip().strip("\"'")
    normalized_key = key.replace("-", "").replace("_", "").replace(" ", "").lower()
    if not key or not any(term in normalized_key for term in _SENSITIVE_FIELD_TERMS):
        return line

    tail = line[separator_index + 1 :]
    leading_ws_len = len(tail) - len(tail.lstrip())
    leading_ws = tail[:leading_ws_len]
    if separator == ":" and head.rstrip().endswith('"'):
        return f'{head}{separator}{leading_ws}"***MASKED***"'
    return f"{head}{separator}{leading_ws}***MASKED***"


def _find_first_assignment_separator(text: str) -> int:
    first_equals = text.find("=")
    first_colon = text.find(":")
    candidates = [index for index in (first_equals, first_colon) if index >= 0]
    return min(candidates) if candidates else -1


def _mask_bearer_tokens(text: str) -> str:
    lower = text.lower()
    parts: list[str] = []
    index = 0
    while index < len(text):
        hit = lower.find("bearer", index)
        if hit < 0:
            parts.append(text[index:])
            break
        parts.append(text[index:hit])
        token_start = hit + len("bearer")
        while token_start < len(text) and text[token_start].isspace():
            token_start += 1
        token_end = token_start
        while token_end < len(text) and text[token_end] in _SENSITIVE_VALUE_CHARS:
            token_end += 1
        if token_end - token_start >= 8:
            parts.append("Bearer ***MASKED***")
            index = token_end
            continue
        parts.append(text[hit : hit + len("bearer")])
        index = hit + len("bearer")
    return "".join(parts)


def _mask_prefixed_keys(text: str) -> str:
    lower = text.lower()
    parts: list[str] = []
    index = 0
    while index < len(text):
        match_start = -1
        match_prefix = ""
        for prefix in _KEY_PREFIXES:
            candidate = lower.find(prefix, index)
            if candidate < 0:
                continue
            if match_start < 0 or candidate < match_start:
                match_start = candidate
                match_prefix = prefix
        if match_start < 0:
            parts.append(text[index:])
            break
        parts.append(text[index:match_start])
        if match_start > 0 and text[match_start - 1] in _SENSITIVE_VALUE_CHARS:
            parts.append(text[match_start])
            index = match_start + 1
            continue
        end = match_start + len(match_prefix)
        while end < len(text) and text[end].isalnum():
            end += 1
        if end - (match_start + len(match_prefix)) >= 16:
            parts.append("***MASKED_KEY***")
            index = end
            continue
        parts.append(text[match_start:end])
        index = end
    return "".join(parts)
