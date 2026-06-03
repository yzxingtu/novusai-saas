# Vben 5.6 Lint Split

- Generated at: 2026-03-26T21:20:00+08:00
- Repo root: `E:\git_clone\novusai-saas-yudi`
- Scope: split lint failures into upgrade-related vs historical debt

## Upgrade-Related

- Status: cleared
- Result: targeted lint on the files changed for the vben 5.6 upgrade now reports `0 errors`
- Verified files:
  - `apps/web-antd/build/vite-plugin-novus-plugins.ts`
  - `apps/web-antd/src/components/business/ai-slide-panel/__tests__/AIChatSlidePanel.test.ts`
  - `apps/web-antd/src/components/business/ai-slide-panel/page-operation-registry.ts`
  - `apps/web-antd/src/components/business/command-bar/__tests__/CommandBar.test.ts`
  - `apps/web-antd/src/composables/__tests__/use-detail-page-ai.test.ts`
  - `apps/web-antd/src/store/shared/__tests__/public-config.test.ts`
  - `eslint.config.mjs`
  - `vitest.config.ts`
  - `scripts/vben/sync-upstream.mjs`
  - `scripts/vben/diff-upstream.mjs`
  - `scripts/vben/verify-upgrade.mjs`
- Notes:
  - Fixed `vite-plugin-novus-plugins.ts` rule issues (`utf8`, nested ternary, non-null assertion).
  - Fixed non-null assertions in the upgrade-touched tests.
  - Added local `vue/one-component-per-file` suppression only inside the two test files that intentionally define multiple inline stub components.

## Historical Debt

- Status: still failing in full `pnpm -C frontend run lint`
- Failure mode: repo-wide formatting and style debt outside this upgrade scope
- Historical batches already cleaned in this thread:
  - `api-endpoints.json`
  - `apps/web-antd/src/layouts/admin-auth.vue`
  - `apps/web-antd/src/layouts/auth.vue`
  - `apps/web-antd/src/layouts/basic.vue`
  - `apps/web-antd/src/layouts/tenant-auth.vue`
  - `apps/web-antd/src/layouts/user-auth.vue`
  - `apps/web-antd/src/layouts/user.vue`
  - `apps/web-antd/src/views/admin/system/codegen/modules/ComponentPalette.vue`
  - `apps/web-antd/src/views/admin/system/codegen/modules/CompositeUniqueEditor.vue`
  - `apps/web-antd/src/views/admin/system/codegen/modules/CustomActionsEditor.vue`
  - `apps/web-antd/src/views/admin/system/codegen/modules/DbTableImportModal.vue`
  - `apps/web-antd/src/views/admin/system/codegen/modules/DetailFieldValue.vue`
  - `apps/web-antd/src/views/admin/system/codegen/modules/CodePreviewModal.vue`
  - `apps/web-antd/src/views/admin/system/codegen/modules/CodePreviewPanel.vue`
  - `apps/web-antd/src/api/**/*.ts`
  - `apps/web-antd/src/views/admin/tenant/plans/data.ts`
  - `apps/web-antd/src/views/admin/tenant/plans/modules/PlanForm.vue`
  - `apps/web-antd/src/views/public/platform-home/index.vue`
  - `apps/web-antd/src/views/shared/periodic-task-utils.ts`
  - `apps/web-antd/src/views/tenant/ai/action-logs/data.ts`
  - `apps/web-antd/src/views/tenant/ai/action-logs/index.vue`
  - `apps/web-antd/src/views/admin/tenant/list/modules/DomainsDnsGuideModal.vue`
  - `apps/web-antd/src/views/admin/tenant/list/modules/DomainsModal.vue`
  - `apps/web-antd/src/views/admin/tenant/list/modules/DomainsSslDrawer.vue`
  - `apps/web-antd/src/views/admin/tenant/list/modules/TenantAdminPanel.vue`
  - `apps/web-antd/src/views/admin/system/operation-logs/data.ts`
  - `apps/web-antd/src/views/admin/system/operation-logs/index.vue`
  - `apps/web-antd/src/views/admin/system/operation-logs/modules/LogDetail.vue`
- Representative areas:
  - `apps/web-antd/src/components/**`
    - broad Prettier and import-order debt outside the files already cleaned
  - `apps/web-antd/src/composables/**`
    - mixed Prettier and unicorn/perfectionist debt outside the files already cleaned
  - `apps/web-antd/src/views/**`
    - many remaining historical formatting and ordering violations outside the codegen files already cleaned
  - broad formatting warnings across existing API, component, composable, and view files that were not modified for the vben 5.6 upgrade

## Conclusion

- The vben 5.6 upgrade no longer introduces lint-blocking errors of its own.
- Remaining full-lint failure is attributable to pre-existing repository debt and should be handled as a separate cleanup track.
