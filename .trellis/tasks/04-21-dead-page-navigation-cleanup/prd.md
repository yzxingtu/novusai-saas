# Retire Dead Page-Navigation Helper And Stale Fallback Docs

## Goal
Delete the unreferenced `frontend/apps/web-antd/src/utils/page-navigation.ts`
helper and any stale tests/docs that still treat its synthetic
`page_context` fallback assembly as part of the live runtime path.

## Requirements
- Confirm the helper has no production imports or runtime callers.
- Remove the dead helper and any isolated tests that only exercise that dead
  path.
- Keep live page-context ownership centered on
  `components/business/ai-runtime/runtime-bridge-snapshot.ts` and the shared
  runtime bridge package.
- Update canonical Trellis docs so future work does not reclassify the deleted
  helper as a live boundary.

## Acceptance Criteria
- [ ] `frontend/apps/web-antd/src/utils/page-navigation.ts` is removed or
      reduced to an explicit non-live stub with no synthetic `page_context`
      assembly.
- [ ] Dead tests or fixtures tied only to that helper are removed or replaced
      with coverage of the actual live runtime owner chain.
- [ ] Canonical AI runtime docs no longer describe `page-navigation.ts` as a
      live runtime/page-context owner.
- [ ] Validation proves no production frontend import path still depends on the
      helper.
