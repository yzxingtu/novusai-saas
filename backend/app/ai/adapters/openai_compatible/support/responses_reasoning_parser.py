"""Responses reasoning extraction helpers for OpenAI-compatible adapters."""

from __future__ import annotations

from typing import Any


def _field(value: Any, name: str) -> Any:
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


def _append_text(parts: list[str], value: Any) -> None:
    if not isinstance(value, str):
        return
    text = value.strip()
    if text and text not in parts:
        parts.append(text)


def _append_candidates(parts: list[str], value: Any, *field_names: str) -> None:
    if value is None:
        return
    if isinstance(value, list):
        for item in value:
            _append_candidates(parts, item, *field_names)
        return
    if isinstance(value, str):
        _append_text(parts, value)
        return
    for field_name in field_names:
        _append_text(parts, _field(value, field_name))


def extract_responses_reasoning_text(response: Any) -> str | None:
    parts: list[str] = []

    for item in _field(response, "output") or []:
        if _field(item, "type") != "reasoning":
            continue

        item_content = _field(item, "content")
        if isinstance(item_content, str):
            _append_text(parts, item_content)
            continue

        if isinstance(item_content, list):
            _append_candidates(
                parts,
                item_content,
                "text",
                "thinking",
                "summary_text",
                "reasoning_content",
            )

        for summary_item in _field(item, "summary") or []:
            _append_candidates(parts, summary_item, "text", "summary_text")

    if not parts:
        _append_candidates(
            parts,
            _field(response, "reasoning_content"),
            "text",
            "summary_text",
            "thinking",
        )

    if not parts:
        _append_candidates(
            parts,
            _field(response, "reasoning"),
            "text",
            "summary_text",
            "thinking",
        )

    if not parts:
        for item in _field(response, "output") or []:
            if _field(item, "type") != "message":
                continue
            for content_item in _field(item, "content") or []:
                if _field(content_item, "type") not in {"thinking", "reasoning"}:
                    continue
                _append_candidates(
                    parts,
                    content_item,
                    "thinking",
                    "text",
                    "reasoning_content",
                )

    if not parts:
        return None
    return "\n\n".join(parts)


__all__ = ["extract_responses_reasoning_text"]
