"""
Unified context budget manager / 统一上下文预算管理器

Keeps the canonical per-source token budgets in one place so contributors and
support helpers can share the same defaults.
"""

from __future__ import annotations

from app.ai.utils.token_estimator import estimate_tokens

DEFAULT_CONTEXT_BUDGET_LIMITS: dict[str, int] = {
    "session_memory": 500,
    "long_term_memory": 800,
    "kb_rag": 2000,
    "web_search": 1500,
    "page_context": 600,
    "capability_manifest": 300,
}


def get_budget_limit(budget_key: str) -> int:
    normalized = str(budget_key or "").strip().lower()
    if normalized not in DEFAULT_CONTEXT_BUDGET_LIMITS:
        raise KeyError(f"Unknown context budget key: {budget_key}")
    return int(DEFAULT_CONTEXT_BUDGET_LIMITS[normalized])


def truncate_text_to_token_limit(text: str, token_limit: int) -> str:
    normalized = str(text or "").strip()
    if not normalized or token_limit <= 0:
        return ""
    if estimate_tokens(normalized) <= token_limit:
        return normalized

    low = 0
    high = len(normalized)
    best = ""
    while low <= high:
        mid = (low + high) // 2
        candidate = normalized[:mid].rstrip()
        if mid < len(normalized):
            candidate = candidate.rstrip(" .,;:") + "\n..."
        if estimate_tokens(candidate) <= token_limit:
            best = candidate
            low = mid + 1
        else:
            high = mid - 1
    return best


def truncate_to_budget(content: str, budget_key: str) -> str:
    return truncate_text_to_token_limit(content, get_budget_limit(budget_key))


__all__ = [
    "DEFAULT_CONTEXT_BUDGET_LIMITS",
    "get_budget_limit",
    "truncate_text_to_token_limit",
    "truncate_to_budget",
]
