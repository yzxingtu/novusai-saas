# AI 编排与工作流平台任务编排模块 4 AI 执行方案（2026-03-23）

## 一、文档目标

本文把 [40-workflow-orchestration-product-module-implementation-checklist-20260323.md](./40-workflow-orchestration-product-module-implementation-checklist-20260323.md) 继续下沉为“4 个 AI 可以直接并行开工”的执行方案。

本文重点解决：

1. 4 个 AI 具体怎么拆，不互相撞文件。
2. 哪些文件是单人所有权，哪些文件必须冻结给集成人。
3. 每个 AI 要交什么，哪些不允许做。
4. 串行集成顺序是什么。

配套提示词与 handoff 模板见：

- `docs/design/ai-orchestration-platform/41-workflow-orchestration-delivery-kit-20260323/`

---

## 二、执行前提

### 2.1 本次并行范围

本次只聚焦一个产品模块：

- `workflow-orchestration`

目标落点：

- `backend/plugins/workflow-orchestration/**`
- `docs/design/ai-orchestration-platform/**` 中与本模块执行相关的文档和交付包

硬约束：

- 本次实现禁止修改 `backend/app/**`
- 本次实现禁止向主系统前端源码落任何插件页面、locale、API 或业务逻辑
- 如果发现某项能力必须依赖宿主补口，直接记为延期项，不得边做边改主项目

### 2.2 本次并行不做

本次并行不覆盖：

- 行业方案插件本身的实现
- 市场商业化页面重做
- 宿主整个平台审批引擎重构
- 插件框架大范围改造

### 2.3 执行模型

推荐继续沿用前面 `31`、`32`、`33` 的方法，但本次切到模块级。

也就是：

- 4 个 AI 并行开发
- 1 个协调者
- 1 个集成人
- 独立 worktree
- 独立分支
- 共享文件冻结

---

## 三、4 AI 拆分总览

| AI | 角色 | 主责 | 只读依赖 |
|---|---|---|---|
| `AI-1` | 后端插件壳与模型负责人 | 插件壳、manifest、模型、迁移、设计时 API | `AI-2` 运行时会消费其模型 |
| `AI-2` | 后端运行时负责人 | 运行时、任务、运行 API、Artifact、企业工作流副本 API | 依赖 `AI-1` 模型和插件壳 |
| `AI-3` | 管理端前端负责人 | 管理端工作台、模板中心、发布中心、运行监控页 | 依赖 `AI-1` 设计时 API，部分依赖 `AI-2` 运行时 API |
| `AI-4` | 企业端前端负责人 | 企业首页、工作流中心、运行中心、Artifact 中心 | 依赖 `AI-2` Tenant API |

### 3.1 核心裁决

这次必须把所有权写死：

- `AI-1` 拥有插件壳与数据模型真相
- `AI-2` 拥有运行时对象真相
- `AI-3` 拥有管理端页面真相
- `AI-4` 拥有企业端页面真相

---

## 四、建议分支与工作副本

建议命名如下：

| 角色 | 分支名 |
|---|---|
| `AI-1` | `feat/workflow-orchestration-ai1-plugin-shell` |
| `AI-2` | `feat/workflow-orchestration-ai2-runtime-api` |
| `AI-3` | `feat/workflow-orchestration-ai3-admin-frontend` |
| `AI-4` | `feat/workflow-orchestration-ai4-tenant-frontend` |
| `integrator` | `feat/workflow-orchestration-integrator` |

工作副本建议目录：

```text
.cursor/worktrees/
├── workflow-orchestration-ai1-plugin-shell/
├── workflow-orchestration-ai2-runtime-api/
├── workflow-orchestration-ai3-admin-frontend/
├── workflow-orchestration-ai4-tenant-frontend/
└── workflow-orchestration-integrator/
```

---

## 五、文件所有权与冻结规则

## 5.1 `AI-1` 独占文件

只能由 `AI-1` 创建或修改：

- `backend/plugins/workflow-orchestration/plugin.yaml`
- `backend/plugins/workflow-orchestration/README.md`
- `backend/plugins/workflow-orchestration/backend/main.py`
- `backend/plugins/workflow-orchestration/backend/models/**`
- `backend/plugins/workflow-orchestration/backend/schemas/**`
- `backend/plugins/workflow-orchestration/backend/migrations/**`
- `backend/plugins/workflow-orchestration/backend/services/template_service.py`
- `backend/plugins/workflow-orchestration/backend/services/release_service.py`
- `backend/plugins/workflow-orchestration/backend/services/module_config_service.py`
- `backend/plugins/workflow-orchestration/backend/api/admin_overview.py`
- `backend/plugins/workflow-orchestration/backend/api/admin_templates.py`
- `backend/plugins/workflow-orchestration/backend/api/admin_releases.py`
- `backend/plugins/workflow-orchestration/backend/api/admin_settings.py`

`AI-1` 额外必须遵守：

- 不得修改任何 `backend/app/**`
- 不得把插件业务逻辑落到主系统目录
- 如发现必须补宿主能力，写入 handoff 的“延期项 / 平台依赖项”，不得直接实施
- `plugin.yaml` 在并行阶段由 `AI-1` 维护；串行阶段允许 `integrator` 仅按 handoff 做最终回填

## 5.2 `AI-2` 独占文件

只能由 `AI-2` 创建或修改：

- `backend/plugins/workflow-orchestration/backend/runtime/**`
- `backend/plugins/workflow-orchestration/backend/tasks/**`
- `backend/plugins/workflow-orchestration/backend/services/tenant_workflow_service.py`
- `backend/plugins/workflow-orchestration/backend/services/run_service.py`
- `backend/plugins/workflow-orchestration/backend/services/artifact_service.py`
- `backend/plugins/workflow-orchestration/backend/services/run_query_service.py`
- `backend/plugins/workflow-orchestration/backend/services/recovery_service.py`
- `backend/plugins/workflow-orchestration/backend/api/admin_runtime.py`
- `backend/plugins/workflow-orchestration/backend/api/tenant_home.py`
- `backend/plugins/workflow-orchestration/backend/api/tenant_workflows.py`
- `backend/plugins/workflow-orchestration/backend/api/runs.py`
- `backend/plugins/workflow-orchestration/backend/api/artifacts.py`
- `backend/plugins/workflow-orchestration/backend/tests/runtime/**`

`AI-2` 绝对不能修改：

- `plugin.yaml`
- `backend/main.py`
- `backend/models/**`
- `backend/migrations/**`
- 任何 `backend/app/**`

如需要改，写进 handoff 交给 integrator 或回流给 `AI-1`。

## 5.3 `AI-3` 独占文件

只能由 `AI-3` 创建或修改：

- `backend/plugins/workflow-orchestration/frontend/src/views/admin/**`
- `backend/plugins/workflow-orchestration/frontend/src/api/admin.ts`
- `backend/plugins/workflow-orchestration/frontend/src/locales/admin/**`
- `backend/plugins/workflow-orchestration/frontend/src/types/admin.ts`

`AI-3` 不得修改：

- 任何 tenant 页面
- 任何后端文件
- 任何插件目录外前端源码
- `frontend/src/index.ts`
- `frontend/src/api/index.ts`
- `frontend/src/locales/index.ts`

## 5.4 `AI-4` 独占文件

只能由 `AI-4` 创建或修改：

- `backend/plugins/workflow-orchestration/frontend/src/views/tenant/**`
- `backend/plugins/workflow-orchestration/frontend/src/api/tenant.ts`
- `backend/plugins/workflow-orchestration/frontend/src/locales/tenant/**`
- `backend/plugins/workflow-orchestration/frontend/src/types/tenant.ts`

`AI-4` 不得修改：

- 任何 admin 页面
- 任何后端文件
- 任何插件目录外前端源码
- `frontend/src/index.ts`
- `frontend/src/api/index.ts`
- `frontend/src/locales/index.ts`

## 5.5 集成人冻结文件

以下文件并行阶段全部冻结，只允许 `integrator` 处理：

- `backend/plugins/workflow-orchestration/plugin.yaml` 的非 `AI-1` 增量回填
- `backend/plugins/workflow-orchestration/frontend/src/index.ts`
- `backend/plugins/workflow-orchestration/frontend/src/api/index.ts`
- `backend/plugins/workflow-orchestration/frontend/src/locales/index.ts`
- `backend/plugins/workflow-orchestration/frontend/src/types/shared.ts`
- `backend/plugins/workflow-orchestration/frontend/dist/**`

如果并行阶段需要这些文件变化，必须通过 handoff 提交。

## 5.6 冻结文件回填协议

并行阶段必须额外遵守一条：

- `plugin.yaml`、`frontend/src/index.ts`、`frontend/src/api/index.ts`、`frontend/src/locales/index.ts` 这类冻结文件，不以“谁最后想起来谁改”为准
- 任何依赖这些冻结文件的新增内容，都必须由对应 AI 在 handoff 中给出**精确回填片段**

回填职责约定如下：

| 来源 AI | 必须在 handoff 中提供 | 最终由谁落入冻结文件 |
|---|---|---|
| `AI-1` | `plugin.yaml` 初始骨架、admin 侧 API 路由、模块元数据 | `AI-1` 并行阶段先落；如后续有增量，由 `integrator` 收尾 |
| `AI-2` | 运行时 / tenant API 路由增量、运行状态常量、共享类型建议 | `integrator` |
| `AI-3` | admin `frontend.pages` 条目、`src/index.ts` 组件导出名、`api/index.ts` admin 导出、`locales/index.ts` admin 注册项 | `integrator` |
| `AI-4` | tenant `frontend.pages` 条目、`src/index.ts` 组件导出名、`api/index.ts` tenant 导出、`locales/index.ts` tenant 注册项 | `integrator` |

因此必须明确：

- `AI-2` 不改 `plugin.yaml`，但必须输出它需要补进 `plugin.yaml` 的 API 路由增量
- `AI-3` / `AI-4` 不改 `plugin.yaml` 与 `frontend/src/index.ts`，但必须输出精确的页面声明与组件导出映射
- `integrator` 必须把 handoff 中这些回填项逐项接入，而不是只合并业务文件

---

## 六、每个 AI 的详细交付物

## 6.1 `AI-1` 交付物

必须完成：

- 插件 `plugin.yaml`
- 插件生命周期壳
- 插件模型与版本快照结构
- 初始迁移
- 模块总览、模板管理、发布管理、模块配置管理后端
- 零宿主约束下的设计时接口与模块边界说明

必须输出给其他 AI 的共享真相：

- 表名
- 主字段
- 状态枚举
- 模板快照结构
- 企业配置结构
- 延期能力清单与当前替代口径

## 6.2 `AI-2` 交付物

必须完成：

- 企业首页与构建能力 API
- 企业工作流副本 API
- Run / NodeRun / Checkpoint / Event / Artifact 运行时
- 重试、恢复、超时扫描与清理任务
- 运行详情与 Artifact 详情所需后端数据

必须输出给前端的共享真相：

- `run` 状态与动作
- `artifact` 状态与类型
- `tenant workflow` 列表与详情结构
- 首页看板统计结构
- 需要补入 `plugin.yaml` 的 runtime / tenant API 路由增量

## 6.3 `AI-3` 交付物

必须完成：

- 管理端模块首页
- 模板列表与模板详情
- 模板编辑器骨架
- 发布中心
- 全局运行中心

必须输出给 integrator：

- admin 侧路由片段
- admin 侧 i18n keys
- admin `frontend.pages` 条目
- `frontend/src/index.ts` 组件导出映射
- `frontend/src/api/index.ts` 导出接线建议
- 对 `AI-1` / `AI-2` API 的依赖摘要

## 6.4 `AI-4` 交付物

必须完成：

- 企业首页
- 工作流列表与工作流详情
- 企业编辑器骨架
- 运行列表与运行详情
- Artifact 列表与详情

必须输出给 integrator：

- tenant 侧路由片段
- tenant 侧 i18n keys
- tenant `frontend.pages` 条目
- `frontend/src/index.ts` 组件导出映射
- `frontend/src/api/index.ts` 导出接线建议
- 对 `AI-2` Tenant API 的依赖摘要

---

## 七、并行阶段统一禁令

所有 AI 一律禁止：

- 越权修改其他 AI 所有文件
- 提前抽全局公共组件
- 改任何 `backend/app/**` 或主系统前端源码
- 在插件外随意扩散业务逻辑
- 为了省事把 admin 和 tenant 写进同一个页面文件
- 不写 handoff 就直接宣布完成

---

## 八、串行集成顺序

建议严格按以下顺序：

1. 合并 `AI-1`
2. 合并 `AI-2`
3. 合并 `AI-3`
4. 合并 `AI-4`
5. 处理冻结文件与统一验证

### 8.1 为什么先 `AI-1`

因为：

- `AI-2` 依赖模型与插件壳
- 前端需要明确 API 结构
- 迁移顺序必须先定

### 8.2 为什么 `AI-3` 先于 `AI-4`

因为：

- 插件前端壳与 admin 侧总入口通常更先成型
- tenant 页可以在其后按 handoff 接入

如果实际开发中 `AI-4` 先完成，不代表集成顺序要改变。

---

## 九、统一验证矩阵

集成人至少要验证：

### 9.1 后端

- 插件安装
- 插件启用
- 企业分配后 tenant 可见
- 模板 CRUD
- 模板发布
- 运行创建
- 运行详情
- Artifact 详情
- 插件禁用与卸载

### 9.2 前端

- Admin 插件页面挂载
- Tenant 插件页面挂载
- 未授权企业不可见
- 已授权企业可见
- 页面 i18n 无硬编码
- 无跨端导入

### 9.3 集成

- 插件 API permission 声明完整
- 前后端字段命名一致
- 迁移只生成一套
- handoff 中的冻结文件接入项都已处理
- `backend/app/**` 与主系统前端源码保持零业务改动
- `plugin.yaml` / `frontend/src/index.ts` / `frontend/src/api/index.ts` / `frontend/src/locales/index.ts` 已按 handoff 完整回填

---

## 十、交付包内容

本执行方案的直接配套文件位于：

- `docs/design/ai-orchestration-platform/41-workflow-orchestration-delivery-kit-20260323/AI-1-backend-plugin-shell-and-model-prompt.md`
- `docs/design/ai-orchestration-platform/41-workflow-orchestration-delivery-kit-20260323/AI-2-backend-runtime-and-api-prompt.md`
- `docs/design/ai-orchestration-platform/41-workflow-orchestration-delivery-kit-20260323/AI-3-admin-frontend-prompt.md`
- `docs/design/ai-orchestration-platform/41-workflow-orchestration-delivery-kit-20260323/AI-4-tenant-frontend-prompt.md`
- `docs/design/ai-orchestration-platform/41-workflow-orchestration-delivery-kit-20260323/Coordinator-launch-and-control-prompt.md`
- `docs/design/ai-orchestration-platform/41-workflow-orchestration-delivery-kit-20260323/Integrator-serial-merge-prompt.md`

以及 4 份 handoff 模板。

---

## 十一、最终建议

这次不是再做一份抽象路线图，而是要进入真正可执行状态。

所以必须坚持：

- 文件所有权写死
- 零宿主落地
- 插件边界守住
- 并行阶段不追求“全局优雅”
- 串行阶段再做统一接线

如果按本文和配套 delivery kit 执行，任务编排模块插件这条线已经足够进入 4 AI 并行开发。
