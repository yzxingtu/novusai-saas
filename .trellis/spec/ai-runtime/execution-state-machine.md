# Execution State Machine

## Canonical Turn Flow

`ingest -> plan intents -> select path -> build context -> route tools -> execute -> recover or exit -> record diagnostics`

Streaming and non-streaming execution must share the same logical state machine.

## Required States

- `planned`
- `executing`
- `waiting_for_tool`
- `recovering`
- `awaiting_consent`
- `partial_exit`
- `completed`
- `failed`
- `interrupted`

## Rules

- Use one execution contract across sync and streaming paths.
- Track progress at intent level, not only at raw tool-call level.
- Budgets are checked during execution, not only after the loop ends.
- Final responses must carry the same outcome semantics regardless of transport mode.
- Consent-gated tool calls must transition to `awaiting_consent`, not `partial_exit`.
- A pending-consent pause must preserve the consent payload in runtime messages or equivalent diagnostics so resume flows can continue from the same intent.

## Prohibited Patterns

- separate retry systems for streaming vs non-streaming
- infinite or near-unbounded tool loops
- hidden state in free-form prompt markers
- treating consent-required tool results as ordinary retryable tool failures
