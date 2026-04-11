# Execution State Machine

## Canonical Turn Flow

`ingest -> classify intents -> resolve protocol plan -> assemble context -> route tools -> execute rounds -> recover or exit -> project diagnostics`

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

- use one execution contract across sync and streaming paths
- protocol planning happens before provider execution
- track progress at intent level, not only at tool-call level
- budgets are checked during execution, not only after the loop ends
- final responses must carry the same outcome semantics regardless of transport
  mode
- consent-gated tool calls transition to `awaiting_consent`, not `partial_exit`
- protocol fallback history must be part of turn diagnostics

## Required Outputs

- active and completed intents
- selected protocol path and fallback history
- selected tools and tool rounds
- finish reason / termination reason
- provider events and recovery events

## Current Implementation Notes (2026-04, Transitional)

- `backend/app/ai/engine/turn_executor.py` is the shared executor for sync and
  streaming paths.
- Streaming path uses `StreamExecutionHandler` +
  `backend/app/ai/engine/stream_generation_view.py` to share turn state and
  avoid private-field reach-ins.

## Prohibited Patterns

- separate retry systems for streaming vs non-streaming
- provider-layer hidden fallback chains that bypass runtime state
- infinite or near-unbounded tool loops
- hidden state in free-form prompt markers
- treating consent-required tool results as ordinary retryable tool failures
