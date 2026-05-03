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
- historical page workflow fields may be read for migration diagnostics only;
  live recovery must not create page-specific retries, page progress snapshots,
  or page-operation hints
- if a request needs data that used to be inferred from the rendered page,
  recovery must stop and point to an explicit backend API/export/skill-pack
  contract instead of trying to operate the page

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
- for invalid page-workflow signals, diagnostics should state that the live path
  is unavailable and should not suggest restoring page operations

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

## Scenario: Hosted Web Search Fallback Must Reach Built-In Search, Not Text-Only Success

### 1. Scope / Trigger

- Trigger: Responses hosted web search is required, emits progress, then fails
  or falls back to a Responses attempt with built-in `web_search` / `fetch_url`
  tools still available.
- Why this needs code-spec depth: providers may answer the fallback round with
  visible preamble text such as "I'll search now" but no tool call. For a
  required `web_research` intent, that text is not completion evidence and must
  not end the turn as a successful answer.

### 2. Signatures

- Protocol fallback owner:
  - `backend/app/ai/runtime/query_engine.py`
  - `ConversationQueryEngine.iter_stream_turn(...)`
  - `ConversationQueryEngine.run_chat_turn(...)`
  - `_runtime_native_web_search_fallback_variant="builtin_web_research_tools"`
- Synthetic fallback marker fields on `TurnRecord.metadata`:
  - `native_web_search_builtin_fallback_synthesized`
  - `native_web_search_builtin_fallback_tool_name`
  - `native_web_search_builtin_fallback_query`
  - `native_web_search_builtin_fallback_synthesized_reason`

### 3. Contracts

- Hosted search remains native-first when available.
- If hosted search becomes unavailable and built-in web research tools remain
  in scope, fallback must keep the `web_research` intent pinned to
  `web_search` / `fetch_url`.
- If the built-in fallback attempt returns only visible text and no tool call,
  the runtime must synthesize a `web_search` function call from the last user
  query instead of treating the text as a completed answer.
- If the built-in fallback attempt fails with retryable gateway/connection
  errors, the runtime may synthesize the same `web_search` function call rather
  than issuing another provider-only rescue.
- Synthetic tool-call fallback is allowed only for the hosted-search-to-built-in
  web-research fallback variant. Ordinary provider 5xx failures must not be
  generalized into silent tool synthesis.
- Fallback history must mark the hosted-search fallback as recovered only after
  a real or synthetic tool-call path can continue execution.

### 4. Validation & Error Matrix

| Condition | Expected Behavior |
|---|---|
| Hosted search times out before meaningful output and built-in tools are available | Retry with hosted search disabled and built-in web research tools still scoped |
| Built-in fallback emits `web_search` tool call | Continue normal tool execution |
| Built-in fallback emits text only, no tool call | Synthesize `web_search` call from the last user query and continue tool execution |
| Built-in fallback fails with retryable 502 / connection error | Synthesize `web_search` call and continue tool execution |
| Ordinary non-web provider 5xx | Preserve provider failure semantics; do not synthesize tool calls |

### 5. Good/Base/Bad Cases

- Good: hosted search fails, the second Responses round says "I'll search now"
  but calls no tool, so the runtime emits a synthetic `web_search` call and the
  user eventually sees concrete search/fetch evidence.
- Base: hosted search fails and the second round directly emits a valid
  `web_search` call; no synthesis marker is needed.
- Bad: the visible "I'll search now" preamble is persisted as the final
  assistant answer for a required web-search request.

### 6. Tests Required

- `backend/tests/ai/engine/test_query_engine_partial_contract.py`
  - hosted-search progress-only fallback to built-in tools
  - hosted-search timeout fallback to built-in tools
  - built-in fallback 502 / connection-error synthetic `web_search`
  - built-in fallback text-only synthetic `web_search`

### 7. Wrong vs Correct

#### Wrong

- Count pre-tool preamble text as a successful answer for a required
  `web_research` intent.
- Broaden all retryable provider 5xx failures into synthetic tool calls.

#### Correct

- Scope synthesis to `_runtime_native_web_search_fallback_variant=
  "builtin_web_research_tools"` and emit a real `web_search` tool call from the
  last user query when the provider fails or returns text-only output.

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
- treating hosted-search fallback preamble text as a completed web-research
  answer when no `web_search` or `fetch_url` evidence was produced
