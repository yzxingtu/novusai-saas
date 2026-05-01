"""
Prompt addition helpers extracted from context.engine.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Any

from app.ai.context.decision_helpers import (
    extract_last_user_text,
    extract_recent_successful_tool_names,
    looks_like_generic_follow_up,
)
from app.ai.page_locale import (
    page_language_name,
    resolve_visible_reply_locale,
)
from app.ai.prompt_contracts import render_prompt_contract
from app.ai.types import ChatMessage
from app.core.base_model import utc_now
from app.core.config import settings


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
        lines.append(f"- {label_map.get(key, key.title())}: {'; '.join(compact_values)}")
    return "\n".join(lines) if len(lines) > 1 else ""


def build_web_research_date_anchor(
    messages: list[ChatMessage],
    *,
    skill_result: Any = None,
    now_fn: Callable[[], datetime] | None = None,
    utc_now_fn: Callable[[], datetime] | None = None,
) -> str:
    current_user_text = extract_last_user_text(messages)
    if not current_user_text:
        return ""

    tools = getattr(skill_result, "tools", None) or []
    has_web_research_tools = any(
        getattr(t, "name", "") in {"web_search", "fetch_url"} for t in tools
    )
    recent_successful_tool_names = extract_recent_successful_tool_names(messages[:-1])
    continuing_web_research = (
        bool(recent_successful_tool_names)
        and recent_successful_tool_names[0] in {"web_search", "fetch_url"}
        and looks_like_generic_follow_up(current_user_text)
    )
    if not has_web_research_tools and not continuing_web_research:
        return ""

    local_now = now_fn() if now_fn is not None else datetime.now(settings.tz)
    utc_today = (utc_now_fn or utc_now)().strftime("%Y-%m-%d")
    current_year = local_now.year
    return (
        "[RUNTIME CLOCK]\n"
        f"Current server-local date/time is {local_now.strftime('%Y-%m-%d %H:%M:%S')} ({settings.TIMEZONE}). "
        f"Current UTC date is {utc_today}. "
        f'The calendar year for "today" and "latest news" queries is {current_year}. '
        "When constructing web_search queries for current events, use this year in date filters—do not substitute a past training-data year. "
        "When the user says today/latest/current/recent or asks about the current time/date, interpret it against this runtime clock. "
        "Do not assume a different year or timezone unless a source or the user explicitly specifies one."
    )


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
    "build_web_research_date_anchor",
    "build_visible_output_locale_hint",
]
