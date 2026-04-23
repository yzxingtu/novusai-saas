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
- page no-progress recovery must not reopen a `page_navigation` retry after a
  snapshot-only verification round when the snapshot already exposes opened-form
  state or another concrete navigation result such as a new active surface or a
  deeper surface stack; successful verify snapshots are completion evidence, not
  another no-progress signal
- page-snapshot recovery evidence must derive the reported focus surface from
  the dominant node/form surface when snapshot content and overlay stack diverge;
  do not blindly surface the top popover/drawer title if the recovered content
  belongs to another surface

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

## Scenario: Terminal Provider Failure Must Not Surface Unfinished Web Evidence As Answer Text

### 1. Scope / Trigger

- Trigger: answer assembly or a downstream provider call fails after one or
  more tool rounds already produced unfinished evidence or `partial_result`
  content.
- Why this needs code-spec depth: raw search titles, URLs, and fetch previews
  are tool evidence, not a trusted assistant final answer. If the turn then
  ends in upstream 5xx or connection failure, surfacing those unfinished
  snippets in chat makes an interrupted turn look partially completed.

### 2. Signatures

- Recovery output builder:
  - `backend/app/ai/engine/recovery_prompt_builders.py`
  - `build_partial_output(...)`
  - `_should_surface_unfinished_partial_result(...)`
  - `is_terminal_failure_kind(...)`
- Failure kinds that count as terminal in user-visible partial output:
  - `provider_unavailable`
  - `provider_http_5xx`
  - `provider_bad_response`
  - `server_interrupt`
  - `budget_exit`
- Intent family with stricter unfinished-evidence suppression:
  - `web_research`

### 3. Contracts

- Completed intent results may still be surfaced on early exit when the result
  is already cached or otherwise trusted.
- Unfinished partial-result previews are only user-visible when the turn is not
  in provider failure. `provider_failure_kind="none"` keeps the normal
  resumable partial-output behavior.
- `web_research` unfinished partial results must be suppressed whenever
  `provider_failure_kind != "none"`, even if a tool already produced titles,
  candidate URLs, or other raw snippets.
- Any terminal failure kind must suppress unfinished partial-result previews
  for every intent family, not only `web_research`.
- On terminal provider failure, the user-visible fallback must collapse to
  interruption language plus any safe unfinished-label summary. It must not
  include “我先把目前拿到的结果给你” for unfinished raw evidence.
- Diagnostics, turn evidence, and cached internal tool state may still retain
  the unfinished evidence. The suppression rule applies to user-visible partial
  answer text only.

### 4. Validation & Error Matrix

| Condition | Expected Behavior |
|---|---|
| `provider_failure_kind="none"` and unfinished `web_research` has `partial_result` | May surface the partial result preview |
| `provider_failure_kind="tool_timeout"` and unfinished `web_research` has `partial_result` | Hide raw web preview; show timeout phrasing only |
| `provider_failure_kind="provider_http_5xx"` and unfinished `web_research` has `partial_result` | Hide raw web preview; show interruption phrasing only |
| Terminal failure on a non-web unfinished intent with `partial_result` | Hide unfinished preview for that intent too |
| One intent completed safely and another hits terminal provider failure | Keep completed safe result, suppress unfinished preview, append interruption guidance |

### 5. Good/Base/Bad Cases

- Good: a `web_search` tool returns titles and URLs, but answer assembly later
  hits upstream `502`. The user sees an interruption message such as
  “新闻来源被系统中断了，请稍后再试。” without the raw URL list.
- Base: retry-budget exhaustion with `provider_failure_kind="none"` may still
  show `web_research` partial snippets because the turn is resumable rather than
  provider-interrupted.
- Bad: a terminal upstream failure dumps raw search snippets or candidate links
  into chat, making unfinished tool evidence look like the assistant's answer.

### 6. Tests Required

- `backend/tests/ai/engine/test_partial_exit_user_output.py`
  - `test_partial_exit_user_output_uses_partial_search_results_before_retry_exhausted_message`
  - `test_partial_exit_user_output_hides_unfinished_web_results_after_provider_failure`
- Failure classification coverage must keep terminal provider kinds canonical so
  partial-output suppression receives the right signal:
  - `backend/tests/test_openai_adapter_responses.py`
  - `backend/tests/ai/engine/test_structured_orchestration_runtime.py`

### 7. Wrong vs Correct

#### Wrong

- Treat unfinished `web_search` / `fetch_url` output as user-visible answer
  text after an upstream 5xx or connection interruption.
- Delete diagnostics evidence entirely just because it is hidden from the
  fallback chat message.

#### Correct

- Keep evidence in diagnostics and cached state, but suppress unfinished preview
  text in `build_partial_output(...)` whenever the failure kind is terminal or
  `web_research` encountered any provider failure.
- Limit user-visible fallback text to completed safe results plus interruption
  guidance.

## Prohibited Patterns

- whole-turn retry for a single unfinished intent
- family drift during recovery
- protocol fallback with no explicit planner authority
- “let me try again” without strategy change
- continuing after repeated failures with no new evidence
- downgrading a consent pause into retry budget exhaustion or internal
  partial-exit text
- promoting unfinished tool evidence into fallback answer text after terminal
  provider failure
