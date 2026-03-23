# AI-3 Handoff

## 1. 本轮目标与结果

- 本轮定位：`admin 前端契约收口轮次`
- 已完成：
  - `publish` 改为发送显式 payload，不再发空 body
  - admin 首页改为消费真实 `overview` / `metrics` 结构，不再依赖 speculative recent lists
  - templates / releases / runtime 页面按当前后端真实 schema 收口
  - 当前后端未暴露的字段统一显示 `未接入 / 当前后端未暴露 / 当前无值`
  - `templates/detail.vue` 中 capability category 统一走 `getCapabilityCategoryText()` fallback helper，不再直出 i18n key
- 未完成且不在 AI-3 ownership：
  - `plugin.yaml frontend.pages` 接线
  - `frontend/src/index.ts` 组件导出接线
  - `frontend/src/api/index.ts` 导出接线
  - `frontend/src/locales/index.ts` 注册接线

## 2. 本轮修改文件

- `backend/plugins/workflow-orchestration/frontend/src/api/admin.ts`
- `backend/plugins/workflow-orchestration/frontend/src/types/admin.ts`
- `backend/plugins/workflow-orchestration/frontend/src/views/admin/home/index.vue`
- `backend/plugins/workflow-orchestration/frontend/src/views/admin/templates/data.ts`
- `backend/plugins/workflow-orchestration/frontend/src/views/admin/templates/index.vue`
- `backend/plugins/workflow-orchestration/frontend/src/views/admin/templates/detail.vue`
- `backend/plugins/workflow-orchestration/frontend/src/views/admin/templates/editor.vue`
- `backend/plugins/workflow-orchestration/frontend/src/views/admin/releases/data.ts`
- `backend/plugins/workflow-orchestration/frontend/src/views/admin/releases/index.vue`
- `backend/plugins/workflow-orchestration/frontend/src/views/admin/runtime/data.ts`
- `backend/plugins/workflow-orchestration/frontend/src/views/admin/runtime/index.vue`
- `backend/plugins/workflow-orchestration/frontend/src/locales/admin/zh-CN.ts`
- `backend/plugins/workflow-orchestration/frontend/src/locales/admin/en-US.ts`
- `docs/design/ai-orchestration-platform/41-workflow-orchestration-delivery-kit-20260323/AI-3-handoff.md`

## 3. 当前页面契约

### 3.1 管理端首页

- 页面文件：`backend/plugins/workflow-orchestration/frontend/src/views/admin/home/index.vue`
- 当前真实后端来源：
  - `GET /admin/plugins/workflow-orchestration/api/overview`
  - `GET /admin/plugins/workflow-orchestration/api/metrics`
- 当前使用的真实字段：
  - `template_summary.total_templates`
  - `template_summary.total_versions`
  - `template_summary.total_runs`
  - `template_summary.total_artifacts`
  - `template_summary.status_counts`
  - `release_summary.total_releases`
  - `release_summary.status_counts`
  - `release_summary.latest_published_at`
  - `runtime_summary.run_status_counts`
  - `runtime_summary.artifact_status_counts`
  - `settings_summary.environment_count`
- 已移除的 speculative 依赖：
  - `summary`
  - `builder_surfaces` 的启用状态判断
  - `recent_templates`
  - `recent_releases`
  - `recent_runs`
- 当前处理方式：
  - recent list 改成显式 contract notice，不再假装有数据
  - builder surface 只保留产品说明，状态显示为 `当前后端未暴露`

### 3.2 模板列表 / 详情 / 编辑器

- 页面文件：
  - `backend/plugins/workflow-orchestration/frontend/src/views/admin/templates/index.vue`
  - `backend/plugins/workflow-orchestration/frontend/src/views/admin/templates/detail.vue`
  - `backend/plugins/workflow-orchestration/frontend/src/views/admin/templates/editor.vue`
- 当前真实后端来源：
  - `GET /admin/plugins/workflow-orchestration/api/templates`
  - `GET /admin/plugins/workflow-orchestration/api/templates/{template_id}`
  - `GET /admin/plugins/workflow-orchestration/api/templates/{template_id}/versions`
  - `POST /admin/plugins/workflow-orchestration/api/templates/{template_id}/publish`
- 模板列表当前服务端筛选：
  - `filter[name][ilike]`
  - `filter[code][eq]`
  - `filter[status][eq]`
  - `filter[category][eq]`
  - `filter[builder_surface][eq]`
  - `filter[release_scope][eq]`
  - `filter[created_by][eq]`
- 模板详情当前消费的真实字段：
  - `nodes`
  - `edges`
  - `latest_version`
  - `published_version`
  - `latest_release`
  - `version_count`
  - `latest_version_no`
  - `latest_version_id`
  - `current_published_version_id`
  - `latest_release_id`
  - `category`
  - `builder_surface`
  - `release_scope`
- 已显式标记未接入的字段：
  - `workflow_type`
  - `risk_level`
  - `owner_name`
  - `builder_capabilities`
  - `locked_segments`
  - `editable_segments`
  - `parameterized_segments`
  - `release_count`
- `publish` 当前明确发送 body：

```json
{
  "version_id": "<template.latest_version_id or null>",
  "release_scope": "<template.release_scope or selected_tenants>",
  "channel": "stable",
  "environment_code": "prod_env",
  "rollout_json": {},
  "notes": null,
  "change_types_json": ["workflow_definition_change"],
  "validation_result_json": {},
  "risk_level": null
}
```

### 3.3 发布中心

- 页面文件：`backend/plugins/workflow-orchestration/frontend/src/views/admin/releases/index.vue`
- 当前真实后端来源：
  - `GET /admin/plugins/workflow-orchestration/api/releases`
  - `POST /admin/plugins/workflow-orchestration/api/releases/{release_id}/rollback`
- 当前服务端筛选：
  - `filter[workflow_kind][eq]`
  - `filter[workflow_id][eq]`
  - `filter[status][eq]`
  - `filter[release_scope][eq]`
  - `filter[channel][eq]`
  - `filter[environment_code][eq]`
- 当前页面本地筛选：
  - `workflow_name / workflow_code / code / environment_code / workflow_version_id` 关键字搜索只对当前页已加载数据生效
- 当前消费的真实字段：
  - `workflow_name`
  - `code`
  - `workflow_version_id`
  - `status`
  - `environment_code`
  - `release_scope`
  - `channel`
  - `notes`
  - `published_at`
- 已收口的 speculative 字段：
  - `template_name`
  - `version` 文本
  - `operator_name`
  - `change_summary`
  - `release_notes`
  - `environment`
- 当前处理方式：
  - 发布人显示名未暴露，不再装作有 `operator_name`
  - 版本展示改为真实 `workflow_version_id`
  - 说明展示改为真实 `notes`

### 3.4 全局运行中心

- 页面文件：`backend/plugins/workflow-orchestration/frontend/src/views/admin/runtime/index.vue`
- 当前真实后端来源：
  - `GET /admin/plugins/workflow-orchestration/api/runs`
  - `GET /admin/plugins/workflow-orchestration/api/runs/{run_id}`
  - `POST /admin/plugins/workflow-orchestration/api/runs/{run_id}/replay`
  - `POST /admin/plugins/workflow-orchestration/api/runs/{run_id}/recover`
  - `POST /admin/plugins/workflow-orchestration/api/runs/{run_id}/terminate`
- 当前服务端筛选：
  - `filter[status][eq]`
  - `filter[tenant_id][eq]`
  - `filter[workflow_id][eq]`
  - `filter[workflow_template_id][eq]`
  - `filter[workflow_version_id][eq]`
  - `filter[release_id][eq]`
- 当前页面本地筛选：
  - workflow / template / node / id 关键字搜索只对当前页已加载数据生效
- 当前消费的真实字段：
  - `workflow_name`
  - `template_name`
  - `tenant_id`
  - `status`
  - `risk_level`
  - `current_node_key`
  - `current_node_name`
  - `node_counts`
  - `available_actions`
  - `workflow_version_id`
  - `release_id`
  - `node_runs`
  - `events`
  - `artifacts`
- 已收口的 speculative 字段：
  - `tenant_name`
  - `current_step_name`
  - `finished_at`
  - runtime 风险等级服务端筛选
- 当前处理方式：
  - tenant 名称改为明确显示 `名称未暴露`
  - 运行风险只作为展示值，不再发 speculative filter

## 4. Integrator 仍需接入

### 4.1 `plugin.yaml frontend.pages`

```yaml
frontend:
  pages:
    - name: orchestration_admin_home
      path: /admin/plugins/workflow-orchestration
      component: WorkflowOrchestrationAdminHome
      scope: admin
    - name: orchestration_admin_templates
      path: /admin/plugins/workflow-orchestration/templates
      component: WorkflowOrchestrationAdminTemplates
      scope: admin
    - name: orchestration_admin_template_detail
      path: /admin/plugins/workflow-orchestration/templates/:id
      component: WorkflowOrchestrationAdminTemplateDetail
      scope: admin
    - name: orchestration_admin_template_editor
      path: /admin/plugins/workflow-orchestration/templates/:id/editor
      component: WorkflowOrchestrationAdminTemplateEditor
      scope: admin
    - name: orchestration_admin_releases
      path: /admin/plugins/workflow-orchestration/releases
      component: WorkflowOrchestrationAdminReleases
      scope: admin
    - name: orchestration_admin_runtime
      path: /admin/plugins/workflow-orchestration/runtime
      component: WorkflowOrchestrationAdminRuntime
      scope: admin
```

### 4.2 `frontend/src/index.ts` 组件导出映射

```ts
export { default as WorkflowOrchestrationAdminHome } from './views/admin/home/index.vue';
export { default as WorkflowOrchestrationAdminTemplates } from './views/admin/templates/index.vue';
export { default as WorkflowOrchestrationAdminTemplateDetail } from './views/admin/templates/detail.vue';
export { default as WorkflowOrchestrationAdminTemplateEditor } from './views/admin/templates/editor.vue';
export { default as WorkflowOrchestrationAdminReleases } from './views/admin/releases/index.vue';
export { default as WorkflowOrchestrationAdminRuntime } from './views/admin/runtime/index.vue';
```

### 4.3 `frontend/src/api/index.ts` 导出项

```ts
export * from './admin';
```

### 4.4 路由与 locale 注册

- 管理端路由需要 integrator 接入到插件前端路由树
- locale 需要 integrator 注册前缀：
  - `plugin.workflowOrchestration.admin`
- locale 文件：
  - `backend/plugins/workflow-orchestration/frontend/src/locales/admin/zh-CN.ts`
  - `backend/plugins/workflow-orchestration/frontend/src/locales/admin/en-US.ts`

## 5. 仍依赖 AI-2 / Integrator 的项目

- 依赖 AI-2：
  - runtime admin API 返回结构需继续保持：
    - `run`
    - `node_runs`
    - `events`
    - `artifacts`
    - `execution_graph`
  - runtime action endpoints 需继续保持：
    - `replay`
    - `recover`
    - `terminate`
- 依赖 Integrator：
  - `plugin.yaml frontend.pages` 页面注册
  - `frontend/src/index.ts` 组件导出
  - `frontend/src/api/index.ts` 导出
  - `frontend/src/locales/index.ts` 注册
  - 插件 admin 菜单和权限实际落点接入

## 6. 已知字段假设

- `publish` 默认继续使用后端 schema 默认值：
  - `channel = stable`
  - `environment_code = prod_env`
  - `change_types_json = ['workflow_definition_change']`
- 发布中心关键字搜索不是后端 contract，本轮改为显式“当前页本地过滤”，没有伪装成服务端筛选
- 运行中心关键字搜索不是后端 contract，本轮改为显式“当前页本地过滤”
- `builder_capabilities` / `segments` 仍未出现在当前 template detail schema，本轮不再假设其真实结构，只保留 fallback 占位
- `tenant_name` 不在当前 run serializer 输出中，本轮不再假设可用

## 7. 测试与验证结果

- 静态验证：
  - 已执行 `typescript.transpileModule + @vue/compiler-sfc` 对 AI-3 ownership 内 admin `.ts/.vue` 文件做逐个编译检查
  - 结果：`admin plugin syntax check passed (18 files)`
- 手工验证：
  - 由于本插件 admin 页面仍未被 integrator 接入 `plugin.yaml frontend.pages`、`frontend/src/index.ts`、`frontend/src/api/index.ts` 与 locale 注册链路，本轮无法在宿主界面做浏览器级手工验证
- 本轮验证结论：
  - AI-3 自有范围内完成了可执行的静态验证
  - 接线完成后建议 integrator 做一次浏览器级回归：
    - 首页加载
    - 模板发布
    - 发布列表回滚
    - 运行列表详情与动作
