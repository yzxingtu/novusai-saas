# Unify AI Admin Time Display

## Goal
Ensure the admin AI API Keys page and AI health monitor page display timestamps using the project's standard frontend time formatting patterns.

## Requirements
- Review the project frontend guidelines and existing admin page patterns for timestamp display.
- Fix `/admin/ai/api-keys` timestamp rendering if any field bypasses the shared formatting helpers.
- Fix `/admin/ai/monitor/health` timestamp rendering so it matches adjacent admin AI pages.
- Reuse shared date formatting utilities instead of adding page-local formatting logic.

## Acceptance Criteria
- [ ] Time values on `/admin/ai/api-keys` follow the same shared formatter pattern used by comparable admin list pages.
- [ ] Time values on `/admin/ai/monitor/health` follow the same shared formatter pattern used by comparable admin AI pages.
- [ ] Browser validation confirms the updated pages no longer show non-standard timestamp output.

## Technical Notes
- Frontend-only change under `frontend/apps/web-antd/src/views/admin/ai/**`.
- Prefer `formatDate` and `formatRelativeTime` from `#/utils/common`.
