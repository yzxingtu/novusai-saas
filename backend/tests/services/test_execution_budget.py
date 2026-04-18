from app.ai.engine.budget_guard import BudgetGuard
from app.ai.engine.types import ExecutionBudget


def _budget(**overrides) -> ExecutionBudget:
    base = ExecutionBudget(
        max_prompt_tokens=100,
        max_completion_tokens=50,
        max_tool_rounds=2,
        max_elapsed_ms=1000,
        max_retry_per_intent=1,
        max_candidate_tools=3,
        max_tool_result_bytes=128,
        finalization_grace_ms=200,
    )
    for key, value in overrides.items():
        setattr(base, key, value)
    return base


def test_execution_budget_reports_none_within_limits() -> None:
    assert _budget().first_exceeded_reason() is None


def test_execution_budget_reports_prompt_budget_exceeded() -> None:
    budget = _budget(prompt_tokens_used=101)

    assert budget.first_exceeded_reason() == "prompt_budget_exceeded"


def test_execution_budget_reports_completion_budget_exceeded() -> None:
    budget = _budget(completion_tokens_used=51)

    assert budget.first_exceeded_reason() == "completion_budget_exceeded"


def test_execution_budget_reports_tool_round_budget_exceeded() -> None:
    budget = _budget(tool_rounds_used=3)

    assert budget.first_exceeded_reason() == "tool_round_budget_exceeded"


def test_execution_budget_reports_tool_result_budget_exceeded() -> None:
    budget = _budget(tool_result_bytes_used=129)

    assert budget.first_exceeded_reason() == "tool_result_budget_exceeded"


def test_execution_budget_reports_candidate_tool_budget_exceeded() -> None:
    budget = _budget(candidate_tools_count=4)

    assert budget.first_exceeded_reason() == "candidate_tool_budget_exceeded"


def test_execution_budget_reports_elapsed_budget_exit() -> None:
    budget = _budget(elapsed_ms_used=5000)

    assert budget.first_exceeded_reason() == "elapsed_budget_exceeded"
    assert BudgetGuard.pre_model_reason(budget) == "elapsed_budget_exceeded"
    assert BudgetGuard.completion_reason(
        budget,
        completion_tokens=10,
        total_tokens=10,
    ) == "elapsed_budget_exceeded"


def test_execution_budget_elapsed_grace_applies_only_when_explicitly_requested() -> None:
    budget = _budget(elapsed_ms_used=1100)

    assert budget.first_exceeded_reason() == "elapsed_budget_exceeded"
    assert budget.finalization_grace_applied is False
    assert (
        BudgetGuard.pre_model_reason(
            budget,
            allow_finalization_grace=True,
        )
        is None
    )
    assert budget.finalization_grace_applied is True
