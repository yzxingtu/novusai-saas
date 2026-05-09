# W5-PKG-04 Info

## Owner Boundary

- package owner: acceptance governance
- scope owner: carry-forward tables and stale-evidence rejection
- excluded owners: runtime implementation, frontend code implementation, smoke execution

## Carry-Forward Template Must Include

- package id
- touched stable routes / components / import surfaces
- must-pass scenario ids for this package
- must-stay-green carried-forward scenario ids from prior packages
- linked bug ids and regression files
- linked screenshot/video/log manifest paths
- same-batch source status and retained status
- explicit reviewer sign-off fields for backend / qa / frontend owner

## Frontend Suite Mapping To Preserve

- `USER-AICHAT-001` -> `frontend/apps/web-antd/__tests__/e2e/ai-chat-shell-cross-surface.spec.ts` plus `/ai-chat` artifacts
- `RETENTION-001` -> `frontend/apps/web-antd/__tests__/e2e/ai-conversations.spec.ts`
- `RETENTION-002` -> `frontend/apps/web-antd/__tests__/e2e/ai-call-logs.spec.ts` + `ai-usage-quotas.spec.ts`
- `RETENTION-003` -> retired standalone tenant AI action-log page; do not recreate `frontend/apps/web-antd/__tests__/e2e/ai-action-logs.spec.ts`. Current gate: `backend/tests/test_admin_operation_log_routes_contract.py`.
- `OPS-001` -> retired standalone operation-log pages; do not recreate `frontend/apps/web-antd/__tests__/e2e/operation-log.spec.ts`. Current gate: `backend/tests/test_admin_operation_log_routes_contract.py` plus `backend/tests/migrations/test_log_product_surface_retirement_migration.py`.
- `SEARCH-001` / `SEARCH-002` / `SEARCH-NEG-001` -> `frontend/apps/web-antd/__tests__/e2e/ai-providers-models.spec.ts`

## Rejection Rules

1. A retained-surface package may not inherit green after a newer source FAIL in the same family.
2. Screenshot-only evidence is insufficient without the linked checked-in Playwright suite.
3. A bug may not remain green if its linked UI smoke or regression file is stale or missing.
4. If a package touches one shared surface family, all previously green suites for that family must be evaluated in the carry-forward table.

## Dependency / Handoff Notes

- **qa** must own the smoke-suite manifest and report exact rerun status per scenario family.
- **frontend owner** must list every touched stable route/component/import surface instead of using vague labels like "chat" or "logs".
- **backend owner** must confirm same-batch source PASS status for retained-surface packages before any retained green is accepted.

## Suggested Use Order

1. update scenario/bug ledgers
2. freeze smoke artifact schema
3. fill carry-forward table for each W4 package
4. review stale-evidence rejection before any milestone closeout

## Not Authorized

- no package-status promotion by chat summary only
- no omission of screenshots for retained-surface packages
- no bug closure without linked regression + smoke proof
