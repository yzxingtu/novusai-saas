# Vben Upgrade Diff Report

- Generated at: 2026-03-26T12:48:56.724Z
- Tracking base tag: `v5.5.9`
- Target upstream tag: `v5.6.0`
- Local frontend root: `E:\git_clone\novusai-saas-yudi-vben560\frontend`
- Base snapshot: `E:\git_clone\novusai-saas-yudi-vben560\frontend\.vendor\vue-vben-admin\v5.5.9`
- Target snapshot: `E:\git_clone\novusai-saas-yudi-vben560\frontend\.vendor\vue-vben-admin\v5.6.0`

## Upstream Delta

| Area               | Changed Files |
| ------------------ | ------------: |
| always_review      |             3 |
| novus_bridge_owned |             0 |
| product_owned      |            10 |
| upstream_owned     |           597 |

### Upstream Added

- `apps/backend-mock/api/timezone/getTimezone.ts`
- `apps/backend-mock/api/timezone/getTimezoneOptions.ts`
- `apps/backend-mock/api/timezone/setTimezone.ts`
- `apps/backend-mock/utils/timezone-utils.ts`
- `apps/web-antd/src/views/_core/profile/base-setting.vue`
- `apps/web-antd/src/views/_core/profile/index.vue`
- `apps/web-antd/src/views/_core/profile/notification-setting.vue`
- `apps/web-antd/src/views/_core/profile/password-setting.vue`
- `apps/web-antd/src/views/_core/profile/security-setting.vue`
- `apps/web-antdv-next/.env`
- `apps/web-antdv-next/.env.analyze`
- `apps/web-antdv-next/.env.development`
- `apps/web-antdv-next/.env.production`
- `apps/web-antdv-next/index.html`
- `apps/web-antdv-next/package.json`
- `apps/web-antdv-next/postcss.config.mjs`
- `apps/web-antdv-next/public/favicon.ico`
- `apps/web-antdv-next/src/adapter/component/index.ts`
- `apps/web-antdv-next/src/adapter/form.ts`
- `apps/web-antdv-next/src/adapter/vxe-table.ts`
- `apps/web-antdv-next/src/api/core/auth.ts`
- `apps/web-antdv-next/src/api/core/index.ts`
- `apps/web-antdv-next/src/api/core/menu.ts`
- `apps/web-antdv-next/src/api/core/user.ts`
- `apps/web-antdv-next/src/api/index.ts`
- `apps/web-antdv-next/src/api/request.ts`
- `apps/web-antdv-next/src/app.vue`
- `apps/web-antdv-next/src/bootstrap.ts`
- `apps/web-antdv-next/src/layouts/auth.vue`
- `apps/web-antdv-next/src/layouts/basic.vue`
- `apps/web-antdv-next/src/layouts/index.ts`
- `apps/web-antdv-next/src/locales/README.md`
- `apps/web-antdv-next/src/locales/index.ts`
- `apps/web-antdv-next/src/locales/langs/en-US/demos.json`
- `apps/web-antdv-next/src/locales/langs/en-US/page.json`
- `apps/web-antdv-next/src/locales/langs/zh-CN/demos.json`
- `apps/web-antdv-next/src/locales/langs/zh-CN/page.json`
- `apps/web-antdv-next/src/main.ts`
- `apps/web-antdv-next/src/preferences.ts`
- `apps/web-antdv-next/src/router/access.ts`
- ... and 159 more

### Upstream Changed

- `.node-version`
- `.npmrc`
- `README.ja-JP.md`
- `README.md`
- `README.zh-CN.md`
- `apps/backend-mock/package.json`
- `apps/backend-mock/utils/mock-data.ts`
- `apps/web-antd/package.json`
- `apps/web-antd/src/adapter/component/index.ts`
- `apps/web-antd/src/adapter/vxe-table.ts`
- `apps/web-antd/src/layouts/auth.vue`
- `apps/web-antd/src/layouts/basic.vue`
- `apps/web-antd/src/locales/langs/en-US/demos.json`
- `apps/web-antd/src/locales/langs/en-US/page.json`
- `apps/web-antd/src/locales/langs/zh-CN/demos.json`
- `apps/web-antd/src/locales/langs/zh-CN/page.json`
- `apps/web-antd/src/router/routes/modules/vben.ts`
- `apps/web-antd/src/views/dashboard/analytics/analytics-visits-sales.vue`
- `apps/web-ele/package.json`
- `apps/web-ele/src/adapter/vxe-table.ts`
- `apps/web-ele/src/layouts/auth.vue`
- `apps/web-ele/src/layouts/basic.vue`
- `apps/web-ele/src/locales/langs/en-US/demos.json`
- `apps/web-ele/src/locales/langs/en-US/page.json`
- `apps/web-ele/src/locales/langs/zh-CN/demos.json`
- `apps/web-ele/src/locales/langs/zh-CN/page.json`
- `apps/web-ele/src/router/routes/modules/vben.ts`
- `apps/web-ele/src/views/dashboard/analytics/analytics-visits-sales.vue`
- `apps/web-naive/package.json`
- `apps/web-naive/src/adapter/vxe-table.ts`
- `apps/web-naive/src/layouts/auth.vue`
- `apps/web-naive/src/layouts/basic.vue`
- `apps/web-naive/src/locales/langs/en-US/demos.json`
- `apps/web-naive/src/locales/langs/en-US/page.json`
- `apps/web-naive/src/locales/langs/zh-CN/demos.json`
- `apps/web-naive/src/locales/langs/zh-CN/page.json`
- `apps/web-naive/src/router/routes/modules/vben.ts`
- `apps/web-naive/src/views/dashboard/analytics/analytics-visits-sales.vue`
- `cspell.json`
- `internal/lint-configs/commitlint-config/index.mjs`
- ... and 370 more

### Upstream Removed

- `vitest.workspace.ts`

## Local Divergence From Tracking Base

| Area               | Changed Files |
| ------------------ | ------------: |
| always_review      |             7 |
| novus_bridge_owned |             8 |
| product_owned      |           594 |
| upstream_owned     |           809 |

### Local Added Vs Base

- `apps/web-antd/build/vite-plugin-novus-plugins.d.ts`
- `apps/web-antd/build/vite-plugin-novus-plugins.ts`
- `apps/web-antd/dist.zip`
- `apps/web-antd/loading.html`
- `apps/web-antd/playwright_mcp_config.json`
- `apps/web-antd/src/api/admin/action-logs.ts`
- `apps/web-antd/src/api/admin/admin-user.ts`
- `apps/web-antd/src/api/admin/ai-agents.ts`
- `apps/web-antd/src/api/admin/ai-call-logs.ts`
- `apps/web-antd/src/api/admin/ai-conversations.ts`
- `apps/web-antd/src/api/admin/ai-models.ts`
- `apps/web-antd/src/api/admin/ai-providers.ts`
- `apps/web-antd/src/api/admin/ai.ts`
- `apps/web-antd/src/api/admin/analytics.ts`
- `apps/web-antd/src/api/admin/attachment.ts`
- `apps/web-antd/src/api/admin/auth.ts`
- `apps/web-antd/src/api/admin/cache.ts`
- `apps/web-antd/src/api/admin/codegen.ts`
- `apps/web-antd/src/api/admin/configs.ts`
- `apps/web-antd/src/api/admin/dashboard.ts`
- `apps/web-antd/src/api/admin/email-log.ts`
- `apps/web-antd/src/api/admin/index.ts`
- `apps/web-antd/src/api/admin/knowledge-bases.ts`
- `apps/web-antd/src/api/admin/menu.ts`
- `apps/web-antd/src/api/admin/notification-templates.ts`
- `apps/web-antd/src/api/admin/operation-log.ts`
- `apps/web-antd/src/api/admin/organization.ts`
- `apps/web-antd/src/api/admin/periodic-task.ts`
- `apps/web-antd/src/api/admin/permission.ts`
- `apps/web-antd/src/api/admin/plan.ts`
- `apps/web-antd/src/api/admin/plugin-marketplace.ts`
- `apps/web-antd/src/api/admin/plugin.ts`
- `apps/web-antd/src/api/admin/preferences.ts`
- `apps/web-antd/src/api/admin/recycle-bin.ts`
- `apps/web-antd/src/api/admin/skill-packages.ts`
- `apps/web-antd/src/api/admin/skills.ts`
- `apps/web-antd/src/api/admin/storage-migration.ts`
- `apps/web-antd/src/api/admin/system-log.ts`
- `apps/web-antd/src/api/admin/task-log.ts`
- `apps/web-antd/src/api/admin/tenant-domain.ts`
- ... and 708 more

### Local Changed Vs Base

- `.node-version`
- `.npmrc`
- `.prettierignore`
- `.stylelintignore`
- `README.ja-JP.md`
- `README.md`
- `README.zh-CN.md`
- `apps/web-antd/.env.analyze`
- `apps/web-antd/.env.development`
- `apps/web-antd/.env.production`
- `apps/web-antd/index.html`
- `apps/web-antd/package.json`
- `apps/web-antd/src/api/index.ts`
- `apps/web-antd/src/bootstrap.ts`
- `apps/web-antd/src/layouts/auth.vue`
- `apps/web-antd/src/layouts/basic.vue`
- `apps/web-antd/src/layouts/index.ts`
- `apps/web-antd/src/locales/index.ts`
- `apps/web-antd/src/locales/langs/en-US/page.json`
- `apps/web-antd/src/locales/langs/zh-CN/page.json`
- `apps/web-antd/src/main.ts`
- `apps/web-antd/src/preferences.ts`
- `apps/web-antd/src/router/access.ts`
- `apps/web-antd/src/router/guard.ts`
- `apps/web-antd/src/router/index.ts`
- `apps/web-antd/src/router/routes/core.ts`
- `apps/web-antd/src/router/routes/index.ts`
- `apps/web-antd/src/store/index.ts`
- `apps/web-antd/tsconfig.json`
- `apps/web-antd/tsconfig.node.json`
- `apps/web-antd/vite.config.mts`
- `cspell.json`
- `eslint.config.mjs`
- `internal/lint-configs/commitlint-config/index.mjs`
- `internal/lint-configs/eslint-config/src/configs/command.ts`
- `internal/lint-configs/eslint-config/src/configs/comments.ts`
- `internal/lint-configs/eslint-config/src/configs/import.ts`
- `internal/lint-configs/eslint-config/src/configs/node.ts`
- `internal/lint-configs/eslint-config/src/configs/perfectionist.ts`
- `internal/lint-configs/eslint-config/src/configs/test.ts`
- ... and 433 more

### Local Missing Vs Base

- `apps/backend-mock/.env`
- `apps/backend-mock/README.md`
- `apps/backend-mock/api/auth/codes.ts`
- `apps/backend-mock/api/auth/login.post.ts`
- `apps/backend-mock/api/auth/logout.post.ts`
- `apps/backend-mock/api/auth/refresh.post.ts`
- `apps/backend-mock/api/demo/bigint.ts`
- `apps/backend-mock/api/menu/all.ts`
- `apps/backend-mock/api/status.ts`
- `apps/backend-mock/api/system/dept/.post.ts`
- `apps/backend-mock/api/system/dept/[id].delete.ts`
- `apps/backend-mock/api/system/dept/[id].put.ts`
- `apps/backend-mock/api/system/dept/list.ts`
- `apps/backend-mock/api/system/menu/list.ts`
- `apps/backend-mock/api/system/menu/name-exists.ts`
- `apps/backend-mock/api/system/menu/path-exists.ts`
- `apps/backend-mock/api/system/role/list.ts`
- `apps/backend-mock/api/table/list.ts`
- `apps/backend-mock/api/test.get.ts`
- `apps/backend-mock/api/test.post.ts`
- `apps/backend-mock/api/upload.ts`
- `apps/backend-mock/api/user/info.ts`
- `apps/backend-mock/error.ts`
- `apps/backend-mock/middleware/1.api.ts`
- `apps/backend-mock/nitro.config.ts`
- `apps/backend-mock/package.json`
- `apps/backend-mock/routes/[...].ts`
- `apps/backend-mock/tsconfig.build.json`
- `apps/backend-mock/tsconfig.json`
- `apps/backend-mock/utils/cookie-utils.ts`
- `apps/backend-mock/utils/jwt-utils.ts`
- `apps/backend-mock/utils/mock-data.ts`
- `apps/backend-mock/utils/response.ts`
- `apps/web-antd/.env`
- `apps/web-antd/src/adapter/component/index.ts`
- `apps/web-antd/src/adapter/form.ts`
- `apps/web-antd/src/adapter/vxe-table.ts`
- `apps/web-antd/src/api/core/auth.ts`
- `apps/web-antd/src/api/core/index.ts`
- `apps/web-antd/src/api/core/menu.ts`
- ... and 157 more

## Local Divergence From Target

| Area               | Changed Files |
| ------------------ | ------------: |
| always_review      |             7 |
| novus_bridge_owned |             8 |
| product_owned      |           599 |
| upstream_owned     |           768 |

### Local Added Vs Target

- `apps/web-antd/build/vite-plugin-novus-plugins.d.ts`
- `apps/web-antd/build/vite-plugin-novus-plugins.ts`
- `apps/web-antd/dist.zip`
- `apps/web-antd/loading.html`
- `apps/web-antd/playwright_mcp_config.json`
- `apps/web-antd/src/api/admin/action-logs.ts`
- `apps/web-antd/src/api/admin/admin-user.ts`
- `apps/web-antd/src/api/admin/ai-agents.ts`
- `apps/web-antd/src/api/admin/ai-call-logs.ts`
- `apps/web-antd/src/api/admin/ai-conversations.ts`
- `apps/web-antd/src/api/admin/ai-models.ts`
- `apps/web-antd/src/api/admin/ai-providers.ts`
- `apps/web-antd/src/api/admin/ai.ts`
- `apps/web-antd/src/api/admin/analytics.ts`
- `apps/web-antd/src/api/admin/attachment.ts`
- `apps/web-antd/src/api/admin/auth.ts`
- `apps/web-antd/src/api/admin/cache.ts`
- `apps/web-antd/src/api/admin/codegen.ts`
- `apps/web-antd/src/api/admin/configs.ts`
- `apps/web-antd/src/api/admin/dashboard.ts`
- `apps/web-antd/src/api/admin/email-log.ts`
- `apps/web-antd/src/api/admin/index.ts`
- `apps/web-antd/src/api/admin/knowledge-bases.ts`
- `apps/web-antd/src/api/admin/menu.ts`
- `apps/web-antd/src/api/admin/notification-templates.ts`
- `apps/web-antd/src/api/admin/operation-log.ts`
- `apps/web-antd/src/api/admin/organization.ts`
- `apps/web-antd/src/api/admin/periodic-task.ts`
- `apps/web-antd/src/api/admin/permission.ts`
- `apps/web-antd/src/api/admin/plan.ts`
- `apps/web-antd/src/api/admin/plugin-marketplace.ts`
- `apps/web-antd/src/api/admin/plugin.ts`
- `apps/web-antd/src/api/admin/preferences.ts`
- `apps/web-antd/src/api/admin/recycle-bin.ts`
- `apps/web-antd/src/api/admin/skill-packages.ts`
- `apps/web-antd/src/api/admin/skills.ts`
- `apps/web-antd/src/api/admin/storage-migration.ts`
- `apps/web-antd/src/api/admin/system-log.ts`
- `apps/web-antd/src/api/admin/task-log.ts`
- `apps/web-antd/src/api/admin/tenant-domain.ts`
- ... and 676 more

### Local Changed Vs Target

- `.prettierignore`
- `.stylelintignore`
- `apps/web-antd/.env.analyze`
- `apps/web-antd/.env.development`
- `apps/web-antd/.env.production`
- `apps/web-antd/index.html`
- `apps/web-antd/package.json`
- `apps/web-antd/src/api/index.ts`
- `apps/web-antd/src/bootstrap.ts`
- `apps/web-antd/src/layouts/auth.vue`
- `apps/web-antd/src/layouts/basic.vue`
- `apps/web-antd/src/layouts/index.ts`
- `apps/web-antd/src/locales/index.ts`
- `apps/web-antd/src/locales/langs/en-US/page.json`
- `apps/web-antd/src/locales/langs/zh-CN/page.json`
- `apps/web-antd/src/main.ts`
- `apps/web-antd/src/preferences.ts`
- `apps/web-antd/src/router/access.ts`
- `apps/web-antd/src/router/guard.ts`
- `apps/web-antd/src/router/index.ts`
- `apps/web-antd/src/router/routes/core.ts`
- `apps/web-antd/src/router/routes/index.ts`
- `apps/web-antd/src/store/index.ts`
- `apps/web-antd/tsconfig.json`
- `apps/web-antd/tsconfig.node.json`
- `apps/web-antd/vite.config.mts`
- `cspell.json`
- `eslint.config.mjs`
- `internal/lint-configs/commitlint-config/index.mjs`
- `internal/lint-configs/commitlint-config/package.json`
- `internal/lint-configs/eslint-config/package.json`
- `internal/lint-configs/eslint-config/src/configs/comments.ts`
- `internal/lint-configs/eslint-config/src/configs/ignores.ts`
- `internal/lint-configs/eslint-config/src/configs/import.ts`
- `internal/lint-configs/eslint-config/src/configs/index.ts`
- `internal/lint-configs/eslint-config/src/configs/jsonc.ts`
- `internal/lint-configs/eslint-config/src/configs/node.ts`
- `internal/lint-configs/eslint-config/src/configs/test.ts`
- `internal/lint-configs/eslint-config/src/configs/vue.ts`
- `internal/lint-configs/eslint-config/src/custom-config.ts`
- ... and 263 more

### Local Missing Vs Target

- `apps/backend-mock/.env`
- `apps/backend-mock/README.md`
- `apps/backend-mock/api/auth/codes.ts`
- `apps/backend-mock/api/auth/login.post.ts`
- `apps/backend-mock/api/auth/logout.post.ts`
- `apps/backend-mock/api/auth/refresh.post.ts`
- `apps/backend-mock/api/demo/bigint.ts`
- `apps/backend-mock/api/menu/all.ts`
- `apps/backend-mock/api/status.ts`
- `apps/backend-mock/api/system/dept/.post.ts`
- `apps/backend-mock/api/system/dept/[id].delete.ts`
- `apps/backend-mock/api/system/dept/[id].put.ts`
- `apps/backend-mock/api/system/dept/list.ts`
- `apps/backend-mock/api/system/menu/list.ts`
- `apps/backend-mock/api/system/menu/name-exists.ts`
- `apps/backend-mock/api/system/menu/path-exists.ts`
- `apps/backend-mock/api/system/role/list.ts`
- `apps/backend-mock/api/table/list.ts`
- `apps/backend-mock/api/test.get.ts`
- `apps/backend-mock/api/test.post.ts`
- `apps/backend-mock/api/timezone/getTimezone.ts`
- `apps/backend-mock/api/timezone/getTimezoneOptions.ts`
- `apps/backend-mock/api/timezone/setTimezone.ts`
- `apps/backend-mock/api/upload.ts`
- `apps/backend-mock/api/user/info.ts`
- `apps/backend-mock/error.ts`
- `apps/backend-mock/middleware/1.api.ts`
- `apps/backend-mock/nitro.config.ts`
- `apps/backend-mock/package.json`
- `apps/backend-mock/routes/[...].ts`
- `apps/backend-mock/tsconfig.build.json`
- `apps/backend-mock/tsconfig.json`
- `apps/backend-mock/utils/cookie-utils.ts`
- `apps/backend-mock/utils/jwt-utils.ts`
- `apps/backend-mock/utils/mock-data.ts`
- `apps/backend-mock/utils/response.ts`
- `apps/backend-mock/utils/timezone-utils.ts`
- `apps/web-antd/.env`
- `apps/web-antd/src/adapter/component/index.ts`
- `apps/web-antd/src/adapter/form.ts`
- ... and 323 more

## P0 Focus Paths

- `package.json`: upstream_changed=true, local_diverges_from_target=true
- `pnpm-workspace.yaml`: upstream_changed=true, local_diverges_from_target=true
- `pnpm-lock.yaml`: upstream_changed=true, local_diverges_from_target=true
- `apps/web-antd/package.json`: upstream_changed=true, local_diverges_from_target=true
- `apps/web-antd/vite.config.mts`: upstream_changed=false, local_diverges_from_target=true
- `apps/web-antd/build/vite-plugin-novus-plugins.ts`: upstream_changed=false, local_diverges_from_target=true
- `apps/web-antd/src/utils/plugin-loader.ts`: upstream_changed=false, local_diverges_from_target=true
- `apps/web-antd/src/utils/plugin-shared.ts`: upstream_changed=false, local_diverges_from_target=true
- `apps/web-antd/src/composables/use-plugin-frontend-init.ts`: upstream_changed=false, local_diverges_from_target=true
