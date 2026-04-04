# Implementation Notes

## Boundary

This workstream owns tenant-side org-node permission assignment parity:

- tenant org node schema/model/service/API behavior
- tenant-side permission preview and selection UI
- shared organization helper contracts used by both backend and frontend

It must preserve tenant-only scope boundaries and avoid leaking platform-only
permissions into tenant assignment flows.

## Key Risks

- Backend saves permission ids but frontend still renders old org-tree shapes.
- Shared helper payload shapes drift between admin and tenant usage.
- Permission preview counts look right while actual save/update payloads are
  incomplete.
