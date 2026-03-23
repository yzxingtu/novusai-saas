# AI 编排与工作流平台任务编排模块插件实施清单（2026-03-23）

## 一、文档目标

本文把 [39-orchestration-module-pluginization-strategy-20260323.md](./39-orchestration-module-pluginization-strategy-20260323.md) 的架构结论继续下沉为“可以直接进入研发拆解”的实施清单。

本文重点回答：

1. 任务编排模块插件第一版到底要交付什么。
2. 需要复用宿主哪些能力，不能重复造哪些轮子。
3. `plugin.yaml` 草案怎么写。
4. 需要落哪些表、哪些页面、哪些 API、哪些权限。
5. 开发顺序应该怎么排，验收应该看什么。

本文是“落地实施清单”，不是最终代码设计稿；但会尽量贴合当前仓库插件系统的真实约束。

## 0. 2026-03-24 对账说明

本文是规划实施清单，不再等同于当前仓库真相。到 2026-03-24 为止，以下内容必须以代码为准，本文对应章节仅可作为历史规划参考：

- 配置真相：
  当前插件已不再通过 manifest `config_schema` / `tenant_config_schema` 承载运行配置。
  当前真实来源是插件运行时上下文 `ctx.get_config()` / `ctx.get_tenant_config()`，以及插件自表 `px_workflow_orchestration_module_configs`。
- 页面与 API 真相：
  当前实际页面以 `backend/plugins/workflow-orchestration/plugin.yaml` 的 `frontend.pages` 为准。
  当前实际 API 以 `plugin.yaml` 的 `admin_routes` / `tenant_routes` / `public_routes` 为准。
  本文后续出现的 `admin settings` 页面、`tenant settings` 页面、`workflows/new`、`metrics` 页面等规划项，若未出现在当前 `plugin.yaml` 中，应视为未落地规划项，不得当成现网事实。
- 前端入口真相：
  当前插件页面挂载链路已经依赖 `frontend/src/index.ts` 真实导出与 `plugin.yaml frontend.pages[*].component` 对齐。
  本文后续提到的 `frontend/src/api/index.ts`、`frontend/src/locales/index.ts` 只是早期规划占位，不是当前宿主挂载所必需的集成前提。
- 运行态状态真相：
  当前运行态状态集合以 `backend/plugins/workflow-orchestration/backend/runtime/constants.py` 为准。
  本文若仍使用早期精简状态集合，只能视为概念化表达，不能直接指导联调或测试断言。

---

## 二、第一版实施目标

### 2.1 第一版正式目标

第一版任务编排模块插件建议以 `workflow-orchestration` 为正式插件名，交付为一个可安装、可启用、可授权、可禁用、可卸载的产品模块插件。

这里的“产品模块插件”是产品语义，不要求主项目先新增 `product_module_plugin` 这种一等字段；第一版仍按当前仓库标准插件模型落地，并通过 `extensions.custom` 声明模块元数据。

第一版必须具备：

- 管理端任务编排工作台
- 企业端任务编排与运行控制台
- 平台模板管理
- 企业工作流副本与简单构建
- 运行实例、节点运行、Artifact 管理
- 插件级权限、菜单、API、定时任务
- 可按企业授权开通

### 2.2 第一版明确不做

第一版不建议做：

- 依赖插件 `middleware` 的核心运行链路
- 依赖插件 `consumer` 的核心状态机
- 跨宿主任意核心表的自由读写
- 企业端代码执行节点
- 企业端新增连接器或执行器
- 平台级活体编辑生产内核

### 2.3 第一版成功标准

第一版成功，不是“功能越多越好”，而是满足以下四条：

- 插件安装后，管理端与已授权企业端都能进入模块页面
- 插件禁用后，模块页面、API、任务入口都能立即收口
- 插件卸载后，模块自有数据和扩展点能被清理
- 行业方案插件后续可以通过依赖关系挂在该模块之上
- 整个实施过程不需要向 `backend/app/**` 或主系统前端源码落任何业务文件

---

## 三、当前仓库现实约束与实施口径

### 3.1 当前仓库第一版应优先复用的现成能力

以下能力当前仓库已经具备，第一版应直接复用：

- 插件生命周期
- 插件运行时 gate
- 插件页面与统一 API dispatcher
- 插件菜单与权限同步
- 插件定时任务
- 插件通知
- 插件 AI 调用能力
- 插件 namespaced storage
- 企业范围可见性控制

### 3.2 当前仓库第一版不应等待的未来统一模型

规划文档里提到了一些未来统一抽象，例如：

- `TenantEntitlement`
- 更正式的产品模块类型字段
- 更完备的统一审批 / 审计 / 计量治理能力

这些是对的，但第一版不能因此停住不做。

第一版的实际落地口径建议是：

- 企业可见性先复用 `Plugin.scope + ResourceTenantAssignment + runtime gate`
- 产品模块类型先通过 `extensions.custom` 写元数据
- 安装、启用、禁用、卸载继续走宿主已有插件生命周期

等统一模型补齐后，再把这部分语义收敛回正式字段。

### 3.3 第一版必须承认的插件沙箱边界

当前插件框架有三个关键硬边界：

1. 插件 DB 默认只能访问自有 `px_{plugin}_*` 表。
2. 插件前端页面必须挂在 `/admin/plugins/*` 或 `/tenant/plugins/*`。
3. `middleware` / `consumer` 完全热拔除并不可靠。

因此第一版任务编排模块的核心链路必须建立在：

- 插件自有表
- 插件标准页面
- 插件标准 API
- 插件标准任务扩展

而不是建立在“我先绕过边界，后面再补”这种做法上。

### 3.4 零宿主落地实施约束

本模块第一版必须补一条硬约束：

- 只允许在 `backend/plugins/workflow-orchestration/**` 内落实现
- 不允许修改 `backend/app/**`
- 不允许把插件页面、locale、API 或业务逻辑落到主系统源码
- 如果某项能力需要主项目先补扩展口、上下文字段或 manifest 字段，说明它不属于第一版可实施范围

所以第一版的实施口径必须是：

- 能在插件内闭环的，就做
- 需要宿主新增能力的，就延期
- 能先用插件内 `human_review`、事件表、结构化日志、插件自有存储承接的，就先在插件内自包含

---

## 四、插件交付包目录

建议第一版插件目录为：

```text
backend/plugins/workflow-orchestration/
├── plugin.yaml
├── README.md
├── backend/
│   ├── main.py
│   ├── api/
│   │   ├── admin_overview.py
│   │   ├── admin_templates.py
│   │   ├── admin_releases.py
│   │   ├── admin_runtime.py
│   │   ├── admin_settings.py
│   │   ├── tenant_home.py
│   │   ├── tenant_workflows.py
│   │   ├── runs.py
│   │   └── artifacts.py
│   ├── services/
│   │   ├── template_service.py
│   │   ├── tenant_workflow_service.py
│   │   ├── run_service.py
│   │   ├── artifact_service.py
│   │   └── release_service.py
│   ├── runtime/
│   │   ├── compiler.py
│   │   ├── dispatcher.py
│   │   ├── node_executor.py
│   │   ├── recovery.py
│   │   └── schema_validator.py
│   ├── tasks/
│   │   ├── run_timeout_sweeper.py
│   │   ├── run_retry_dispatcher.py
│   │   └── artifact_retention.py
│   ├── models/
│   ├── schemas/
│   ├── seed/
│   └── migrations/
├── frontend/
│   ├── src/
│   │   ├── index.ts
│   │   ├── api/
│   │   ├── views/
│   │   ├── components/
│   │   └── locales/
│   └── dist/
└── locales/
    ├── zh-CN.json
    └── en.json
```

### 4.1 目录职责

- `backend/main.py` 只放生命周期、初始化和注册入口
- `backend/api/` 只做路由分发和参数收口
- `backend/services/` 放业务逻辑
- `backend/runtime/` 放编排运行时
- `backend/tasks/` 放周期任务或后台状态推进任务
- `frontend/views/` 放页面
- `frontend/api/` 放插件前端接口封装

---

## 五、`plugin.yaml` 草案

### 5.1 实施原则

下面这个草案优先遵守“当前仓库已经支持的 manifest 结构”。

其中：

- “这是产品模块插件”的身份先写在 `extensions.custom`
- 企业作用域先用 `scope: admin_and_selected_tenants`
- 企业安装授权继续复用宿主插件市场和分配机制

### 5.2 草案示例

下面示例已经按 2026-03-24 当前仓库真相收口，来源以
`backend/plugins/workflow-orchestration/plugin.yaml` 为准。

但仍要明确：

- 这是一份**同步后的关键子集示例**
- 真实执行时应直接以仓库内 `plugin.yaml` 文件为单一事实来源
- 模块运行配置不再通过 manifest `config_schema` / `tenant_config_schema` 承载
- 集成人必须核对 `plugin.yaml`、第八章页面树、第九章 API 清单三者是否一致
```yaml
name: workflow-orchestration
version: "1.0.0"
display_name:
  zh-CN: "任务编排"
  en: "Workflow Orchestration"
description:
  zh-CN: "可安装的任务编排产品模块，提供模板管理、运行控制、Artifact 管理与企业轻编排。"
  en: "Installable workflow orchestration product module with template management, runtime control, artifact management and tenant-safe builder surfaces."
author: "NovusAI"
icon: ""
scope: admin_and_selected_tenants
tags: ["workflow", "orchestration", "product-module"]

capabilities:
  - db:own_tables
  - storage:read
  - storage:write
  - ai:call
  - notifications:send

dependencies:
  python: []
  plugins: []

pricing:
  type: paid
  price: 9999
  currency: CNY
  trial:
    enabled: false
    days: 14

extensions:
  custom:
    - type: product_module
      name: workflow_orchestration
      description: "Workflow orchestration product module with zero-host persistence boundary"
      data:
        module_kind: product_module
        module_code: workflow_orchestration
        deployment_mode: plugin_only
        host_footprint: none
        persistence_mode: plugin_tables_only
        delivery_status: integrated_dev_runtime
        builder_surfaces:
          - platform_workflow_studio
          - tenant_template_editor
          - tenant_simple_builder

  permissions:
    - code: orchestration_admin
      scope: admin
      actions: [view, configure]
    - code: platform_template
      scope: admin
      actions: [list, view, create, edit, publish]
    - code: release_ops
      scope: admin
      actions: [list, view, rollback]
    - code: runtime_ops
      scope: admin
      actions: [list, view, replay, recover, terminate]
    - code: workflow_center
      scope: tenant
      actions: [list, view]
    - code: workflow_builder
      scope: tenant
      actions: [create, copy, edit, publish]
    - code: workflow_run
      scope: tenant
      actions: [list, view, execute, pause, resume, retry, terminate]
    - code: artifact_center
      scope: tenant
      actions: [list, view, edit, export, feedback]

  notifications:
    - code: run_failed
      title:
        zh-CN: "运行失败"
        en: "Run Failed"
      channels: ["ws", "inbox"]
      category: "biz"
    - code: artifact_ready
      title:
        zh-CN: "产物已生成"
        en: "Artifact Ready"
      channels: ["ws", "inbox"]
      category: "biz"

  tasks:
    - name: workflow_run_timeout_sweeper
      handler: "tasks.run_timeout_sweeper.handle"
      schedule_type: interval
      interval_seconds: 300
      queue: default
    - name: workflow_run_retry_dispatcher
      handler: "tasks.run_retry_dispatcher.handle"
      schedule_type: interval
      interval_seconds: 120
      queue: default
    - name: workflow_artifact_retention
      handler: "tasks.artifact_retention.handle"
      schedule_type: interval
      interval_seconds: 3600
      queue: default

  api:
    admin_routes:
      - method: GET
        path: overview
        handler: "api.admin_overview.get_overview"
        permission: "orchestration_admin:view"
      - method: GET
        path: metrics
        handler: "api.admin_overview.get_metrics"
        permission: "orchestration_admin:view"
      - method: GET
        path: templates
        handler: "api.admin_templates.list_templates"
        permission: "platform_template:list"
      - method: POST
        path: templates
        handler: "api.admin_templates.create_template"
        permission: "platform_template:create"
      - method: GET
        path: "templates/{template_id}"
        handler: "api.admin_templates.get_template_detail"
        permission: "platform_template:view"
      - method: PUT
        path: "templates/{template_id}"
        handler: "api.admin_templates.update_template"
        permission: "platform_template:edit"
      - method: GET
        path: "templates/{template_id}/versions"
        handler: "api.admin_templates.list_template_versions"
        permission: "platform_template:view"
      - method: POST
        path: "templates/{template_id}/publish"
        handler: "api.admin_releases.publish_template"
        permission: "platform_template:publish"
      - method: GET
        path: releases
        handler: "api.admin_releases.list_releases"
        permission: "release_ops:list"
      - method: POST
        path: "releases/{release_id}/rollback"
        handler: "api.admin_releases.rollback_release"
        permission: "release_ops:rollback"
      - method: GET
        path: settings
        handler: "api.admin_settings.get_settings"
        permission: "orchestration_admin:view"
      - method: PUT
        path: settings
        handler: "api.admin_settings.update_settings"
        permission: "orchestration_admin:configure"
      - method: GET
        path: runs
        handler: "api.admin_runtime.list_runs"
        permission: "runtime_ops:list"
      - method: GET
        path: "runs/{run_id}"
        handler: "api.admin_runtime.get_run_detail"
        permission: "runtime_ops:view"
      - method: POST
        path: "runs/{run_id}/replay"
        handler: "api.admin_runtime.replay_run"
        permission: "runtime_ops:replay"
      - method: POST
        path: "runs/{run_id}/recover"
        handler: "api.admin_runtime.recover_run"
        permission: "runtime_ops:recover"
      - method: POST
        path: "runs/{run_id}/terminate"
        handler: "api.admin_runtime.terminate_run"
        permission: "runtime_ops:terminate"

    tenant_routes:
      - method: GET
        path: home
        handler: "api.tenant_home.get_home"
        permission: "workflow_center:view"
      - method: GET
        path: "builder-capabilities"
        handler: "api.tenant_home.get_builder_capabilities"
        permission: "workflow_center:view"
      - method: GET
        path: workflows
        handler: "api.tenant_workflows.list_workflows"
        permission: "workflow_center:list"
      - method: POST
        path: workflows
        handler: "api.tenant_workflows.create_workflow"
        permission: "workflow_builder:create"
      - method: POST
        path: "workflows/copy-from-template"
        handler: "api.tenant_workflows.copy_from_template"
        permission: "workflow_builder:copy"
      - method: GET
        path: "workflows/{workflow_id}"
        handler: "api.tenant_workflows.get_workflow_detail"
        permission: "workflow_center:view"
      - method: PUT
        path: "workflows/{workflow_id}"
        handler: "api.tenant_workflows.update_workflow"
        permission: "workflow_builder:edit"
      - method: GET
        path: "workflows/{workflow_id}/versions"
        handler: "api.tenant_workflows.list_workflow_versions"
        permission: "workflow_center:view"
      - method: POST
        path: "workflows/{workflow_id}/publish"
        handler: "api.tenant_workflows.publish_workflow"
        permission: "workflow_builder:publish"
      - method: POST
        path: "workflows/{workflow_id}/run"
        handler: "api.runs.create_run"
        permission: "workflow_run:execute"
      - method: GET
        path: runs
        handler: "api.runs.tenant_list_runs"
        permission: "workflow_run:list"
      - method: GET
        path: "runs/{run_id}"
        handler: "api.runs.tenant_get_run_detail"
        permission: "workflow_run:view"
      - method: POST
        path: "runs/{run_id}/pause"
        handler: "api.runs.tenant_pause_run"
        permission: "workflow_run:pause"
      - method: POST
        path: "runs/{run_id}/resume"
        handler: "api.runs.tenant_resume_run"
        permission: "workflow_run:resume"
      - method: POST
        path: "runs/{run_id}/retry"
        handler: "api.runs.tenant_retry_run"
        permission: "workflow_run:retry"
      - method: POST
        path: "runs/{run_id}/terminate"
        handler: "api.runs.tenant_terminate_run"
        permission: "workflow_run:terminate"
      - method: GET
        path: artifacts
        handler: "api.artifacts.list_artifacts"
        permission: "artifact_center:list"
      - method: GET
        path: "artifacts/{artifact_id}"
        handler: "api.artifacts.get_artifact_detail"
        permission: "artifact_center:view"
      - method: POST
        path: "artifacts/{artifact_id}/feedback"
        handler: "api.artifacts.submit_feedback"
        permission: "artifact_center:feedback"
      - method: GET
        path: "artifacts/{artifact_id}/download"
        handler: "api.artifacts.download_artifact"
        permission: "artifact_center:export"

  frontend:
    pages:
      - name: workflow-orchestration-admin-home
        path: /admin/plugins/workflow-orchestration
        component: "WorkflowOrchestrationAdminHomePage"
        scope: admin
        icon: "lucide:workflow"
        title:
          zh-CN: "任务编排"
          en: "Workflow Orchestration"
        menu:
          icon: "lucide:workflow"
          sort_order: 70
          title:
            zh-CN: "任务编排"
            en: "Workflow Orchestration"
      - name: workflow-orchestration-admin-templates
        path: /admin/plugins/workflow-orchestration/templates
        component: "WorkflowOrchestrationAdminTemplateListPage"
        scope: admin
        icon: "lucide:copy-plus"
        title:
          zh-CN: "平台模板"
          en: "Templates"
        menu:
          icon: "lucide:copy-plus"
          parent: workflow-orchestration-admin-home
          sort_order: 71
          title:
            zh-CN: "平台模板"
            en: "Templates"
      - name: workflow-orchestration-admin-template-detail
        path: /admin/plugins/workflow-orchestration/templates/:id
        component: "WorkflowOrchestrationAdminTemplateDetailPage"
        scope: admin
        icon: "lucide:copy-check"
        title:
          zh-CN: "模板详情"
          en: "Template Detail"
      - name: workflow-orchestration-admin-template-editor
        path: /admin/plugins/workflow-orchestration/templates/:id/editor
        component: "WorkflowOrchestrationAdminTemplateEditorPage"
        scope: admin
        icon: "lucide:spline"
        title:
          zh-CN: "模板编辑器"
          en: "Template Editor"
      - name: workflow-orchestration-admin-releases
        path: /admin/plugins/workflow-orchestration/releases
        component: "WorkflowOrchestrationAdminReleaseListPage"
        scope: admin
        icon: "lucide:rocket"
        title:
          zh-CN: "发布管理"
          en: "Releases"
        menu:
          icon: "lucide:rocket"
          parent: workflow-orchestration-admin-home
          sort_order: 72
          title:
            zh-CN: "发布管理"
            en: "Releases"
      - name: workflow-orchestration-admin-runtime
        path: /admin/plugins/workflow-orchestration/runtime
        component: "WorkflowOrchestrationAdminRuntimePage"
        scope: admin
        icon: "lucide:activity"
        title:
          zh-CN: "运行治理"
          en: "Runtime"
        menu:
          icon: "lucide:activity"
          parent: workflow-orchestration-admin-home
          sort_order: 73
          title:
            zh-CN: "运行治理"
            en: "Runtime"
      - name: workflow-orchestration-tenant-home
        path: /tenant/plugins/workflow-orchestration
        component: "WorkflowOrchestrationTenantHomePage"
        scope: tenant
        icon: "lucide:workflow"
        title:
          zh-CN: "任务编排"
          en: "Workflow Orchestration"
        menu:
          icon: "lucide:workflow"
          sort_order: 70
          title:
            zh-CN: "任务编排"
            en: "Workflow Orchestration"
      - name: workflow-orchestration-tenant-workflows
        path: /tenant/plugins/workflow-orchestration/workflows
        component: "WorkflowOrchestrationTenantWorkflowListPage"
        scope: tenant
        icon: "lucide:blocks"
        title:
          zh-CN: "工作流中心"
          en: "Workflows"
        menu:
          icon: "lucide:blocks"
          parent: workflow-orchestration-tenant-home
          sort_order: 71
          title:
            zh-CN: "工作流中心"
            en: "Workflows"
      - name: workflow-orchestration-tenant-workflow-detail
        path: /tenant/plugins/workflow-orchestration/workflows/:id
        component: "WorkflowOrchestrationTenantWorkflowDetailPage"
        scope: tenant
        icon: "lucide:scan-search"
        title:
          zh-CN: "工作流详情"
          en: "Workflow Detail"
      - name: workflow-orchestration-tenant-workflow-editor
        path: /tenant/plugins/workflow-orchestration/workflows/:id/editor
        component: "WorkflowOrchestrationTenantWorkflowEditorPage"
        scope: tenant
        icon: "lucide:square-pen"
        title:
          zh-CN: "工作流编辑器"
          en: "Workflow Editor"
      - name: workflow-orchestration-tenant-runs
        path: /tenant/plugins/workflow-orchestration/runs
        component: "WorkflowOrchestrationTenantRunListPage"
        scope: tenant
        icon: "lucide:activity"
        title:
          zh-CN: "运行中心"
          en: "Runs"
        menu:
          icon: "lucide:activity"
          parent: workflow-orchestration-tenant-home
          sort_order: 72
          title:
            zh-CN: "运行中心"
            en: "Runs"
      - name: workflow-orchestration-tenant-run-detail
        path: /tenant/plugins/workflow-orchestration/runs/:runId
        component: "WorkflowOrchestrationTenantRunDetailPage"
        scope: tenant
        icon: "lucide:list-tree"
        title:
          zh-CN: "运行详情"
          en: "Run Detail"
      - name: workflow-orchestration-tenant-artifacts
        path: /tenant/plugins/workflow-orchestration/artifacts
        component: "WorkflowOrchestrationTenantArtifactListPage"
        scope: tenant
        icon: "lucide:package-search"
        title:
          zh-CN: "产物中心"
          en: "Artifacts"
        menu:
          icon: "lucide:package-search"
          parent: workflow-orchestration-tenant-home
          sort_order: 73
          title:
            zh-CN: "产物中心"
            en: "Artifacts"
      - name: workflow-orchestration-tenant-artifact-detail
        path: /tenant/plugins/workflow-orchestration/artifacts/:artifactId
        component: "WorkflowOrchestrationTenantArtifactDetailPage"
        scope: tenant
        icon: "lucide:file-output"
        title:
          zh-CN: "产物详情"
          en: "Artifact Detail"
    dev:
      entry: "src/index.ts"
    release:
      manifest: "plugin.manifest.json"
```

### 5.3 草案说明

- “产品模块插件”语义目前先用 `extensions.custom` 表达，不直接假设 manifest 已支持新的顶层类型字段。
- 企业启用能力不需要在本插件内重做安装逻辑，继续走宿主插件市场与插件分配机制。
- 路由权限值应使用 `code:action` 形式，例如 `workflow_builder:create`。
- 当前运行配置真相是 `ctx.get_config()` / `ctx.get_tenant_config()` 与
  `px_workflow_orchestration_module_configs`，不再使用 manifest schema 承载配置。
- `scope` 必须使用当前仓库已支持的 `ResourceScopeEnum` 值；本模块第一版应使用 `admin_and_selected_tenants`。
- `frontend.pages` 是当前插件前端页面路由的单一事实来源；凡是需要直接访问 URL 的页面，都应在这里显式声明。
- 如果后续把某些详情页改成同页签 / Drawer / Modal 承载，就必须同步收敛第八章页面树，不能保留失真的独立路由清单。
- `api.handler` 路径必须与实际 `backend/api/*.py` 文件布局一致，避免文档示例与 4 AI 文件所有权冲突。
- `pricing.type = paid` 时，建议在草案中同时给出 `price / currency / trial` 字段，避免安装预览阶段出现缺项警告。
- 上述 `price` 仅为清单结构示意值，不代表最终商业定价。

---

## 六、数据模型实施清单

### 6.1 应直接复用的宿主对象

第一版直接复用以下宿主对象，不再重复建模：

| 宿主对象 | 用途 |
|---|---|
| `Plugin` | 插件发行、安装、启用、禁用、卸载 |
| `PluginVersion` | 插件版本与升级记录 |
| `ResourceTenantAssignment` | 指定企业可见性与企业级配置 |
| `PluginLicense` / runtime gate | 运行授权与可用性判断 |
| `Permission` | 菜单与动作权限 |
| 宿主通知系统 | 模块消息提醒 |
| 宿主 AI 链路 | 模块级 AI 调用与 AI 能力编排 |

### 6.2 插件自有表清单

以下表以当前迁移链 `wo_001_init` + `wo_002_wf_ver_nullable_fix`
为准，表示已经进入插件自有持久化真相的对象。

表前缀统一为：

- `px_workflow_orchestration_`

建议表清单：

| 表名 | 作用 | 是否第一版必做 |
|---|---|---|
| `px_workflow_orchestration_templates` | 平台模板定义头信息 | 是 |
| `px_workflow_orchestration_template_versions` | 模板版本快照 | 是 |
| `px_workflow_orchestration_template_nodes` | 模板节点明细 | 是 |
| `px_workflow_orchestration_template_edges` | 模板边明细 | 是 |
| `px_workflow_orchestration_environments` | 发布环境定义 | 是 |
| `px_workflow_orchestration_change_sets` | 变更集快照 | 是 |
| `px_workflow_orchestration_triggers` | 触发器定义与绑定 | 是 |
| `px_workflow_orchestration_releases` | 发布记录 | 是 |
| `px_workflow_orchestration_module_configs` | 模块平台/企业配置真相 | 是 |
| `px_workflow_orchestration_tenant_workflows` | 企业工作流副本头信息 | 是 |
| `px_workflow_orchestration_tenant_workflow_versions` | 企业工作流版本快照 | 是 |
| `px_workflow_orchestration_runs` | 运行实例头信息 | 是 |
| `px_workflow_orchestration_node_runs` | 节点运行明细 | 是 |
| `px_workflow_orchestration_checkpoints` | 恢复点与快照 | 是 |
| `px_workflow_orchestration_events` | 运行事件流、人工接管、恢复记录 | 是 |
| `px_workflow_orchestration_artifacts` | Artifact 元数据与引用 | 是 |

以下对象仍可继续作为规划，但到 2026-03-24 并未进入当前迁移链：

- 行业方案与模板绑定
- 运行到评估集或基准记录的关联
- 聚合指标与日报缓存

### 6.3 当前不在迁移链中的对象

以下对象当前不应被当成“已落地持久化真相”：

| 对象 | 第一版建议 |
|---|---|
| 模块运行配置 schema | 不再用 manifest `config_schema` / `tenant_config_schema` |
| 平台级模块设置 | 当前走 `ctx.get_config()` 与 `px_workflow_orchestration_module_configs` |
| 企业级模块设置 | 当前走 `ctx.get_tenant_config()` 与 `px_workflow_orchestration_module_configs` |
| 插件安装授权 | 用宿主插件授权与 scope 体系 |
| 插件菜单权限 | 用宿主权限同步机制 |

### 6.4 版本快照真相原则

第一版建议写死一条规则：

- 运行时真相以 `*_versions.snapshot_json` 为准。

也就是说：

- `template_nodes` / `template_edges` 是结构化查询和 UI 渲染友好层
- 但真正用于发布、运行、回滚的，是版本快照

这样能避免：

- UI 明细和运行时快照漂移
- 局部修改后难以还原完整执行图

### 6.5 Artifact 存储口径

第一版优先建议：

- Artifact 元数据放插件表
- Artifact 内容文件走插件 namespaced storage
- 页面下载和预览通过插件 API 暴露

这样第一版不依赖宿主附件桥接，也更符合“可卸载模块”的边界。

---

## 七、权限实施清单

### 7.1 管理端插件权限

建议定义以下管理端插件权限资源：

| 权限 code | actions | 说明 |
|---|---|---|
| `orchestration_admin` | `view` `configure` | 模块总览、指标与配置接口 |
| `platform_template` | `list` `view` `create` `edit` `publish` | 平台模板管理 |
| `release_ops` | `list` `view` `rollback` | 发布与回滚 |
| `runtime_ops` | `list` `view` `replay` `recover` `terminate` | 全局运行处置 |

### 7.2 企业端插件权限

建议定义以下企业端插件权限资源：

| 权限 code | actions | 说明 |
|---|---|---|
| `workflow_center` | `list` `view` | 浏览工作流和详情 |
| `workflow_builder` | `create` `copy` `edit` `publish` | 企业副本与简单构建 |
| `workflow_run` | `list` `view` `execute` `pause` `resume` `retry` `terminate` | 运行操作 |
| `artifact_center` | `list` `view` `edit` `export` `feedback` | 草稿、报告、反馈 |

### 7.3 权限设计规则

必须遵守：

- 路由里使用 `code:action`
- 插件真实权限码由系统自动补全为 `plugin.{plugin_name}.{code}`
- 企业端动作粒度优先围绕“看、建、发、跑、处置”
- 不要把每个按钮都拆成一个独立 permission code

---

## 八、页面树实施清单

### 8.1 管理端页面树

```text
/admin/plugins/workflow-orchestration
├── (index)                           模块首页，承载 overview/metrics/settings 数据入口
├── templates                         模板列表
├── templates/:id                     模板详情
├── templates/:id/editor              模板编辑器
├── releases                          发布中心
└── runtime                           全局运行中心
```

### 8.2 企业端页面树

```text
/tenant/plugins/workflow-orchestration
├── (index)                           企业首页
├── workflows                         工作流中心
├── workflows/:id                     工作流详情
├── workflows/:id/editor              工作流编辑器
├── runs                              运行列表
├── runs/:runId                       运行详情
├── artifacts                         Artifact 中心
└── artifacts/:artifactId             Artifact 详情
```

### 8.3 第一版页面开放规则

第一版建议：

- 模板编辑器在管理端完整开放
- 企业端编辑器只开放 `tenant_template_editor` 和 `tenant_simple_builder`
- `builder-capabilities` 当前是企业端 API，不是独立页面
- 企业端审批中心第一版不重复造独立系统，可从运行详情深链到宿主审批页
- 企业端首页重点展示“今日待处理”“运行异常”“待确认 Artifact”

---

## 九、API 实施清单

### 9.1 API 设计总原则

必须遵守：

- 安装、启用、禁用、卸载、企业分配不在模块插件 API 内重做
- 这些动作继续走宿主插件管理 API
- 模块插件只负责自己的业务 API

### 9.2 管理端 API 清单

建议第一版至少提供以下管理端 API：

| Method | Path | 权限 | 作用 |
|---|---|---|---|
| `GET` | `overview` | `orchestration_admin:view` | 模块首页概览 |
| `GET` | `metrics` | `orchestration_admin:view` | 模块指标汇总 |
| `GET` | `templates` | `platform_template:list` | 模板列表 |
| `POST` | `templates` | `platform_template:create` | 新建模板 |
| `GET` | `templates/{template_id}` | `platform_template:view` | 模板详情 |
| `PUT` | `templates/{template_id}` | `platform_template:edit` | 更新模板 |
| `GET` | `templates/{template_id}/versions` | `platform_template:view` | 模板版本列表 |
| `POST` | `templates/{template_id}/publish` | `platform_template:publish` | 发布模板 |
| `GET` | `releases` | `release_ops:list` | 发布记录列表 |
| `POST` | `releases/{release_id}/rollback` | `release_ops:rollback` | 回滚 |
| `GET` | `settings` | `orchestration_admin:view` | 读取模块配置 |
| `PUT` | `settings` | `orchestration_admin:configure` | 更新模块配置 |
| `GET` | `runs` | `runtime_ops:list` | 全局运行列表 |
| `GET` | `runs/{run_id}` | `runtime_ops:view` | 运行详情 |
| `POST` | `runs/{run_id}/replay` | `runtime_ops:replay` | 重放一条新运行 |
| `POST` | `runs/{run_id}/recover` | `runtime_ops:recover` | 从检查点恢复 |
| `POST` | `runs/{run_id}/terminate` | `runtime_ops:terminate` | 强制终止 |

### 9.3 企业端 API 清单

建议第一版至少提供以下企业端 API：

| Method | Path | 权限 | 作用 |
|---|---|---|---|
| `GET` | `home` | `workflow_center:view` | 企业首页 |
| `GET` | `builder-capabilities` | `workflow_center:view` | 当前企业可用构建能力 |
| `GET` | `workflows` | `workflow_center:list` | 工作流列表 |
| `POST` | `workflows` | `workflow_builder:create` | 新建简单工作流 |
| `POST` | `workflows/copy-from-template` | `workflow_builder:copy` | 从平台模板复制 |
| `GET` | `workflows/{workflow_id}` | `workflow_center:view` | 工作流详情 |
| `PUT` | `workflows/{workflow_id}` | `workflow_builder:edit` | 更新工作流 |
| `GET` | `workflows/{workflow_id}/versions` | `workflow_center:view` | 工作流版本列表 |
| `POST` | `workflows/{workflow_id}/publish` | `workflow_builder:publish` | 发布企业工作流 |
| `POST` | `workflows/{workflow_id}/run` | `workflow_run:execute` | 启动运行 |
| `GET` | `runs` | `workflow_run:list` | 运行列表 |
| `GET` | `runs/{run_id}` | `workflow_run:view` | 运行详情 |
| `POST` | `runs/{run_id}/pause` | `workflow_run:pause` | 暂停 |
| `POST` | `runs/{run_id}/resume` | `workflow_run:resume` | 恢复 |
| `POST` | `runs/{run_id}/retry` | `workflow_run:retry` | 失败重试 |
| `POST` | `runs/{run_id}/terminate` | `workflow_run:terminate` | 终止 |
| `GET` | `artifacts` | `artifact_center:list` | Artifact 列表 |
| `GET` | `artifacts/{artifact_id}` | `artifact_center:view` | Artifact 详情 |
| `POST` | `artifacts/{artifact_id}/feedback` | `artifact_center:feedback` | 提交反馈 |
| `GET` | `artifacts/{artifact_id}/download` | `artifact_center:export` | 下载 Artifact |

### 9.4 第一版不建议暴露的 API

第一版不建议直接开放：

- 企业端自定义连接器 API
- 企业端代码节点注册 API
- 企业端直接改平台模板 API
- 跨企业运行查询 API

---

## 十、后台任务与运行时作业清单

### 10.1 第一版建议任务

当前 manifest 已声明以下插件任务：

| 任务名 | 作用 | 是否必做 |
|---|---|---|
| `workflow_run_timeout_sweeper` | 扫描超时运行并转异常状态 | 是 |
| `workflow_run_retry_dispatcher` | 处理可自动重试的失败运行 | 是 |
| `workflow_artifact_retention` | 清理过期 Artifact 内容文件 | 是 |

仍属规划但尚未进入当前 manifest 的任务：

- `metrics_aggregator`

### 10.2 运行时状态推进原则

第一版状态推进建议优先用：

- 请求触发
- 插件周期任务
- 插件表事件流

而不是优先依赖：

- 插件 middleware
- 插件 consumer

这样更容易做到：

- 禁用即停
- 卸载可清
- 故障边界明确

---

## 十一、零宿主落地约束与能力裁剪

### 11.1 第一版可以直接使用的插件能力

当前插件框架已可直接复用：

- 插件 DB 代理
- 插件通知
- 插件 AI 调用
- 插件 HTTP 请求
- 插件存储命名空间
- 插件事件总线

### 11.2 第一版明确不允许的做法

第一版禁止以下落地方式：

- 为了本模块去新增 `backend/app/**` 主项目扩展文件
- 为了本模块去修改 `backend/app/plugins/context.py`
- 为了本模块去修改 `backend/app/plugins/manifest.py`
- 为了本模块把审批、审计、计量、附件能力硬接进主项目
- 为了赶第一版而放宽插件沙箱边界

### 11.3 第一版能力裁剪与替代策略

如果某项能力当前没有插件内稳定承接方式，第一版按以下口径处理：

- Approval：第一版先以插件自有 `human_review` 节点、审批任务表、审批事件表承接
- Audit：第一版先保证插件事件表、结构化日志和运行留痕完整
- Usage Meter：第一版先在插件内记录运行成本、预算消耗、额度事件，作为模块内部报表口径
- Attachment / Artifact：第一版先用插件 namespaced storage 与插件自有 artifact 表
- 任何“需要宿主补统一桥”的做法：明确延后到第二版平台能力建设阶段

但要明确：

- 这些是**在零宿主约束下的第一版正式设计**
- 不是“先违规接进宿主，后面再回收”
- 第二版如果平台要统一审批 / 审计 / 计量 / 附件能力，应以平台公共能力建设项目单独推进，而不是在本模块里夹带实现

---

## 十二、前后端开发实施要求

### 12.1 后端要求

必须遵守：

- API 只收口请求，不写复杂业务逻辑
- Service 处理业务规则
- Runtime 模块负责执行图、恢复、补偿和状态推进
- 插件业务数据只落插件自有表
- 迁移只放在插件 `backend/migrations/`

### 12.2 前端要求

必须遵守当前项目规则：

- 所有页面在插件 `frontend/` 内实现
- 列表页优先 `useCrudPage` 或 `useCrudList`
- 不手写重复 CRUD 状态管理
- 不硬编码文案
- 不新增在线图标依赖
- 不跨端导入无关模块

### 12.3 AI 页面接入要求

如果后续编辑器页要接入页面 AI：

- 优先复用当前平台页面 AI 能力
- 不在插件内重复造一套页面操作协议
- 页面 AI 能力按页面级白名单开放

---

## 十三、研发阶段拆分

### 13.1 P0 基础建壳

交付物：

- 插件目录结构
- `plugin.yaml`
- 管理端首页与企业端首页空壳
- 基础权限、菜单、路由
- 插件迁移骨架

### 13.2 P1 模板中心

交付物：

- 平台模板 CRUD
- 模板版本
- 模板节点与边编辑
- 管理端模板编辑器

### 13.3 P2 企业工作流中心

交付物：

- 企业复制模板
- 企业简单工作流新建
- 企业工作流版本与发布
- 企业构建能力限制

### 13.4 P3 运行时

交付物：

- Run / NodeRun / Artifact
- 运行详情页
- 失败重试、恢复、终止
- 定时清理与超时扫描

### 13.5 P4 行业挂载

交付物：

- `solution_plugin -> workflow-orchestration` 依赖打通
- 方案模板绑定
- 方案启用后企业落地路径打通

---

## 十四、验收清单

### 14.1 生命周期验收

- 安装插件后，管理端页面可访问
- 未授权企业不能访问企业端页面
- 给企业分配后，企业端页面可访问
- 禁用插件后，企业端和管理端 API 都应被 gate 拦住
- 卸载插件后，插件页面、记录、自有表和文件被清理

### 14.2 权限验收

- 企业端只看到自己有权看的页面
- 企业端只能执行已声明动作
- 企业端 owner 与普通 admin 权限行为不同
- Admin 端拥有插件管理超集能力

### 14.3 数据验收

- 模板发布后形成稳定版本快照
- 运行实例绑定版本快照
- 节点运行有输入输出摘要
- Artifact 可追溯到 Run / NodeRun
- 检查点可支持恢复

### 14.4 边界验收

- 模块不依赖 middleware 作为核心执行链路
- 模块不依赖 consumer 作为核心状态机
- 模块不直接写宿主核心事实表
- 企业端无法新增代码节点和连接器

### 14.5 工程装配验收

- `plugin.yaml` 最终声明的 `extensions.api` 与实际 handler 文件一一对应
- `plugin.yaml` 最终声明的 `extensions.frontend.pages` 覆盖所有可直接访问 URL
- `frontend/src/index.ts` 已正确导出 `plugin.yaml` 引用的全部页面组件名
- `frontend.dev.entry = src/index.ts` 与 `frontend.release.manifest = plugin.manifest.json` 均可被宿主解析
- locale 注册与插件 `setup()` 链路可在真实宿主加载时生效，不要求必须存在 `frontend/src/locales/index.ts`
- 如后续引入 `frontend/src/api/index.ts`、`frontend/src/locales/index.ts` 这类 barrel 文件，必须与真实导出保持同步；但它们不是当前必选装配前提
- handoff 中要求回填到冻结文件的片段都已被集成人接入
- 整个模块实现未向 `backend/app/**` 或主系统前端源码落任何业务文件

---

## 十五、最终实施建议

如果按当前仓库现状推进，最稳妥的路径不是一步把“全平台工作流内核”插件化，而是：

1. 先把 `workflow-orchestration` 做成一个边界干净的产品模块插件。
2. 第一版只依赖当前插件框架已经稳定支持的能力。
3. 把模板、运行、Artifact、企业构建这四块做实。
4. 审批、审计、计量等平台统一能力单独立项，作为后续平台工程推进，不夹带到本模块第一版。
5. 行业方案插件第二阶段再正式挂载到该模块。

按这个顺序推进，能同时保证：

- 能落地
- 能售卖
- 能按企业开通
- 能禁用卸载
- 能继续演化成平台级能力

如果要直接进入 4 AI 并行执行，继续看：

- [41-workflow-orchestration-module-4-agent-execution-plan-20260323.md](./41-workflow-orchestration-module-4-agent-execution-plan-20260323.md)
