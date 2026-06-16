"""中文: AI 测试模块分类标记。

EN: AI test module classification marker.

Test type: structural / behavioral
Scope: Existing AI tests in this module; no real-dialogue smoke acceptance is claimed.
"""

from app.ai.engine.budget_guard import BudgetGuard


def test_fast_budget_uses_provider_tolerant_elapsed_default() -> None:
    budget = BudgetGuard.build_default("fast", intent_count=1)

    assert budget.max_tool_rounds == 4  # ReAct 循环需要更多轮次
    assert budget.max_completion_tokens == 2000
    assert budget.max_elapsed_ms == 40000
    assert budget.max_retry_per_intent == 1
