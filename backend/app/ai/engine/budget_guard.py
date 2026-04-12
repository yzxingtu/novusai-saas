"""Hard runtime budget helpers."""

from __future__ import annotations

from .types import ExecutionBudget, ExecutionPath


class BudgetGuard:
    @staticmethod
    def build_default(path: ExecutionPath, *, intent_count: int) -> ExecutionBudget:
        if path == "fast":
            return ExecutionBudget(
                max_prompt_tokens=4000,
                max_completion_tokens=2000,
                max_tool_rounds=2,
                max_elapsed_ms=40000,
                max_retry_per_intent=1,
                max_candidate_tools=3,
                max_tool_result_bytes=16000,
                finalization_grace_ms=15000,
            )
        if path == "normal":
            return ExecutionBudget(
                max_prompt_tokens=8000,
                max_completion_tokens=4000,
                max_tool_rounds=3,
                max_elapsed_ms=60000,
                max_retry_per_intent=1,
                max_candidate_tools=5,
                max_tool_result_bytes=40000,
                finalization_grace_ms=15000,
            )
        return ExecutionBudget(
            max_prompt_tokens=12000,
            max_completion_tokens=6000,
            max_tool_rounds=min(6, max(2, intent_count * 2)),
            max_elapsed_ms=75000,
            max_retry_per_intent=1,
            max_candidate_tools=6,
            max_tool_result_bytes=60000,
            finalization_grace_ms=15000,
        )

    @staticmethod
    def register_preparation(
        budget: ExecutionBudget,
        *,
        prompt_tokens: int,
        candidate_tools_count: int,
    ) -> None:
        budget.prompt_tokens_used = max(0, int(prompt_tokens))
        budget.candidate_tools_count = max(0, int(candidate_tools_count))

    @staticmethod
    def pre_model_reason(
        budget: ExecutionBudget | None,
        *,
        allow_finalization_grace: bool = False,
    ) -> str | None:
        if budget is None:
            return None
        reason = budget.first_exceeded_reason()
        if (
            allow_finalization_grace
            and reason == "elapsed_budget_exceeded"
            and budget.apply_finalization_grace()
        ):
            return budget.first_exceeded_reason()
        return reason

    @staticmethod
    def completion_reason(
        budget: ExecutionBudget | None,
        *,
        completion_tokens: int | None = None,
        total_tokens: int,
    ) -> str | None:
        if budget is None:
            return None
        used_completion_tokens = (
            int(completion_tokens)
            if completion_tokens is not None
            else int(total_tokens or 0)
        )
        if (
            budget.max_completion_tokens
            and used_completion_tokens > budget.max_completion_tokens
        ):
            return "completion_budget_exceeded"
        return budget.first_exceeded_reason()

    @staticmethod
    def tool_round_reason(
        budget: ExecutionBudget | None,
        *,
        next_rounds_used: int,
    ) -> str | None:
        if budget is None:
            return None
        if (
            budget.max_tool_rounds
            and int(next_rounds_used or 0) > budget.max_tool_rounds
        ):
            return "tool_round_budget_exceeded"
        return budget.first_exceeded_reason()

    @staticmethod
    def tool_result_reason(
        budget: ExecutionBudget | None,
        *,
        current_bytes_used: int,
        additional_results: list[object],
    ) -> str | None:
        if budget is None:
            return None
        additional_bytes = 0
        for result in additional_results:
            output = (
                getattr(result, "output", None) or getattr(result, "error", None) or ""
            )
            additional_bytes += len(str(output).encode("utf-8"))
        if (
            budget.max_tool_result_bytes
            and current_bytes_used + additional_bytes > budget.max_tool_result_bytes
        ):
            return "tool_result_budget_exceeded"
        return budget.first_exceeded_reason()

    @staticmethod
    def retry_reason(
        budget: ExecutionBudget | None,
        *,
        intent_id: str | None,
    ) -> str | None:
        if budget is None or not intent_id:
            return None
        retries = int(budget.retries_by_intent.get(intent_id, 0) or 0)
        if budget.max_retry_per_intent >= 0 and retries >= budget.max_retry_per_intent:
            return "retry_budget_exhausted"
        return budget.first_exceeded_reason()


__all__ = ["BudgetGuard"]
