# Recovery And Stop-Loss

## Goal

Recovery should narrow the task, not restart the entire turn blindly.

## Rules

- classify failures before retrying
- retry only the unfinished intent
- cap recovery attempts per intent
- distinguish provider failures from orchestration failures
- distinguish protocol failure from tool failure
- return partial results when stop-loss is reached
- treat consent-required tool responses as a pause that waits for user input,
  not as retry exhaustion
- keep page-intent completion stage-aware: snapshot-only, click-only, or
  open-only rounds must not complete navigation/detail workflows when the
  workflow still requires a verification read or submit step
- reuse canonical page workflow metadata (`page_workflow_stage`,
  `page_workflow_phase`, `page_workflow_state`, `page_workflow_completion`)
  across routing, recovery, and completion checks instead of letting each seam
  guess page progress independently
- page-intent recovery/stop-loss must also project machine-readable
  `page_workflow_progress` and carry the active page-workflow snapshot on retry,
  consent-pause, and partial-exit decisions so downstream diagnostics do not
  fall back to prompt-only page-progress guesses
- when a page turn stalls inside an inner tool loop, recovery must freeze the
  narrowed tool subset and write the pending `page_workflow_progress` back into
  the active runtime intent/view state instead of appending an ad-hoc page
  recovery system hint

## Stop-Loss

Stop execution when any of these is true:

- tool round budget is exhausted
- elapsed time budget is exhausted
- retry budget for the active intent is exhausted
- repeated failures exceed the sliding-window threshold
- protocol planner has no safe next step

Do not consume retry budget solely because a tool is waiting for consent.

## Required Output On Early Exit

- completed intents
- unfinished intents
- failure classification
- protocol history when relevant
- next-step guidance only when actionable
- for page intents, the active workflow stage and the narrowed recovery tool
  subset when a follow-up page step is still required; prefer reporting the
  canonical workflow phase/contract instead of prompt-only recovery hints
- for page intents, diagnostics and turn events should expose the same
  `active_page_workflow` snapshot
  (`stage` / `phase` / `goal` / `completion` / `progress` / narrowed tool subset)
  that recovery used, instead of rebuilding another stop-loss explanation path
- user-visible partial output for unfinished page turns should read from that
  workflow snapshot so submit/read/verify/discover phases do not collapse back
  into a generic page “not finished yet” line

## Consent Pause

- `pause_for_consent` is a first-class recovery action
- sync and streaming paths must both surface the turn as interrupted/awaiting
  consent instead of partial completion
- user-visible output for consent pauses should stay natural-language and must
  not leak internal partial-exit markers

## Prohibited Patterns

- whole-turn retry for a single unfinished intent
- family drift during recovery
- protocol fallback with no explicit planner authority
- “let me try again” without strategy change
- continuing after repeated failures with no new evidence
- downgrading a consent pause into retry budget exhaustion or internal
  partial-exit text
