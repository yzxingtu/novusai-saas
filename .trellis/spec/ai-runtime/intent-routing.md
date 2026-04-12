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
- `memory_recall` takes precedence over `memory_save` when both signals appear.
- `weather_query` without a detectable location may set `allow_text_response`
with `missing_args=["city"]` instead of failing tool routing.
- `knowledge_query` is only emitted when a KB is bound and the user signal is
explicit (definition-like or KB-specific). KB binding alone is not enough.
- `web_research` must be suppressed when the user explicitly forbids web access.

## Multi-Intent Behavior

- Track status per intent and retry only unfinished intents.
- Partial failures return completed intents when stop-loss or tool limits hit.
- Tool routing always scopes to the active intent set.

## Prohibited Patterns

- Tool routing before intent planning.
- Intent classification that performs retrieval or memory side effects.
- Defaulting to `knowledge_query` solely because a KB is bound.
- Collapsing page and web research intents into one ambiguous family.
