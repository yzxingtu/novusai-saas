# 执行信息

## 执行模式

- 这是一个 `deep` 路径 umbrella task。
- 采用六个 worker 并行审计和并行实施。
- 主代理负责：
  - 冻结边界
  - 编写 umbrella control plane
  - 分发任务
  - 审核并接线
  - 统一验证
  - 回填 `.trellis`
- `.trellis/tasks/04-10-non-ai-governance-refactor/**` 与 `.trellis/spec/**`
  属于 umbrella control-plane 写集，不挂到任何业务 workstream；只允许主代理
  或专门的 docs worker 更新。

## 并行规则

- 各 worker 只能写 ownership matrix 中明确分配的文件。
- 不允许在他人 owned file 中顺手改“相邻逻辑”。
- 所有跨工作流 contract 只能通过 facade 或主代理冻结的模块导出。
- AI 相关代码只允许保留薄兼容入口，不允许顺手重构 AI 内核。
- `.trellis` task/spec backfill 视为独立写集；业务 worker 不得把 task/spec
  更新塞进自己的业务写集里一并处理。

## 目录与兼容策略

- Python 大文件默认拆为包目录 + facade 文件。
- 治理类大文件优先采用 `facade + mixin/parts`：
  facade 负责兼容导出/接线，mixin/parts 负责稳定职责域实现。
- Vue/TS 大文件默认拆为 page shell / composable / section component /
  helper module。
- facade 默认保留原导入路径、原 controller/service 名称、原 CLI 命令组
  名称，减少调用方回归风险。

## `.trellis` 回填范围

- 更新：
  - `.trellis/spec/backend/index.md`
  - `.trellis/spec/backend/quality-guidelines.md`
  - `.trellis/spec/frontend/index.md`
  - `.trellis/spec/frontend/quality-guidelines.md`
  - `.trellis/spec/guides/code-reuse-thinking-guide.md`
  - `.trellis/spec/guides/cross-layer-thinking-guide.md`
  - `.trellis/spec/guides/plugin-runtime-playbook.md`
  - `.trellis/spec/guides/repo-stabilization-workstreams.md`
- 回填重点：
  - controller 禁止直查库
  - facade + package 拆分模式
  - 超大页面/组件的拆分模式
  - 插件平台与 Codegen 的推荐目录结构

## 风险

- 当前工作树已有大量 AI 相关未提交改动，非 AI 重构必须严格避开这些已有
  改动的写集。
- `backend/app/cli.py` 是混合文件，非 AI 部分拆出时必须保持 AI 子命令兼容。
- `.trellis/` 更新必须和实际落地结果同批提交；不允许把 ownership/spec 只留
  在本地聊天记录或未暂存的工作树里。

## 回归补强

- 仓储 facade 热修已通过提交 `8c9e6865f` 固化：
  - `backend/app/core/base_repository.py`
  - `backend/app/core/repository_parts/tenant_scope.py`
  - `backend/tests/core/test_base_repository_facade.py`
- 附件公开访问链路黑盒回归已通过提交 `6c54aae78` 固化：
  - `backend/tests/api/test_public_attachments_endpoints.py`
  - 覆盖 `/api/public/attachments/{id}/image` 公开 happy path
  - 覆盖 `/api/public/attachments/{id}/access` 云端自跳转 fail-close 404
- 插件管理端读路径 facade 哨兵已通过提交 `2860846a4` 固化：
  - `backend/tests/services/test_plugin_read_model_service.py`
  - 强制经过 `PluginReadModelService -> PluginService -> BaseService -> PluginRepository(BaseRepository)`
  - 覆盖 `build_admin_plugin_list()` 与 `build_admin_plugin_detail()` 的
    `query_list/get_by_id` facade 路径
- 插件管理端 route 读路径哨兵已新增：
  - `backend/tests/test_admin_plugin_read_routes_contract.py`
  - 覆盖 `GET /plugins` 与 `GET /plugins/{id}`
  - 强制经过 `AdminPluginController -> PluginReadModelService`
  - 与 service 级哨兵组合后，形成 `route + read-model + base-service/repository facade`
    的双层保护
- 操作日志管理端 route 读路径哨兵已新增：
  - `backend/tests/test_admin_operation_log_routes_contract.py`
  - 覆盖 `GET /operation-logs/{id}`
  - 覆盖 `GET /operation-logs`
  - 覆盖 `GET /operation-logs/operators?page=...`
  - 强制经过 `AdminOperationLogController -> OperationLogService -> BaseService -> OperationLogRepository`
  - 用于补齐 operation-log 现有 mock-heavy service 测试之外的 transport/facade 保护
- 系统日志管理端 route 合约哨兵已新增：
  - `backend/tests/test_admin_system_log_routes_contract.py`
  - 覆盖 `GET /system-logs/stats`
  - 覆盖 `GET /system-logs/categories`
  - 覆盖 `GET /system-logs/files`
  - 覆盖 `GET /system-logs/files/{filename}/content` 的 success / 404
  - 覆盖 `GET /system-logs/files/{filename}/download`
  - 覆盖 `DELETE /system-logs/files/{filename}` 的当前日志 fail-close 400
  - 主要用于补齐 system-log UI 强依赖的 transport contract，避免前端吞错时后端回归失去可见性
- 任务管理与定时任务管理 route 合约哨兵已新增：
  - `backend/tests/test_admin_task_routes_contract.py`
  - `backend/tests/test_admin_periodic_task_routes_contract.py`
  - 覆盖 `GET /tasks`、`GET /tasks/active`、`POST /tasks/{task_log_id}/retry`
  - 覆盖 `GET /periodic-tasks`、`POST /periodic-tasks`、
    `PUT /periodic-tasks/{task_id}/bindings`
  - 主要用于补齐 control-plane route transport contract，确保薄 facade +
    query-service/controller 协调层不会静默回归
- Shared ops 前端 seam 回归已新增：
  - `frontend/apps/web-antd/src/components/business/config-form/__tests__/use-config-form-model.test.ts`
  - `frontend/apps/web-antd/src/views/admin/plugins/modules/plugin-config-drawer/__tests__/use-plugin-config-drawer.test.ts`
  - 覆盖 `config-form` 的嵌套 JSON 子字段回填、加密占位保护、dirty snapshot 重置
  - 覆盖 `plugin-config-drawer` 的配置 schema 本地化映射、租户分配装载、结构化配置保存、非法 JSON 拦截
  - 审计结论同步确认：
    `system-logs/index.vue`、`PluginConfigDrawer.vue`、`config-form/index.vue`
    已进入“薄壳 + composable/section”状态，本轮不再为拆而拆
- Auth / RBAC 服务拆分已进一步收口：
  - `backend/app/services/common/auth_service.py` 从 608 行降到 441 行
  - 新增 `backend/app/services/common/auth_domains/facades.py`
  - `backend/app/rbac/services/permission_service.py` 从 532 行降到 307 行
  - 新增 `backend/app/rbac/services/permission_domains/checks.py`
  - 新增 `backend/app/rbac/services/permission_domains/query.py`
  - 新增 `backend/app/rbac/services/permission_domains/tenant_admin.py`
  - 认证 service 继续保留稳定 façade，对外方法名不变；权限 service 变成真正的 façade + domains，而不是“同文件内伪拆分”
- Codegen 全链路拆分与回归已新增：
  - `backend/app/api/admin/codegen.py`
  - `backend/app/services/system/codegen_service_parts/execution_mixin.py`
  - `backend/app/services/system/codegen_service_parts/workbench_mixin.py`
  - `backend/tests/codegen/test_codegen_service_orchestration.py`
  - `frontend/apps/web-antd/src/views/admin/system/codegen/workbench-utils.ts`
  - `frontend/apps/web-antd/src/views/admin/system/codegen/composables/workflow-helpers.ts`
  - `frontend/apps/web-antd/src/views/admin/system/codegen/__tests__/workbench-utils.test.ts`
  - `frontend/apps/web-antd/src/views/admin/system/codegen/composables/__tests__/workflow-helpers.test.ts`
  - admin codegen controller 已把 generate / rollback / manifest-history orchestration 下沉到 service parts
  - codegen 前端 workbench 规则与 builder workflow helper 已从 `index.vue` / `use-codegen-builder-workflows.ts` 抽离
- Plugin 平台后端拆分与回归已新增：
  - `backend/app/api/admin/plugins.py`
  - `backend/app/api/admin/plugin_install_preview.py`
  - `backend/app/api/admin/plugin_admin_contracts.py`
  - `backend/app/plugins/lifecycle.py`
  - `backend/app/plugins/lifecycle_orchestrator.py`
  - `backend/app/plugins/registry.py`
  - `backend/app/plugins/registry_runtime_extensions.py`
  - `backend/app/services/system/plugin_read_model_service.py`
  - `backend/app/services/system/plugin_cleanup_service.py`
  - `backend/tests/test_admin_plugin_dependency_contract.py`
  - admin plugins controller 已收成更薄的 write-side façade
  - marketplace / upload preview-install 已沉到 `plugin_install_preview.py`
  - admin plugins read routes 已沉到 `plugin_admin_contracts.py`
  - registry 的 notification / permission / menu / socketio / frontend-slot 运行时家族已抽到 `registry_runtime_extensions.py`
  - lifecycle 新增 menu override 的持久化与 runtime 重挂 orchestration seam
- Bundled plugin 前端拆分与回归已新增：
  - `backend/plugins/storage-billing/frontend/src/views/admin/index.vue`
  - `backend/plugins/storage-billing/frontend/src/views/admin/use-storage-billing-admin-page.ts`
  - `backend/plugins/storage-billing/frontend/src/views/admin/use-storage-billing-admin-bindings.ts`
  - `backend/plugins/storage-billing/frontend/src/views/admin/storage-billing-admin-contracts.ts`
  - `backend/plugins/storage-billing/frontend/src/views/admin/storage-billing-admin-presenters.ts`
  - `backend/plugins/storage-billing/frontend/src/views/admin/__tests__/reconciliation-helpers.test.ts`
  - `backend/plugins/storage-billing/frontend/src/views/admin/__tests__/use-reconciliation-run-detail.test.ts`
  - `backend/plugins/storage-billing/frontend/src/views/admin/__tests__/use-storage-billing-admin-run-actions.test.ts`
  - `backend/plugins/storage-billing/frontend/vitest.config.ts`
  - `backend/plugins/slider-captcha/frontend/src/SliderCaptcha.vue`
  - `backend/plugins/slider-captcha/frontend/src/use-slider-captcha-controller.ts`
  - `backend/plugins/slider-captcha/frontend/src/use-slider-captcha-copy.ts`
  - `backend/plugins/slider-captcha/frontend/src/slider-captcha-shared.ts`
  - `backend/plugins/slider-captcha/frontend/src/__tests__/slider-captcha-a11y.test.ts`
  - `backend/plugins/slider-captcha/frontend/src/__tests__/slider-captcha-state-machine.test.ts`
  - `backend/plugins/slider-captcha/frontend/src/__tests__/use-slider-captcha-layout.test.ts`
  - `backend/plugins/slider-captcha/frontend/src/__tests__/use-slider-captcha-controller.test.ts`
  - storage-billing admin page 已收成 `page shell + plugin-local page/bindings/presenters/contracts`，`index.vue` 降到约 300 行
  - slider-captcha 已收成 `shell + controller + copy + shared helper`，`SliderCaptcha.vue` 降到约 222 行
  - 两个 bundled plugin 都保持原组件导出路径、plugin manifest/runtime gate 与 frontend slot 契约不变

## 验证补充

- 非 AI 宽回归已通过：
  - control-plane 主链：`38 passed`
  - plugin 平台后端：仓库内 `TMP/TEMP` 下 `56 passed, 4 skipped`
  - codegen 后端：仓库内 `TMP/TEMP` 下 `114 passed`
  - 附件/operation-log/仓储哨兵：定向集合通过
- 当前环境存在两个与业务逻辑无关的测试噪音：
  - 系统 `Temp` 目录权限会导致部分 `pytest_asyncio` fixture 初始化失败
  - `backend/.pytest_cache` 目录存在 `WinError 5` 写权限告警
- 当前本地执行约定：
  - 宽回归优先把 `TMP`、`TEMP` 指向
    `E:/git_clone/novusai-saas-yudi/.codex-temp/pytest-temp`
  - `.pytest_cache` 告警可记录但不视为业务失败
- 本轮新增定向验证：
  - `ruff check backend/tests/test_admin_task_routes_contract.py backend/tests/test_admin_periodic_task_routes_contract.py`
  - `python -m pytest backend/tests/test_admin_task_routes_contract.py backend/tests/test_admin_periodic_task_routes_contract.py -q`
  - 结果：`6 passed`，伴随 `.pytest_cache` `WinError 5` warning（环境噪音，不视为业务失败）
  - `pnpm --dir frontend exec vitest run --dom apps/web-antd/src/components/business/config-form/__tests__/use-config-form-model.test.ts apps/web-antd/src/views/admin/plugins/modules/plugin-config-drawer/__tests__/use-plugin-config-drawer.test.ts`
  - `pnpm --dir frontend exec vue-tsc --noEmit --skipLibCheck --pretty false -p apps/web-antd/tsconfig.json`
  - 结果：`2 files passed / 6 tests passed`，`vue-tsc` 通过
  - `ruff check backend/app/services/common/auth_service.py backend/app/services/common/auth_domains/facades.py backend/app/services/common/auth_domains/__init__.py backend/tests/services/test_auth_service.py`
  - `python -m pytest backend/tests/services/test_auth_service.py backend/tests/api/test_tenant_auth.py backend/tests/api/test_tenant_admins.py backend/tests/api/test_admin_tenants.py -q`
  - 结果：`31 passed`，伴随 `.pytest_cache` `WinError 5` warning
  - `ruff check backend/app/rbac/services/permission_service.py backend/app/rbac/services/permission_domains/__init__.py backend/app/rbac/services/permission_domains/checks.py backend/app/rbac/services/permission_domains/tenant_admin.py backend/app/rbac/services/permission_domains/query.py backend/tests/rbac/test_permission_service_menu_ai_meta.py backend/tests/services/test_permission_service_tenant_org_node.py`
  - `python -m pytest backend/tests/rbac/test_permission_service_menu_ai_meta.py backend/tests/services/test_permission_service_tenant_org_node.py -q`
  - 结果：`3 passed`，伴随 `.pytest_cache` `WinError 5` warning
  - `ruff check backend/app/services/system/codegen_service_parts/execution_mixin.py backend/app/services/system/codegen_service_parts/workbench_mixin.py backend/app/api/admin/codegen.py backend/tests/codegen/test_codegen_service_orchestration.py`
  - `python -m pytest backend/tests/codegen/test_codegen_service.py backend/tests/codegen/test_codegen_service_orchestration.py -q`
  - `pnpm --dir frontend exec vitest run apps/web-antd/src/views/admin/system/codegen/__tests__/workbench-utils.test.ts apps/web-antd/src/views/admin/system/codegen/composables/__tests__/workflow-helpers.test.ts apps/web-antd/src/store/admin/__tests__/codegen-builder.test.ts`
  - `pnpm --dir frontend exec vue-tsc --noEmit --skipLibCheck --pretty false -p apps/web-antd/tsconfig.json`
  - 结果：后端 `14 passed`，前端 `3 files passed / 8 tests passed`，`vue-tsc` 通过
  - `ruff check backend/app/api/admin/plugins.py backend/app/api/admin/plugin_install_preview.py backend/app/api/admin/plugin_admin_contracts.py backend/app/plugins/lifecycle.py backend/app/plugins/lifecycle_orchestrator.py backend/app/plugins/registry.py backend/app/plugins/registry_runtime_extensions.py backend/app/services/system/plugin_read_model_service.py backend/app/services/system/plugin_cleanup_service.py backend/tests/test_admin_plugin_dependency_contract.py backend/tests/test_admin_plugin_read_routes_contract.py backend/tests/services/test_plugin_read_model_service.py backend/tests/services/test_plugin_cleanup_service.py backend/tests/test_admin_plugin_repair_fail_close.py backend/tests/test_admin_plugin_marketplace_contract.py`
  - `python -m pytest backend/tests/test_admin_plugin_dependency_contract.py backend/tests/test_admin_plugin_read_routes_contract.py backend/tests/services/test_plugin_read_model_service.py backend/tests/services/test_plugin_cleanup_service.py backend/tests/test_admin_plugin_repair_fail_close.py backend/tests/test_admin_plugin_marketplace_contract.py -q`
  - 结果：`23 passed`，伴随 `.pytest_cache` `WinError 5` warning
  - `pnpm --dir frontend exec vitest run --config E:/git_clone/novusai-saas-yudi/backend/plugins/storage-billing/frontend/vitest.config.ts --root E:/git_clone/novusai-saas-yudi/backend/plugins/storage-billing/frontend src/views/admin/__tests__/reconciliation-helpers.test.ts src/views/admin/__tests__/use-reconciliation-run-detail.test.ts src/views/admin/__tests__/use-storage-billing-admin-run-actions.test.ts`
  - `pnpm --dir backend/plugins/storage-billing/frontend exec vite build`
  - 结果：storage-billing 插件前端 `3 files passed / 11 tests passed`，生产打包通过
  - `pnpm --dir frontend exec vitest run --dom --root .. backend/plugins/slider-captcha/frontend/src/__tests__/offset-detector.test.ts backend/plugins/slider-captcha/frontend/src/__tests__/render-slider-assets.test.ts backend/plugins/slider-captcha/frontend/src/__tests__/use-slider-captcha-challenge.test.ts backend/plugins/slider-captcha/frontend/src/__tests__/use-slider-captcha-controller.test.ts backend/plugins/slider-captcha/frontend/src/__tests__/slider-captcha-a11y.test.ts backend/plugins/slider-captcha/frontend/src/__tests__/slider-captcha-state-machine.test.ts backend/plugins/slider-captcha/frontend/src/__tests__/use-slider-captcha-layout.test.ts`
  - `pnpm --dir backend/plugins/slider-captcha/frontend exec vite build`
  - 结果：slider-captcha 插件前端 `7 files passed / 24 tests passed`，生产打包通过

## 本轮已确认收口的 facade

- 下列文件当前已经属于“薄 facade / 兼容壳”状态，不再作为主要拆分热点：
  - `backend/app/cli.py`
  - `backend/app/core/base_repository.py`
  - `backend/app/services/system/codegen_service.py`
  - `backend/app/codegen/generator.py`
  - `backend/plugins/storage-billing/backend/services/reconciliation_service.py`
- 后续如需继续演进，优先改其内部 parts/helpers，不回头把逻辑塞回 facade。

## 本轮残余审计图

- `agent-1 / control-plane-and-core-foundation`
  - `backend/app/services/system/operation_log_service.py` 仍是最大 service 团块。
  - `backend/app/api/admin/tasks.py`、`backend/app/api/admin/periodic_tasks.py` 已去掉直查库，但 controller 仍直接编排二级 service/query。
  - `backend/app/core/base_repository.py`、`backend/app/cli.py` 已完成 facade 化，剩余重点转向 route contract 与 query-service 收口。
- `agent-2 / auth-rbac-and-org-boundary`
  - `backend/app/services/common/auth_service.py` 已继续下沉 façade 类到 `auth_domains/facades.py`，主 service 主要保留 domain 委托与兼容方法。
  - `backend/app/rbac/services/permission_service.py` 已继续下沉到 `permission_domains/checks.py`、`query.py`、`tenant_admin.py`，主 service 已收成 façade。
  - 这批 controller 已基本清掉 `db.execute(...)`，但 `tenant/configs.py`、`admin/tenant_admins.py`、`admin/tenants.py` 仍有 controller-file-local presenter/workflow。
  - auth 事务边界仍混杂在 helper 内部 `commit/rollback` 与 controller 外层提交之间。
- `agent-3 / plugin-platform-backend`
  - `backend/app/plugins/lifecycle.py` 已压到 432 行，作为 facade/mixin 汇聚层使用。
  - `backend/app/plugins/lifecycle_orchestrator.py` 已压到 833 行，承接生命周期编排主逻辑（parts）。
  - lifecycle 相关拆分模式由“假拆分”更新为可执行样例：`facade + mixin/parts`。
  - 本轮已修复 `PluginCleanupService` 的 alembic `LIKE` 转义风险，并补了回归测试。
  - `backend/scripts/plugin_cli.py` 已降为 825 行，仍需持续沿 facade + parts 收敛其余主干。
  - 本轮已把 admin plugin 写路由、preview-install、registry runtime families 进一步拆开并补齐 23 个定向回归。
- `agent-4 / codegen-fullstack`
  - `backend/app/services/system/codegen_service.py`、`backend/app/codegen/generator.py` 已完成 facade 化，剩余重点转向 `backend/app/api/admin/codegen.py` 与前端 Builder/FieldPropertyPanel 的 workflow seams。
  - `frontend/.../builder.vue` 已抽出 `scope/workflows`，本轮继续补了 `workflow-helpers.ts` 与 `workbench-utils.ts`。
  - `FieldPropertyPanel` 和 `use-field-property-panel` 仍需按 section / contract 继续拆。
- `agent-5 / frontend-shared-ops-pages`
  - `system-logs`、`plugin-config-drawer`、`config-form` 已确认完成“薄壳 + composable/section”收口，本轮通过 seam 测试加锁。
  - `frontend/.../file-picker/FilePicker.vue` 与 `use-file-picker-core.ts` 仍是共享大件对子系统，但当前更偏能力内聚而非壳层回潮。
  - `file-picker` 上传队列/拖拽与 `system-logs` 交互流仍缺 slice 级专项测试，可作为后续补强点。
- `agent-6 / bundled-plugins-and-surface-contracts`
  - `backend/plugins/storage-billing/backend/services/reconciliation_service.py` 已完成 facade 化。
  - `backend/plugins/storage-billing/frontend/src/views/admin/index.vue` 已完成 `page shell + plugin-local page/bindings/presenters/contracts` 收口，并用 plugin-local vitest 锁住运行详情与 action seams。
  - `backend/plugins/slider-captcha/frontend/src/SliderCaptcha.vue` 已完成 `shell + controller + copy + shared helper` 收口，并补齐 a11y/state-machine/layout/controller/challenge 定向测试。
  - `backend/plugins/storage-migration/backend/services/migration_service.py` 仍需拆 runtime registry / runner / transfer / recovery；这是 bundled plugin 工作流里当前唯一仍保留的后续热点。
