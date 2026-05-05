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

## Scenario: Online Search Requests Must Fail Closed

### 1. Scope / Trigger

- Trigger: a user asks the assistant to search, browse, fetch a public URL for a
  research answer, check live/current public information, or call a retired
  online-search tool directly.
- Trigger: recovery, replay, or provider diagnostics encounter legacy
  online-search records from older turns.
- Trigger: a provider emits hosted/native search progress events despite the
  runtime not supporting online search.

### 2. Retired Signatures

The following names are retired from AI dialogue live paths and may appear only
as historical diagnostics, explicit removal tests, or cleanup task references:

- `web_research`
- `web_search`
- `fetch_url`
- `SearchProvider`
- hosted or native web-search provider flags
- provider events such as `response.web_search_call.*`
- public search backends used only for AI dialogue online research
- synthetic search/fetch recovery markers

### 3. Contracts

- Recovery must not create, synthesize, retry, or complete any online-search or
  public-fetch tool step. Search/fetch recovery branches are removed, not merely
  disabled behind provider failure handling.
- Current-information prompts must keep a no-tool unsupported outcome unless a
  separate supported non-web capability can satisfy the request from supplied
  sources, KB content, memory, variables, or installed skills.
- Provider preamble text, hosted-search progress, stale tool traces, candidate
  URLs, fetched metadata, or synthetic citations must never complete a new turn.
- Historical online-search traces may remain readable for operator diagnosis,
  but projections must label them as legacy/unsupported diagnostics and must not
  advertise the removed capability for new turns.
- Terminal failure handling stays generic: unfinished tool evidence from any
  family must not be promoted to final answer text after terminal provider or
  orchestration failure.

### 4. Validation & Error Matrix

| Condition | Expected Behavior |
|---|---|
| User asks for today's news or latest rankings | No search/fetch tools; return unsupported/no-tool wording or ask for supplied sources |
| User asks to call a retired search/fetch tool by name | Reject as unavailable; do not expose the tool to satisfy the guard |
| User supplies a public URL and asks the assistant to fetch it for research | Do not fetch; ask for pasted content or an uploaded/source artifact |
| Provider emits hosted-search progress event | Preserve only as unsupported provider diagnostic; do not mark progress or success |
| Legacy conversation contains retired online-search evidence | Keep readable as historical diagnostic detail; do not use as active capability evidence |
| New candidate tool list contains a retired search/fetch tool | Treat as a removal regression |

### 5. Good/Base/Bad Cases

- Good: a current-information prompt produces a clear unsupported/no-tool
  answer and diagnostics show no selected online-search tools.
- Base: an old conversation detail page can still show that a legacy tool event
  happened without describing it as a currently available capability.
- Bad: recovery synthesizes a fetch step from a retained candidate URL.
- Bad: provider-hosted search progress text becomes the assistant's final answer
  or unlocks a fallback search chain.
- Bad: the assistant fabricates source URLs or citations to make an unsupported
  online-search prompt look successful.

### 6. Tests Required

- Behavioral tests must prove current-information prompts do not emit retired
  online-search intents, candidate tools, selected tools, provider payloads, or
  completion evidence.
- Resolver/tool availability tests must prove retired online-search tool names
  are absent or rejected.
- Smoke/replay evidence for this removal must inspect diagnostics and show the
  unsupported/no-tool path, not merely assert that answer text is non-empty.

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
- creating any retry, fallback, synthetic tool call, or recovery output for a
  removed online-search capability
- treating hosted/native search preamble or progress text as a completed answer
- promoting legacy search/fetch evidence into new-turn success
- fabricating citations or source URLs to make an unsupported online-search
  prompt look successful
