# Tool And Skill Governance

## Page Awareness Retirement

Page awareness and page operation runtime are retired from AI dialogue live
paths. Do not rebuild DOM/page perception as a platform capability.

Retired concepts include:

- `page_context`, `page_data`, `page_session_id`, `ui_epoch`, active surface,
  active form, and DOM snapshot payloads as AI dialogue context.
- `ui_*`, `pageop_*`, `get_page_context`, `invoke_page_operation`, and
  `list_page_operations` as live AI dialogue tools.
- Frontend DOM scanners, page-operation registries, UI action channels, and
  page-session socket joins used to let the model operate the current page.
- Prompt, planner, router, manifest, or diagnostics logic that promotes a user
  request into a `page_ops` family.

Compatibility fields may remain temporarily on public schemas, but they are
ignored by live AI dialogue. They must not be used as evidence that page
awareness is enabled.

## Replacement Pattern

When AI needs to analyze business/page data, expose the data through a stable
backend boundary instead of page perception:

- Prefer backend read-model/query APIs for structured records and summaries.
- Use report/export endpoints for larger datasets or reproducible artifacts.
- Use installable skill-pack tools when the analysis is optional, domain-owned,
  permissioned, and intentionally callable by AI.
- Return structured data with provenance and authorization checks; do not ask
  the model to infer state from rendered DOM.

## Skill Governance

- Skill packs remain installable, governable, and callable extension
  capabilities.
- Builtin runtime tools may cover platform-owned capabilities such as native
  search, current time, memory, variables, and knowledge retrieval.
- Page operation tools are not valid builtin or installable tools for AI
  dialogue. Resolver, sandbox, and semantic-family code must filter or reject
  them.
- Rich text editing should use explicit editor/domain operations or future
  skill-pack tools, not page awareness or DOM scanning.

## Required Guards

- API entrypoints must ignore `page_context` and `page_session_id`.
- Runtime context assembly must not create `page_context` context sources.
- Tool definitions returned to the model must not include retired page tools.
- `ToolSandbox` must reject retired page tool names even when supplied by a
  manual definition or plugin.
- Frontend chat shells must not collect DOM, join page sessions, render page AI
  rails, or send page context fields.
- Tests touching AI dialogue live paths must state whether they are
  structural, behavioral, or smoke, and must not treat mocks of page operation
  success as live acceptance.
