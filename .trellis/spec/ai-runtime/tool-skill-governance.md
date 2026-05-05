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
- Builtin runtime tools may cover platform-owned capabilities such as current
  time, memory, variables, and knowledge retrieval. Online search is not a
  supported builtin capability.
- Skill/package defects in new-system live paths must be corrected at the owner
  contract boundary rather than papered over in downstream diagnostics,
  read-models, or frontend compatibility logic. Temporary compatibility patches
  need an explicit removal plan and must not become the primary behavior.
- Catalog/package previews and agent runtime resolution must share the same
  resolver failure semantics. Catalog preview metadata is a read-only
  `catalog_resolution` view, not runtime truth, but plugin-owned skills that
  cannot produce executable tools must still surface structured
  `resolution_issues` such as `plugin_resolver_missing` instead of silently
  appearing as an empty package.
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

## Online Search Removed

AI dialogue no longer supports online search, WebResearch, public URL fetch for
research answers, or provider-hosted/native search as runtime capabilities.

- Candidate tools, model tool definitions, runtime manifests, capability
  summaries, prompt contracts, provider request payloads, skill-pack exposure,
  and frontend/CLI diagnostics for new turns must not advertise `web_search`,
  `fetch_url`, `web_research`, hosted/native search, `SearchProvider`, public
  search backends, or URL-fetch-for-research tools.
- Current-information prompts such as "联网查一下最新消息", "search today's
  news", "搜一下", "latest/current ranking", or direct requests to call a
  retired search/fetch tool must fail closed. The planner may keep a
  text-capable unsupported response path, ask the user to provide sources, or
  route to a non-web capability already present in the request, but it must not
  browse, search, fetch, synthesize citations, or call a provider-hosted search
  feature.
- Provider-native or hosted search events such as OpenAI
  `response.web_search_call.*` are unsupported for new AI dialogue turns. They
  must not be used as completion evidence, progress evidence, or a trigger to
  synthesize any builtin search/fetch call.
- Historical persisted traces may still contain retired online-search names.
  Read-models may display those records as generic legacy diagnostics only; the
  records must not make online search appear available and must not recover,
  retry, or complete a new turn.
- This removal does not forbid ordinary application networking, internal HTTP
  clients, attachment download, plugin API calls, KB retrieval, or user-supplied
  document analysis. It forbids AI dialogue live paths from browsing/searching
  the public web to answer a prompt.

## Required Guards

- API entrypoints must not accept `page_context` or `page_session_id`.
- Runtime context assembly must not create `page_context` context sources.
- Tool definitions returned to the model must not include UI/page operation tools.
- Tool definitions returned to the model must not include retired online-search
  tools or provider-hosted search declarations.
- `ToolSandbox` must reject UI/page operation tool names even when supplied by a
  manual definition or plugin.
- `ToolSandbox` and resolver boundaries must reject retired online-search tool
  names even when supplied by a manual definition, plugin, provider capability,
  or compatibility fixture.
- Frontend chat shells must not collect DOM, join page sessions, render page AI
  rails, or send page context fields.
- Tests touching AI dialogue live paths must state whether they are
  structural, behavioral, or smoke, and must not treat mocks of page operation
  success as live acceptance.
