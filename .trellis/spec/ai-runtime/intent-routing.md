# Intent Routing

## Goal

Produce explicit, ordered intents before tool routing or context injection.

## Canonical Output

- Intent routing emits a list of `IntentPlan` items.
- Each intent includes `kind`, `family`, `shortcircuit`, `requires_tools`,
  `allow_text_response`, `continuation`, and `metadata`.
- During the current migration, page-routing metadata must carry the collapsed
  workflow projection (`page_workflow_kind=page_workflow`,
  `page_workflow_goal`, plus stage or phase fields when available). If an
  emitted `kind` is still a legacy `page_*` alias for downstream compatibility,
  that alias lives in `IntentPlan.kind`, not in a duplicated metadata field.

## Supported Intent Families

- `direct_reply` for pure text responses and capability self-report prompts.
- `memory_save` and `memory_recall` under the `memory` family.
- `knowledge_query` for KB-backed retrieval.
- `web_research` for external search.
- `time_query` and `weather_query` for tool families that are explicitly
available.
- `page_workflow` for page operations under the `page_ops` family. Historical
`page_*` kinds are bounded read-path aliases during migration only; live
routing truth is `page_workflow` plus `IntentPlan.metadata.page_workflow_*`.

## Routing Rules

- Build a provisional capability bundle before intent planning so tool families
and page context are known.
- Split user input into clauses and emit intents ordered by clause position.
- If no intent signal is found, return a single `direct_reply` intent.
- When a page continuation context is active, route to `page_workflow` with
collapsed workflow metadata and suppress `knowledge_query` or `web_research`
signals from the same clause.
- Action-style page continuations such as `点击一下添加供应商`, `单击`, or
  `click` must override a prior read-only page intent and route to
  `page_navigation`; continuation inheritance must not pin those clauses to
  `page_summary` or another read-only `page_*` kind.
- Page-continuation runtime facts such as `last_tool_name`, `last_page_key`,
  and `last_page_op` must be read from canonical turn diagnostics or
  `turn_record` payloads first. Parsing legacy tool-call arguments is a
  bounded historical fallback only, not the live owner path for continuation
  routing.
- `memory_recall` takes precedence over `memory_save` when both signals appear.
- Codeword save prompts such as `把这个代号写入长期记忆` stay in
  `memory_save`; placeholder tokens like `CASE-*` / `SAVED_*` and caveats such
  as `不要使用页面内容` must not create `page_form_write` or `memory_recall`.
- `weather_query` without a detectable location may set `allow_text_response`
  with `missing_args=["city"]` instead of failing tool routing.
- `knowledge_query` is only emitted when a KB is bound and the user signal is
  explicit (definition-like or KB-specific). KB binding alone is not enough.
- `web_research` must be suppressed when the user explicitly forbids web access.
- Explicit URL fetch requests stay in `web_research` even when the user forbids
  generic web search, and negative page caveats such as "不要参考当前页面" /
  "do not use the current page" must not create `page_*` intents.
- Tool-verification guard clauses such as "若没实际调用 fetch_url 就回答
  NO_FETCH" or "if you did not actually call the tool, answer NO_TOOL" are
  output constraints, not additional intents.
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
- Page intent taxonomy is being collapsed. The target live taxonomy keeps a
  single `page_workflow` intent family; per-phase decisions (`discover`,
  `navigate_or_open`, `read`, `write`, `submit`, `verify`) live in
  `IntentPlan.metadata` and in the page workflow state machine, not in separate
  intent kinds such as `page_navigation` / `page_row_detail` / `page_form_*` /
  `page_editor_*` / `page_search` / `page_pagination` / `page_summary` /
  `page_screenshot`. Those kinds are kept only as transitional read-path
  aliases during migration.
- Continuation guards, page-negation guards, and deterministic shortcircuits are
  allowed to stay as keyword-based checks, but they must be colocated in a
  single shortcircuit module and explicitly marked with `# SHORTCIRCUIT: <reason>`.
- Implementations should stamp routing provenance in `IntentPlan.metadata`
  (`routing_mode=deterministic_shortcircuit` or `routing_mode=structured_semantic`)
  so downstream audits can distinguish bounded guards from semantic fallback.

## Prohibited Patterns

- Tool routing before intent planning.
- Intent classification that performs retrieval or memory side effects.
- Defaulting to `knowledge_query` solely because a KB is bound.
- Collapsing page and web research intents into one ambiguous family.
- Adding new hardcoded verb / noun vocabulary lists to extend intent coverage
  (e.g., `_PAGE_NAVIGATION_PREFACE_*`, `_KNOWLEDGE_TERMS`, `_WEATHER_TERMS` style
  expansions). New coverage must come from LLM-driven routing or from explicit
  bounded shortcircuits, not from an ever-growing phrase bucket.
- Introducing a new `page_*` intent kind beyond the collapsed `page_workflow`
  target (e.g., `page_screenshot`, `page_editor_write`). Instead, extend the
  workflow state machine or add a new tool.
