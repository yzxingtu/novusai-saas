# 非 AI 模块一次性治理与六子代理并行重构

## 目标

在不改动 AI 专项计划边界的前提下，一次性完成非 AI 模块的规范审计、
control plane 搭建、六工作流并行重构、总装验证，以及 `.trellis`
规范回填。

## 必达结果

1. 建立 umbrella task + 六个 workstream 子任务，并冻结 ownership matrix。
2. 所有本次已点名的非 AI 超大业务文件都纳入同一重构项目，不允许留作
   “后续再说”。
3. 所有已审计到的 controller/helper 直查库点都迁回 service/query/repository
   边界。
4. 六个 workstream 的写集完全不重叠，主代理只处理 contract、接线、总装
   和 `.trellis` 回填。
5. 对外 API、路由、CLI 命令名、插件 manifest/runtime gate、前端页面入口
   保持兼容。
6. 完成后把新增的实践规则补回 `.trellis/spec/**`，不能只留在任务文档或聊天
   记录中。
7. 插件生命周期主干采用 `facade + mixin/parts` 可执行样例沉淀：
   `backend/app/plugins/lifecycle.py`（432 行兼容 facade）+
   `backend/app/plugins/lifecycle_orchestrator.py`（833 行编排 parts）。

## 范围内文件域

- 控制面与基础层：
  - `backend/app/cli.py`
  - `backend/app/core/base_repository.py`
  - `backend/app/services/system/operation_log_service.py`
  - `backend/app/api/admin/tasks.py`
  - `backend/app/api/admin/periodic_tasks.py`
- 认证 / RBAC / 组织边界：
  - `backend/app/services/common/auth_service.py`
  - `backend/app/rbac/services/permission_service.py`
  - `backend/app/api/tenant/auth.py`
  - `backend/app/api/tenant/configs.py`
  - `backend/app/api/admin/{tenant_admins,users,tenants}.py`
- 插件平台后端：
  - `backend/app/plugins/{lifecycle,registry,context,manifest}.py`
  - `backend/app/api/admin/plugins.py`
  - `backend/app/api/tenant/plugins.py`
  - `backend/app/api/shared/{_storage_helpers,_skill_package_export}.py`
  - `backend/scripts/plugin_cli.py`
- Codegen 全链路：
  - `backend/app/services/system/codegen_service.py`
  - `backend/app/codegen/generator.py`
  - `backend/app/api/admin/codegen.py`
  - `frontend/apps/web-antd/src/views/admin/system/codegen/**`
- 前端共享/运维页面：
  - `frontend/apps/web-antd/src/components/business/file-picker/FilePicker.vue`
  - `frontend/apps/web-antd/src/views/admin/system/system-logs/index.vue`
  - `frontend/apps/web-antd/src/views/admin/plugins/modules/PluginConfigDrawer.vue`
  - `frontend/apps/web-antd/src/components/business/config-form/index.vue`
- 内置插件表面合同：
  - `backend/plugins/storage-billing/backend/services/reconciliation_service.py`
  - `backend/plugins/storage-billing/frontend/src/views/admin/index.vue`
  - `backend/plugins/slider-captcha/frontend/src/SliderCaptcha.vue`
  - `backend/plugins/storage-migration/backend/services/migration_service.py`

## 排除项

- `backend/app/ai/**` 与 AI 专项页面/测试，按 `PLAN.md` 另行推进。
- lockfile、generated 文件、locale 大 JSON、报告 JSON、视觉资源型超大
  SFC 仅记治理备注，不进入本次业务拆分。

## 验收标准

1. 六个 workstream 均提交了：
   - 结构化审计结论
   - 实际代码改动
   - 子系统验证记录
2. 所有列出的 controller/helper 直查库点清零。
3. 所有列出的非 AI 超大业务文件完成职责拆分，或降级为仅承担兼容/装配
   的 facade。
4. `.trellis/spec/**`、umbrella task、子任务文档与 ownership matrix
   与最终实现一致。
5. 规范文本中明确记录“controller 禁止直查库、页面禁止业务总管、插件生命周期/
   运行时推荐拆法（facade + mixin/parts）”并可用于 code review 执行。
