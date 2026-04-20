# Memory And RAG Pipeline

## Goal

Memory and RAG must be explicit contributors with clear ownership. Retrieval,
capture, and persistence are separate concerns.
Memory is a runtime resource, not a page-specific adaptation or prompt-only
reminder mechanism.

## Ownership Layers

- Thread/session memory policy owns whether a thread may read or write durable
  memory and whether external context has polluted that thread.
- Memory capture owns post-turn extraction and background consolidation.
- Memory recall owns what profile or recall artifacts are eligible for live
  context injection in the current turn.
- RAG retrieval remains separate from memory and must not become the fallback
  owner for missing memory behavior.

## Intent Boundaries

- `memory_save` and `memory_recall` are distinct intents.
- `memory_save` triggers post-turn capture. It must not trigger recall during
context assembly.
- `memory_recall` forces rich long-term recall in the context pipeline
  (profile snapshot plus vector recall), but it is not the only path that may
  enable memory participation.
- Generic turns with `long_term_memory_enabled=true` and a user-scoped request
  may run bounded vector recall under runtime policy even when the user did not
  explicitly say “recall memory”.
- `ContextPipelineOrchestrator` now exports both `has_memory_intent` and
  `memory_context_enabled`: the former is explicit-intent truth for
  `memory_save` / `memory_recall`, while the latter is the runtime-policy owner
  for actual memory participation, capability hinting, and context injection.
- Runtime and service layers should share one normalized `memory_runtime_policy`
  owner. Context orchestration, runtime manifests, session-memory load, and
  long-term capture must all consult that same policy instead of each
  re-deriving memory eligibility from raw request flags.
- The normalized owner snapshot now also carries machine-readable lifecycle
  fields (`thread_memory_owner_state`, `thread_memory_owner_reason`,
  `session_memory_state`, `long_term_memory_recall_state`,
  `long_term_memory_capture_state`) so startup priming, polluted-turn
  degradation, recall gating, and read-model projection can follow one
  canonical thread owner contract instead of parallel boolean-only heuristics.
- The normalized `memory_runtime_policy` snapshot must persist with both the
  assistant-turn metadata and the conversation-level `thread_memory_state`
  snapshot so thread-scoped pollution or mode changes remain observable after
  the turn completes.
- KB binding does not imply `knowledge_query`; the intent must be explicit.
- Current implementation still derives long-term recall eligibility from the
  context orchestrator, but that orchestrator now mixes intent signals with
  runtime memory flags. Treat further coupling to page hints, skill prompt
  blocks, or recovery prompts as prohibited.

## Pipeline Overview

1. Build system and user messages.
2. Resolve KB bindings and runtime model capabilities.
3. Plan intents (IntentPlan list).
4. If a knowledge intent is present, run the RAG retrieval pipeline
   (hooks → rewrite → search → rerank → cache) and inject context using agent `rag_config`.
5. Compute compaction and system prompt additions (date anchors, locale hints).
6. If runtime memory policy allows it, inject bounded memory context:
   generic turns may inject vector recall blocks, while explicit
   `memory_recall` turns may inject both profile snapshot and vector recall.
7. Inject system additions into the system message.
8. Prune and finalize capability bundle and diagnostics.

## Session Memory

- Session memory is loaded by the service layer when memory is enabled and the
conversation has a user and conversation id.
- The injected session memory block sets `session_memory_injected` on the
request and is surfaced as a context source.
- Session memory injection is independent of `memory_recall` intent.
- Session memory availability should be controlled by session or thread policy
  and runtime flags, not by page-local hints or installed skill-pack metadata.
- Chat and stream startup must resolve one normalized `thread_memory_state`
  snapshot through a shared service-layer startup owner before session memory
  load or context assembly; duplicated inline parsing of
  `conversation.metadata_.thread_memory_state` inside command handlers is
  prohibited.
- Runtime capability summaries, contributor enablement, and memory-aware
  context-source selection should key off `memory_context_enabled` (or its
  future replacement), not only `has_memory_intent`.
- Conversation read models may fall back to `thread_memory_state` when the
  latest assistant payload does not carry `memory_runtime_policy`, so thread
  owner signals do not disappear on error-only or metadata-light turns.
- Conversation diagnostics and last-run summaries should project the normalized
  `memory_runtime_policy` payload plus a compact derived `memory_mode` from
  assistant metadata or thread fallback, rather than exposing only ad-hoc
  pollution booleans.
- Conversation diagnostics and last-run summaries should also expose the thread
  owner lifecycle fields above when available, so operators can distinguish
  active, polluted, scope-limited, and capture-suppressed states without
  re-deriving them from mixed flags.
- When a read model uses assistant metadata or thread fallback to derive
  memory policy, it should also project the effective owner source
  (`assistant_metadata` vs `thread_memory_state`) and preserve
  `thread_memory_state.updated_at` when available, so operators can tell which
  thread snapshot is being surfaced and how fresh it is.

## Long-Term Memory

- Context assembly uses a LongTermMemoryProvider interface for recall and
profile snapshot retrieval.
- Generic turns with long-term memory enabled may call vector recall without an
  explicit `memory_recall` intent, but profile snapshots remain reserved for
  explicit memory-recall flows unless runtime policy evolves further.
- Long-term memory capture happens after the turn in the service layer and
uses a memory extraction step plus a provider factory.
- Long-term memory capture may run even when session memory persistence is
disabled, as long as the request still carries a conversation/user scope and
`long_term_memory_enabled=true`.
- When the runtime marks a turn as polluted by external research or other
  off-thread context, blind long-term capture must be suppressed even if
  `long_term_memory_enabled=true`; runtime diagnostics should record the
  pollution reason instead of silently mixing foreign facts into durable memory.
- Memory extraction failures degrade to empty output and must not break the
main turn.
- Durable memory policy is distinct from page routing and tool routing. Page
  context, `suggested_tools`, or prompt hints must not decide whether long-term
  memory is eligible.
- “Need to mention recall first” is not an acceptable durable-memory UX model
  for the default SaaS runtime; runtime flags and thread policy must be able to
  activate recall on ordinary turns.

## Convergence Direction (2026-04)

- Align memory ownership with codex-style thread handling: background memory
  generation, explicit thread/session memory mode, and pollution guards for
  external context.
- Current implementation now persists `thread_memory_state`, exposes polluted
  state in conversation diagnostics, suppresses blind durable capture on
  polluted turns, and primes both chat and stream requests from a shared
  startup owner that normalizes thread snapshot state before request startup.
  Startup memory jobs, stage-1/stage-2 style background consolidation, and a
  stronger state-DB-backed thread owner are still future convergence work.
- External web, MCP, or other off-thread context should be able to mark memory
  mode polluted or suppress blind reuse rather than silently mixing foreign
  context into durable recall or capture.
- Do not encode memory availability inside skill prompt blocks, page adapters,
  or recovery hints.

## RAG Retrieval

- RAG injection uses the agent-level `rag_config` and validated KB bindings.
- RAG only executes when a knowledge intent is present and the turn is not
short-circuited.
- `BEFORE_KB_SEARCH` hooks may rewrite `query` / `kb_ids` / `top_k` before
retrieval; `AFTER_KB_SEARCH` hooks may adjust result lists after retrieval.
- Query rewrite (multi-query / HyDE / none) runs before vector/keyword/hybrid
search to expand recall.
- Optional rerank runs after merge to re-score results, then the filtered list
is cached for reuse.
- RAG sources and kinds are recorded in diagnostics and capability context.

## Diagnostics Requirements

- Context diagnostics include `rag_sources`, `rag_source_kinds`,
`memory_recalled`, `memory_recall_slice`, and `session_memory_injected`.
- Capability bundles publish `knowledge_base`, `session_memory`, and
`long_term_memory` context sources when active.
- Assistant-turn persistence must carry `memory_runtime_policy`, and
  conversation persistence must mirror a normalized `thread_memory_state`
  snapshot for thread-level monitoring and future startup ownership.
- When memory policy exists, conversation detail/read-model projections should
  expose both the normalized `memory_runtime_policy` payload and the derived
  `memory_mode`, alongside any pollution flags.
- Conversation detail/read-model projections should also expose
  `memory_runtime_policy_source` and, when present,
  `thread_memory_state_updated_at` so thread-owner fallback remains explicit
  instead of looking like a second implicit memory truth source.

## Required Behavior

- `memory_save` must not execute long-term vector recall.
- Generic long-term-memory turns may execute bounded vector recall without
  forcing a profile snapshot.
- Memory extraction parser must accept plain JSON or fenced JSON responses.
- Memory-capability hints and context-provider selection must follow runtime
  memory policy (`memory_context_enabled`), while `has_memory_intent` remains an
  explicit-intent diagnostic and behavior flag.
- Stream/non-stream persistence fallbacks must preserve normalized
  `memory_runtime_policy` without reconstructing runtime result objects from
  arbitrary private attributes.

## Prohibited Patterns

- Defaulting to knowledge query solely because a KB is bound.
- Treating `memory_save` as a signal to recall memory in the same turn.
- Requiring explicit `memory_recall` wording before long-term memory may assist
  an ordinary turn.
- Treating page context, `suggested_tools`, or page recovery hints as memory
  policy controls.
- Encoding durable memory availability in skill prompt blocks or page-local
  adaptation code.
- Mixing profile snapshots and vector recall without separate diagnostics.
