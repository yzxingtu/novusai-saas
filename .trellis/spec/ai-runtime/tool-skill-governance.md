# Tool And Skill Governance

## Scenario: Page Runtime Tool + Skill Governance (Thin `page_context`, Shared UI Runtime Bridge)

### 1. Scope / Trigger
- Route skills and tools for AI runtime turns that may invoke UI/page tools.
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

`page_context.page_data` is an optional backend-side extension used for navigation and locale heuristics.

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
      "available_menus": [
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
- Candidate tool and skill sets are capped per turn; avoid exposing whole families for convenience.
- Overlapping skills resolve by scope, not by stacking.
- Page runtime tools stay separate from generic tool families.
- Web-search orchestration stays separate from generic provider chat logic.

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
- `page_context.page_data` is optional and backend-only; it must remain summary-first and is used for navigation/locale semantics.

#### 3.4 Summary-First Constraint
- `getRuntimeThinPageContext()` always uses `compact` snapshots; only summary fields flow into `page_context`.
- Heavy UI content must be retrieved via `ui_get_snapshot` (full), `ui_read_region`, or `ui_read_table`.
- `page_context` should only carry active form summary, surface stack, suggested tools, and `ui_epoch`.

#### 3.5 Read/Write Separation and Consent
- Every page tool must declare `PageOperation.readonly`.
- Read tools: `ui_get_snapshot`, `ui_list_interactables`, `ui_read_region`, `ui_read_table`, `ui_get_form_state`.
- Write tools: `ui_click`, `ui_open_surface`, `ui_set_field`, `ui_fill_form`, `ui_submit_form`.
- `serializeAvailableOperations` filters operations via route AI policy and `filterPageOperationsByPolicy`; `PageContextSuggestedTool` is limited to the UI tool set.
- `security-policy` enforces `data-ai*` directives and route policy; `evaluateAIActionSecurity` blocks and requires confirmation for dangerous action kinds; `submitRuntimeForm` enforces `submit_policy === 'confirm'`.

#### 3.6 Budget Governance
- Backend: `validate_page_context_size` serializes the payload and enforces `ai_page_context_max_bytes` (default 8192, min 1). Oversized payload raises `ValidationException` with message key `agent_chat.error.page_context_too_large` and `current/limit` interpolation.
- Frontend: `UISnapshotGenerator` budgets compact to 10 KB and full to 50 KB, with compact node limit 160 and truncation rules; DOM fallback scanning uses `maxDepth=6`, `maxNodes=160`; `listRuntimeInteractables` returns up to 200 items; `surface_stack` is capped at 12, form sessions at 8, required fields at 32.

#### 3.7 Navigation Semantics Alignment
- Backend `has_navigation_intent` requires navigation action terms and a semantic match against `page_context.page_data.available_menus`.
- `available_menus` entries should include title/path/page_key plus optional description/category/keywords/capabilities/breadcrumb to enable scoring.
- Locale resolution checks `page_data.locale` or `page_context.locale`, then infers from `page_title`, `entity_description`, and breadcrumbs, finally falling back to `get_locale()` or `"zh_CN"`.

#### 3.8 Transitional Boundaries (2026-04)
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
- Frontend: `getRuntimeThinPageContext()` uses `compact` snapshot and excludes `[data-ai-panel]` / `data-ai="off"` subtrees.
- Frontend: `UISnapshotGenerator` truncates to compact/full budgets and enforces node limits.
- Frontend: `PageOperation.readonly` mapping matches UI tool behavior; read tools never mutate state.
- Frontend: route AI policy filters available operations; `PageContextSuggestedTool` stays within UI tool set.
- Frontend: `UIActionExecutor` returns `confirmation_required` for confirm-gated actions and `policy_blocked` for disallowed actions.
- Backend: `has_navigation_intent` requires `page_data.available_menus` and matches scoring thresholds.
- Backend: `resolve_page_locale` prioritizes `page_data.locale` / `page_context.locale`, then inferred text, then `get_locale()`.

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
- Recursive skill escalation.
- Tool exposure without minimal-necessity filtering.
- Page runtime hidden inside monolithic builtin executors.
- Reviving removed page registration / page operation registry flows alongside the shared UI runtime bridge.
- Duplicated rule bodies across `.trellis`, `.claude`, `.agents`, and `.cursor`.
