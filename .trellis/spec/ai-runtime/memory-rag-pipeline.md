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
- Runtime capability summaries, contributor enablement, and memory-aware
  context-source selection should key off `memory_context_enabled` (or its
  future replacement), not only `has_memory_intent`.

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

## Required Behavior

- `memory_save` must not execute long-term vector recall.
- Generic long-term-memory turns may execute bounded vector recall without
  forcing a profile snapshot.
- Memory extraction parser must accept plain JSON or fenced JSON responses.
- Memory-capability hints and context-provider selection must follow runtime
  memory policy (`memory_context_enabled`), while `has_memory_intent` remains an
  explicit-intent diagnostic and behavior flag.

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
