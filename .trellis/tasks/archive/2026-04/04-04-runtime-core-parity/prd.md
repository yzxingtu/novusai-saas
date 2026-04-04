# Runtime Core Parity

## Goal

Make sync and streaming orchestration use the same intent-aware recovery path and remove legacy whole-turn contract-breach retry from the active runtime path.

## Requirements

- Remove pre-tool and post-tool legacy contract-breach retry from the active sync path.
- Make streaming execution support `retry_intent`, not only `return_partial`.
- Ensure `ExecutionStateMachine` owns real execution state transitions and records retry/tool-round diagnostics.
- Keep recovery intent-scoped and aligned with `.trellis/spec/ai-runtime/execution-state-machine.md` and `recovery-stop-loss.md`.

## Ownership

- Allowed files:
  - `backend/app/ai/engine/conversation.py`
  - `backend/app/ai/engine/stream_handler.py`
  - `backend/app/ai/engine/execution_state_machine.py`
- Do not edit any other files.

## Acceptance

- Sync and stream both retry only unfinished intents.
- `retry_events` are emitted on both transports.
- Legacy whole-turn breach retry no longer participates in the main recovery flow.
