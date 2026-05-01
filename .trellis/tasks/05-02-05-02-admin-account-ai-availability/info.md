# Implementation Notes

## Data Flow

`Admin/TenantAdmin.ai_enabled` is persisted at the account level and returned through auth `/me`, management list/detail serializers, and identity detail. The frontend stores it in user info and combines it with RBAC and route policy inside `useAIEntryPolicy`.

For tenant admins, backend AI chat access additionally checks the tenant plan feature `features.ai_enabled` through the existing quota/plan feature service path. The platform surface has no tenant-plan dimension.

## Permission Model

The account AI switch is not modeled as a normal RBAC permission removal. RBAC still controls resources/actions, while `ai_enabled` is a hard account gate. Management of the switch is an assignable operation permission:

- `organization:manage_member_ai` under admin organization.
- `organization:manage_member_ai` under tenant organization.
- `tenant_admin:manage_ai` under platform tenant admin.

Routes keep their existing create/update decorators. They add a second check only when the request explicitly contains `ai_enabled`. This preserves normal editing for delegated admins while preventing stealth AI switch changes.

## Backend Guard

The guard must execute before `AgentChatService`, `handle_route`, conversation read-models, provider runtime, tool replay, or memory side effects. Account-disabled and tenant-plan-disabled responses use stable `reason` values in the public payload so the frontend can refresh `/me` and switch to disabled UI state.

## Frontend Policy

`commandBarEnabled` means the command/search shell can open. `aiChatEnabled` means AI chat may be used. `aiEnabled` remains a compatibility alias for `aiChatEnabled`.

When `aiChatEnabled=false`, `CommandBar` must not call AI APIs, emit AI submit events, or open `AIChatSlidePanel`. It should remain a command search surface and show only a short disabled hint when the user tries to submit plain AI text.

## Testing Discipline

This task touches AI dialogue live paths, so testing must satisfy the repo's AI runtime testing discipline. Structural tests are not enough. Behavioral tests must prove observable denial and no downstream AI service call. Smoke must prove real browser entry behavior for disabled and enabled accounts.
