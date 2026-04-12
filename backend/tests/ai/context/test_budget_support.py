from app.ai.context.budget_support import (
    _DEFAULT_CAPABILITY_BLOCK_BUDGET_TOKENS,
    _DEFAULT_COMPACT_SUMMARY_BUDGET_TOKENS,
    _DEFAULT_CONTEXT_OUTPUT_RESERVE_RATIO,
    _DEFAULT_CONTEXT_PROMPT_BUDGET_TOKENS,
    _DEFAULT_DATE_ANCHOR_BUDGET_TOKENS,
    _DEFAULT_MEMORY_BLOCK_BUDGET_TOKENS,
    _DEFAULT_PAGE_LOCALE_BUDGET_TOKENS,
    _DEFAULT_SYSTEM_ADDITIONS_BUDGET_TOKENS,
    _MIN_ADDITION_SECTION_TOKENS,
    append_budgeted_addition,
    resolve_context_budget,
    trim_text_to_token_limit,
)
from app.ai.utils.token_estimator import estimate_tokens


def test_trim_text_to_token_limit_trims_and_marks_ellipsis() -> None:
    text = " ".join(["word"] * 200)
    trimmed = trim_text_to_token_limit(text, 20)

    assert trimmed
    assert trimmed.endswith("\n...")
    assert len(trimmed) < len(text)
    assert estimate_tokens(trimmed) <= 20


def test_append_budgeted_addition_skips_when_remaining_budget_too_low() -> None:
    additions: list[str] = []
    budget_usage: dict[str, object] = {"used_tokens": 0}

    append_budgeted_addition(
        additions=additions,
        text="short budget test",
        category="budget_skip",
        per_item_token_limit=_MIN_ADDITION_SECTION_TOKENS,
        total_token_limit=_MIN_ADDITION_SECTION_TOKENS - 1,
        budget_usage=budget_usage,
    )

    assert additions == []
    assert budget_usage["skipped_sections"] == ["budget_skip"]


def test_append_budgeted_addition_tracks_trimmed_sections() -> None:
    additions: list[str] = []
    budget_usage: dict[str, object] = {"used_tokens": 0}
    text = " ".join(["context"] * 120)

    append_budgeted_addition(
        additions=additions,
        text=text,
        category="budget_trim",
        per_item_token_limit=20,
        total_token_limit=200,
        budget_usage=budget_usage,
    )

    assert len(additions) == 1
    assert additions[0].endswith("\n...")
    assert budget_usage["trimmed_sections"] == ["budget_trim"]


def test_resolve_context_budget_defaults_match_engine_values() -> None:
    budget = resolve_context_budget({})

    assert budget["prompt_budget_tokens"] == _DEFAULT_CONTEXT_PROMPT_BUDGET_TOKENS
    assert budget["output_reserve_ratio"] == _DEFAULT_CONTEXT_OUTPUT_RESERVE_RATIO
    assert budget["prompt_target_tokens"] == 6000
    assert budget["system_additions_tokens"] == 1500
    assert budget["capability_block_tokens"] == min(
        _DEFAULT_CAPABILITY_BLOCK_BUDGET_TOKENS,
        1500,
    )
    assert budget["memory_block_tokens"] == min(
        _DEFAULT_MEMORY_BLOCK_BUDGET_TOKENS,
        1500,
    )
    assert budget["compact_summary_tokens"] == min(
        _DEFAULT_COMPACT_SUMMARY_BUDGET_TOKENS,
        1500,
    )
    assert budget["date_anchor_tokens"] == min(
        _DEFAULT_DATE_ANCHOR_BUDGET_TOKENS,
        1500,
    )
    assert budget["page_locale_tokens"] == min(
        _DEFAULT_PAGE_LOCALE_BUDGET_TOKENS,
        1500,
    )
    assert budget["system_additions_tokens"] == min(
        _DEFAULT_SYSTEM_ADDITIONS_BUDGET_TOKENS,
        1500,
    )
