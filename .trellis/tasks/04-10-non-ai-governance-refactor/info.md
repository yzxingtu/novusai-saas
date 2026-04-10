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

## 并行规则

- 各 worker 只能写 ownership matrix 中明确分配的文件。
- 不允许在他人 owned file 中顺手改“相邻逻辑”。
- 所有跨工作流 contract 只能通过 facade 或主代理冻结的模块导出。
- AI 相关代码只允许保留薄兼容入口，不允许顺手重构 AI 内核。

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
- `.trellis/` 为本地治理目录，可能不会进入常规 git 追踪；需要明确把补充的
  规范同步写入受版本控制的入口文件时机。

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

## 本轮残余审计图

- `agent-1 / control-plane-and-core-foundation`
  - `backend/app/services/system/operation_log_service.py` 仍是最大 service 团块。
  - `backend/app/api/admin/tasks.py`、`backend/app/api/admin/periodic_tasks.py` 已去掉直查库，但 controller 仍直接编排二级 service/query。
  - `backend/app/core/base_repository.py`、`backend/app/cli.py` 仍需按 facade + 子模块继续落刀。
- `agent-2 / auth-rbac-and-org-boundary`
  - `backend/app/services/common/auth_service.py`、`backend/app/rbac/services/permission_service.py` 目前仍以同文件 facade 包装为主，真实实现还未分域。
  - 这批 controller 已基本清掉 `db.execute(...)`，但 `tenant/configs.py`、`admin/tenant_admins.py`、`admin/tenants.py` 仍有 controller-file-local presenter/workflow。
  - auth 事务边界仍混杂在 helper 内部 `commit/rollback` 与 controller 外层提交之间。
- `agent-3 / plugin-platform-backend`
  - `backend/app/plugins/lifecycle.py` 已压到 432 行，作为 facade/mixin 汇聚层使用。
  - `backend/app/plugins/lifecycle_orchestrator.py` 已压到 833 行，承接生命周期编排主逻辑（parts）。
  - lifecycle 相关拆分模式由“假拆分”更新为可执行样例：`facade + mixin/parts`。
  - 本轮已修复 `PluginCleanupService` 的 alembic `LIKE` 转义风险，并补了回归测试。
  - `backend/scripts/plugin_cli.py` 已降为 825 行，仍需持续沿 facade + parts 收敛其余主干。
- `agent-4 / codegen-fullstack`
  - `backend/app/services/system/codegen_service.py`、`backend/app/codegen/generator.py`、`backend/app/api/admin/codegen.py` 仍是大块。
  - `frontend/.../builder.vue` 已抽出 `scope/workflows`，但仍保留页面装载、离页保护、快捷键、DB import merge、modal 模板。
  - `FieldPropertyPanel` 和 `use-field-property-panel` 仍需按 section / contract 继续拆。
- `agent-5 / frontend-shared-ops-pages`
  - `frontend/.../config-form/index.vue` 是最大的共享低内聚点。
  - `frontend/.../file-picker/FilePicker.vue` 与 `use-file-picker-core.ts` 仍是共享大件对子系统。
  - `useSystemLogs.ts`、`use-plugin-config-drawer.ts` / `PluginConfigDrawerBody.vue` 仍需继续按 presenter / domain 收口。
- `agent-6 / bundled-plugins-and-surface-contracts`
  - `backend/plugins/storage-billing/backend/services/reconciliation_service.py` 仍是本工作流最大后端热点。
  - `backend/plugins/storage-billing/frontend/src/views/admin/index.vue`、`AdminRunsCard.vue` 仍掌握过多 view-model 和 workflow。
  - `backend/plugins/storage-migration/backend/services/migration_service.py` 仍需拆 runtime registry / runner / transfer / recovery。
  - `backend/plugins/slider-captcha/frontend/src/SliderCaptcha.vue` 外部 contract 清晰，但内部 orchestration 还偏重。
