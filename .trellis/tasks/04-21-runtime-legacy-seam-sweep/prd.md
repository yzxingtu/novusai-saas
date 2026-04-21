# Runtime Legacy Seam Sweep

## Goal

Remove the remaining bounded legacy seams that survived the larger Phase 1 / Phase 2 mainline closeouts, without reopening compatibility layers on the live SaaS path.

## Requirements

- Remove dead page no-progress recovery hint plumbing and keep only the structured recovery subset plus diagnostics.
- Delete any unreferenced prompt-contract registration/template that still implies prompt-hint-owned page recovery.
- Freeze the page snapshot read contract to `ui_get_snapshot` and stop carrying backend-only alias surfaces that are no longer canonical.
- Delete dead frontend helper code that still performs legacy streaming content back-projection into `thinkingContent`.

## Acceptance Criteria

- `build_page_no_progress_recovery()` no longer returns or types a dead hint slot.
- No `page_flow_recovery` prompt contract registration or template remains if nothing renders it.
- Backend page-runtime definitions/tests expose only the canonical snapshot contract and do not keep `ui_read_page` / `ui_read_surface` as live-facing seams.
- Frontend `chat-input-utils` retains live mention helpers while removing the unused streaming-thinking helper and its dedicated test.
- Targeted backend/frontend lint and regression tests pass.
