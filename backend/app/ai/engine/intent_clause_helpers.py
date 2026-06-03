"""Clause splitting helpers extracted from IntentPlanner."""

from __future__ import annotations

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


__all__ = ["_CLAUSE_SEPARATORS", "_split_clauses"]
