# Tool And Skill Governance

## No Current-Page Runtime

AI dialogue live paths must not include a DOM/current-page perception or
page-operation runtime. Do not build browser-page state into the platform
capability model.

Forbidden concepts include:

- `page_context`, `page_data`, `page_session_id`, `ui_epoch`, active surface,
  active form, and DOM snapshot payloads as AI dialogue context.
- `ui_*`, `pageop_*`, `get_page_context`, `invoke_page_operation`, and
  `list_page_operations` as live AI dialogue tools.
- Frontend DOM scanners, page-operation registries, UI action channels, and
  page-session socket joins used to let the model operate the current page.
- Prompt, planner, router, manifest, or diagnostics logic that promotes a user
  request into a `page_ops` family.

This is a new-system boundary, not a compatibility mode. Do not keep or add
public request fields, frontend route metadata, socket channels, or runtime
bridges whose only purpose is to preserve `page_context`, `page_session_id`, or
`ui_*` page-operation behavior.

## Replacement Pattern

When AI needs to analyze business data, expose the data through a stable
backend boundary instead of page perception:

- Prefer backend read-model/query APIs for structured records and summaries.
- Use report/export endpoints for larger datasets or reproducible artifacts.
- Use installable skill-pack tools when the analysis is optional, domain-owned,
  permissioned, and intentionally callable by AI.
- Return structured data with provenance and authorization checks; do not ask
  the model to infer state from rendered DOM.
- If a product area knows AI will need to analyze its data, reserve an explicit
  backend API or skill-pack tool contract during feature design. Do not add a
  generic page-perception fallback later.

## Skill Governance

- Skill packs remain installable, governable, and callable extension
  capabilities.
- Builtin runtime tools may cover platform-owned capabilities such as native
  search, current time, memory, variables, and knowledge retrieval.
- UI/page operation tools are not valid builtin or installable tools for AI
  dialogue. Public request and sandbox boundaries must reject them.
- Rich text editing should use explicit editor/domain operations or future
  skill-pack tools, not DOM scanning.

## Web Search Governance

- Generic current-information requests such as "联网查一下最新消息", "search
  today's news", or other `web_research` intents must prefer provider-native
  Responses hosted web search when the active `openai_compatible` provider
  declares Responses support and the effective upstream model supports hosted
  search.
- Builtin or skill-pack web tools (`web_search`, `fetch_url`) are fallback
  execution paths. They may be exposed on the first model round only when
  native hosted search is unavailable, or when the user explicitly asks for the
  builtin/tool/skill path, for example by naming `web_search`, `fetch_url`,
  "联网搜索技能", or "search tool".
- Native-first turns may retain builtin web tool definitions as fallback schema
  in the runtime plan, but the OpenAI Responses payload must strip those
  function tools when hosted search is forced and send only the provider
  hosted `web_search` tool with required tool choice.
- Native Responses evidence is the `web_search_call` output item,
  `response.web_search_call.*` stream progress, or URL citations in provider
  output. That evidence must complete `web_research` recovery intents and must
  not trigger a second builtin search retry.

## Required Guards

- API entrypoints must not accept `page_context` or `page_session_id`.
- Runtime context assembly must not create `page_context` context sources.
- Tool definitions returned to the model must not include UI/page operation tools.
- `ToolSandbox` must reject UI/page operation tool names even when supplied by a
  manual definition or plugin.
- Frontend chat shells must not collect DOM, join page sessions, render page AI
  rails, or send page context fields.
- Tests touching AI dialogue live paths must state whether they are
  structural, behavioral, or smoke, and must not treat mocks of page operation
  success as live acceptance.
