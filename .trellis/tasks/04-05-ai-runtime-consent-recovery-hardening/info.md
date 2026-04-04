# Implementation Notes

## Verified In Current Working Tree

- `backend/app/ai/engine/budget_guard.py` already uses a `fast` elapsed budget of `20000ms`, so the old `10000ms` behavior came from an earlier runtime state. We may still raise it further if current tests and audit goals justify more headroom.
- Non-streaming consent handling currently returns early from `BaseEngine._handle_tool_calls()` with `pending_consent` metadata but no successful tool result, which leaves intents in `pending` and allows `RecoveryManager.decide()` to fall through to `return_partial`.
- Streaming consent handling similarly records pending consent in messages/events but never marks the affected intent as a paused state.
- The raw `[PARTIAL EXIT]` content is still produced from `backend/app/ai/prompt_contracts/resources/partial_exit.md`.
- `backend/app/services/ai/call_log_service.py` already normalizes many Decimal-bearing structures, but truncation/serialization paths still need verification against the reported failure.
- No Nominatim/geocoding implementation is currently present under tracked `backend/app` sources, so that issue may belong to an older plugin/runtime or an external weather tool implementation.

## Work Split

- Main agent: task scaffolding, cross-file integration, final verification, and any edits that span multiple worker boundaries.
- Worker 1: consent pause semantics in runtime types/recovery manager/execution state.
- Worker 2: conversation/stream integration for consent pause and non-partial exit behavior.
- Worker 3: user-facing partial-exit rendering and regression tests.
- Worker 4: dynamic capability awareness bug root cause and fix.
- Worker 5: runtime trust-policy downgrade review, including whether a code change is warranted or the issue is config-only.
- Worker 6: call-log Decimal serialization verification/fix plus weather/geocode code ownership check.

## Validation Focus

- Prefer targeted pytest modules around AI engine/runtime and call-log services before any broader suite.
- Treat missing runtime trust policy and weather geocoding as “fix in code only if source is present and behavior is clearly wrong”; otherwise report them as operational follow-up.
