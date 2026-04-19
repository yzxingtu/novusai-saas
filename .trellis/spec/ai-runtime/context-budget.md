# Context Budget

## Goal

Inject the smallest context that preserves correctness and can be explained by
diagnostics.

## Rules

- every system prompt addition must be budgeted
- every context addition should come from an explicit contributor
- contributor families may be gated by intent-aware orchestration rather than
  always-on injection
- tool awareness and capability summaries should be injected once per turn, not
  every round
- old history should be summarized before it crowds out active work
- tool results must be size-limited; large raw payloads are not valid default
  context
- large tool inventories should use discoverable/deferred exposure instead of
  full prompt enumeration
- directory-wide spec loading is not allowed in default governance flows

## Priority Order

1. current turn and active intent
2. minimal system/runtime rules
3. current page or active external context
4. compacted history
5. session memory
6. long-term profile snapshot
7. long-term recall
8. RAG extras

## Contributor Selection Rules

- `skills` are the installed capability inventory, but only turn-selected packs
  and discoverable/deferred tool specs should be surfaced; do not inject full
  `SKILL.md` bodies, prompt blocks, or every installed tool description into
  the baseline prompt
- Live selected skill names should come from execution-backed capability packs
  (`capability_pack`) and resolved tool bindings. Descriptor-only entries with
  `has_execution_tools=false` are catalog metadata, not budget-worthy live
  capability context.
- `page_context` should be attached only when the intent plan actually needs
  page-aware runtime behavior
- `knowledge_base` should not be injected for all-shortcircuit turns that do
  not need retrieval
- `memory` should be attached only when the turn or runtime flags justify it;
  page hints and `suggested_tools` must not toggle memory injection
- Runtime memory attachment should follow `memory_context_enabled` (or the
  successor runtime policy seam), not only explicit `memory_recall` wording.
- long-term memory may participate in ordinary turns when runtime policy allows
  bounded recall; explicit `memory_recall` wording is not required for every
  assisted turn
- `runtime_model` capability summaries may stay always-on because they drive
  downstream tool/runtime decisions
- thin `page_context` payload size must respect the runtime config
  `ai_page_context_max_bytes` (default `8192`); large UI content belongs behind
  `ui_get_snapshot` / `ui_read_*`, not inside the baseline prompt payload
- `page_context.page_data` is a strict compact seam; unsupported keys are
  contract violations that should be rejected rather than silently dropped

## Required Diagnostics

- contributor kind
- token cost
- source reference
- whether the block was injected or pruned

## Current Implementation Notes (2026-04, Transitional)

- Current context injection uses `append_budgeted_addition(category, budget_usage)`
  in `backend/app/ai/context/engine.py`, which records category + budget usage
  instead of full `ContextContribution`.
- `MemoryContextContribution` currently exposes recall flags rather than full
  `kind/text_block/token_cost/source_ref/diagnostic_payload`.
- Current generic-turn memory behavior is bounded: runtime flags may enable
  vector recall on ordinary turns, while profile snapshots still stay behind
  explicit memory-recall semantics.
- Current live skill-descriptor behavior is also bounded: runtime producers emit
  `capability_pack` descriptors, while `prompt_skill` remains compatibility-only
  input during migration.
- Treat the full `ContextContribution` contract as the target-state schema; do
  not hardcode new contributor fields into caller code until the pipeline
  upgrade lands.

## Prohibited Patterns

- full workflow injection at session start
- full spec-index injection at session start
- full file bodies for every referenced context file
- full installed skill-pack docs or prompt-block bodies injected into every
  turn
- repeated capability/tool rule duplication across system prompts, hooks, and
  skills
- untracked memory or RAG text inserted without contributor metadata
