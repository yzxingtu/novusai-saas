# Execution State Machine

## Canonical Turn Flow

`prepare -> plan intents -> assemble context -> plan protocol -> execute model/tool rounds -> recover or exit -> project diagnostics`

Streaming and non-streaming execution share the same logical state machine and
emit the same outcome semantics.

## Required States

- `prepared`
- `model_call`
- `tool_round`
- `recovery`
- `awaiting_consent`
- `partial_exit`
- `completed`
- `failed`
- `interrupted`

## Rules

- One execution contract drives both sync and streaming paths.
- Protocol planning happens before provider execution and produces a protocol
chain for the turn.
- Intent progress is tracked explicitly; recovery decisions target unfinished
intents rather than replaying the entire turn.
- Budgets are checked during execution, not just after completion.
- Consent-gated tool calls transition to `awaiting_consent`, not `partial_exit`.
- Protocol fallback history is captured in TurnRecord and surfaced in
diagnostics.

## Required Outputs

- intent status and completion per turn
- protocol path and fallback history
- selected tools, tool rounds, and provider events
- termination reason and outcome
- recovery decisions and budget exit reason

## Prohibited Patterns

- separate retry systems for streaming vs non-streaming execution
- provider-layer fallback chains that bypass the runtime protocol plan
- unbounded tool loops without budget checks
- storing state only in prompt markers
- treating consent-required tool results as ordinary retry failures
- stream-only or sync-only hook overrides that diverge policy or diagnostics
