# AI-4 Handoff

## 0. 冻结信息

- `AI 编号`：`AI-4`
- `负责人`：`workflow-orchestration` 企业端前端负责人
- `工作副本路径`：`E:/git_clone/novusai-saas-yudi`
- `分支名`：`main`
- `最后提交 SHA`：`c6e2d7710516bc918abd3fdec5aa4671b6ba4253`
- `冻结时间`：`2026-03-23`

## 1. 文件清单

| 文件路径 | 类型 | 用途 | 备注 |
|---|---|---|---|
| `backend/plugins/workflow-orchestration/frontend/src/types/tenant.ts` | `new/update` | Tenant 侧共享类型、Run / Artifact / Query 真字段收口 | 已按 AI-2 当前运行时真相补充 `statusBucket`、`availableActions`、`downloadAvailable` |
| `backend/plugins/workflow-orchestration/frontend/src/api/tenant.ts` | `new/update` | Tenant API 封装、响应归一化、列表查询参数构造 | 已移除“多别名并行猜测”式 query 构造 |
| `backend/plugins/workflow-orchestration/frontend/src/views/tenant/shared/use-tenant-orchestration.ts` | `new/update` | Tenant 导航、文案、状态标签、动作 gating helper、本地 i18n fallback | 本轮 correctness 核心修复点之一 |
| `backend/plugins/workflow-orchestration/frontend/src/views/tenant/shared/ConsoleShell.vue` | `new` | 企业端控制台统一外壳 | 无本轮变更 |
| `backend/plugins/workflow-orchestration/frontend/src/views/tenant/shared/StatusPill.vue` | `new` | Tenant 状态胶囊组件 | 无本轮变更 |
| `backend/plugins/workflow-orchestration/frontend/src/views/tenant/shared/EmptyState.vue` | `new` | Tenant 空态组件 | 无本轮变更 |
| `backend/plugins/workflow-orchestration/frontend/src/views/tenant/home/index.vue` | `new/update` | 企业首页 | 继续消费 AI-2 首页 payload |
| `backend/plugins/workflow-orchestration/frontend/src/views/tenant/workflows/index.vue` | `new/update` | 工作流列表 | 关键字查询口径已收窄到真实后端字段 |
| `backend/plugins/workflow-orchestration/frontend/src/views/tenant/workflows/detail.vue` | `new` | 工作流详情 | 无本轮行为修复 |
| `backend/plugins/workflow-orchestration/frontend/src/views/tenant/workflows/editor.vue` | `new` | 企业编辑器骨架 | 无本轮行为修复 |
| `backend/plugins/workflow-orchestration/frontend/src/views/tenant/runs/index.vue` | `new/update` | 运行列表 | 已移除虚假的 risk filter，动作 gating 统一走安全规则 |
| `backend/plugins/workflow-orchestration/frontend/src/views/tenant/runs/detail.vue` | `new/update` | 运行详情 | 已按 `availableActions -> can* -> status fallback` 收口 |
| `backend/plugins/workflow-orchestration/frontend/src/views/tenant/artifacts/index.vue` | `new/update` | Artifact 列表 | 状态筛选已对齐 AI-2 当前状态枚举 |
| `backend/plugins/workflow-orchestration/frontend/src/views/tenant/artifacts/detail.vue` | `new/update` | Artifact 详情与反馈 | 下载策略、禁用态、提示文案已收口 |
| `backend/plugins/workflow-orchestration/frontend/src/locales/tenant/zh-CN.ts` | `new/update` | 企业端中文 locale | 已补齐 AI-2 当前动态状态 / 分类 / 提示 |
| `backend/plugins/workflow-orchestration/frontend/src/locales/tenant/en-US.ts` | `new/update` | 企业端英文 locale | 已补齐 AI-2 当前动态状态 / 分类 / 提示 |
| `backend/plugins/workflow-orchestration/frontend/src/locales/tenant/index.ts` | `new` | 企业端 locale 导出聚合 | 无本轮变更 |
| `docs/design/ai-orchestration-platform/41-workflow-orchestration-delivery-kit-20260323/AI-4-handoff.md` | `update` | 本 handoff | 已改成当前 correctness 轮真实契约 |

## 2. 本轮 correctness 修复摘要

### 2.1 动态 i18n fallback

- `use-tenant-orchestration.ts` 现在的回退顺序为：
  1. 宿主 `shared.$t(key, params)`，仅当返回值不是原始 key / 相对 key / key 尾段时才认为是真翻译。
  2. 插件本地 locale（`src/locales/tenant/zh-CN.ts` / `en-US.ts`）。
  3. 调用点提供的显式 fallback。
  4. `humanizeCode(tail)`。
- 本地 locale fallback 支持 `{param}` 插值。
- 因此即使 integrator 尚未把 `plugin.workflowOrchestration.tenant` 注册进宿主 i18n，页面也不会把原始 key 直接展示给用户。

### 2.2 Artifact 下载链路

- 当前下载链路的行为顺序为：
  1. 先看后端是否允许下载：
     - `availableActions` 若存在，则必须包含 `download`
     - 否则回退 `canDownload !== false`
     - 且 `downloadAvailable !== false`
  2. 满足后端允许后，优先走 `requestClient.download('/tenant/plugins/workflow-orchestration/api/artifacts/{id}/download')`
  3. 若宿主未暴露 `requestClient.download`，且详情接口提供 `downloadUrl` / `signed downloadUrl`，则回退到 signed URL fetch
  4. 若两条通路都不可用，则按钮禁用，并展示明确提示文案
- 本轮**没有**继续增加“直接 fetch 插件下载端点”的第三条前端兜底，因为用户要求明确以 `requestClient.download` 优先、signed URL 次之；两者都不可用时应显式禁用，而不是继续发明额外路径。

### 2.3 Run 详情动作 gating

- 当前 Run 动作判定顺序为：
  1. `availableActions`
  2. `canPause/canResume/canRetry/canTerminate`
  3. 基于 `status` 的安全 fallback
- 状态 fallback 已按 AI-2 `runtime/constants.py` 收口：
  - `pause`：仅 `running`
  - `resume`：`paused` / `waiting_human` / `waiting_approval` / `waiting_input`
  - `retry`：仅 `failed`
  - `terminate`：`pending` / `queued` / `validating` / `planning` / `running` / `waiting_human` / `waiting_approval` / `waiting_input` / `paused` / `recovering` / `compensating`
- 运行列表和运行详情现在共用同一套 helper，不再各自维护不同规则。

### 2.4 Tenant list query 契约收口

- 本轮已把 `src/api/tenant.ts` 从“多别名并行追加”改成按资源维度收口：
  - `workflows`
    - `page[number]`
    - `page[size]`
    - `filter[name][ilike]`
    - `filter[status][in|eq]`
    - `filter[builder_mode][in]`
  - `runs`
    - `page[number]`
    - `page[size]`
    - `filter[code][ilike]`
    - `filter[status][in|eq]`
    - `filter[workflow_id][eq]`
  - `artifacts`
    - `page[number]`
    - `page[size]`
    - `filter[name][ilike]`
    - `filter[status][in|eq]`
    - `filter[artifact_type][in]`
    - `filter[workflow_id][eq]`
- 已删除继续发送的猜测型参数：
  - `filter[q]`
  - `filter[title][ilike]`
  - `filter[type][in]` 作为 Artifact 类型兼容参数
  - `filter[risk_level][in]`
- `runs/index.vue` 的 risk filter 已移除，因为 AI-2 当前 run list 后端并不支持 `risk_level` 过滤；继续保留只会制造伪筛选。

## 3. 依赖的 Tenant API

### 3.1 页面依赖 API

```text
GET    /tenant/plugins/workflow-orchestration/api/home
GET    /tenant/plugins/workflow-orchestration/api/builder-capabilities

GET    /tenant/plugins/workflow-orchestration/api/workflows
POST   /tenant/plugins/workflow-orchestration/api/workflows
GET    /tenant/plugins/workflow-orchestration/api/workflows/{workflow_id}
PUT    /tenant/plugins/workflow-orchestration/api/workflows/{workflow_id}
GET    /tenant/plugins/workflow-orchestration/api/workflows/{workflow_id}/versions
POST   /tenant/plugins/workflow-orchestration/api/workflows/{workflow_id}/publish
POST   /tenant/plugins/workflow-orchestration/api/workflows/{workflow_id}/run

GET    /tenant/plugins/workflow-orchestration/api/runs
GET    /tenant/plugins/workflow-orchestration/api/runs/{run_id}
POST   /tenant/plugins/workflow-orchestration/api/runs/{run_id}/pause
POST   /tenant/plugins/workflow-orchestration/api/runs/{run_id}/resume
POST   /tenant/plugins/workflow-orchestration/api/runs/{run_id}/retry
POST   /tenant/plugins/workflow-orchestration/api/runs/{run_id}/terminate

GET    /tenant/plugins/workflow-orchestration/api/artifacts
GET    /tenant/plugins/workflow-orchestration/api/artifacts/{artifact_id}
POST   /tenant/plugins/workflow-orchestration/api/artifacts/{artifact_id}/feedback
GET    /tenant/plugins/workflow-orchestration/api/artifacts/{artifact_id}/download
```

### 3.2 当前前端已消费的关键字段

- `home`
  - `summary.pending_approvals`
  - `summary.failed_runs`
  - `summary.pending_artifacts`
  - `summary.active_workflows`
  - `summary.running_now`
  - `summary.quota_warnings`
  - `todos[*].category`
  - `alerts[*].level`
  - `builder_capabilities`
  - `highlighted_workflows`
  - `latest_runs`
  - `latest_artifacts`
- `workflows`
  - `status`
  - `builder_mode`
  - `current_version`
  - `latest_run_status`
  - `pending_approvals`
  - `run_count_7d`
  - `success_rate_7d`
  - `can_edit`
  - `can_publish`
  - `can_execute`
- `runs`
  - `status`
  - `status_bucket`
  - `available_actions`
  - `can_pause`
  - `can_resume`
  - `can_retry`
  - `can_terminate`
  - `risk_level`
  - `artifact_count`
  - `node_runs`
  - `artifacts`
  - `approvals`
  - `recovery_events`
  - `checkpoints`
  - `execution_graph`
- `artifacts`
  - `artifact_type`
  - `status`
  - `available_actions`
  - `can_feedback`
  - `can_download`
  - `download_available`
  - `download_filename`
  - `downloadUrl` / `download_url`（若未来提供 signed URL）
  - `feedback[*].decision/comments/rating/submitted_at` 或兼容字段

## 4. 当前字段与枚举口径

### 4.1 Run 状态

- 已对齐 AI-2 当前真值：
  - `pending`
  - `queued`
  - `validating`
  - `planning`
  - `running`
  - `waiting_human`
  - `waiting_approval`
  - `waiting_input`
  - `paused`
  - `recovering`
  - `compensating`
  - `succeeded`
  - `completed`
  - `partially_completed`
  - `failed`
  - `cancelled`
- 前端仍保留 `terminated` 作为 legacy label 兼容值，但不再把它当作 AI-2 当前真状态。

### 4.2 Artifact 状态

- 已对齐 AI-2 当前真值：
  - `draft`
  - `ready`
  - `adopted`
  - `rejected`
  - `archived`
  - `expired`
  - `failed`
- 前端仍保留 `pending_review` / `returned` 的 label 兼容，以防集成阶段短时间拿到旧 payload；但列表筛选已不再把它们当当前真值。

### 4.3 Todo / Alert 分类

- AI-2 当前首页 todo 分类：
  - `approval_todo`
  - `recovery_todo`
  - `artifact_review_todo`
  - `context_fix_todo`
  - `activation_todo`
  - `quota_warning_todo`
- Tenant locale 已补齐这些分类，避免再回退成生硬的 humanized 英文。

## 5. 需要 integrator 接入的共享项

### 5.1 `plugin.yaml frontend.pages`

```yaml
frontend:
  pages:
    - path: /tenant/plugins/workflow-orchestration
      component: WorkflowOrchestrationTenantHome
    - path: /tenant/plugins/workflow-orchestration/workflows
      component: WorkflowOrchestrationTenantWorkflowList
    - path: /tenant/plugins/workflow-orchestration/workflows/new
      component: WorkflowOrchestrationTenantWorkflowEditor
    - path: /tenant/plugins/workflow-orchestration/workflows/:id
      component: WorkflowOrchestrationTenantWorkflowDetail
    - path: /tenant/plugins/workflow-orchestration/workflows/:id/editor
      component: WorkflowOrchestrationTenantWorkflowEditor
    - path: /tenant/plugins/workflow-orchestration/runs
      component: WorkflowOrchestrationTenantRunList
    - path: /tenant/plugins/workflow-orchestration/runs/:runId
      component: WorkflowOrchestrationTenantRunDetail
    - path: /tenant/plugins/workflow-orchestration/artifacts
      component: WorkflowOrchestrationTenantArtifactList
    - path: /tenant/plugins/workflow-orchestration/artifacts/:artifactId
      component: WorkflowOrchestrationTenantArtifactDetail
```

### 5.2 `frontend/src/index.ts` 组件导出映射

```ts
export { default as WorkflowOrchestrationTenantHome } from './views/tenant/home/index.vue';
export { default as WorkflowOrchestrationTenantWorkflowList } from './views/tenant/workflows/index.vue';
export { default as WorkflowOrchestrationTenantWorkflowDetail } from './views/tenant/workflows/detail.vue';
export { default as WorkflowOrchestrationTenantWorkflowEditor } from './views/tenant/workflows/editor.vue';
export { default as WorkflowOrchestrationTenantRunList } from './views/tenant/runs/index.vue';
export { default as WorkflowOrchestrationTenantRunDetail } from './views/tenant/runs/detail.vue';
export { default as WorkflowOrchestrationTenantArtifactList } from './views/tenant/artifacts/index.vue';
export { default as WorkflowOrchestrationTenantArtifactDetail } from './views/tenant/artifacts/detail.vue';
```

### 5.3 `frontend/src/api/index.ts` 导出项

```ts
export * from './tenant';
```

### 5.4 路由与 locale 接线

- 路由片段：

```ts
[
  {
    path: '/tenant/plugins/workflow-orchestration',
    component: WorkflowOrchestrationTenantHome,
  },
  {
    path: '/tenant/plugins/workflow-orchestration/workflows',
    component: WorkflowOrchestrationTenantWorkflowList,
  },
  {
    path: '/tenant/plugins/workflow-orchestration/workflows/new',
    component: WorkflowOrchestrationTenantWorkflowEditor,
  },
  {
    path: '/tenant/plugins/workflow-orchestration/workflows/:id',
    component: WorkflowOrchestrationTenantWorkflowDetail,
  },
  {
    path: '/tenant/plugins/workflow-orchestration/workflows/:id/editor',
    component: WorkflowOrchestrationTenantWorkflowEditor,
  },
  {
    path: '/tenant/plugins/workflow-orchestration/runs',
    component: WorkflowOrchestrationTenantRunList,
  },
  {
    path: '/tenant/plugins/workflow-orchestration/runs/:runId',
    component: WorkflowOrchestrationTenantRunDetail,
  },
  {
    path: '/tenant/plugins/workflow-orchestration/artifacts',
    component: WorkflowOrchestrationTenantArtifactList,
  },
  {
    path: '/tenant/plugins/workflow-orchestration/artifacts/:artifactId',
    component: WorkflowOrchestrationTenantArtifactDetail,
  },
]
```

- locale 导出：

```ts
export {
  enUS as workflowOrchestrationTenantEnUS,
  zhCN as workflowOrchestrationTenantZhCN,
} from './tenant';
```

- 宿主注册：

```ts
import {
  enUS as workflowOrchestrationTenantEnUS,
  zhCN as workflowOrchestrationTenantZhCN,
} from './locales/tenant';

shared?.registerLocale?.(
  'zh-CN',
  'plugin.workflowOrchestration.tenant',
  workflowOrchestrationTenantZhCN,
);
shared?.registerLocale?.(
  'zh',
  'plugin.workflowOrchestration.tenant',
  workflowOrchestrationTenantZhCN,
);
shared?.registerLocale?.(
  'en-US',
  'plugin.workflowOrchestration.tenant',
  workflowOrchestrationTenantEnUS,
);
shared?.registerLocale?.(
  'en',
  'plugin.workflowOrchestration.tenant',
  workflowOrchestrationTenantEnUS,
);
```

## 6. 已知字段假设

- `downloadUrl` / `download_url`
  - 前端已支持，但 AI-2 当前 backend truth 里主下载通路仍是 `/artifacts/{id}/download`。
  - 若后端不返回 signed URL，且宿主没暴露 `requestClient.download`，下载会明确禁用。
- `feedback[*]`
  - 当前兼容 `comment/comments`、`kind/type/decision`、`created_at/submitted_at`。
  - 这是为了兼容 AI-2 当前 `feedback_summary` 序列化形态。
- `status_bucket`
  - 已接入类型和 normalizer，但当前动作安全规则仍优先用 `availableActions` 或细分 `status`，不依赖 bucket 做放权判断。
- `runs` 搜索
  - 当前只按 `filter[code][ilike]` 发请求，因为 AI-2 当前 run list 后端没有 joined `workflow_name` / derived `name` 搜索能力。
- `workflows` / `artifacts` 搜索
  - 当前只按 `filter[name][ilike]` 发请求，不再发 `title/q` 等猜测字段。

## 7. 测试与静态验证结果

### 7.1 已完成

- `pnpm exec vue-tsc --noEmit --pretty false -p %TEMP%/workflow-orchestration-tenant-check/tsconfig.json`
  - 结果：`passed`
  - 说明：使用临时 tsconfig，仅覆盖本插件 tenant 范围文件，并显式指向 `frontend/apps/web-antd/node_modules` 下的 `vue` / `vue-router` 类型入口。
- locale key 对齐检查
  - `zh-CN.ts`：`323`
  - `en-US.ts`：`323`
  - `missingInZh = []`
  - `missingInEn = []`
- tenant 范围中文硬编码扫描
  - 范围：`views/tenant/**`、`api/tenant.ts`、`types/tenant.ts`
  - 结果：无命中
- literal i18n key 覆盖检查
  - 静态引用 key：`259`
  - 动态拼接产生的 family 前缀：`artifact.status.*`、`artifact.type.*`、`capability.labels.*`、`capability.locked.*`、`capability.state.*`、`common.risk.*`、`common.severity.*`、`common.todoCategory.*`、`common.tones.*`、`run.status.*`、`workflow.builderMode.*`、`workflow.status.*`
  - family 覆盖结果：全部存在对应 locale keys

### 7.2 未完成

- 浏览器级挂载 / 交互冒烟未执行
  - 原因：`plugin.yaml frontend.pages`、`frontend/src/index.ts`、`frontend/src/api/index.ts`、`frontend/src/locales/index.ts` 仍属于冻结文件，尚需 integrator 接线后才能从宿主实际挂载 tenant 页面。

## 8. 仍依赖 AI-2 / integrator 的项目

### 8.1 仍依赖 AI-2

- 若 AI-2 后续补充 `downloadUrl` / `signed downloadUrl`，tenant 详情页会自动启用第二下载通路，无需再改 UI。
- 若 AI-2 后续新增 run / workflow / artifact 的真实关键词搜索字段，应同步回流给 `src/api/tenant.ts`，而不是继续在前端猜测别名。
- `approvalStatus` 仍展示原始值，因为 AI-2 handoff 没有给出稳定枚举翻译真相。

### 8.2 仍依赖 integrator

- 冻结文件接线：
  - `plugin.yaml frontend.pages`
  - `frontend/src/index.ts`
  - `frontend/src/api/index.ts`
  - `frontend/src/locales/index.ts`
- 宿主共享能力：
  - `NovusPluginShared.requestClient.download`
  - `NovusPluginShared.registerLocale`
  - `NovusPluginShared.router`
- 若 integrator 未接入 `requestClient.download`，而后端又未提供 signed `downloadUrl`，Artifact 下载会保持禁用，这属于当前设计的显式保护行为，不是前端 bug。
