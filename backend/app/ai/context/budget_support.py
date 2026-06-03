"""
Budget helper support for context assembly / 上下文预算辅助模块

Extracted from context engine to enable reuse while preserving behavior.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from app.ai.context.budget_manager import (
    DEFAULT_CONTEXT_BUDGET_LIMITS,
    truncate_text_to_token_limit,
)
from app.ai.utils.token_estimator import estimate_tokens

_DEFAULT_CONTEXT_PROMPT_BUDGET_TOKENS = 8000
_DEFAULT_CONTEXT_OUTPUT_RESERVE_RATIO = 0.25
_DEFAULT_SYSTEM_ADDITIONS_BUDGET_TOKENS = 1600
_DEFAULT_CAPABILITY_BLOCK_BUDGET_TOKENS = DEFAULT_CONTEXT_BUDGET_LIMITS[
    "capability_manifest"
]
_DEFAULT_MEMORY_BLOCK_BUDGET_TOKENS = DEFAULT_CONTEXT_BUDGET_LIMITS["session_memory"]
_DEFAULT_COMPACT_SUMMARY_BUDGET_TOKENS = 700
_DEFAULT_DATE_ANCHOR_BUDGET_TOKENS = 160
_DEFAULT_PAGE_LOCALE_BUDGET_TOKENS = 96
_MIN_ADDITION_SECTION_TOKENS = 48


def resolve_context_budget(context_config: dict[str, Any]) -> dict[str, Any]:
    prompt_budget_tokens = int(
        context_config.get("prompt_budget_tokens")
        or context_config.get("max_prompt_tokens")
        or _DEFAULT_CONTEXT_PROMPT_BUDGET_TOKENS
    )
    reserve_ratio = float(
        context_config.get("output_reserve_ratio")
        or _DEFAULT_CONTEXT_OUTPUT_RESERVE_RATIO
    )
    reserve_ratio = min(max(reserve_ratio, 0.05), 0.5)
    prompt_target_tokens = max(
        1200,
        int(prompt_budget_tokens * (1 - reserve_ratio)),
    )
    system_additions_tokens = int(
        context_config.get("system_additions_budget_tokens")
        or min(
            _DEFAULT_SYSTEM_ADDITIONS_BUDGET_TOKENS,
            max(400, prompt_target_tokens // 4),
        )
    )
    return {
        "prompt_budget_tokens": prompt_budget_tokens,
        "prompt_target_tokens": prompt_target_tokens,
        "output_reserve_ratio": reserve_ratio,
        "system_additions_tokens": system_additions_tokens,
        "capability_block_tokens": int(
            context_config.get("capability_block_budget_tokens")
            or min(_DEFAULT_CAPABILITY_BLOCK_BUDGET_TOKENS, system_additions_tokens)
        ),
        "memory_block_tokens": int(
            context_config.get("memory_block_budget_tokens")
            or min(_DEFAULT_MEMORY_BLOCK_BUDGET_TOKENS, system_additions_tokens)
        ),
        "compact_summary_tokens": int(
            context_config.get("compact_summary_budget_tokens")
            or min(_DEFAULT_COMPACT_SUMMARY_BUDGET_TOKENS, system_additions_tokens)
        ),
        "date_anchor_tokens": int(
            context_config.get("date_anchor_budget_tokens")
            or min(_DEFAULT_DATE_ANCHOR_BUDGET_TOKENS, system_additions_tokens)
        ),
        "page_locale_tokens": int(
            context_config.get("page_locale_budget_tokens")
            or min(_DEFAULT_PAGE_LOCALE_BUDGET_TOKENS, system_additions_tokens)
        ),
    }


def append_budgeted_addition(
    *,
    additions: list[str],
    text: str,
    category: str,
    per_item_token_limit: int,
    total_token_limit: int,
    budget_usage: dict[str, Any],
    trim_text_fn: Callable[[str, int], str] | None = None,
) -> None:
    normalized = str(text or "").strip()
    if not normalized:
        return

    used_tokens = int(budget_usage.get("used_tokens", 0) or 0)
    remaining_total = max(total_token_limit - used_tokens, 0)
    if remaining_total < _MIN_ADDITION_SECTION_TOKENS:
        budget_usage.setdefault("skipped_sections", []).append(category)
        return

    effective_limit = max(
        _MIN_ADDITION_SECTION_TOKENS,
        min(int(per_item_token_limit or remaining_total), remaining_total),
    )
    original_tokens = estimate_tokens(normalized)
    trimmed = (trim_text_fn or truncate_text_to_token_limit)(
        normalized, effective_limit
    )
    if not trimmed:
        budget_usage.setdefault("skipped_sections", []).append(category)
        return

    additions.append(trimmed)
    budget_usage["used_tokens"] = used_tokens + estimate_tokens(trimmed)
    if original_tokens > estimate_tokens(trimmed):
        budget_usage.setdefault("trimmed_sections", []).append(category)


trim_text_to_token_limit = truncate_text_to_token_limit


__all__ = [
    "append_budgeted_addition",
    "resolve_context_budget",
    "trim_text_to_token_limit",
]
