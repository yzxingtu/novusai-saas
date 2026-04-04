# Trellis Governance Cleanup

## Goal

Make Trellis truly path-driven by removing phase-era task metadata, retired lifecycle commands, auto-commit behavior, and duplicated heavy entrypoint guidance.

## Requirements

- Remove `current_phase` and `next_action` from active task schema and task-management logic.
- Remove `finish` and `create-pr` from task lifecycle commands.
- Delete `.trellis/scripts/common/phase.py` and callers.
- Remove archive/session auto-commit behavior.
- Remove Ralph Loop markers and thin `.claude` / `.agents` entrypoints back to `.trellis` truth.
- Migrate active task metadata to the new minimal schema.

## Ownership

- Allowed files:
  - `.trellis/*`
  - `.claude/*`
  - `.agents/*`
- Do not edit backend runtime code or tests outside Trellis smoke coverage.

## Acceptance

- Active tasks no longer carry phase-era fields.
- `archive` no longer commits.
- `.claude`, `.agents`, and `.trellis` no longer document retired behaviors.
