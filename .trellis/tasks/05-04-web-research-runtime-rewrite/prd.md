# WebResearch Runtime Rewrite

## Problem

The current AI dialogue web-research path has accumulated several incompatible decisions:

- Runtime policy currently prefers provider hosted/native web search for generic `web_research` intents.
- Builtin `web_search` and `fetch_url` are exposed as fallback tools, but the model/provider often decides whether the fallback progresses from search to fetch.
- Provider hosted search, builtin function tools, protocol fallback, contract retry, evidence recovery, CLI projection, and historical repairs all inspect different signals.
- OpenAI-compatible providers are treated as if hosted search may be generally available, even though most OpenAI-compatible gateways and non-OpenAI models do not support OpenAI hosted search semantics.
- Repeated incidents around conversations 2276, 2280, 2281, and 2282 show the same root class: search/fetch/evidence completion is not owned by one deterministic platform contract.
- Conversation 2285 exposed the next layer of the same class: a successful fetch of a low-relevance article about AI 投毒 / GEO / OpenClaw was promoted to completed evidence for a prompt asking for a 2026 LLM leaderboard.

This task supersedes the 05-02 native-first audit. The new desired system is provider-neutral and platform-controlled.

## User Direction

- Default path is our own `web_search + fetch_url` builtin/skill toolchain.
- OpenAI, Gemini, Claude, and Mistral native/hosted search are optional `SearchProvider`s only.
- All search providers output one unified evidence schema.
- `search -> fetch -> evidence -> answer` is controlled by the platform, not by the LLM or provider fallback.
- For `openai_compatible`, hosted/native search is disabled by default unless explicit config and smoke evidence prove support.
- This is a new system. Do not preserve legacy/native-first behavior for compatibility.
- Delete old code that exists only to keep the broken native-first/fallback path alive.

## Goals

1. Introduce a single WebResearch runtime contract that owns `search -> fetch -> evidence -> answer/recovery`.
2. Make builtin `web_search + fetch_url` the default execution provider for `web_research`.
3. Make hosted/native provider search optional and explicit via provider capability/config.
4. Normalize builtin and native search outputs into one evidence schema before answer synthesis or recovery.
5. Require accepted query-relevant evidence before any page becomes `fetched_urls`, citations, `recovery_evidence`, or completed answer state.
6. Remove native-first tool policy, synthetic hosted-search fallback branches, and adapter-local hosted-search assumptions from new live paths.
7. Ensure OpenAI-compatible providers do not enable hosted search by default.
8. Preserve operator diagnostics, but make them consume canonical WebResearch facts instead of reconstructing truth from scattered metadata.
9. Replace test coverage that asserted native-first behavior with structural, behavioral, known-bug, and smoke/replay coverage for the new deterministic pipeline.

## Non-Goals

- No page runtime/current DOM/page-context revival.
- No compatibility shim for old native-first semantics.
- No per-model hardcoded integrations in orchestration code.
- No LLM-driven decision to fetch after search results already exist.
- No downstream read-model repair as the primary fix for live producer bugs.

## Requirements

### R1. Provider-Neutral Contract

Define a stable provider contract:

- `SearchProvider.search(query, options) -> SearchResultSet`
- `FetchProvider.fetch(url, options) -> PageEvidence`
- provider output must be normalized into `WebResearchEvidence`
- provider identity, raw diagnostics, citations, fetch status, and answer-quality markers are explicit fields

### R2. Default Builtin Pipeline

For ordinary `web_research` intents:

1. plan query from intent/user text;
2. run builtin `web_search`;
3. choose fetch candidates using platform rules;
4. run builtin `fetch_url` for at least the primary candidate when answer-quality evidence is required;
5. normalize evidence;
6. synthesize answer or recover from evidence if provider answer synthesis fails.

### R3. Optional Native/Hosted Search

Hosted/native search may run only when all are true:

- provider capability explicitly declares the search provider;
- tenant/runtime config enables it;
- model/protocol support is validated by smoke or fixture evidence;
- platform WebResearch runtime selects it as a `SearchProvider`;
- output is normalized into the same evidence schema.

### R4. OpenAI-Compatible Default

OpenAI-compatible providers default to:

- `supports_hosted_web_search=false`;
- no hosted web-search payload injection;
- no `_runtime_hosted_web_search_required` default;
- no native-first required `tool_choice`;
- no adapter-local fallback from hosted search to builtin tools.

Official OpenAI hosted search can be enabled later through explicit provider capability plus smoke evidence.

### R5. Platform-Controlled Chain

The platform runtime owns progression:

- `web_search` success with candidate URLs must not wait for another model turn to decide whether to fetch.
- `fetch_url` success/failure must be represented as evidence, not free-form assistant text.
- raw search snippets are not answer-quality evidence unless a provider schema explicitly marks them as such and no fetch is required.
- provider answer synthesis failure after completed evidence may recover from evidence.

### R6. Relevance Gate

Fetched page evidence must be query-relevant before it can be accepted:

- low-relevance pages are recorded as rejected/skipped evidence;
- rejected pages must not populate `fetched_urls`, citations, or recovery answer text;
- `evidence_status` must be `partial` or `failed` when no accepted evidence remains;
- `failure_kind` must explain the rejection, for example `low_query_relevance`, `blocked_url`, `fetch_failed`, `fetch_not_attempted`, `no_answer_quality_evidence`, or `search_failed`;
- operator surfaces must not call this state completed/success.

### R7. Observability

TurnRecord/read models/CLI must expose:

- `web_research_pipeline_id`
- `search_provider`
- `fetch_provider`
- `evidence_status`
- `candidate_urls`
- `fetched_urls`
- `evidence_quality`
- `answer_source`
- rejected URLs and relevance rejection counts when evidence is unaccepted
- provider fallback/disable reason when optional native provider was skipped

### R8. Deletion Bias

Delete or isolate old branches that only support:

- native-first `web_research` policy;
- hosted-search progress-only fallback into synthetic builtin tool call;
- scattered `native_web_search_evidence` completion logic;
- OpenAI-compatible hosted search default assumptions;
- read-model reinterpretation of new live malformed evidence.

Public imports, CLI command names, and persisted diagnostic fields may remain as thin facades only when needed for operator surfaces.

## Acceptance Criteria

- Canonical spec no longer says generic `web_research` should prefer provider-native hosted search.
- A new WebResearch runtime package owns provider selection, search, fetch, normalization, and answer/recovery evidence handoff.
- `openai_compatible` hosted search is off by default and only opt-in via explicit provider capability/config.
- Turn execution no longer depends on LLM/provider fallback to advance from successful search results to required fetch evidence.
- All search providers produce the same evidence schema before final answer synthesis.
- Tests are annotated as `structural`, `behavioral`, or `smoke/replay` per testing discipline.
- Tests prove the new default builtin pipeline and the disabled-by-default OpenAI-compatible hosted search behavior.
- Obsolete native-first tests are removed or rewritten rather than retained with inverted assumptions.
- CLI/replay diagnostics for conversations 2281/2282 remain explainable without inventing missing historical evidence.
- Historical diagnostics for conversation 2285 are downgraded to failed/partial without inventing a good answer from its rejected low-relevance evidence.

## Break-Loop Analysis

### Root Cause Category

- **B. Cross-Layer Contract**: provider native search, tool routing, fetch recovery, and read-model projection each define their own completion evidence.
- **D. Test Coverage Gap**: previous tests validated fragments and fallback mechanics, but did not prove the user-visible `search -> fetch -> answer` chain.
- **E. Implicit Assumption**: OpenAI-compatible provider was treated as if OpenAI hosted search semantics were portable.

### Why Prior Fixes Kept Failing

1. Native-first policy was patched when provider hosted search failed, instead of making builtin search/fetch the deterministic default.
2. Fetch chaining was added as a local rescue, but the chain still lived inside a broader model/tool fallback loop.
3. Read-model repair improved historical display, but producer-side evidence ownership remained scattered.
4. Tests asserted local branches rather than a single owner contract for WebResearch completion.

### Prevention Mechanism

- Architecture: single WebResearch runtime owner.
- Provider contract: hosted/native search is a provider adapter, not the orchestration default.
- Testing: known-bug regressions plus non-self-fulfilling behavioral pipeline tests.
- Observability: one evidence schema projected into diagnostics/read models/CLI.

## Milestone Gates

- Structural: imports, schema tests, ruff, prompt-contract check.
- Behavioral: deterministic WebResearch pipeline tests with real executor boundaries or validated fixtures.
- Smoke/replay: real-dialogue or recorded replay scenario for “查一下大模型排行榜 2026 水平排行！”.
- Known-bug: 2276/2280/2281/2282 remain documented; 2282 must stay explainable as historical no-fetch evidence, while new turns must fetch deterministically.
- Known-bug 2285: irrelevant fetched evidence must be reproduced by a RED test, then turn green only when low-relevance evidence is rejected and the real dialogue/browser smoke shows partial/error instead of completed/success.
