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
- Plugin-owned skills must be resolved through a plugin skill contract, not by
  silently falling back to canonical toolkit/builtin/http/email/code resolvers.
  If the plugin resolver or executor is missing, failed, or returns no executable
  tools, the skill is `unavailable` or `degraded` with structured runtime
  diagnostics. Catalog/manifest preview metadata is only `declared` capability
  evidence; it must not by itself make a plugin skill or extension `available`.
- Plugin skill identity is `plugin_name + manifest skill name`. Lifecycle sync
  must persist that identity on `Skill.key` / `Skill.source_ref`, registry lookup
  must be keyed by the same identity, and runtime execution must fail closed when
  a plugin-owned skill lacks that stable identity.
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
- Explicit builtin web-search requests require the user to ask to use or call
  the builtin/search tool/skill, or to name `web_search` / `fetch_url`
  directly. Mentions of "tool", "skill", or "call" as the research subject,
  such as "联网搜索最新 AI 工具" or "search how to call a tool", still follow
  the native-first path.
- Native-first turns may retain builtin web tool definitions as fallback schema
  in the runtime plan, but the OpenAI Responses payload must strip those
  function tools and any unrelated function tools when hosted search is forced,
  sending only the provider hosted `web_search` tool with required tool choice.
- Native-first overrides apply only to search rounds where `web_search` is still
  an allowed tool. Follow-up rounds that are narrowed to `fetch_url` must not be
  re-promoted to hosted search; they should call the retained builtin
  `fetch_url` tool directly.
- If forced hosted search fails before meaningful output, times out, loses
  provider connectivity, or emits only progress without meaningful output,
  runtime-v2 may fall back to the retained builtin `web_search` / `fetch_url`
  function-tool schema. Providers that also allow `chat_completions` may use
  that protocol for the builtin fallback; Responses-only providers must retry
  the same Responses protocol with the hosted-search override disabled rather
  than violating `allowed_wire_apis`. The fallback history reason must start
  with `hosted_web_search_unavailable:`.
- Responses create-stage calls and required-tool streams must be bounded even
  when an upstream-compatible SDK omits or cannot normalize a timeout. A
  required-tool stream that produces no tool call or text before its deadline
  must raise a typed timeout so runtime recovery can fall back or close
  gracefully instead of waiting for the browser-side SSE timeout.
- Native Responses evidence is the `web_search_call` output item,
  `response.web_search_call.*` stream progress, URL citations in provider
  output, or `response.tool_usage.web_search.num_requests > 0`. That evidence
  must complete `web_research` recovery intents and must not trigger a second
  builtin search retry.

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
