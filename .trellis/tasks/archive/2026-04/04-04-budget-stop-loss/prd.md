# Budget Stop Loss

## Goal

Turn orchestration budgets into real execution stop-loss checks instead of post-hoc reporting.

## Requirements

- Remove `MAX_TOOL_CALL_ROUNDS` as an active control path.
- Make `ExecutionBudget` the single source for prompt, completion, tool-round, elapsed, tool-result-byte, and retry budgets.
- Check budgets before model calls, before tool rounds, after tool results, and before recovery.
- Emit standardized `budget_exit_reason` values and stop immediately on breach.

## Ownership

- Allowed files:
  - `backend/app/ai/engine/budget_guard.py`
  - `backend/app/ai/engine/base.py`
  - minimal state hooks directly needed for budget enforcement
- Do not edit prompt contracts or Trellis files.

## Acceptance

- Every declared budget can stop execution directly.
- Diagnostics expose stable exit reasons for each budget type.
- No active loop depends on `MAX_TOOL_CALL_ROUNDS`.
