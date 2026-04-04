# Recovery And Stop-Loss

## Goal

Recovery should narrow the task, not restart the entire turn blindly.

## Rules

- classify failures before retrying
- retry only the unfinished intent
- cap recovery attempts per intent
- distinguish provider failures from orchestration failures
- return partial results when stop-loss is reached
- treat consent-required tool responses as a pause that waits for user input, not as retry exhaustion

## Stop-Loss

Stop execution when any of these is true:

- tool round budget is exhausted
- elapsed time budget is exhausted
- retry budget for the active intent is exhausted
- repeated failures exceed the sliding-window threshold

Do not consume retry budget solely because a tool is waiting for consent.

## Required Output On Early Exit

- completed intents
- unfinished intents
- failure classification
- next-step guidance only when actionable

## Consent Pause

- `pause_for_consent` is a first-class recovery action.
- Sync and streaming paths must both surface the turn as interrupted/awaiting consent instead of partial completion.
- User-visible output for consent pauses should stay natural-language and must not leak internal partial-exit markers.

## Prohibited Patterns

- whole-turn retry for a single unfinished intent
- family drift during recovery
- “let me try again” without strategy change
- continuing after repeated failures with no new evidence
- downgrading a consent pause into retry budget exhaustion or internal partial-exit text
