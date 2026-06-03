# Work Package F Compatibility And Testing Discipline Audit

Date: 2026-05-10
Branch: `main`

## Scope

This note records the Work Package F rescan for compatibility keywords, retired
online-search/current-page surfaces, selected skill aliases, `tenant_id` style
aliases, `items` fallback patterns, and changed-test discipline.

The scan treats keywords as triage signals. Normal business fallback/failover,
i18n/display fallback, OpenAI-compatible provider support, browser/framework
compatibility, plugin compatibility metadata, and protocol-safe provider
fallback are not removal targets.

## Commands Run

```powershell
python .\.trellis\scripts\get_context.py
rg -l -i "compat|compatibility|compatible|legacy|fallback|shim|alias|deprecated|backward|旧系统|兼容|旧版|补丁" -g "*.py" -g "*.ts" -g "*.tsx" -g "*.vue" -g "*.json" -g "*.md" -g "*.yml" -g "*.yaml" -g "!frontend/**/node_modules/**" -g "!frontend/**/dist/**" -g "!backend/.venv/**" -g "!**/__pycache__/**" .
rg -n "联网搜索|在线搜索|网页搜索|web_search|online_search|web_research|fetch_url|SearchProvider|WebResearch|WebSearch|native_web_search|hosted_web_search" backend/app frontend/apps/web-antd/src ops docs .trellis -g "*.py" -g "*.ts" -g "*.vue" -g "*.json" -g "*.md"
rg -n "mentions_weather|_WEATHER_TERMS|weather|get_current_weather|get_weather_forecast|weather_query|weather_tools|天气|forecast" backend/app/ai backend/app/services/ai -g "*.py"
rg -n "\b(tenant_id|assigned_tenant_ids|owner_tenant_id)\b" backend/app/schemas/ai backend/app/services/ai backend/tests/services -g "*.py"
rg -n -i "items fallback|items_fallback|fallback.*items|items.*fallback|legacy.*\bitems\b|\bitems\b.*legacy" backend frontend .trellis ops docs -g "*.py" -g "*.ts" -g "*.vue" -g "*.json" -g "*.md"
rg -n "selected_skill_names|selectedSkillNames" backend/app/api backend/app/schemas frontend/apps/web-antd/src/components/business/ai-chat-panel frontend/apps/web-antd/src/api -g "*.py" -g "*.ts" -g "*.vue"
rg -n -i "patch|hotfix|workaround|temporary|临时|补丁|兼容.*临时|TODO.*compat|TODO.*legacy" backend/app frontend/apps/web-antd/src backend/tests frontend/apps/web-antd/src ops docs .trellis -g "*.py" -g "*.ts" -g "*.vue" -g "*.md" -g "*.json"
```

Changed-test discipline checks:

```powershell
$files = @((git diff --name-only --diff-filter=ACMRTUXB) + (git ls-files --others --exclude-standard)) | Where-Object { $_ -match '(^|/)(tests|__tests__)/|\.test\.|\.spec\.' -and $_ -match '\.(py|ts|tsx|vue)$' } | Sort-Object -Unique; foreach ($f in $files) { $has = if (Select-String -Path $f -Pattern 'Test type:' -Quiet) { 'yes' } else { 'NO' }; "${has}`t$f" }
$files = @((git diff --name-only --diff-filter=ACMRTUXB) + (git ls-files --others --exclude-standard)) | Where-Object { $_ -match '(^|/)(tests|__tests__)/|\.test\.|\.spec\.' -and $_ -match '\.(py|ts|tsx|vue)$' } | Sort-Object -Unique; foreach ($f in $files) { Select-String -Path $f -Pattern 'assert\s+.+\s+is\s+not\s+None|assert\s+len\(.+\)\s*>\s*0|assert\s+.+\.called\b|assert\s+True\b|expect\(.+\)\.toBeTruthy\(\)|expect\(.+\)\.toBeDefined\(\)|expect\(.+\)\.toBeGreaterThan\(0\)' | ForEach-Object { "$($f):$($_.LineNumber):$($_.Line.Trim())" } }
```

## Classification

### Real Issues Found

No confirmed low-conflict live compatibility surface was found in the current
working tree during this pass. I did not edit business code because the
remaining hits are either explicit denylist/negative evidence or current
business contracts that require coordinated migration if they ever change.

### Retired Online Search

Remaining `web_search`, `fetch_url`, `web_research`, `online_search`,
`hosted_web_search`, `native_web_search`, and `联网搜索` hits are limited to:

- Backend denylist/guard/filter paths:
  `invalid_ai_runtime_input.py`, `retired_skill_guard.py`,
  `retired_skill_catalog_filters.py`, skill package import/export checks, and
  plugin lifecycle sync guards.
- Provider defensive checks and smoke evidence failure checks:
  OpenAI-compatible response parsers and
  `RuntimeRealDialogueSmokeService`.
- Frontend diagnostic filtering and negative tests:
  `ai-runtime-diagnostics.ts`, `ChatMessageDiagnostics.test.ts`, and
  `MonitoringConversationDiagnosticsCard.turn-flow.test.ts`.
- Locale rejection copy and Trellis/spec audit notes.

These are rejection, sanitization, or historical diagnostic references. They do
not advertise retired search as a live capability.

### Weather

The targeted main-runtime weather scan returned no hits under
`backend/app/ai` or `backend/app/services/ai`. Weather references elsewhere are
plugin-owned or ordinary product copy, not core runtime hardcoding.

### Selected Skill Names

Public backend request schemas do not expose `selected_skill_names`; backend
schema hits are monitoring/read-model diagnostics. Frontend request type
`AgentChatRequestBody` also omits `selected_skill_names`. Remaining frontend
hits are diagnostic display/merge paths, SSE turn metadata, or tests asserting
request bodies do not carry selected skills.

### `tenant_id` / `assigned_tenant_ids` Aliases

Knowledge-base admin write aliases are rejected:

- `backend/app/schemas/ai/knowledge_base.py` rejects `tenant_id` and
  `assigned_tenant_ids`.
- `backend/app/services/ai/knowledge_base_command_service.py` rejects both
  aliases before command execution.
- `backend/tests/services/test_knowledge_base_service.py` covers schema and
  service rejection.

`assigned_tenant_ids` remains a current public field for periodic-task,
agent/plugin assignment read models and frontend form state. It is not the same
retired KB alias and should not be removed in this package.

### `items` Fallback

Current hits are legal:

- `frontend/.../useSystemLogs.ts` builds display rows from raw log lines only
  when structured log `items` are absent.
- `conversation_read_model_service.py` strips legacy turn projection fields
  while building message items.
- OpenAI-compatible capability fallback is protocol-safe provider behavior, not
  an old live entrypoint.

### Patch / Temporary / Compatibility Noise

Most raw hits are historical docs, normal PATCH HTTP method usage, codegen
update-patch object names, plugin dispatcher terminology, upload temporary file
cleanup, and normal frontend state patch helpers. No live old-system shim was
confirmed in changed code.

## Changed-Test Discipline

All currently changed tracked and untracked test files have `Test type:`
classification:

- `backend/tests/ai/test_gateway_failover_requirements.py`
- `backend/tests/migrations/test_task_definition_entitlement_migration.py`
- `backend/tests/migrations/test_task_run_dispatch_truth_migration.py`
- `backend/tests/models/test_task_scheduling_foundation_models.py`
- `backend/tests/services/test_knowledge_base_service.py`
- `backend/tests/services/test_model_service.py`
- `backend/tests/services/test_notification_service.py`
- `backend/tests/services/test_runtime_cli_bridge.py`
- `backend/tests/services/test_task_definition_service.py`
- `backend/tests/services/test_task_log_query_service.py`
- `backend/tests/services/test_task_manager_service.py`
- `backend/tests/services/test_task_tenant_eligibility_service.py`
- `backend/tests/tasks/test_ai_health_check.py`
- `backend/tests/tasks/test_base_task_run_reliability.py`
- `backend/tests/tasks/test_task_scheduling_wrappers.py`
- `backend/tests/test_admin_periodic_task_routes_contract.py`
- `backend/tests/test_ai_real_dialogue_smoke_service.py`
- `backend/tests/test_production_acceptance_probe.py`
- `frontend/apps/web-antd/__tests__/e2e/admin-ai-health-monitor.spec.ts`
- `frontend/apps/web-antd/src/api/admin/__tests__/notification-templates.test.ts`
- `frontend/apps/web-antd/src/api/admin/__tests__/periodic-task-bindings.test.ts`

The weak-assertion scan returned no hits for the forbidden changed-test
patterns checked above.

Smoke-adjacent caveat: `backend/tests/test_ai_real_dialogue_smoke_service.py`
mocks `AgentChatService` and call-log lookup to test smoke-service validation
and report mapping. That is acceptable as behavioral service testing, but it is
not real-dialogue smoke evidence and must not be used to claim production smoke
green.

## Parent Release Checklist

- Compatibility cleanup: no confirmed live old search/current-page/alias
  compatibility surface found by this pass.
- Test discipline: changed tests are classified; no forbidden weak assertion
  pattern found in changed tests.
- AI dialogue acceptance: not enough to publish on AI dialogue grounds until
  archived real-provider or approved replay smoke evidence exists for the final
  runtime/deploy commit.
- External release gates still required: production credentials, capacity/load,
  DAST/security review, backup restore, operator signoff, and production smoke
  artifact review.
