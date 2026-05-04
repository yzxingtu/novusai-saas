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
- Builtin runtime tools may cover platform-owned capabilities such as web
  search, current time, memory, variables, and knowledge retrieval.
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

## Web Search Governance

- Generic current-information requests such as "联网查一下最新消息", "search
  today's news", or other `web_research` intents must use the platform-owned
  WebResearch pipeline by default:
  `search -> fetch -> evidence -> answer`.
- The default search and fetch providers are the platform builtin
  `web_search` and `fetch_url` toolchain. They are first-class runtime
  providers, not a fallback after hosted search fails.
- The platform runtime owns progression through the chain. Once search results
  produce candidate URLs for a required `web_research` intent, runtime must
  fetch the selected candidate through the configured fetch provider instead of
  waiting for an LLM/provider continuation to decide whether `fetch_url` should
  happen.
- OpenAI, Gemini, Claude, Mistral, or other provider-native/hosted web search
  implementations are optional `SearchProvider` adapters. They may be selected
  only by explicit provider capability/config and must emit the same normalized
  evidence schema as builtin search.
- `openai_compatible` providers must not enable hosted/native web search by
  default. Hosted search is available only when explicit config, model/protocol
  capability, and real smoke or approved replay evidence prove support.
- Provider-native search progress events such as OpenAI
  `response.web_search_call.*` are provider diagnostics. They are not canonical
  completion evidence until normalized into the WebResearch evidence schema.
- Runtime must not implement a hosted-search-first fallback chain where provider
  timeout/progress-only output later synthesizes builtin `web_search` calls.
  Builtin search is the default provider path, so hosted search failure should
  be represented as optional-provider failure/skip diagnostics rather than the
  normal route to builtin execution.
- Raw search snippets, redirect links, or provider preamble text are not
  answer-quality evidence for required `web_research` when fetch evidence is
  available or required. Final answer synthesis and recovery must consume
  normalized evidence, preferably fetched body evidence.

### Native Search vs Platform WebResearch Boundary

- **Platform WebResearch / 联网搜索** is the default user-facing path for
  ordinary "查一下 / 联网查 / 搜一下 / latest/current ranking" requests. It owns
  tool planning, provider selection, URL fetch, relevance gating, canonical
  evidence, citations, partial/no-result wording, and frontend diagnostics.
- **Builtin `web_search` / `fetch_url`** are platform runtime tools used inside
  WebResearch. They are not "raw final answer" sources by themselves; their
  outputs must be normalized into WebResearch evidence before final synthesis.
- **Provider-native / hosted search / 原生搜索** is an optional SearchProvider
  adapter for a specific provider/model/protocol combination. It may be used
  only when explicit configuration, capability checks, and real smoke or
  approved replay evidence prove that combination. Its provider events are
  diagnostics until converted into the same WebResearch evidence schema.
- Do **not** silently switch an ordinary `web_research` turn to native search
  just because builtin public search is weak or a fetch candidate is blocked.
  Weak builtin results should instead be rejected/skipped with typed
  diagnostics (`no_results`, `candidate_*`, `blocked_url`, `low_query_relevance`)
  and, when evidence is insufficient, a transparent no-result/partial answer.
- If a user explicitly asks to test or use the builtin search tool itself
  ("用内置 web_search", "调用 fetch_url", etc.), route as a direct builtin-tool
  request. Otherwise, the runtime should treat "联网查一下" as a WebResearch
  evidence task, not as a request for the raw tool or hosted-search provider.

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
