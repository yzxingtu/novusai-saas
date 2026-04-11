# Memory And RAG Pipeline

## Goal

Memory and RAG should be explicit contributors, not side effects hidden inside
intent routing or context assembly.

## Intent Taxonomy

- `memory_save`
- `memory_recall`
- `knowledge_query`
- `web_research`
- `page_read`
- `page_write`
- `direct_reply`

## Rules

- `memory_save` and `memory_recall` are different intents
- saving memory does not imply vector recall
- bound knowledge bases do not imply automatic `knowledge_query`
- memory extraction failures degrade safely without poisoning the main turn
- RAG retrieval and long-term memory recall must publish distinct diagnostics and
  embedding reasons

## Context Contribution Order

1. current turn and active intent
2. minimal system/runtime rules
3. page context or active external context
4. compacted history
5. session memory
6. long-term profile snapshot
7. long-term vector recall
8. RAG results

## Required Contributor Model

Each contributor must publish:

- `kind`
- `text_block`
- `token_cost`
- `source_ref`
- `diagnostic_payload`

## Current Implementation Notes (2026-04, Transitional)

- `backend/app/ai/context/engine.py` still records contribution metadata via
  `append_budgeted_addition(category, budget_usage)` rather than the full
  contributor schema.
- `backend/app/ai/context/contributors/memory.py` exposes recall flags but does
  not yet emit full `ContextContribution` payloads.
- Treat the full contributor model as the target-state contract and avoid
  coding against it until the pipeline upgrade completes.

## Required Behavior

- `"存入记忆"`, `"记住这个"`, `"remember this"` must classify as `memory_save`
- memory-save turns must not execute long-term vector recall
- knowledge-query turns may execute RAG only when classifier or explicit rule
  allows it
- memory extraction parser must support plain JSON, fenced JSON, and structured
  outputs

## Prohibited Patterns

- “if no other signal and KB is bound, default to knowledge query”
- `has_memory_intent = true` for every authenticated turn
- mixing profile snapshots and vector recall into one indistinguishable block
