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
  - `backend/app/services/system/plugin_admin_workflow_service.py`
  - `backend/app/services/system/plugin_install_preview_service.py`
  - `backend/tests/test_admin_plugin_dependency_contract.py`
  - `backend/tests/test_admin_plugin_install_preview_routes_contract.py`
  - `backend/tests/services/test_plugin_install_preview_service.py`
  - admin plugins controller 已收成更薄的 write-side façade
  - marketplace / upload preview-install workflow 已沉到 `plugin_install_preview_service.py`，`plugin_install_preview.py` 仅保留路由/兼容导出
  - admin plugins read routes 已沉到 `plugin_admin_contracts.py`
  - admin plugins write-side 协调已继续下沉到 `plugin_admin_workflow_service.py`
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

## Optional Hardening（本轮补强）

- `backend/tests/test_admin_user_routes_contract.py`
  - admin 用户路由合约：`/users/select`、`/users/{id}`、`/users/{id}/force-logout` 均保持 controller -> service 委托路径。
- `backend/tests/test_recycle_bin_registry.py`
  - 回收站 registry 合约：admin module codes、side 校验、delete scope 映射保持稳定。
- `backend/tests/codegen/test_codegen_service.py`
  - codegen validate 解析异常时必须做安全文案 sanitize，避免路径/Traceback 泄漏。
- `frontend/apps/web-antd/src/views/admin/system/system-logs/__tests__/use-system-logs.test.ts`
  - system-logs composable 合约：日志行解析、刷新保持选中项、分页追加、搜索计数稳定；测试类型清理用于保持验证清洁度。
- `frontend/apps/web-antd/src/components/business/file-picker/__tests__/use-file-picker-core.upload-queue.test.ts`
  - file-picker upload queue slice：入队分流、批量上传与任务状态保持稳定。
- `frontend/apps/web-antd/src/components/business/file-picker/__tests__/use-file-picker-core.drag-drop.test.ts`
  - file-picker drag/drop slice：拖拽叠层与 drop 入队流程保持稳定。
- `frontend/apps/web-antd/src/components/business/file-picker/__tests__/FilePicker.slice.test.ts`
  - FilePicker shell slice 合约：壳层交互与核心组合契约保持稳定。
- `frontend/apps/web-antd/src/views/admin/system/system-logs/__tests__/SystemLogToolbar.slice.test.ts`
  - system-logs toolbar 壳层切片：分类/文件 chips 与 download/copy 禁用状态保持稳定。
- `frontend/apps/web-antd/src/views/admin/system/codegen/modules/__tests__/preview-builders.test.ts`
  - codegen WYSIWYG 列表预览构建：当全部字段被标记为不显示时仍会回退列构建，首行默认值解析保持稳定。
- `frontend/apps/web-antd/src/views/admin/plugins/modules/plugin-config-drawer/use-plugin-config-drawer.ts`
  - plugin-config-drawer 对 `manifest.config_schema.properties` 改为运行时 guard：异常 schema 不再被误解析成伪字段，非法 `enum/minimum/maximum` 也不会静默污染 UI 配置表单。
- `frontend/apps/web-antd/src/views/admin/plugins/modules/plugin-config-drawer/__tests__/use-plugin-config-drawer.test.ts`
  - plugin-config-drawer 新增 malformed schema 用例，锁住“跳过坏字段、保留合法字段”的 fail-close 行为。
- `backend/plugins/storage-billing/frontend/src/views/admin/use-storage-billing-admin-page.ts`
  - storage-billing admin page 对 `NovusPluginShared.getAccessCodes()` 增加 fail-close guard：宿主返回异常值时按“无权限”处理，不再把坏值继续传入权限判断链。
- `backend/plugins/storage-billing/frontend/src/views/admin/__tests__/use-storage-billing-admin-page.test.ts`
  - storage-billing admin page 新增 shared bridge 合约测试，锁住“坏 access codes fail-close / wildcard access 放行”的宿主桥接行为。
- `frontend/apps/web-antd/src/views/admin/system/codegen/composables/use-codegen-builder-scope.ts`
  - codegen builder scope composable 对 `model/endpoints/frontend` 增加运行时归一化：异常 endpoint 条目会被忽略，坏 `frontend` 节点回退为空对象，不再把脏配置直接带入 scope/base-class 同步逻辑。
- `frontend/apps/web-antd/src/views/admin/system/codegen/composables/__tests__/use-codegen-builder-scope.test.ts`
  - codegen builder scope 新增 malformed config 用例，锁住“忽略坏 endpoint / 保留有效 tenant scope / 开启 admin scope 时仍能同步 base_class”的行为。
- `backend/tests/services/test_plugin_read_model_service.py`
  - plugin registry fail-close 清理：当 unregister handler 抛错时，permission / notification / skill runtime caches 仍必须被清空。
- `backend/tests/services/test_tenant_admin_workflow_services.py`
  - tenant-admin workflow：空更新请求必须 fail-close，不允许 controller/service 把空 payload 视为成功更新。

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
  - `pnpm --dir frontend exec vitest run apps/web-antd/src/views/admin/plugins/modules/plugin-config-drawer/__tests__/use-plugin-config-drawer.test.ts`
  - `pnpm --dir frontend exec vue-tsc --noEmit --skipLibCheck --pretty false -p apps/web-antd/tsconfig.json`
  - 结果：`1 file passed / 3 tests passed`，`vue-tsc` 通过；`PluginConfigDrawerBody.vue` 的 lifecycle audit 区块继续下沉到 `PluginLifecycleAuditPanel.vue`
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
  - `ruff check backend/app/services/system/codegen_service.py backend/app/api/admin/codegen.py backend/tests/codegen/test_codegen_service_orchestration.py`
  - `TMP=E:/git_clone/novusai-saas-yudi/.codex-temp/pytest-temp TEMP=E:/git_clone/novusai-saas-yudi/.codex-temp/pytest-temp python -m pytest backend/tests/codegen/test_codegen_service_orchestration.py -q -p no:cacheprovider`
  - 结果：`6 passed`；preset 路径遍历与文件存在性守卫已从 `admin/codegen.py` 下沉到 `CodegenService.get_preset_detail_safe()`
  - `ruff check backend/app/api/admin/plugins.py backend/app/api/admin/plugin_install_preview.py backend/app/api/admin/plugin_admin_contracts.py backend/app/plugins/lifecycle.py backend/app/plugins/lifecycle_orchestrator.py backend/app/plugins/registry.py backend/app/plugins/registry_runtime_extensions.py backend/app/services/system/plugin_read_model_service.py backend/app/services/system/plugin_cleanup_service.py backend/tests/test_admin_plugin_dependency_contract.py backend/tests/test_admin_plugin_read_routes_contract.py backend/tests/services/test_plugin_read_model_service.py backend/tests/services/test_plugin_cleanup_service.py backend/tests/test_admin_plugin_repair_fail_close.py backend/tests/test_admin_plugin_marketplace_contract.py`
  - `python -m pytest backend/tests/test_admin_plugin_dependency_contract.py backend/tests/test_admin_plugin_read_routes_contract.py backend/tests/services/test_plugin_read_model_service.py backend/tests/services/test_plugin_cleanup_service.py backend/tests/test_admin_plugin_repair_fail_close.py backend/tests/test_admin_plugin_marketplace_contract.py -q`
  - 结果：`23 passed`，伴随 `.pytest_cache` `WinError 5` warning
  - `pnpm --dir frontend exec vitest run --config E:/git_clone/novusai-saas-yudi/backend/plugins/storage-billing/frontend/vitest.config.ts --root E:/git_clone/novusai-saas-yudi/backend/plugins/storage-billing/frontend src/views/admin/__tests__/reconciliation-helpers.test.ts src/views/admin/__tests__/use-reconciliation-run-detail.test.ts src/views/admin/__tests__/use-storage-billing-admin-run-actions.test.ts`
  - `pnpm --dir backend/plugins/storage-billing/frontend exec vite build`
  - 结果：storage-billing 插件前端 `3 files passed / 11 tests passed`，生产打包通过
  - `pnpm --dir frontend exec vitest run --dom --root .. backend/plugins/slider-captcha/frontend/src/__tests__/offset-detector.test.ts backend/plugins/slider-captcha/frontend/src/__tests__/render-slider-assets.test.ts backend/plugins/slider-captcha/frontend/src/__tests__/use-slider-captcha-challenge.test.ts backend/plugins/slider-captcha/frontend/src/__tests__/use-slider-captcha-controller.test.ts backend/plugins/slider-captcha/frontend/src/__tests__/slider-captcha-a11y.test.ts backend/plugins/slider-captcha/frontend/src/__tests__/slider-captcha-state-machine.test.ts backend/plugins/slider-captcha/frontend/src/__tests__/use-slider-captcha-layout.test.ts`
  - `pnpm --dir backend/plugins/slider-captcha/frontend exec vite build`
  - 结果：slider-captcha 插件前端 `7 files passed / 24 tests passed`，生产打包通过
  - `ruff check backend/app/api/tenant/configs.py backend/app/api/admin/tenants.py backend/app/services/tenant/tenant_config_workflow_service.py backend/app/services/system/tenant_storage_admin_service.py backend/app/services/system/tenant_impersonation_service.py backend/app/services/system/tenant_service.py backend/app/services/tenant/tenant_admin_service.py backend/tests/test_tenant_config_routes_contract.py backend/tests/test_admin_tenant_workflow_routes_contract.py backend/tests/services/test_tenant_admin_workflow_services.py`
  - `python -m pytest backend/tests/services/test_tenant_admin_workflow_services.py backend/tests/test_tenant_config_routes_contract.py backend/tests/test_admin_tenant_workflow_routes_contract.py -q -p no:cacheprovider`
  - 结果：`10 passed`；`tenant/configs.py` 与 `admin/tenants.py` 的 controller-local workflow 已下沉到 `tenant_config_workflow_service.py`、`tenant_storage_admin_service.py`、`tenant_impersonation_service.py`，并补齐 route + service 双层哨兵
- `ruff check backend/app/api/admin/tenant_admins.py backend/app/services/system/tenant_admin_workflow_service.py backend/tests/test_admin_tenant_admin_routes_contract.py backend/tests/services/test_tenant_admin_workflow_services.py`
  - `python -m pytest backend/tests/test_admin_tenant_admin_routes_contract.py backend/tests/services/test_tenant_admin_workflow_services.py -q -p no:cacheprovider`
  - 结果：`7 passed`；`admin/tenant_admins.py` 的 controller-local workflow/序列化胶水已下沉到 `tenant_admin_workflow_service.py`，并补齐 route + service 双层哨兵
  - `pnpm --dir frontend exec vitest run --dom apps/web-antd/src/components/business/file-picker/__tests__/use-file-picker-core.upload-queue.test.ts apps/web-antd/src/components/business/file-picker/__tests__/use-file-picker-core.drag-drop.test.ts apps/web-antd/src/components/business/file-picker/__tests__/FilePicker.slice.test.ts apps/web-antd/src/views/admin/system/system-logs/__tests__/use-system-logs.test.ts`
  - 结果：`4 files passed / 16 tests passed`
  - `pnpm --dir frontend test:unit -- --run apps/web-antd/src/views/admin/system/system-logs/__tests__/use-system-logs.test.ts`
  - 结果：`1 file passed / 5 tests passed`
  - `pnpm --dir frontend test:unit -- --run apps/web-antd/src/components/business/file-picker/__tests__/use-file-picker-core.upload-queue.test.ts`
  - 结果：`1 file passed / 5 tests passed`
  - `ruff check backend/app/api/admin/plugins.py backend/app/api/admin/plugin_install_preview.py backend/app/services/system/plugin_service.py backend/tests/test_admin_plugin_write_routes_contract.py backend/tests/test_admin_user_routes_contract.py backend/app/api/admin/tenant_admins.py backend/app/services/system/tenant_admin_workflow_service.py backend/tests/test_admin_tenant_admin_routes_contract.py backend/tests/services/test_tenant_admin_workflow_services.py`
  - 结果：`All checks passed!`
  - `python -m pytest backend/tests/test_admin_plugin_write_routes_contract.py backend/tests/test_admin_user_routes_contract.py backend/tests/test_admin_plugin_dependency_contract.py backend/tests/test_admin_plugin_marketplace_contract.py backend/tests/test_admin_tenant_admin_routes_contract.py backend/tests/services/test_tenant_admin_workflow_services.py -q -p no:cacheprovider`
  - 结果：`22 passed`
  - `python -m pytest backend/tests/test_admin_plugin_write_routes_contract.py backend/tests/test_admin_plugin_read_routes_contract.py backend/tests/test_admin_plugin_dependency_contract.py backend/tests/test_admin_plugin_marketplace_contract.py backend/tests/test_admin_plugin_repair_fail_close.py backend/tests/services/test_plugin_read_model_service.py backend/tests/test_admin_user_routes_contract.py backend/tests/test_recycle_bin_registry.py backend/tests/test_admin_tenant_admin_routes_contract.py backend/tests/services/test_tenant_admin_workflow_services.py -q -p no:cacheprovider`
  - 结果：`37 passed`
  - `pnpm --dir frontend exec vitest run --dom apps/web-antd/src/components/business/file-picker/__tests__/use-file-picker-core.drag-drop.test.ts`
  - 结果：`1 file passed / 3 tests passed`
  - `pnpm --dir frontend exec vue-tsc --noEmit --skipLibCheck --pretty false -p apps/web-antd/tsconfig.json`
  - 结果：通过
  - `ruff check backend/app/api/admin/plugins.py backend/app/services/system/plugin_admin_workflow_service.py backend/app/services/system/__init__.py backend/tests/test_admin_plugin_write_routes_contract.py backend/tests/services/test_plugin_admin_workflow_service.py backend/tests/test_admin_plugin_repair_fail_close.py`
  - `python -m pytest backend/tests/test_admin_plugin_write_routes_contract.py backend/tests/services/test_plugin_admin_workflow_service.py backend/tests/test_admin_plugin_read_routes_contract.py backend/tests/test_admin_plugin_dependency_contract.py backend/tests/test_admin_plugin_marketplace_contract.py backend/tests/test_admin_plugin_repair_fail_close.py backend/tests/services/test_plugin_read_model_service.py -q -p no:cacheprovider`
  - 结果：`All checks passed!`；`34 passed`

## 本轮已确认收口的 facade

- 下列文件当前已经属于“薄 facade / 兼容壳”状态，不再作为主要拆分热点：
  - `backend/app/cli.py`
  - `backend/app/core/base_repository.py`
  - `backend/app/services/system/operation_log_service.py`
  - `backend/scripts/plugin_cli.py`
  - `backend/app/services/system/codegen_service.py`
  - `backend/app/codegen/generator.py`
  - `backend/plugins/storage-billing/backend/services/reconciliation_service.py`
  - `backend/plugins/storage-migration/backend/services/migration_service.py`
- 后续如需继续演进，优先改其内部 parts/helpers，不回头把逻辑塞回 facade。

## 本轮已确认收口的 shell / workflow seams

- 下列文件当前已经属于“薄 shell / workflow seam”状态，不再作为主要拆分热点：
  - `backend/app/api/tenant/configs.py`
  - `backend/app/api/admin/tenants.py`
  - `backend/app/api/admin/tenant_admins.py`
  - `frontend/apps/web-antd/src/views/admin/system/codegen/modules/FieldPropertyPanel.vue`
- 后续如需继续演进，优先修改对应 workflow service、section components 或 typed contracts，不回头把 presenter / storage / impersonation / field-section 逻辑塞回 controller 或页面壳层。

## 本轮残余审计图

- `agent-1 / control-plane-and-core-foundation`
  - `backend/app/services/system/operation_log_service.py` 已拆成 façade + `operation_log_service_parts/**`，并补齐 service 回归，不再作为主要拆分热点。
  - `backend/app/api/admin/tasks.py`、`backend/app/api/admin/periodic_tasks.py` 已去掉直查库，并通过 route contract 锁住 controller + query-service seam。
  - `backend/app/core/base_repository.py`、`backend/app/cli.py` 已完成 facade 化，当前 workstream 已收口。
- `agent-2 / auth-rbac-and-org-boundary`
  - `backend/app/services/common/auth_service.py` 已继续下沉 façade 类到 `auth_domains/facades.py`，主 service 主要保留 domain 委托与兼容方法。
  - `backend/app/rbac/services/permission_service.py` 已继续下沉到 `permission_domains/checks.py`、`query.py`、`tenant_admin.py`，主 service 已收成 façade。
  - `tenant/configs.py`、`admin/tenants.py` 的 controller-local workflow 已下沉到专门 service，并补齐 route + service 双层哨兵。
  - `admin/tenant_admins.py` 已把 controller-local workflow/serializer/tenant 校验胶水下沉到 `tenant_admin_workflow_service.py`，并补齐 route + service 哨兵。
- `agent-3 / plugin-platform-backend`
  - `backend/app/plugins/lifecycle.py` 已压到 443 行，作为 facade/mixin 汇聚层使用。
  - `backend/app/plugins/lifecycle_orchestrator.py` 已压到 987 行，承接生命周期编排主逻辑（parts）。
  - lifecycle 相关拆分模式由“假拆分”更新为可执行样例：`facade + mixin/parts`。
  - 本轮已修复 `PluginCleanupService` 的 alembic `LIKE` 转义风险，并补了回归测试。
  - `backend/scripts/plugin_cli.py` 已收口为薄 facade，create/build/validate/pack/release/parser 等职责已经分拆到 companion modules。
  - `backend/app/api/admin/plugins.py` 已继续把 write-side 协调下沉到 `plugin_admin_workflow_service.py`，controller 现在只保留 transport 协调；`backend/app/plugins/registry.py` 也已完成 host seam 收口，本轮 blocker 已关闭。
  - install-preview workflow 已由 `plugin_install_preview_service.py` 承接，`plugin_install_preview.py` 保留路由/兼容导出，`test_admin_plugin_marketplace_contract.py` 继续覆盖 preview/confirm 与 token 校验合约。
  - 2026-04-12 定向验证：`python -m ruff check backend/app/api/admin/plugin_install_preview.py backend/app/services/system/__init__.py backend/tests/test_admin_plugin_marketplace_contract.py backend/tests/services/test_plugin_install_preview_service.py backend/tests/test_admin_plugin_install_preview_routes_contract.py .trellis/spec/backend/index.md .trellis/spec/backend/quality-guidelines.md .trellis/spec/guides/plugin-runtime-playbook.md` 通过；`python -m pytest tests/test_admin_plugin_marketplace_contract.py tests/test_admin_plugin_install_preview_routes_contract.py tests/services/test_plugin_install_preview_service.py tests/test_admin_plugin_write_routes_contract.py tests/test_admin_plugin_read_routes_contract.py tests/test_admin_plugin_dependency_contract.py tests/test_admin_plugin_repair_fail_close.py tests/services/test_plugin_read_model_service.py -q -p no:cacheprovider --basetemp .pytest_tmp/install-preview` 结果 `35 passed`。
- `agent-4 / codegen-fullstack`
  - `backend/app/services/system/codegen_service.py`、`backend/app/codegen/generator.py` 已完成 facade 化；`backend/app/api/admin/codegen.py`、`FieldPropertyPanel.vue` 的 workflow / section seams 已通过定向回归锁住。
  - `admin/codegen.py` 的 preset 安全校验已进一步下沉到 `CodegenService.get_preset_detail_safe()`，controller 保持 transport-only。
  - `frontend/.../builder.vue` 已抽出 `scope/workflows`，本轮继续补了 `workflow-helpers.ts` 与 `workbench-utils.ts`。
  - `FieldPropertyPanel` 已收口为 section components + typed contracts，不再作为主要拆分热点。
- `agent-5 / frontend-shared-ops-pages`
  - `system-logs`、`plugin-config-drawer`、`config-form` 已确认完成“薄壳 + composable/section”收口，本轮通过 seam 测试加锁。
  - `PluginConfigDrawerBody.vue` 的 lifecycle audit 展示已继续抽成 `PluginLifecycleAuditPanel.vue`，避免 DrawerBody 回潮成 audit 展示聚合层。
  - `frontend/.../file-picker/FilePicker.vue` 与 `use-file-picker-core.ts` 仍是共享大件对子系统，但当前更偏能力内聚而非壳层回潮；contracts + core tests 已补齐。
  - `file-picker` 上传队列/拖拽/壳层 slice 已补齐；`system-logs` 交互流仍可作为后续补强点。
- `agent-6 / bundled-plugins-and-surface-contracts`
  - `backend/plugins/storage-billing/backend/services/reconciliation_service.py` 已完成 facade 化。
  - `backend/plugins/storage-billing/frontend/src/views/admin/index.vue` 已完成 `page shell + plugin-local page/bindings/presenters/contracts` 收口，并用 plugin-local vitest 锁住运行详情与 action seams。
  - `backend/plugins/slider-captcha/frontend/src/SliderCaptcha.vue` 已完成 `shell + controller + copy + shared helper` 收口，并补齐 a11y/state-machine/layout/controller/challenge 定向测试。
  - `backend/plugins/storage-migration/backend/services/migration_service.py` 已完成 facade + runtime registry / runner / transfer / recovery 收口，bundled plugin 工作流本轮 blocker 已关闭。

## 2026-04-12 残余收口

- Plugin platform backend 最后一批残余已关闭：
  - `backend/app/services/system/plugin_install_preview_service.py` 已正式入库，
    消除 clean checkout 缺文件 blocker。
  - `backend/app/plugins/manifest.py` 已降到 849 行，并保留 `PluginManifest`
    导入路径不变；公共 helper/constants 下沉到
    `backend/app/plugins/manifest_helpers.py`，feature/dependency/pricing/resources
    元数据 schema 下沉到
    `backend/app/plugins/manifest_metadata_schemas.py`。
  - `backend/app/plugins/context.py` 已降到 775 行，并把 `RequestContext`、
    `PluginDbProxy`、`_NamespacedStorageProxy` 下沉到
    `backend/app/plugins/context_primitives.py`，`PluginContext` 对外导出保持兼容。
- Auth / dashboard 最后一批大文件残余已关闭：
  - `backend/app/services/common/auth_domains/tenant_user_auth.py` 已降到 157 行
    facade，并把登录/验证码/账户与 token 逻辑下沉到
    `tenant_user_login.py` 与 `tenant_user_login_code.py`。
  - `backend/app/services/system/dashboard_service.py` 已降到 42 行 facade，
    主逻辑下沉到 `dashboard_service_parts/{admin,tenant,base,activity,visibility}.py`。
  - dashboard parts 已按 facade seam 兼容现有测试 monkeypatch，避免“真拆分但测不着”的回归。
- Codegen / bundled plugin 前端残余已关闭：
  - `frontend/.../WysiwygFormView.vue` 已降到 37 行壳层，
    header/body/preview-state 分别下沉到
    `WysiwygFormHeader.vue`、`WysiwygFormBody.vue`、
    `useWysiwygFormPreview.ts`、`wysiwyg-form-context.ts`。
  - `frontend/.../WysiwygListView.vue` 已清掉残余 `Record<string, any>`，
    改为显式 quick-search 类型。
  - `backend/plugins/weather-widget/frontend/src/styles.ts` 已改为 `WX_STYLES`
    聚合器，样式片段拆到 `styles.base.ts`、`styles.panel.ts`、
    `styles.dashboard.ts`、`styles.scene.ts`、`styles.trigger.ts`、
    `styles.skeleton.ts`、`styles.responsive.ts`。

## 2026-04-12 定向验证

- `python -m ruff check backend/app/plugins/context.py backend/app/plugins/context_primitives.py backend/app/plugins/manifest.py backend/app/plugins/manifest_helpers.py backend/app/services/system/plugin_install_preview_service.py backend/app/services/common/auth_domains/__init__.py backend/app/services/common/auth_domains/tenant_user_auth.py backend/app/services/common/auth_domains/tenant_user_login.py backend/app/services/common/auth_domains/tenant_user_login_code.py backend/app/services/system/dashboard_service.py backend/app/services/system/dashboard_service_parts`
  - 结果：通过。
- `python -m ruff check app/plugins/manifest.py app/plugins/manifest_metadata_schemas.py`
  - 工作目录：`backend`
  - 结果：通过。
- `python -m pytest tests/services/test_auth_service.py tests/services/test_admin_dashboard_service.py tests/services/test_tenant_dashboard_service.py tests/services/test_plugin_install_preview_service.py tests/test_admin_plugin_marketplace_contract.py tests/test_admin_plugin_install_preview_routes_contract.py tests/test_plugin_api_dispatcher_security.py tests/test_plugin_api_dispatcher_context_safety.py tests/test_plugin_storage_runtime.py tests/test_plugin_manifest_validation.py tests/test_plugin_dependency_runtime_model.py -q -p no:cacheprovider --basetemp E:/git_clone/novusai-saas-yudi/.pytest_tmp/non-ai-residual`
  - 结果：`94 passed`。
- `python -m pytest tests/services/test_admin_dashboard_service.py tests/services/test_tenant_dashboard_service.py -q -p no:cacheprovider --basetemp E:/git_clone/novusai-saas-yudi/.pytest_tmp/non-ai-residual`
  - 结果：`8 passed`。
- `pnpm --dir frontend exec vue-tsc --noEmit --skipLibCheck --pretty false -p apps/web-antd/tsconfig.json`
  - 结果：通过。
- `pnpm exec vite build`
  - 工作目录：`backend/plugins/weather-widget/frontend`
  - 结果：通过。
- `python -m pytest tests/test_plugin_manifest_validation.py tests/test_plugin_extension_registration.py tests/test_plugin_storage_runtime.py tests/test_plugin_manifest_sync_service.py tests/test_plugin_startup_discovery_boundaries.py -q -p no:cacheprovider --basetemp E:/git_clone/novusai-saas-yudi/.pytest_tmp/manifest-runtime`
  - 工作目录：`backend`
  - 结果：`24 passed`。
- `python -m pytest tests/services/test_plugin_read_model_service.py -q -p no:cacheprovider --basetemp E:/git_clone/novusai-saas-yudi/.pytest_tmp/plugin-read-guard`
  - 工作目录：`backend`
  - 结果：`3 passed`。
- `python -m pytest tests/services/test_tenant_admin_workflow_services.py -q -p no:cacheprovider --basetemp E:/git_clone/novusai-saas-yudi/.pytest_tmp/tenant-admin-guard`
  - 工作目录：`backend`
  - 结果：`7 passed`。
- `pnpm --dir frontend test:unit -- preview-builders SystemLogToolbar.slice`
  - 结果：`2 files passed / 4 tests passed`。
- `pnpm --dir frontend exec vitest run apps/web-antd/src/views/admin/plugins/modules/plugin-config-drawer/__tests__/use-plugin-config-drawer.test.ts`
  - 结果：`1 file passed / 4 tests passed`。
- `pnpm --dir frontend exec vue-tsc --noEmit --skipLibCheck --pretty false -p apps/web-antd/tsconfig.json`
  - 结果：通过。
- `pnpm --dir frontend exec vitest run --config E:/git_clone/novusai-saas-yudi/backend/plugins/storage-billing/frontend/vitest.config.ts --root E:/git_clone/novusai-saas-yudi/backend/plugins/storage-billing/frontend src/views/admin/__tests__/use-storage-billing-admin-page.test.ts`
  - 结果：`1 file passed / 2 tests passed`。
- `pnpm --dir backend/plugins/storage-billing/frontend exec vite build`
  - 结果：通过。
- `pnpm --dir frontend exec vitest run apps/web-antd/src/views/admin/system/codegen/composables/__tests__/use-codegen-builder-scope.test.ts`
  - 结果：`1 file passed / 2 tests passed`。
