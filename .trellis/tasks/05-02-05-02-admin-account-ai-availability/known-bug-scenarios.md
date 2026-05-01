# Known Bug Scenarios

## BUG-2026-05-02-AI-ACCOUNT-001

- reporter: user
- report_date: 2026-05-02
- status: fixed_with_green_test
- reproduction: use an admin/tenant account that should not be allowed to use AI, press `Ctrl+K` or click the top AI entry.
- current_wrong_behavior: the current frontend couples command bar visibility with AI chat permission, so lack of AI chat permission can hide or block the command/search panel entirely.
- expected_behavior: command/search panel still opens; menu search and navigation work; AI chat submit, agent mention, recent AI conversations, and AI panel are unavailable.
- required_evidence:
  - RED/GREEN behavioral test for `CommandBar canChat=false` opening and not emitting AI actions.
  - Frontend policy test proving `commandBarEnabled=true` while `aiChatEnabled=false`.
- evidence:
  - `frontend/apps/web-antd/src/components/business/command-bar/__tests__/CommandBar.test.ts`
  - `frontend/apps/web-antd/src/composables/__tests__/use-ai-entry-policy.test.ts`
  - `frontend/apps/web-antd/src/store/shared/__tests__/ai-panel.test.ts`

## BUG-2026-05-02-AI-ACCOUNT-002

- reporter: user
- report_date: 2026-05-02
- status: fixed_with_green_test
- reproduction: use an account whose account-level AI switch is disabled and call `/admin/ai/agent-chat/**` or `/tenant/ai/agent-chat/**` directly.
- current_wrong_behavior: no account-level `ai_enabled` persistence or hard guard exists, so RBAC-only permission can still reach AI chat services.
- expected_behavior: disabled accounts receive structured HTTP 403 before `AgentChatService`, routing, provider runtime, memory, or conversation side effects run.
- required_evidence:
  - Behavioral route contract tests for admin and tenant disabled accounts.
  - Test proving `is_super` / `is_owner` does not bypass `ai_enabled=false`.
- evidence:
  - `backend/tests/test_ai_chat_availability_guard_contract.py`
  - Covers admin super and tenant owner account-disabled guards across chat, stream, route, conversations, memory-state, compact, and timeline route families.

## BUG-2026-05-02-AI-ACCOUNT-003

- reporter: user
- report_date: 2026-05-02
- status: fixed_with_green_test
- reproduction: delegate ordinary admin/member editing to a non-super admin and try to control another account's AI switch.
- current_wrong_behavior: no separate assignable AI switch management permission exists.
- expected_behavior: ordinary edit permissions do not permit changing `ai_enabled`; dedicated `organization:manage_member_ai` or `tenant_admin:manage_ai` permission is required.
- required_evidence:
  - Behavioral tests for payloads with and without explicit `ai_enabled`.
  - UI tests or assertions proving the switch is read-only/omitted without management permission.
- evidence:
  - `backend/tests/test_ai_account_switch_permission_contract.py`
  - `backend/tests/regressions/test_bug_2026_05_02_ai_account_003_admin_org_member_update.py`
  - `frontend/apps/web-antd/src/views/admin/tenant/list/modules/__tests__/TenantAdminForm.test.ts`
  - `frontend/apps/web-antd/src/components/business/member-panel/modules/__tests__/AdminFormDrawer.test.ts`
