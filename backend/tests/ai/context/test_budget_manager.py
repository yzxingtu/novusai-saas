import pytest

from app.ai.context.budget_manager import (
    DEFAULT_CONTEXT_BUDGET_LIMITS,
    get_budget_limit,
    truncate_to_budget,
)
from app.ai.utils.token_estimator import estimate_tokens


def test_get_budget_limit_returns_canonical_named_limits() -> None:
    assert DEFAULT_CONTEXT_BUDGET_LIMITS == {
        "session_memory": 500,
        "long_term_memory": 800,
        "kb_rag": 2000,
        "web_search": 1500,
        "capability_manifest": 300,
    }
    assert get_budget_limit("web_search") == 1500


def test_get_budget_limit_raises_for_unknown_budget_key() -> None:
    with pytest.raises(KeyError):
        get_budget_limit("missing-budget")


def test_truncate_to_budget_uses_named_budget_limit() -> None:
    content = " ".join(["context"] * 600)

    trimmed = truncate_to_budget(content, "capability_manifest")

    assert trimmed
    assert trimmed.endswith("\n...")
    assert estimate_tokens(trimmed) <= get_budget_limit("capability_manifest")
