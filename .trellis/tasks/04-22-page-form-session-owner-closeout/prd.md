# Remove page_key Form-Session Recovery From Live Page Context

## Goal

Finish the page-session identity cleanup by removing `page_key`-based form
session recovery from live frontend runtime snapshot and form action
resolution.

## Requirements

- Live runtime page context must derive active form state from explicit surface
  or form-session identity only.
- Runtime form actions must not recover a target form by `page_key` when no
  explicit `form_session_id` or surface-owned mapping is available.
- The page workflow state owner must not receive `active_form_summary` sourced
  from `page_key` alias recovery.

## Acceptance Criteria

- `runtime-bridge-snapshot.ts` no longer falls back through page-key session
  lookup or legacy `getActiveSession(pageKey)` paths when resolving the active
  form session.
- `runtime-bridge-form-actions.ts` resolves form state/actions from explicit
  form-session or surface ownership only.
- Regression coverage proves stale page-key mappings cannot reintroduce active
  form state into thin page context after the explicit live owner is absent.
