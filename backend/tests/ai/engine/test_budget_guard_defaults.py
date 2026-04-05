from app.ai.engine.budget_guard import BudgetGuard


def test_fast_budget_uses_provider_tolerant_elapsed_default() -> None:
    budget = BudgetGuard.build_default("fast", intent_count=1)

    assert budget.max_tool_rounds == 2
    assert budget.max_completion_tokens == 2000
    assert budget.max_elapsed_ms == 40000
    assert budget.max_retry_per_intent == 1
