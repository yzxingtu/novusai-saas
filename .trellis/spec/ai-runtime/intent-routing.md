# Intent Routing

## Goal

Produce explicit, ordered intents before tool routing or context injection.

## Canonical Output

- Intent routing emits a list of `IntentPlan` items.
- Each intent includes `kind`, `family`, `shortcircuit`, `requires_tools`,
  `allow_text_response`, `continuation`, and `metadata`.
- Page-routing metadata is not valid for AI dialogue live paths. Historical
  `page_workflow` or `page_*` records may be read for diagnostics only; new
  planner output must not emit `page_ops` intents.

## Supported Intent Families

- `direct_reply` for pure text responses and capability self-report prompts.
- `memory_save` and `memory_recall` under the `memory` family.
- `knowledge_query` for KB-backed retrieval.
- `time_query` and `weather_query` for tool families that are explicitly
available.
- Page operation routing is not valid. Do not emit `page_workflow`, `page_*`, or
  `page_ops` intents for live AI dialogue.
- Online search routing is not valid. Do not emit `web_research` or any
  search/fetch intent family for live AI dialogue.

## Routing Rules

- Build a provisional capability bundle before intent planning so non-page tool
  families are known.
- Split user input into clauses and emit intents ordered by clause position.
- If no intent signal is found, return a single `direct_reply` intent.
- Page-continuation clauses such as click, open, fill, submit, summarize this
  page, or use current page must not trigger page tools. If data analysis is
  needed, route through an explicit backend/API/export or skill-pack capability.
- `memory_recall` takes precedence over `memory_save` when both signals appear.
- Codeword save prompts such as `把这个代号写入长期记忆` stay in
  `memory_save`; placeholder tokens like `CASE-*` / `SAVED_*` and caveats such
  as `不要使用页面内容` must not create `page_form_write` or `memory_recall`.
- `weather_query` without a detectable location may set `allow_text_response`
  with `missing_args=["city"]` instead of failing tool routing.
- `knowledge_query` is only emitted when a KB is bound and the user signal is
  explicit (definition-like or KB-specific). KB binding alone is not enough.
- Requests to browse, search, check live/current public information, fetch a
  public URL for a research answer, or directly invoke retired search/fetch
  tools must not create tool-bearing online-search intents. Emit a text-capable
  unsupported path, or route only to another already-supported non-web family
  when the user supplied enough non-web material.
- Negative page caveats such as "不要参考当前页面" / "do not use the current page"
  must not create `page_*` intents.
- Tool-verification guard clauses such as "若没实际调用工具就回答 NO_TOOL" are
  output constraints, not additional intents. If the named tool is retired, the
  runtime must still fail closed instead of trying to satisfy the guard by
  exposing it.
- `time_query` detection must cover direct `get_current_time` instructions and
  localized city-time prompts such as `当前上海时间`, not only the older fixed
  phrase bucket.

## Multi-Intent Behavior

- Track status per intent and retry only unfinished intents.
- Partial failures return completed intents when stop-loss or tool limits hit.
- Tool routing always scopes to the active intent set.

## LLM-first Routing Direction (2026-04)

- New intents must NOT be added by extending hardcoded keyword / verb tables.
  Intent classification should move toward LLM-driven structured output; only a
  small bounded set of deterministic shortcircuits (`memory_save` / `memory_recall`
  marker phrases, explicit `get_current_time`-style commands, KB-binding gate for
  `knowledge_query`) is allowed.
- Until a dedicated planner-time model classifier exists, the fallback planner
  may use local structured semantic profiles plus the bounded shortcircuit
  layer above. That fallback must remain schema-shaped and compact; it must not
  regress into per-intent verb buckets.
- Page intent taxonomy is not valid for live AI dialogue. New planner output must
  not emit `page_workflow`, `page_*`, or `page_ops`; historical records may only
  be read for diagnostics or invalid-input guards.
- Page-negation guards may remain only to prevent invalid page-routing behavior.
  They must not create page intents or page-tool requests.
- Implementations should stamp routing provenance in `IntentPlan.metadata`
  (`routing_mode=deterministic_shortcircuit` or `routing_mode=structured_semantic`)
  so downstream audits can distinguish bounded guards from semantic fallback.

## Prohibited Patterns

- Tool routing before intent planning.
- Intent classification that performs retrieval or memory side effects.
- Defaulting to `knowledge_query` solely because a KB is bound.
- Introducing or restoring `web_research`, search/fetch, or provider-native
  search as a live intent family.
- Collapsing page, online-search, and ordinary text intents into one ambiguous
  family.
- Adding new hardcoded verb / noun vocabulary lists to extend intent coverage
  (e.g., `_PAGE_NAVIGATION_PREFACE_*`, `_KNOWLEDGE_TERMS`, `_WEATHER_TERMS` style
  expansions). New coverage must come from LLM-driven routing or from explicit
  bounded shortcircuits, not from an ever-growing phrase bucket.
- Introducing or restoring `page_workflow`, `page_*`, or `page_ops` as a live
  intent family. Use explicit backend APIs, exports, or permissioned skill-pack
  tools for analyzable data instead.
