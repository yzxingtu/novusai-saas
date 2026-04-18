# Memory And RAG Pipeline

## Goal

Memory and RAG must be explicit contributors with clear ownership. Retrieval,
capture, and persistence are separate concerns.

## Intent Boundaries

- `memory_save` and `memory_recall` are distinct intents.
- `memory_save` triggers post-turn capture. It must not trigger recall during
context assembly.
- `memory_recall` is the only intent that enables long-term recall in the
context pipeline.
- KB binding does not imply `knowledge_query`; the intent must be explicit.

## Pipeline Overview

1. Build system and user messages.
2. Resolve KB bindings and runtime model capabilities.
3. Plan intents (IntentPlan list).
4. If a knowledge intent is present, run the RAG retrieval pipeline
   (hooks → rewrite → search → rerank → cache) and inject context using agent `rag_config`.
5. Compute compaction and system prompt additions (date anchors, locale hints).
6. If memory recall is enabled, inject profile snapshot and vector recall blocks.
7. Inject system additions into the system message.
8. Prune and finalize capability bundle and diagnostics.

## Session Memory

- Session memory is loaded by the service layer when memory is enabled and the
conversation has a user and conversation id.
- The injected session memory block sets `session_memory_injected` on the
request and is surfaced as a context source.
- Session memory injection is independent of `memory_recall` intent.

## Long-Term Memory

- Context assembly uses a LongTermMemoryProvider interface for recall and
profile snapshot retrieval.
- Long-term memory capture happens after the turn in the service layer and
uses a memory extraction step plus a provider factory.
- Long-term memory capture may run even when session memory persistence is
disabled, as long as the request still carries a conversation/user scope and
`long_term_memory_enabled=true`.
- Memory extraction failures degrade to empty output and must not break the
main turn.

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
- Memory extraction parser must accept plain JSON or fenced JSON responses.

## Prohibited Patterns

- Defaulting to knowledge query solely because a KB is bound.
- Treating `memory_save` as a signal to recall memory in the same turn.
- Mixing profile snapshots and vector recall without separate diagnostics.
