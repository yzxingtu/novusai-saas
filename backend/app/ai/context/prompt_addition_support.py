"""
Prompt addition helpers extracted from context.engine.
"""

from __future__ import annotations

from typing import Any

from app.ai.page_locale import (
    page_language_name,
    resolve_visible_reply_locale,
)
from app.ai.prompt_contracts import render_prompt_contract


def build_memory_recall_block(records: list[Any]) -> str:
    lines = ["[LONG-TERM MEMORY RECALL]"]
    for record in records:
        memory_type = str(getattr(record, "memory_type", "") or "").strip()
        summary = str(
            getattr(record, "summary", None) or getattr(record, "content", "") or ""
        ).strip()
        if not summary:
            continue
        label = memory_type.replace("_", " ").title() if memory_type else "Memory"
        lines.append(f"- {label}: {summary}")
    return "\n".join(lines) if len(lines) > 1 else ""


def build_profile_snapshot_block(snapshot: dict[str, Any]) -> str:
    profile = snapshot.get("profile") if isinstance(snapshot, dict) else None
    if not isinstance(profile, dict):
        return ""

    lines = ["[PROFILE SNAPSHOT]"]
    label_map = {
        "constraints": "Constraints",
        "corrections": "Corrections",
        "decisions": "Decisions",
        "facts": "Facts",
        "patterns": "Patterns",
        "preferences": "Preferences",
        "relationships": "Relationships",
        "task_summaries": "Task Summaries",
    }
    for key in (
        "preferences",
        "constraints",
        "facts",
        "decisions",
        "patterns",
        "corrections",
        "relationships",
        "task_summaries",
    ):
        values = profile.get(key)
        if not isinstance(values, list) or not values:
            continue
        compact_values = [
            str(value).strip() for value in values[:2] if str(value).strip()
        ]
        if not compact_values:
            continue
        lines.append(
            f"- {label_map.get(key, key.title())}: {'; '.join(compact_values)}"
        )
    return "\n".join(lines) if len(lines) > 1 else ""


def build_visible_output_locale_hint(request: Any) -> str:
    reply_locale = resolve_visible_reply_locale(
        getattr(request, "messages", None),
        getattr(request, "input_variables", None),
    )
    return render_prompt_contract(
        "visible_output_locale",
        reply_locale=reply_locale,
        reply_language=page_language_name(reply_locale),
    )


__all__ = [
    "build_memory_recall_block",
    "build_profile_snapshot_block",
    "build_visible_output_locale_hint",
]
