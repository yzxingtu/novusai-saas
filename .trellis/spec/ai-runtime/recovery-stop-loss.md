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

## Retired Scenario: Hosted Web Search Fallback To Built-In Search

### 1. Scope / Trigger

- This scenario documented the former native-first hosted-search design.
  That design is retired for new-system live paths.
- The retained lesson is still valid: provider preamble text such as "I'll
  search now" is not completion evidence for a required `web_research` intent.
  The new owner of this rule is the WebResearch pipeline, not a hosted-search
  fallback branch.

### 2. Signatures

- Former signatures that should be deleted or kept only as historical replay
  diagnostics:
  - `backend/app/ai/runtime/query_engine.py`
  - `_runtime_native_web_search_fallback_variant="builtin_web_research_tools"`
  - `native_web_search_builtin_fallback_synthesized`
  - `native_web_search_builtin_fallback_tool_name`
  - `native_web_search_builtin_fallback_query`
  - `native_web_search_builtin_fallback_synthesized_reason`

### 3. New-System Contracts

- Builtin `web_search` / `fetch_url` are the default WebResearch providers, not
  the fallback after hosted search failure.
- Hosted/native search is optional provider capability. If it fails, the
  failure is recorded as optional-provider diagnostics; it must not be the
  normal route into builtin execution.
- Runtime must not synthesize builtin search because a hosted-search fallback
  provider emitted text-only output. Instead, the platform WebResearch pipeline
  should already own the required search/fetch steps.
- Provider text without normalized search/fetch evidence must not complete a
  `web_research` intent.

### 4. Validation & Error Matrix

| Condition | Expected Behavior |
|---|---|
| Ordinary `web_research` request | Run platform WebResearch pipeline with builtin search/fetch default |
| Optional hosted search disabled or unsupported | Skip optional provider with diagnostics and continue builtin default path |
| Optional hosted search emits progress-only or text-only output | Do not complete intent; require normalized evidence; builtin search remains the default provider path, not a query-engine fallback synthesized from hosted progress |
| Search results contain candidate URLs and fetch is required | Fetch deterministically without another provider/model continuation |
| Ordinary non-web provider 5xx | Preserve provider failure semantics; do not synthesize tool calls |

### 5. Good/Base/Bad Cases

- Good: generic web research enters WebResearchRuntime, runs builtin
  `web_search`, fetches the selected URL, normalizes evidence, and then
  synthesizes or recovers the final answer.
- Base: an explicitly enabled hosted provider returns normalized search
  evidence; runtime still controls fetch and answer-quality decisions.
- Bad: the visible "I'll search now" preamble is persisted as the final
  assistant answer for a required web-search request.
- Bad: hosted search times out first, then query-engine synthesizes builtin
  tool calls as a compatibility fallback instead of using the default
  WebResearch pipeline.

### 6. Tests Required

- Rewrite or delete old tests in
  `backend/tests/ai/engine/test_query_engine_partial_contract.py` that assert
  hosted-search-first fallback.
- Add behavioral WebResearch tests proving builtin default search/fetch
  progression, optional hosted-provider normalization, and text-only provider
  output rejection.

### 7. Wrong vs Correct

#### Wrong

- Count pre-tool preamble text as a successful answer for a required
  `web_research` intent.
- Preserve hosted-search-first fallback branches for new live paths.

#### Correct

- Route required web research into the platform WebResearch pipeline and
  complete only from normalized evidence.

## Scenario: Recovered Web Evidence Must Not Use Truncated Fetch Metadata As Final Answer

### 1. Scope / Trigger

- Trigger: web research has completed `web_search` / `fetch_url` evidence, but
  the final assistant synthesis call times out, hits provider failure, or exits
  the elapsed budget before a normal model-authored answer is available.
- Why this needs code-spec depth: `fetch_url.summary` and page `description`
  fields may come from HTML metadata and can end mid-sentence (for example
  "调研用户通过"). Treating that metadata as a completed answer makes the UI show
  "已完成" while the answer is visibly clipped.

### 2. Signatures

- Recovery evidence helpers:
  - `backend/app/ai/engine/recovery_tool_result_helpers.py`
  - `extract_fetch_url_user_preview(...)`
  - `intent_result_from_tool_results(...)`
- Completion salvage callers and representative finalization paths:
  - `backend/app/ai/engine/recovery_prompt_builders.py`
  - `build_completed_output(...)`
  - `recover_web_search_output_from_evidence(...)`
  - `backend/app/ai/engine/recovery_status_update.py`
  - `update_intent_statuses(...)`
  - `backend/app/ai/engine/conversation_sync_result_support.py`
  - `backend/app/ai/engine/stream_generation_pipeline.py`
  - `backend/app/ai/engine/turn_executor.py`
  - `backend/app/ai/engine/stream_execution_runtime.py`
  - `_build_stream_exception_artifacts(...)`

### 3. Contracts

- Recovered final output may use tool evidence only when the evidence is
  successful. Completed `fetch_url` evidence can supply answer text through the
  intent cached-result path; unfinished web-research recovery remains scoped to
  the narrower successful `web_search` evidence recovery path.
- For `fetch_url` evidence, user-facing recovery output should prefer useful
  body lines over generated `title - description` summaries whenever the
  summary is only a title/description join and the fetched body contains
  substantive content.
- A generic `fetch_url.summary` status such as `Fetched https://...` is not
  answer-quality evidence. If the fetched body contains substantive content,
  recovery output must use body lines; if it does not, the generic status must
  not by itself complete a `web_research` answer.
- Obvious short navigation/body headings such as "报告详情" must not become the
  primary recovered answer line.
- A page `description` without terminal punctuation is not enough by itself to
  mark the evidence as answer-quality when fetched body text is available.
- A `fetch_url.summary` that includes a truncation marker such as
  `... [truncated]` is not enough by itself to mark the evidence as
  answer-quality when fetched body text is available.
- Recovery may still include a complete page description when it has terminal
  punctuation and does not duplicate the first useful body lines.

### 4. Validation & Error Matrix

| Condition | Expected Behavior |
|---|---|
| `fetch_url.summary` is complete and no body text is available | May use the summary |
| `fetch_url.summary` is `title - description` and body contains substantive lines | Use body lines for recovered output |
| `fetch_url.summary` is generic `Fetched https://...` and body contains substantive lines | Use body lines for recovered output |
| `fetch_url.summary` is generic `Fetched https://...` and no useful body text is available | Do not treat the generic status as a completed answer |
| `fetch_url.summary` ends with `... [truncated]` and body contains substantive lines | Use body lines for recovered output |
| `description` ends mid-sentence and body contains facts | Do not end the final answer with the clipped description |
| Body contains only obvious short headings/navigation | Skip those lines; fall back to safer summary/fallback text |
| Search or fetch evidence is unsuccessful | Do not promote it to recovered completed output |

### 5. Good/Base/Bad Cases

- Good: final synthesis times out after fetching an Aliyun/Sullivan report; the
  recovered answer mentions concrete body facts such as "37万亿Tokens" and
  "千问大模型占比32.1%位列第一".
- Base: a small article has no extracted body but a complete summary; recovery
  may surface the summary.
- Bad: the assistant final message is just "沙利文发布...报告，调研用户通过" and the
  turn is marked completed.
- Bad: the assistant final message is just `Fetched https://...` while the
  successful fetched body contains the facts the user asked for.

### 6. Tests Required

- `backend/tests/ai/engine/test_partial_exit_user_output.py`
  - recovered `fetch_url` evidence uses body lines when generated
    title/description summary is incomplete.
  - recovered final output also uses body lines when `fetch_url.summary` carries
    a truncation marker such as `... [truncated]`.
  - recovered final output uses body lines when `fetch_url.summary` is only a
    generic `Fetched https://...` status.
  - complete summary with no body text remains usable, and failed fetch evidence
    is not promoted.
- `backend/tests/regressions/test_bug_2026_05_04_2281_generic_fetched_url_recovery.py`
  - completed `fetch_url` recovery must not finalize a generic fetched-URL
    status when body evidence contains answer facts.
- Existing stream/turn finalization tests must continue proving that
  unsuccessful searches or untrusted raw tool evidence are not promoted as
  canonical assistant answers.

## Scenario: Required Fetch URL Must Chain After Successful Search Before Budget Partial Exit

### 1. Scope / Trigger

- Trigger: a required `web_research` turn successfully executes `web_search`
  and obtains candidate URLs, but the next provider/model continuation is
  unavailable, emits only text, or the elapsed turn budget is already near or
  past the normal limit before `fetch_url` has been attempted.
- Why this needs code-spec depth: search snippets and redirect URLs are not
  answer-quality evidence, but once candidate URLs are retained, `fetch_url` is
  a deterministic required tool step. Abandoning it solely because another model
  round would exceed elapsed budget leaves the user with an avoidable partial
  failure.

### 2. Signatures

- Required-fetch chaining owner:
  - `backend/app/ai/engine/turn_executor_tool_batch.py`
  - `execute_tool_batch(...)`
  - `build_required_fetch_url_fallback_response(...)`
  - `record_synthetic_required_fetch_url(...)`
- Budgeted completion owner:
  - `backend/app/ai/engine/turn_executor.py`
  - `finalize_turn_execution(...)`

### 3. Contracts

- When `web_search` succeeds and `RecoveryWebResearchGate` narrows the active
  `web_research` intent to `fetch_url`, runtime may synthesize the `fetch_url`
  tool call directly from the retained candidate URL instead of asking the
  provider for another required-tool round.
- This synthesis is allowed only when `fetch_url` is available in the retained
  tool pool, a candidate URL remains unattempted, and the projected tool-round
  count stays within the tool-round budget.
- The synthetic `fetch_url` step is part of completing the current successful
  search tool batch. It must not promote raw `web_search` snippets to a final
  answer if `fetch_url` is unavailable, blocked, exhausted, or unsuccessful.
- If elapsed budget is exceeded after the deterministic `fetch_url` succeeds,
  finalization should recover from fetched body evidence directly and must not
  require another provider synthesis call for this synthetic-fetch path.
- Diagnostics must mark the recovery with
  `synthetic_required_fetch_url_after_search_success` and
  `synthetic_required_fetch_url_reason=required_fetch_url_after_search_success`.

### 4. Validation & Error Matrix

| Condition | Expected Behavior |
|---|---|
| `web_search` succeeds with candidate URLs and no `fetch_url` attempt yet | Synthesize `fetch_url` from the first remaining candidate URL |
| The provider follow-up would be needed only to choose that URL | Do not call the provider; execute deterministic `fetch_url` |
| Elapsed budget is over the normal limit after search, but tool-round budget remains | Complete the deterministic `fetch_url` tool step before partial-exit finalization |
| Tool-round budget would be exceeded by the synthetic fetch | Do not synthesize; keep normal budget partial-exit behavior |
| `fetch_url` succeeds but elapsed budget is exceeded before answer synthesis | Use recovered fetched body evidence; skip another provider synthesis call for this synthetic path |
| `fetch_url` is blocked, failed, unavailable, or candidate URLs are exhausted | Do not mark the web research intent completed from raw search evidence |

### 5. Good/Base/Bad Cases

- Good: hosted search fallback eventually produces a builtin `web_search` call
  at 75 seconds, returns Baidu candidates, and runtime immediately executes
  `fetch_url` on the candidate before returning a recovered answer from fetched
  body evidence.
- Base: a normal search round leaves enough budget and the provider directly
  emits `fetch_url`; runtime executes the real tool call without synthesis.
- Bad: runtime stops with “sources still need verification” after successful
  search candidates while `fetch_url` remained available and unattempted.

### 6. Tests Required

- `backend/tests/regressions/test_bug_2026_05_04_2282_required_fetch_url_budget_exit.py`
  - `BUG-2026-05-04-2282`: after a successful `web_search` result and elapsed
    budget overrun, TurnExecutor must synthesize `fetch_url`, complete the
    intent from fetched body evidence, and skip provider synthesis.
- Existing fetch recovery regressions must stay green:
  - `BUG-2026-05-04-2276`
  - `BUG-2026-05-04-2280`
  - `BUG-2026-05-04-2281`

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
- promoting clipped `fetch_url` title/description metadata as a completed
  web-research answer when substantive fetched body text is available
- promoting generic `Fetched https://...` fetch status as a completed
  web-research answer when substantive fetched body text is available
