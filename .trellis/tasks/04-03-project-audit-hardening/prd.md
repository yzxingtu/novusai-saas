# Project Audit Hardening

## Goal
Implement the actionable hardening items identified during the project audit so
delivery guardrails, plugin runtime behavior, duplicated API surfaces, and large
frontend detail pages become safer and easier to maintain.

## Requirements
- Align frontend CI tooling with the repository's declared package manager
  contract and run frontend unit tests in CI.
- Make backend typing enforcement incremental but real instead of purely
  informational.
- Fail closed or surface a degraded state when plugin task-definition changes
  cannot refresh the in-process scheduler.
- Add targeted backend tests for the new plugin lifecycle behavior.
- Reduce duplication between admin and tenant organization APIs without crossing
  surface boundaries.
- Reduce size and duplication in the admin and tenant agent detail pages by
  extracting shared logic and/or presentational modules that preserve existing
  behavior.
- Add targeted frontend tests for the new shared agent detail logic.

## Acceptance Criteria
- [ ] GitHub Actions uses a pnpm version compatible with the frontend workspace
      declaration.
- [ ] GitHub Actions runs frontend unit tests in addition to lint, typecheck,
      and build steps.
- [ ] Backend typing enforcement is no longer fully non-blocking at the whole
      project level.
- [ ] Plugin lifecycle paths no longer silently continue after scheduler refresh
      failures during enable/disable/uninstall task-definition sync.
- [ ] Backend tests cover the scheduler refresh failure behavior.
- [ ] Admin and tenant organization APIs share extracted helpers for repeated
      logic while preserving surface-specific behavior.
- [ ] Admin and tenant agent detail pages are split into smaller units or shared
      abstractions without introducing cross-surface imports.
- [ ] Frontend tests cover the newly extracted shared agent detail logic.

## Technical Notes
- Keep changes compatible with the current dirty worktree and avoid reverting
  unrelated local edits.
- Prefer extracting shared logic into `api/shared`, `components/`, or
  `composables/` rather than introducing cross-surface imports between admin and
  tenant business modules.
- Preserve existing request/response contracts and i18n behavior.
