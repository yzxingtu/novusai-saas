# W5-PKG-04 PRD

## Goal Anchor

Define how every later W4 milestone carries forward prior must-pass scenarios, retained UI smoke, screenshot archives, and fixed bug chains so no frontend package can claim green on stale evidence.

## Baseline

- 04-27 umbrella remains `designed`.
- Successor scenario / bug ledgers and smoke-harness schema now exist as planning anchors.
- Existing frontend smoke is already split across `/ai-chat` and tenant call logs, while standalone action-log and operation-log product pages have since been retired. Carry-forward rules must not resurrect retired page smoke just to preserve an old ledger row.

## Deliverables

- carry-forward table template covering package id, touched surfaces, must-pass scenarios, must-stay-green scenarios, bug ids, screenshot manifests, and same-batch source status
- stale-evidence rejection rule for retained UI smoke
- milestone gate checklist for frontend packages
- explicit mapping from W4 packages to required browser suites and screenshot archives

## Stable Governance / Smoke Surface

- governance docs: `acceptance-matrix.md`, `smoke-scenarios.md`, `known-bug-scenarios.md`, `smoke-runs/README.md`
- current checked-in frontend smoke anchors:
  - `frontend/apps/web-antd/__tests__/e2e/ai-chat-shell-cross-surface.spec.ts`
  - `frontend/apps/web-antd/__tests__/e2e/ai-call-logs.spec.ts`
- retired standalone log product-page anchors:
  - `frontend/apps/web-antd/__tests__/e2e/ai-action-logs.spec.ts` is historical only and must not be recreated.
  - `frontend/apps/web-antd/__tests__/e2e/operation-log.spec.ts` is historical only and must not be recreated.
  - Current evidence is `backend/tests/test_admin_operation_log_routes_contract.py` and `backend/tests/migrations/test_log_product_surface_retirement_migration.py`.
- planned W4 browser suites to bind into carry-forward tables:
  - `ai-conversations.spec.ts`
  - `ai-usage-quotas.spec.ts`
  - `ai-providers-models.spec.ts`

## Verification Commands

### Governance review inputs

- `pnpm --dir frontend/apps/web-antd test:e2e -- --grep "AI Chat shell cross-surface smoke"`
- `cd backend && python -m pytest tests/test_admin_operation_log_routes_contract.py tests/migrations/test_log_product_surface_retirement_migration.py -q`
- `pnpm --dir frontend/apps/web-antd exec playwright test __tests__/e2e/ai-call-logs.spec.ts`
- `pnpm --dir frontend/apps/web-antd exec playwright test __tests__/e2e/ai-conversations.spec.ts __tests__/e2e/ai-usage-quotas.spec.ts __tests__/e2e/ai-providers-models.spec.ts`

## Screenshot / Smoke Requirements

- Every retained-surface package must link its screenshot/video/log artifact manifest inside the carry-forward table.
- A later package may only inherit green from an earlier frontend suite when the suite is re-run in the same batch or explicitly recorded as untouched and still paired to a current source PASS.
- USER-AICHAT-001, RETENTION-001, RETENTION-002, RETENTION-003, OPS-001, SEARCH-001, SEARCH-002, and SEARCH-NEG-001 must each have an explicit current-status column in the carry-forward template. RETENTION-003 and OPS-001 are now retirement-contract rows, not page-smoke rows.

## Non-Goals

- no smoke execution
- no runtime or frontend implementation
- no cleanup execution
- no replacement of 04-23 authority without explicit successor adoption

## Four-Gate Acceptance

- `structural`: carry-forward template and milestone gate checklist exist.
- `behavioral`: touched surfaces cannot inherit green after a newer upstream FAIL; screenshot and smoke artifacts are explicit, not implied.
- `smoke`: this package does not run smoke, but it defines the hard rule that retained smoke needs same-batch source PASS and archived artifacts.
- `known-bug`: bug chains remain green only when linked regression files and linked UI smoke remain green.

## Stop Conditions

- carry-forward review still depends on human memory or chat history
- screenshot archives are optional for retained-surface acceptance
- package-local green claims can ignore a newer upstream FAIL
