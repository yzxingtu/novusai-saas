# Tool And Skill Governance

## Goal

Tools and skills should be routed deliberately, with explicit cost awareness.

## Rules

- skill routing and tool routing are different decisions
- neither layer should widen context or candidate actions without a clear payoff
- overlapping skills must be resolved by scope, not by stacking all of them
- explicit mutual exclusion is better than prompt-era “best effort”
  arbitration
- page runtime tools must stay separate from generic tool families
- web-search orchestration must stay separate from generic provider chat logic

## Budget Rules

- cap candidate tools per turn
- cap candidate skills per turn
- do not expose tools that are irrelevant to the active intent
- do not expose whole tool families for convenience

## Trigger Rules

- use a skill only when the task matches its scope
- do not trigger deep workflow mechanics for routine tasks
- do not load large reference bundles by default
- page-read and page-write tools must be distinct capability groups

## Page Runtime Rules

- readonly page operations and write page operations must be separated
- consent flow is a page-runtime concern, not a generic retry concern
- generic `invoke_page_operation` is a fallback, not the primary interface when
  dedicated tools exist
- frontend page runtime should publish a thin `page_context` through the shared
  UI Runtime bridge; pages and CRUD helpers only contribute stable page keys,
  policy, and form/session hooks
- `page_context` should stay summary-first: active form summary, surface stack,
  `suggested_tools`, and `ui_epoch`; heavy DOM or content detail stays behind
  `ui_get_snapshot`, `ui_read_region`, and `ui_read_table`
- runtime scans must exclude the AI panel itself and any subtree marked with
  `data-ai="off"` so tool exposure matches the actual allowed surface
- page capability filtering must run through shared policy helpers such as
  `use-ai-page-policy.ts` and `utils/ai-page-capabilities.ts`, not per-page
  registry reinvention

## Current Implementation Notes (2026-04, Transitional)

- `backend/app/ai/tools/executors/builtin_executor.py` still includes
  `web_search` orchestration and some public HTML parsing utilities. Treat this
  as transitional; new work should go into dedicated `web_search` or
  `page_runtime` modules.
- Page read/write execution is partially split but not yet fully isolated into
  a dedicated `page_runtime` package. Do not add new page-runtime behavior
  directly into `builtin_executor.py`.

## Prohibited Patterns

- recursive skill escalation
- tool exposure without minimal-necessity filtering
- page runtime hidden inside monolithic builtin executors
- reviving removed page registration / page operation registry flows alongside
  the shared UI Runtime bridge
- duplicated rule bodies across `.trellis`, `.claude`, `.agents`, and `.cursor`
