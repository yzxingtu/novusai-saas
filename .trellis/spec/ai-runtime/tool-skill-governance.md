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
- Turn-flow, diagnostics, monitoring, and root-cause read models must not turn
  retired current-page, `page_search`, `web`, `search`, or URL-only evidence into
  knowledge-base source chips. Knowledge references for new turns must come from
  formal KB retrieval, explicit documents/artifacts, memory, or executed tool
  evidence with provenance.

## Skill Governance

- Skill packs remain installable, governable, and callable extension
  capabilities.
- Builtin runtime tools may cover platform-owned capabilities such as current
  time, memory, variables, and knowledge retrieval. Online search is not a
  supported builtin capability.
- Skill-pack invocation is LLM-facing metadata driven: the runtime exposes only
  the currently authorized tool names, descriptions, JSON schemas, semantic
  family, tags, ownership, and availability diagnostics, then lets the model
  decide when to call those tools within the normal tool-use contract.
- Public chat requests must not use `selected_skill_names`, legacy aliases, or
  frontend-side selection chips as positive skill activation input. Clients may
  pass user content, variables, attachments, KB selection, trust policy, and
  explicit domain operation payloads; skill activation is derived from the
  authorized metadata exposed to the model and server-side deny policies.
- Main runtime code must not hardcode plugin-owned skill-pack names, tool names,
  prompt snippets, business descriptions, or domain-specific routing branches
  such as weather/search/provider packages. A plugin-owned skill must express
  that behavior through its manifest, resolver, executor, and tool metadata.
  Platform-owned generic controls may still enforce authorization, tenant
  isolation, quotas, budgeting, schema conversion, provider safety guards, and
  retired capability deny lists.
- AI smoke and diagnostics checks must stay generic as well. If an intent plan
  marks `requires_tools=true`, acceptance must come from tool-completion
  evidence such as `completed_by_tool_names`, successful tool events, or matching
  executed tool names from diagnostics. Do not special-case a plugin domain such
  as weather, search, CRM, or storage in the main smoke validator.
- Agent routing may show the LLM skill names/descriptions only after the runtime
  resolver has produced executable tools for that agent and tenant. Active grant
  rows, catalog preview tool names, and manifest preview semantic families are
  not enough to advertise a capability or to direct-select an agent.
- Skill/package defects in new-system live paths must be corrected at the owner
  contract boundary rather than papered over in downstream diagnostics,
  read-models, or frontend compatibility logic. Do not add temporary
  compatibility exceptions that keep retired capability behavior alive.
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
  skill-pack tools, not DOM scanning. Editor-local writing chat is part of that
  explicit editor/domain operation contract: it may pass selected text,
  cursor before/after text, document identifiers, and bounded chat history, but
  it must not open or depend on the global AI side panel as the conversation
  runtime for selection-bound editor work.
- Plain `input` and `textarea` AI writing helpers follow the same explicit
  operation boundary as rich text editing. They may pass the selected text and
  bounded before/after text from the focused control, but they must not promote
  the surrounding rendered page, form schema, DOM snapshot, or page-operation
  tool state into AI dialogue context.
- Local selection AI may use a DOM rectangle, selection range, and element
  editability only for client-side anchoring and writeback validation. Those
  values are UI mechanics, not model context: requests may include only the
  explicit selected text, bounded before/after text, document/control metadata
  allowed by the editor-domain schema, user instruction, target language, and
  bounded local chat history.
- Editor-local rich-text chat is not a shortcut around runtime governance. It
  must resolve the same `system.ai_writing` assignment, enforce the same tenant
  access/quota guards, and reject `page_context`, `page_session_id`, `ui_*`,
  `pageop_*`, DOM snapshot, or active-surface fields. It must not hardcode a
  plugin-owned or platform-owned skill name into the generic chat runtime as a
  positive activation signal.
- The model-facing prompt for editor-local chat must include the explicit
  editor-domain context that the request body carried: selected text, cursor
  before/after text, document title/id/type when available, the user's current
  question or instruction, and bounded prior chat turns. Do not rely on a
  global side panel, page perception, or hidden frontend state to recover that
  context.

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

## Compatibility Keyword Scan Rule

Repo-wide `compat`, `legacy`, `fallback`, `alias`, and related keyword scans are
triage inputs, not delete lists. Keep matches only when they describe an
explicit current-system contract:

- OpenAI-compatible providers, protocol-safe model fallback/failover, 404 or
  route fallback pages, i18n/display fallback labels, plugin dependency or
  compatibility matrices, storage-driver compatibility, and browser/framework
  compatibility.
- Historical diagnostics, cleanup migrations, denylist guards, and regression
  tests that prove retired page-operation or online-search names are hidden,
  rejected, or audit-only.
- Stable public v1 API fields that are still the current frontend/backend
  contract and require a coordinated breaking migration before removal.

Do not keep matches that act as old-system live shims: positive activation from
`selected_skill_names`, retired skill aliases, page-runtime bridges, provider
hosted-search config, adapter compat entrypoints, package re-export shims, or
frontend fixtures that present retired online-search/page-operation names as
ordinary usable capabilities.

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
