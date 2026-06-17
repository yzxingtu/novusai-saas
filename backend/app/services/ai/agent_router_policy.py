"""
Agent router policy helpers for non-page AI routing signals.
"""

from __future__ import annotations

from app.ai.text_semantics import collapse_whitespace

_CLAUSE_SEPARATORS = (
    "，然后",
    "，再",
    "，顺便",
    "，并且",
    "然后",
    "再帮我",
    "顺便",
    "对了",
    "另外",
    "并且",
    "以及",
    "同时",
    "；",
    ";",
    ", then",
    " and then ",
)


def _split_clauses(text: str) -> list[tuple[int, str]]:
    """Split text into clauses by separator tokens."""
    if not text:
        return []
    lowered = text.lower()
    start = 0
    idx = 0
    clauses: list[tuple[int, str]] = []
    while idx < len(lowered):
        separator = next(
            (token for token in _CLAUSE_SEPARATORS if lowered.startswith(token, idx)),
            None,
        )
        if separator is None:
            idx += 1
            continue
        chunk = text[start:idx].strip(" ，,。；;、")
        if chunk:
            clauses.append((start, chunk))
        idx += len(separator)
        start = idx
    tail = text[start:].strip(" ，,。；;、")
    if tail:
        clauses.append((start, tail))
    return clauses or [(0, text.strip())]

NON_PAGE_TIME_TOKENS = (
    "几点",
    "星期几",
    "周几",
    "几号",
    "current time",
    "what day is it",
)


def _normalize_message(message: str) -> str:
    return collapse_whitespace(message).strip().lower()


def _iter_message_clauses(message: str) -> list[str]:
    text = str(message or "").strip()
    if not text:
        return []
    clauses = [
        clause.strip() for _offset, clause in _split_clauses(text) if clause.strip()
    ]
    return clauses or [text]


def requested_tool_families(message: str) -> list[str]:
    """Infer explicit non-page tool families requested by the user's message."""
    normalized_message = _normalize_message(message)
    if not normalized_message:
        return []

    families: list[str] = []

    def add(family: str) -> None:
        if family not in families:
            families.append(family)

    for clause in _iter_message_clauses(message):
        normalized_clause = _normalize_message(clause)
        if not normalized_clause:
            continue

        if any(token in normalized_clause for token in NON_PAGE_TIME_TOKENS):
            add("time_ops")
    return families


__all__ = [
    "NON_PAGE_TIME_TOKENS",
    "requested_tool_families",
]
