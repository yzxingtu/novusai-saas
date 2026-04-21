# Intent Routing

## Goal

Produce explicit, ordered intents before tool routing or context injection.

## Canonical Output

- Intent routing emits a list of `IntentPlan` items.
- Each intent includes `kind`, `family`, `shortcircuit`, `requires_tools`,
  `allow_text_response`, `continuation`, and `metadata`.

## Supported Intent Families

- `direct_reply` for pure text responses and capability self-report prompts.
- `memory_save` and `memory_recall` under the `memory` family.
- `knowledge_query` for KB-backed retrieval.
- `web_research` for external search.
- `time_query` and `weather_query` for tool families that are explicitly
available.
- `page_*` intents for page operations under the `page_ops` family. The current
set includes summary, navigation, search, form read or write, editor read or
write, pagination, row detail, and screenshot operations.

## Routing Rules

- Build a provisional capability bundle before intent planning so tool families
and page context are known.
- Split user input into clauses and emit intents ordered by clause position.
- If no intent signal is found, return a single `direct_reply` intent.
- When a page continuation context is active, route to `page_*` intents and
suppress `knowledge_query` or `web_research` signals from the same clause.
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

## Prohibited Patterns

- Tool routing before intent planning.
- Intent classification that performs retrieval or memory side effects.
- Defaulting to `knowledge_query` solely because a KB is bound.
- Collapsing page and web research intents into one ambiguous family.
