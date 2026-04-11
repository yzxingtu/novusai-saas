# Intent Routing

## Goal

Produce stable, explicit intents before tool routing or context injection.

## Required Intent Set

- `direct_reply`
- `memory_save`
- `memory_recall`
- `knowledge_query`
- `web_research`
- `page_read`
- `page_write`
- `time_query`
- `weather_query`

## Current Entry (2026-04, Transitional)

- Current classifier output is `IntentPlan` entries from
  `backend/app/ai/engine/intent_planner.py` (fields: `kind`, `family`,
  `shortcircuit`, `requires_tools`).
- `IntentSet` is the target contract but not the current runtime interface.
  When updating rules, keep `IntentPlan` output stable and add mapping tests.

## Rules

- plan one or more explicit intents, not a single family string
- classify intent before choosing tools or retrieval strategy
- tool routing happens after intent classification
- context injection happens after intent classification
- candidate tools must be minimized to the active intent set
- do not expose mixed-family tools and hope later heuristics will sort them out

## Multi-Intent

- split the turn into explicit intents
- track completion per intent
- retry only unfinished intents
- return partial results when one intent fails after stop-loss

## Required Special Cases

- memory-save phrases such as `"存入记忆"` or `"记住这个"` must stay in
  `memory_save`
- bound knowledge bases do not create implicit `knowledge_query`
- page-read and page-write must be distinct intents
- capability self-report prompts should stay `direct_reply`

## Prohibited Patterns

- regex-order alone decides primary routing
- intent classification performing retrieval as a side effect
- tool family drift during recovery
- retrying the entire turn when only one intent is incomplete
