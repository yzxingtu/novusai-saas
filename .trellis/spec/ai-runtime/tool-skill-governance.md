# Tool And Skill Governance

## Scenario: Page Runtime Tool + Skill Governance (Thin `page_context`, Shared UI Runtime Bridge)

### 1. Scope / Trigger
- Route skills and tools for AI runtime turns that may invoke UI/page tools.
- Resolve installable skill packs and generic tool families without turning
  them into page-specific prompt adaptations.
- Emit or validate `page_context` and optional `page_data`.
- Expose page operations with read/write separation and consent gating.
- Enforce payload budgets, summary-first constraints, and scan exclusions.

### 2. Signatures

```ts
export type PageContextSuggestedTool =
  | 'ui_click'
  | 'ui_fill_form'
  | 'ui_get_form_state'
  | 'ui_get_snapshot'
  | 'ui_list_interactables'
  | 'ui_open_surface'
  | 'ui_read_region'
  | 'ui_read_table'
  | 'ui_set_field'
  | 'ui_submit_form';

export interface PageContextSuggestedTools {
  primary: PageContextSuggestedTool[];
  reason?: string;
  secondary?: PageContextSuggestedTool[];
}

export interface PageContext {
  active_form_session_id?: string;
  active_form_summary?: ActiveFormSummary;
  active_surface_id?: string;
  locale?: string;
  page_key: string;
  page_session_id?: string;
  page_title?: string;
  suggested_tools?: PageContextSuggestedTools;
  surface_stack?: PageSurfaceSummary[];
  ui_epoch?: number;
}

export interface PageOperation {
  name: string;
  label: string;
  description?: string;
  readonly: boolean;
  params?: Record<string, unknown>;
  handler?: PageOperationHandler;
}
```

```py
async def get_ui_runtime_payload_max_bytes(db) -> int
async def validate_page_context_size(db, page_context) -> None
def resolve_page_locale(input_variables: dict | None) -> str
def has_navigation_intent(query: str, page_context: Mapping | None = None) -> bool
```

```ts
export function getRuntimeThinPageContext(explicitPageKey?: string): PageContext | null
export function getRuntimeSnapshot(mode: 'compact' | 'full'): UISnapshot
export function readRuntimeRegion(locator: string): Record<string, unknown>
export function readRuntimeTable(args: { locator: string; page?: number; pageSize?: number }): Record<string, unknown>
export function listRuntimeInteractables(surfaceId?: string): Record<string, unknown>
export async function fillRuntimeForm(args: { fields: Record<string, unknown>; formSessionId?: string }): Promise<RuntimeFormActionResult>
export async function submitRuntimeForm(args: { confirm?: boolean; formSessionId?: string }): Promise<RuntimeFormActionResult>
```

`AgentChatRequestBody.page_context?: PageContext` is the thin UI runtime payload injected by the frontend.

`page_context.page_data` is an optional compact extension shared between the frontend runtime and backend navigation/locale heuristics.

```json
{
  "page_context": {
    "page_key": "admin.ai.agents",
    "page_title": "Agents",
    "locale": "en",
    "ui_epoch": 12,
    "suggested_tools": { "primary": ["ui_get_snapshot"], "reason": "..." },
    "page_data": {
      "locale": "en",
      "entity_description": "Agent list and actions",
      "navigation_context": { "breadcrumb": ["AI", "Agents"] },
      "navigation_catalog": [
        {
          "title": "Agents",
          "path": "/admin/ai/agents",
          "page_key": "admin.ai.agents",
          "description": "Manage agents",
          "category": "AI",
          "keywords": ["agent", "assistant"],
          "capabilities": ["create", "edit"],
          "breadcrumb": ["AI", "Agents"]
        }
      ]
    }
  }
}
```

### 3. Contracts

#### 3.1 Tool/Skill Routing
- Skill routing and tool routing are distinct decisions; do not widen both without intent.
- Installed skills are runtime capability packs. Live runtime truth comes from
  resolved tool definitions, execution policy, and dependency metadata, not
  from `Skill.skill_md`, package `SKILL.md`, prompt blocks, or
  `CapabilityDescriptor(kind="prompt_skill")`.
- Resolved capability inventory and turn-level activation are distinct seams.
  The resolver may carry a broader installed inventory for planning or catalog
  surfaces, but live runtime summaries must speak from the turn-activated
  subset and, after tool planning, from the selected tool subset.
- Initial/provisional capability bundles used for intent planning or
  continuation planning must also refresh after turn activation is applied.
  It is not sufficient to narrow only the later prepared-execution tool list;
  startup planning must stop speaking from the broader agent inventory once
  explicit skill mentions or runtime-policy activation are known.
- Live installed-skill descriptors should normalize to
  `CapabilityDescriptor(kind="capability_pack")`. Accepting
  `prompt_skill`-style descriptors is compatibility-only behavior during
  migration, not the target live contract.
- Turn-level `selected_skill_names` and capability summaries must be derived
  from execution-backed capability packs. Descriptor-only entries with
  `has_execution_tools=false` are catalog or diagnostics metadata, not live
  runtime skill truth.
- After tool planning, the live capability bundle, runtime manifest, and
  `selected_skill_names` diagnostics must be projected to the selected tool
  subset before runtime summaries are emitted. Capability-reporting turns may
  keep broader inventory visibility only when the turn intentionally has no
  live tool subset.
- Turn-scoped capability activation must be driven by explicit mention,
  runtime policy, or bounded routing decisions. Installing a skill pack must
  not require per-page adaptation before it becomes usable.
- Resolver startup should prefilter grant resolution when the turn already
  carries a bounded activation signal such as an explicit skill mention,
  explicit tool-call name, or capability-reporting query. Resolver startup
  may keep a safety fallback to the broader grant set when startup signals are
  absent or the preview is incomplete, but command/dispatcher entrypoints must
  pass the live request into skill resolution so that prefilter seam can run.
- Startup activation may narrow skill-owned tools, but auto-injected baseline
  runtime builtins remain startup-available. Do not reclassify those baseline
  builtins as skill-owned just because they expose `source_skill_name`-style
  compatibility metadata.
- Capability-reporting turns may intentionally surface the broader installed
  inventory, but tool-bearing turns must collapse back to the turn-activated
  or tool-selected subset before manifest, diagnostics, and capability-aware
  summaries are emitted.
- Candidate tool and skill sets are capped per turn; avoid exposing whole families for convenience.
- Overlapping skills resolve by scope, not by stacking.
- Page runtime tools stay separate from generic tool families.
- Large MCP or skill inventories must support deferred or discoverable
  exposure, search, or threshold-based reveal; do not dump full installed
  catalogs into the prompt just because the packages exist.
- `suggested_tools` is a frontend/read-model hint only. It may shape local UX
  affordances, but it must not become authoritative input for backend tool
  exposure, capability descriptions, or recovery policy.
- Capability descriptions may summarize page title, active surface, and active
  form state, but must not mirror `suggested_tools` back into runtime-facing
  awareness or selection logic.
- When a `web_research` intent is pinned to an explicit external URL, route it
  directly to `fetch_url` when available instead of preferring `web_search`.
- `page_form_write` routing must be runtime-state aware: when no active form session exists, expose discovery/open tools (`ui_list_interactables`, `ui_open_surface`, `ui_click`) before form mutation tools so the model can find and open the create/edit surface first; when an active form exists, prioritize form read/write tools instead.
- Page-intent routing must project explicit workflow metadata into the live
  intent plan. `IntentPlan.metadata` is the canonical seam for
  `page_workflow_stage`, `page_workflow_phase`, `page_workflow_goal`,
  `page_workflow_state`, and `page_workflow_completion`; completion,
  recovery, and contract-breach checks must all consume that same metadata
  contract instead of re-inferring page progress from prompt hints or keeping
  a second stage table.
- `page_navigation` and `page_row_detail` must distinguish
  discover/open/verify phases using canonical UI runtime facts such as
  `active_surface_id`, `surface_stack`, surface kind, and overlay presence.
  Opening or clicking a surface is not by itself the completion signal when the
  workflow stage still requires a follow-up read or verification step.
- `page_editor_write` follows the same owner rule as `page_form_write`: once
  the active editor/form stage is `ready_to_submit`, completion must be gated
  on `ui_submit_form` rather than treating `ui_fill_form` as turn-complete.
- Web-search orchestration stays separate from generic provider chat logic.
- Responses request builders must preserve the builtin function `web_search` by default so the runtime web-search orchestrator keeps its native/public fallback chain. Rewriting that function into provider-hosted `{"type":"web_search"}` is allowed only when `provider.config.web_search.prefer_hosted_tool` is explicitly true.

#### 3.2 Shared UI Runtime Bridge Boundary
- The shared bridge is `frontend/.../ai-runtime/runtime-bridge.ts`; it is the only place that builds thin `page_context` from DOM/form/session state.
- The shared frontend page-runtime package is `frontend/.../ai-runtime/**`.
  `runtime-bridge.ts` owns thin `page_context` assembly,
  `form-session-manager.ts` owns form-session tracking,
  `locator-resolver.ts` owns locator semantics, and
  `ui-action-executor.ts` owns UI read/write execution and diff reporting.
  These public files may stay as thin facades, but new logic should land in
  co-located companion modules such as `*-core.ts`, `*-support.ts`, or
  `*-contracts.ts` instead of re-expanding the public entrypoint.
  Pages and generic composables may consume those public helpers, but must not
  recreate the same domains elsewhere.
- Pages and CRUD helpers contribute stable page keys, route policy, and form/session hooks only; do not embed DOM, HTML, or UI graph data in `page_context`.
- Runtime scans must exclude the AI panel (`[data-ai-panel]`) and any subtree with `data-ai="off"`.

#### 3.3 `page_context` and `page_data` Positioning
- `page_context` is injected into `AgentChatRequestBody.page_context` and is built via `getRuntimeThinPageContext()` using `UISnapshotGenerator.buildThinPageContext`.
- `page_key` is required and normalized via `normalizePageKey` / `resolveRoutePageKey`, honoring `route.meta.ai.pageContextKey`.
- Optional fields: `page_title`, `locale`, `page_session_id`, `active_form_summary`, `active_form_session_id`, `surface_stack`, `ui_epoch`, `suggested_tools`.
- `page_context.page_data` is optional, summary-first, and is the only allowed seam for compact navigation metadata such as `navigation_catalog` and `navigation_context`.
- `page_context.page_data` is a strict compact contract. Unknown keys are invalid request payload, not silently ignored runtime hints.
- `/ai/agent-chat/{agent_id}/chat` and `/ai/agent-chat/route` must preserve the
  same request-boundary contract: unknown `page_data` keys fail validation,
  while malformed `navigation_catalog` items are filtered instead of taking
  down the whole turn.

#### 3.4 Summary-First Constraint
- `getRuntimeThinPageContext()` always uses `compact` snapshots; only summary fields flow into `page_context`.
- Heavy UI content must be retrieved via `ui_get_snapshot` (full), `ui_read_region`, or `ui_read_table`.
- `page_context` should only carry active form summary, surface stack, suggested tools, and `ui_epoch`.

#### 3.5 Read/Write Separation and Consent
- Every page tool must declare `PageOperation.readonly`.
- Read tools: `ui_get_snapshot`, `ui_list_interactables`, `ui_read_region`, `ui_read_table`, `ui_get_form_state`.
- Write tools: `ui_click`, `ui_open_surface`, `ui_set_field`, `ui_fill_form`, `ui_submit_form`.
- `serializeAvailableOperations` filters operations via route AI policy and `filterPageOperationsByPolicy`; `PageContextSuggestedTool` is limited to the UI tool set.
- Frontend capability filters, pending-op display, and tool-call chips must
  treat canonical `ui_*` names as the only live page-runtime tool truth.
  Legacy names such as `navigate_menu`, `open_page`, `read_visible_rows`,
  `fill_form`, and `submit_form` are no longer part of the live runtime path.
- Frontend route-security bridges should emit canonical form-write action kinds
  (`ui_set_field`, `ui_fill_form`, `ui_submit_form`) when projecting live
  runtime policy into `disabledActionKinds` / `confirmActionKinds`.
  Legacy values such as `fill_field`, `fill_form`, and `submit_form` are
  compatibility-only inputs if older route config still carries them; shared
  defaults must not keep re-emitting those names.
- Pending-confirmation replay across frontend and backend should treat
  `tool_name` as the canonical live match key. Legacy `action` / `table`
  fields may remain as evidence or replay compatibility metadata, but
  `interaction_updates` and persistence matching must not depend on those older
  page-op semantics when `tool_name` is present.
- Page-operation helper factories outside the shared UI runtime must not silently
  default to legacy live-ish names such as `create_record`, `open_page`,
  `open_current`, or `read_row_detail`. If a page still needs those helpers, it
  must pass an explicit operation name instead of reviving a hidden default seam.
- `security-policy` enforces `data-ai*` directives and route policy; `evaluateAIActionSecurity` blocks and requires confirmation for dangerous action kinds; `submitRuntimeForm` enforces `submit_policy === 'confirm'`.

#### 3.6 Budget Governance
- Backend: `validate_page_context_size` serializes the payload and enforces `ai_page_context_max_bytes` (default 8192, min 1). Oversized payload raises `ValidationException` with message key `agent_chat.error.page_context_too_large` and `current/limit` interpolation.
- Frontend: `UISnapshotGenerator` budgets compact to 10 KB and full to 50 KB, with compact node limit 160 and truncation rules; DOM fallback scanning uses `maxDepth=6`, `maxNodes=160`; `listRuntimeInteractables` returns up to 200 items; `surface_stack` is capped at 12, form sessions at 8, required fields at 32.

#### 3.7 Navigation Semantics Alignment
- Backend `has_navigation_intent` requires navigation action terms and a semantic match against `page_context.page_data.navigation_catalog`.
- Backend `app.schemas.ai.agent_chat.PageContext` must model `page_data` explicitly so compact `navigation_catalog` / `navigation_context` survives request normalization instead of being dropped as extra payload.
- `navigation_catalog` entries should include title/path/page_key plus optional description/category/keywords/capabilities/breadcrumb to enable scoring.
- Malformed `navigation_catalog` items should be filtered during normalization instead of failing the entire turn; blank required title/path/page_key values are invalid after trimming.
- `available_menus` is outside the live contract. New runtime code must neither emit nor consume it; cross-page routing is allowed to depend only on `navigation_catalog`.
- Locale resolution checks `page_data.locale` or `page_context.locale`, then infers from `page_title`, `entity_description`, and breadcrumbs, finally falling back to `get_locale()` or `"zh_CN"`.

#### 3.8 Transitional Boundaries (2026-04)
- `backend/app/models/ai/skill.py` still carries `Skill.skill_md`, and
  `backend/app/ai/skills/packaging.py` still parses package `SKILL.md`. Treat
  those paths as packaging or catalog metadata only; do not add new live tool
  exposure or prompt-injection dependencies there.
- `backend/app/ai/runtime/context_assembler.py`,
  `backend/app/ai/runtime/capabilities.py`, and
  `backend/app/ai/capabilities/description_builder.py` still preserve
  read-path compatibility for `prompt_skill`-style descriptors, but live
  runtime producers now emit `capability_pack` descriptors and derive
  `selected_skill_names` from execution-backed tool bindings. Treat
  `prompt_skill` inputs as diagnostics or UX compatibility only, not as the
  authoritative runtime source for installed capability packs. Descriptor
  entries that explicitly resolve to `has_execution_tools=false` must be
  treated as catalog-only.
- `backend/app/ai/skills/resolver.py` now performs a bounded startup
  prefilter for explicit skill mentions, explicit tool-call names, and
  capability-reporting queries before full skill resolution, while
  `backend/app/ai/skills/turn_activation.py` remains the live activation seam
  for runtime-policy page/web activation and later turn narrowing. Treat those
  two layers together as the current startup/live owner chain; do not add new
  prompt-driven or page-specific paths that bypass them.
- `frontend/.../ai-slide-panel/use-page-ai-capability.ts` and
  `frontend/.../utils/page-navigation.ts` still read `suggested_tools` for
  local affordance display and fallback assembly. Keep that boundary UX-only;
  do not promote those hints back into runtime tool routing.
- `frontend/.../components/business/ai-runtime/runtime-bridge-snapshot.ts`
  and `frontend/.../utils/page-navigation.ts` now inject compact
  `page_data.navigation_catalog` / `page_data.navigation_context` into live
  page context and navigation results. Keep that payload summary-first and do
  not regress to heavy page-local `page_data` blobs or a second navigation
  truth source.
- `backend/app/ai/tools/executors/builtin_executor.py` still hosts legacy web_search and HTML parsing; treat as transitional and do not add new page-runtime behavior there.
- Page read/write execution is partially split; avoid adding new page-runtime logic into builtin executors.

### 4. Validation & Error Matrix

| Scenario | Source | Error / Behavior |
| --- | --- | --- |
| `page_context` serialized size exceeds `ai_page_context_max_bytes` | `validate_page_context_size` | `ValidationException` with `agent_chat.error.page_context_too_large` and `current/limit` |
| `page_context` empty or non-dict | `validate_page_context_size` | No validation error |
| `ai_page_context_max_bytes` invalid | `get_ui_runtime_payload_max_bytes` | Fallback to default 8192 and enforce min 1 |
| `getRuntimeThinPageContext()` cannot resolve `page_key` | frontend runtime | Returns `null` |
| UI locator invalid/ambiguous/not found | `LocatorResolver` | `error_type`: `invalid_locator` / `ambiguous` / `not_found` |
| UI action blocked by policy | `evaluateAIActionSecurity` | `error_type`: `policy_blocked` |
| UI action requires confirmation | `evaluateAIActionSecurity` | `error_type`: `confirmation_required` |
| UI target disabled | `UIActionExecutor` | `error_type`: `element_disabled` |
| `fillRuntimeForm` no writable fields | `applyFormValues` | `error_type`: `no_writable_fields` |
| `submitRuntimeForm` needs confirm | `submitRuntimeForm` | `error_type`: `confirmation_required` |
| `readRuntimeRegion` / `readRuntimeTable` locator missing | runtime-bridge | Throw error, surface as tool failure |

### 5. Good / Base / Bad Cases

**Good**: Thin `page_context` with summary fields, optional `page_data` menus, and UI details fetched via `ui_read_region` or `ui_get_snapshot`.

**Base**: `page_context` absent; runtime proceeds without page semantics, navigation intent returns false, locale falls back to `get_locale()` or `"zh_CN"`.

**Bad**: `page_context` embeds full DOM, large HTML, or full UI graph; size validation fails and tool routing leaks sensitive data.

### 6. Tests Required
- Backend: oversize `page_context` raises `ValidationException` with `current/limit`, invalid config falls back to default, empty context is accepted.
- Backend: skill resolution and capability descriptions must not require
  `skill_md` prompt blocks or page-local hints to expose installed tools.
- Backend: descriptor-only skills with `has_execution_tools=false` must not be
  reported as live `selected_skill_names`.
- Backend: turn-scoped skill activation may narrow live summaries to explicit
  mention or runtime-policy subsets, while capability-reporting turns may keep
  broader inventory visibility when no live tool subset is active.
- Backend: page capability descriptions must ignore `suggested_tools`; those
  hints stay UX-only.
- Frontend: `getRuntimeThinPageContext()` uses `compact` snapshot and excludes `[data-ai-panel]` / `data-ai="off"` subtrees.
- Frontend: `UISnapshotGenerator` truncates to compact/full budgets and enforces node limits.
- Frontend: `PageOperation.readonly` mapping matches UI tool behavior; read tools never mutate state.
- Frontend: route AI policy filters available operations; `PageContextSuggestedTool` stays within UI tool set.
- Frontend: `UIActionExecutor` returns `confirmation_required` for confirm-gated actions and `policy_blocked` for disallowed actions.
- Backend: `has_navigation_intent` requires `page_data.navigation_catalog`, ignores legacy `available_menus`, and matches scoring thresholds.
- Backend: `resolve_page_locale` prioritizes `page_data.locale` / `page_context.locale`, then inferred text, then `get_locale()`.
- Frontend: `getRuntimeThinPageContext()` and navigation tool results keep `page_data` compact while carrying `navigation_catalog` / `navigation_context` for cross-page routing.

### 7. Wrong vs Correct

#### Wrong
```ts
// Embeds heavy DOM in page_context and bypasses UI tools
const pageContext = {
  page_key: 'admin.users',
  page_data: { html: document.body.innerHTML },
};
```

#### Correct
```ts
// Keep page_context summary-first and read details via UI tools
const pageContext = getRuntimeThinPageContext();
// Later: ui_read_region / ui_get_snapshot for detailed content
```

## Prohibited Patterns
- Installed skill packs that only work after page-specific prompt or route adaptation.
- Treating `Skill.skill_md`, package `SKILL.md`, or `CapabilityDescriptor(kind="prompt_skill")` as live tool-exposure truth.
- Recursive skill escalation.
- Tool exposure without minimal-necessity filtering.
- Letting `suggested_tools`, page-local fallback builders, or capability-description text decide backend runtime tool routing.
- Page runtime hidden inside monolithic builtin executors.
- Reviving removed page registration / page operation registry flows alongside the shared UI runtime bridge.
- Duplicated rule bodies across `.trellis`, `.claude`, `.agents`, and `.cursor`.
