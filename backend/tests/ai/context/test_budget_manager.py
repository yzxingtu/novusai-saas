import pytest

from app.ai.context.budget_manager import (
    get_budget_limit,
    truncate_to_budget,
)
from app.ai.utils.token_estimator import estimate_tokens


def test_get_budget_limit_raises_for_unknown_budget_key() -> None:
    with pytest.raises(KeyError):
        get_budget_limit("missing-budget")


def test_truncate_to_budget_uses_named_budget_limit() -> None:
    content = " ".join(["context"] * 600)

    trimmed = truncate_to_budget(content, "capability_manifest")

    assert trimmed
    assert trimmed.endswith("\n...")
    assert estimate_tokens(trimmed) <= get_budget_limit("capability_manifest")
