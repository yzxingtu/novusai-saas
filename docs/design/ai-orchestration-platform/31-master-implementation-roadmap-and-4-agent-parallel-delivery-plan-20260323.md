# AI 编排平台实施总路线图与 4 AI 并行交付方案（2026-03-23）

## 一、文档目标

本文档用于把前面 `01-30` 的平台规划文档，收敛成一份可以直接执行的实施总路线图，并给出 4 个 AI 并行开发时的正式拆分方案。

这份文档要解决的不是“产品还要不要继续想”，而是下面这些更实际的问题：

1. 第一阶段代码实施到底先做什么、后做什么。
2. 4 个 AI 同时开工时，如何按目录、按模块、按共享文件冻结边界来拆分，尽量避免冲突。
3. 哪些共享文件在并行阶段一律不允许碰，必须留到串行集成窗口再处理。
4. 每个 AI 的交付边界、输出物、验收标准、handoff 内容应该是什么。
5. 如何确保所有 AI 严格遵守本项目 `rules`、`skill` 和现有代码规范，而不是各写各的。

本文档默认适用于当前仓库：

- 后端：`backend/app/**`
- 前端：`frontend/apps/web-antd/src/**`
- 规划文档：`docs/design/ai-orchestration-platform/**`

---

## 二、前提判断

前面 `01-30` 已经完成的是“平台蓝图”。

现在要进入的是“第一阶段实施”。

第一阶段实施不等于一次把所有规划文档百分之百落成完整商用品，而是要先做出一套：

- 有正式数据模型
- 有正式 API
- 有正式页面骨架
- 有正式权限和租户隔离
- 有测试、审批、推荐、激活、市场治理入口

的第一版平台骨架。

所以本路线图的目标是：

> 先把 AI 编排平台的一阶段骨架做对、做稳、做可持续扩展，再逐步补充更深的运行时智能和行业细节。

---

## 三、所有 AI 的强制遵守项

4 个 AI 无论各自负责什么，都必须先遵守本项目的 `rules` 和 `skill`。

## 3.1 必读规则

并行开发开始前，每个 AI 都必须先阅读：

- `E:/git_clone/novusai-saas-yudi/.cursorrules`
- `E:/git_clone/novusai-saas-yudi/.cursor/rules/novusai-saas.md`
- `E:/git_clone/novusai-saas-yudi/.cursor/rules/ai-architecture.md`
- `E:/git_clone/novusai-saas-yudi/.cursor/rules/plugin-system.md`
- `E:/git_clone/novusai-saas-yudi/.cursor/rules/testing-validation.md`
- `E:/git_clone/novusai-saas-yudi/.cursor/rules/rbac-and-data-permission.md`
- `E:/git_clone/novusai-saas-yudi/.cursor/rules/trace-and-monitoring.md`

## 3.2 必读技能

如果执行环境是 Codex，还必须阅读：

- `C:/Users/Administrator/.codex/skills/novusai-saas/novusai-saas/SKILL.md`

如果执行环境是 Cursor / Windsurf，也必须同步遵守仓库内技能：

- `E:/git_clone/novusai-saas-yudi/.cursor/skills/novusai-saas/SKILL.md`

## 3.3 必读规划文档

4 个 AI 都至少需要通读：

- [01-platform-architecture-20260323.md](./01-platform-architecture-20260323.md)
- [02-platform-data-model-20260323.md](./02-platform-data-model-20260323.md)
- [03-page-and-permission-map-20260323.md](./03-page-and-permission-map-20260323.md)
- [08-workflow-builder-capability-matrix-20260323.md](./08-workflow-builder-capability-matrix-20260323.md)
- [12-runtime-policy-engine-spec-20260323.md](./12-runtime-policy-engine-spec-20260323.md)
- [15-workflow-data-contract-and-schema-spec-20260323.md](./15-workflow-data-contract-and-schema-spec-20260323.md)
- [17-enterprise-operator-console-spec-20260323.md](./17-enterprise-operator-console-spec-20260323.md)
- [23-enterprise-data-governance-and-sensitive-information-boundary-spec-20260323.md](./23-enterprise-data-governance-and-sensitive-information-boundary-spec-20260323.md)
- [24-agent-memory-and-long-term-learning-boundary-spec-20260323.md](./24-agent-memory-and-long-term-learning-boundary-spec-20260323.md)
- [29-recommendation-decision-engine-and-strategy-output-spec-20260323.md](./29-recommendation-decision-engine-and-strategy-output-spec-20260323.md)

不同 AI 还会有各自的补充必读，见后文和独立 prompt。

并行正式执行前，4 个 AI 还必须补读：

- [32-parallel-execution-control-spec-20260323.md](./32-parallel-execution-control-spec-20260323.md)
- [33-cross-agent-contract-matrix-20260323.md](./33-cross-agent-contract-matrix-20260323.md)

---

## 四、并行开发时绝不允许破坏的总规则

## 4.1 统一禁令

所有 AI 必须同时遵守：

- 禁止硬编码中文字符串，前端必须用 `$t()`，后端必须用 `_()`
- 禁止 `console.log`
- 禁止业务代码使用 `any`
- 禁止魔法字符串，后端使用枚举
- 禁止跨端导入
- 禁止 Controller 写业务逻辑
- 禁止 Service 直接写裸 SQL 业务判断
- 禁止裸返回，必须走统一响应
- 禁止把敏感信息写进代码
- 禁止为了省事直接改现有共享文件做“大重构”

## 4.2 并行阶段禁止做的事

为了防止 4 个 AI 打架，并行阶段一律禁止：

- 改已有全局通用组件，只为服务自己这条线
- 提前抽公共基础层，导致多人同时改 `components` / `composables` / `core`
- 提前合并到共享 API 索引或全局导出索引
- 提前生成多份 Alembic 迁移
- 多个 AI 同时改后端 `messages.json` / `menu.json`
- 多个 AI 同时改后端 `__init__.py` 路由注册文件

结论很简单：

> 并行阶段先做“各自完整”，不要先做“全局优雅”。

全局抽象和共享整合放到串行集成窗口。

---

## 五、第一阶段实施目标拆解

第一阶段推荐只做以下 4 个大块，正好映射给 4 个 AI：

| AI | 主责方向 |
|---|---|
| `AI-1` | 后端设计时域与串行集成准备 |
| `AI-2` | 后端运行时治理、推荐、激活与市场运行域 |
| `AI-3` | 管理端前端工作台、市场审核、测试与变更中心 |
| `AI-4` | 企业端前端运营控制台、激活中心、审批与推荐中心 |

其中：

- `AI-1` 和 `AI-2` 负责后端，但文件命名空间彻底分开
- `AI-3` 只碰 admin 前端
- `AI-4` 只碰 tenant 前端

共享文件统一留到集成窗口处理。

---

## 六、并行拆分总原则

## 6.1 只按“命名空间 + 目录”切分，不按“谁先想到什么”切分

否则并行过程中最容易出现：

- 两个人都觉得某个文件“顺手一起改一下”
- 最后同一个文件四个人都动了

所以本方案采用：

- 后端按 `orchestration_*` 业务命名空间切
- 前端按 `views/admin/ai/orchestration/**` 与 `views/tenant/ai/orchestration/**` 切
- 集成文件统一冻结

## 6.2 每个 AI 只能在自己的根目录内纵向做完

例如：

- 能在自己目录下新增 `data.ts`
- 能在自己目录下新增 `index.vue`
- 能在自己目录下新增 `modules/*`
- 能在自己目录下新增 API 文件

但不能为了方便去改别人负责的全局文件。

## 6.3 所有共享接入点统一走 handoff

并行阶段所有需要主协调者后续统一处理的事项，都必须写进各自 handoff 文件，而不是直接去改共享文件。

handoff 至少包括：

- 需要注册的模型
- 需要注册的 API 路由
- 需要合并的 i18n key
- 需要合并的权限与菜单 key
- 需要纳入统一迁移的表
- 需要补的 metrics 点位

---

## 七、共享文件冻结清单

以下文件在并行阶段一律冻结，不允许 4 个 AI 直接改。

## 7.1 后端冻结文件

- `backend/app/models/__init__.py`
- `backend/app/api/admin/__init__.py`
- `backend/app/api/tenant/__init__.py`
- `backend/app/locales/en/messages.json`
- `backend/app/locales/zh_CN/messages.json`
- `backend/app/locales/en/menu.json`
- `backend/app/locales/zh_CN/menu.json`
- `backend/migrations/env.py`
- `backend/migrations/versions/*`
- `backend/app/core/metrics.py`

## 7.2 前端冻结文件

- `frontend/apps/web-antd/src/api/admin/index.ts`
- `frontend/apps/web-antd/src/api/tenant/index.ts`
- `frontend/apps/web-antd/src/locales/index.ts`
- 现有非本次新增页面对应的共享 `components/**`
- 现有非本次新增页面对应的共享 `composables/**`

## 7.3 为什么必须冻结

这些文件的特点都一样：

- 全局入口
- 高冲突
- 一改就影响多人
- 最适合串行整合，不适合并行乱改

---

## 八、4 个 AI 的正式文件边界

## 8.1 AI-1 文件边界

AI-1 只允许创建或修改以下新增命名空间文件：

- `backend/app/models/business/orchestration_solution*.py`
- `backend/app/models/business/orchestration_workflow*.py`
- `backend/app/models/business/orchestration_release*.py`
- `backend/app/models/business/orchestration_trigger*.py`
- `backend/app/models/business/orchestration_environment*.py`
- `backend/app/models/business/orchestration_change_set*.py`
- `backend/app/schemas/business/orchestration_solution*.py`
- `backend/app/schemas/business/orchestration_workflow*.py`
- `backend/app/schemas/business/orchestration_release*.py`
- `backend/app/schemas/business/orchestration_trigger*.py`
- `backend/app/schemas/business/orchestration_environment*.py`
- `backend/app/schemas/business/orchestration_change_set*.py`
- `backend/app/repositories/business/orchestration_solution*.py`
- `backend/app/repositories/business/orchestration_workflow*.py`
- `backend/app/repositories/business/orchestration_release*.py`
- `backend/app/repositories/business/orchestration_trigger*.py`
- `backend/app/repositories/business/orchestration_environment*.py`
- `backend/app/repositories/business/orchestration_change_set*.py`
- `backend/app/services/business/orchestration_solution*.py`
- `backend/app/services/business/orchestration_workflow*.py`
- `backend/app/services/business/orchestration_release*.py`
- `backend/app/services/business/orchestration_trigger*.py`
- `backend/app/services/business/orchestration_environment*.py`
- `backend/app/services/business/orchestration_change_set*.py`
- `backend/app/api/admin/orchestration_solutions.py`
- `backend/app/api/admin/orchestration_workflows.py`
- `backend/app/api/admin/orchestration_releases.py`
- `backend/app/api/admin/orchestration_triggers.py`
- `backend/app/api/admin/orchestration_environments.py`
- `backend/app/api/admin/orchestration_change_sets.py`

## 8.2 AI-2 文件边界

AI-2 只允许创建或修改以下新增命名空间文件：

- `backend/app/models/business/orchestration_run*.py`
- `backend/app/models/business/orchestration_node_run*.py`
- `backend/app/models/business/orchestration_approval*.py`
- `backend/app/models/business/orchestration_artifact*.py`
- `backend/app/models/business/orchestration_activation*.py`
- `backend/app/models/business/orchestration_market*.py`
- `backend/app/models/business/orchestration_recommendation*.py`
- `backend/app/models/business/orchestration_feedback*.py`
- `backend/app/schemas/business/orchestration_run*.py`
- `backend/app/schemas/business/orchestration_approval*.py`
- `backend/app/schemas/business/orchestration_artifact*.py`
- `backend/app/schemas/business/orchestration_activation*.py`
- `backend/app/schemas/business/orchestration_market*.py`
- `backend/app/schemas/business/orchestration_recommendation*.py`
- `backend/app/repositories/business/orchestration_run*.py`
- `backend/app/repositories/business/orchestration_approval*.py`
- `backend/app/repositories/business/orchestration_artifact*.py`
- `backend/app/repositories/business/orchestration_activation*.py`
- `backend/app/repositories/business/orchestration_market*.py`
- `backend/app/repositories/business/orchestration_recommendation*.py`
- `backend/app/services/business/orchestration_run*.py`
- `backend/app/services/business/orchestration_approval*.py`
- `backend/app/services/business/orchestration_artifact*.py`
- `backend/app/services/business/orchestration_activation*.py`
- `backend/app/services/business/orchestration_market*.py`
- `backend/app/services/business/orchestration_recommendation*.py`
- `backend/app/api/admin/orchestration_runs.py`
- `backend/app/api/admin/orchestration_approvals.py`
- `backend/app/api/admin/orchestration_marketplace_reviews.py`
- `backend/app/api/admin/orchestration_testing.py`
- `backend/app/api/admin/orchestration_recommendations.py`
- `backend/app/api/tenant/orchestration_operator_console.py`
- `backend/app/api/tenant/orchestration_activations.py`
- `backend/app/api/tenant/orchestration_runs.py`
- `backend/app/api/tenant/orchestration_approvals.py`
- `backend/app/api/tenant/orchestration_recommendations.py`

## 8.3 AI-3 文件边界

AI-3 只允许创建或修改以下 admin 前端文件：

- `frontend/apps/web-antd/src/views/admin/ai/orchestration/**`
- `frontend/apps/web-antd/src/api/admin/ai-orchestration-*.ts`
- `frontend/apps/web-antd/src/locales/langs/zh-CN/admin/orchestration.json`
- `frontend/apps/web-antd/src/locales/langs/en-US/admin/orchestration.json`

AI-3 不允许改：

- `frontend/apps/web-antd/src/views/tenant/**`
- 现有 `frontend/apps/web-antd/src/views/admin/ai/*` 旧模块，除非明确在自己新目录内
- 全局 `components/**`
- 全局 `composables/**`

## 8.4 AI-4 文件边界

AI-4 只允许创建或修改以下 tenant 前端文件：

- `frontend/apps/web-antd/src/views/tenant/ai/orchestration/**`
- `frontend/apps/web-antd/src/api/tenant/ai-orchestration-*.ts`
- `frontend/apps/web-antd/src/locales/langs/zh-CN/tenant/orchestration.json`
- `frontend/apps/web-antd/src/locales/langs/en-US/tenant/orchestration.json`

AI-4 不允许改：

- `frontend/apps/web-antd/src/views/admin/**`
- 现有 `frontend/apps/web-antd/src/views/tenant/ai/*` 旧模块，除非明确在自己新目录内
- 全局 `components/**`
- 全局 `composables/**`

---

## 九、4 个 AI 的职责与输出物

## 9.1 AI-1：后端设计时域

主责：

- 方案、工作流、版本、发布、环境、触发、变更单元的后端实现骨架
- 管理端设计时 API
- 所有设计时数据契约与枚举

输出物：

- 设计时业务模型
- 设计时 Schema
- Repository / Service / Admin API
- 单元测试最小集
- handoff 清单

## 9.2 AI-2：后端运行时治理域

主责：

- 运行实例、节点运行、审批、Artifact、激活、市场运行态、推荐引擎、反馈闭环
- 管理端运行态 API
- 企业端运营控制台 API

输出物：

- 运行时与治理域模型
- Recommendation / Activation / Approval / Run API
- 指标与预算/风险相关服务设计点
- 单元测试最小集
- handoff 清单

## 9.3 AI-3：管理端工作台

主责：

- 管理端工作流设计中心
- 方案版本 / 发布 / 环境变更中心
- 测试仿真中心
- 市场审核中心

输出物：

- Admin 新页面目录
- Admin API 封装
- Admin 双语 i18n 文件
- 浏览器联调说明
- handoff 清单

## 9.4 AI-4：企业端运营控制台

主责：

- 企业端激活中心
- 企业端运营控制台
- 审批与运行中心
- 推荐决策中心

输出物：

- Tenant 新页面目录
- Tenant API 封装
- Tenant 双语 i18n 文件
- 浏览器联调说明
- handoff 清单

---

## 十、实施阶段与顺序

## 10.1 阶段 A：并行前冻结

主协调者先完成：

1. 按 `32` 文档创建 4 个执行工作副本和 1 个 `integrator` 工作副本
2. 冻结共享文件清单
3. 把 4 个执行 prompt 发给 4 个 AI，并把 `Integrator` prompt 发给集成人
4. 指定 4 个 AI 的 handoff 文件
5. 明确并行阶段不允许修改共享文件

## 10.2 阶段 B：4 AI 并行开发

4 个 AI 同时进行，但都只能在自己的边界内做。

并行阶段目标不是“马上跑通全部平台”，而是：

- 把各自负责域做完整
- 把所有共享接入需求写进 handoff

## 10.3 阶段 C：串行集成窗口

并行阶段结束后，由主协调者或指定集成人完成：

1. 合并 `backend/app/models/__init__.py`
2. 合并 `backend/app/api/admin/__init__.py`
3. 合并 `backend/app/api/tenant/__init__.py`
4. 合并 `messages.json` / `menu.json`
5. 统一生成 Alembic 迁移
6. 统一补 `metrics.py`

这一步必须串行，不能继续并行。

串行集成必须由独立 `integrator` 按以下文档执行：

- [32-parallel-execution-control-spec-20260323.md](./32-parallel-execution-control-spec-20260323.md)
- [33-cross-agent-contract-matrix-20260323.md](./33-cross-agent-contract-matrix-20260323.md)
- [34-integrator-prompt-and-serial-merge-checklist-20260323.md](./34-integrator-prompt-and-serial-merge-checklist-20260323.md)

并行启动、节奏控制、冻结验收和正式移交，则由 `coordinator` 按以下文档执行：

- [35-coordinator-launch-and-delivery-runbook-20260323.md](./35-coordinator-launch-and-delivery-runbook-20260323.md)

## 10.4 阶段 D：联调与校验

至少完成：

- 后端最小 pytest
- `alembic upgrade heads`
- 前端 `pnpm typecheck`
- 浏览器最小联调
- 权限和租户隔离抽查

## 10.5 阶段 E：问题收敛

收敛重点：

- 权限与菜单缺口
- i18n key 漏项
- 变量命名与数据契约不一致
- API 字段 snake_case / camelCase 不一致
- 前后端分页、过滤、状态枚举不一致

---

## 十一、handoff 机制

为避免 4 个 AI 直接抢共享文件，本方案要求每个 AI 只更新自己的 handoff 文件。

配套 handoff 模板位于：

- [AI-1-handoff.md](./31-parallel-delivery-kit-20260323/AI-1-handoff.md)
- [AI-2-handoff.md](./31-parallel-delivery-kit-20260323/AI-2-handoff.md)
- [AI-3-handoff.md](./31-parallel-delivery-kit-20260323/AI-3-handoff.md)
- [AI-4-handoff.md](./31-parallel-delivery-kit-20260323/AI-4-handoff.md)

每个 handoff 至少要写清：

- 工作副本、分支、冻结提交、冻结时间
- 本 AI 新增了哪些文件
- 哪些共享文件后续必须合并，以及具体合并项
- 需要新增哪些权限码
- 需要新增哪些后端 message key / menu key
- 需要纳入统一迁移的表
- 已完成哪些测试与结果
- 依赖其他 AI 或集成人补齐的字段、接口、入口或指标
- 还剩哪些阻塞点、风险与临时假设

---

## 十二、建议的合并顺序

为了降低冲突，推荐合并顺序如下：

1. 先合并 `AI-1` 与 `AI-2` 的业务文件，不碰共享文件
2. 再由主协调者根据 `AI-1`、`AI-2` handoff 串行处理后端共享文件
3. 再合并 `AI-3` 与 `AI-4` 的前端业务文件
4. 最后串行补权限、菜单、页面入口、联调修正

这个顺序的核心逻辑是：

- 先合并“各自局部域”
- 后合并“全局注册层”

---

## 十三、统一验收标准

## 13.1 后端验收最低线

- 分层正确
- 枚举正确
- 统一响应正确
- 多租户边界正确
- 无硬编码中文
- 无共享文件越权改动

## 13.2 前端验收最低线

- 用项目既有 CRUD 模式
- 无 `any`
- 无 `console.log`
- 页面 i18n 完整
- admin / tenant 严格分端
- 不越权修改全局共享层

## 13.3 并行协作验收最低线

- 4 个 AI 没有同时编辑同一个冻结文件
- 每个 AI 都补齐了 handoff
- 串行集成时不需要回头重读全部代码猜改动意图

---

## 十四、路线图结论

如果你要让 4 个 AI 真正同时做，并且尽可能少冲突，这套方案的核心不是“多派几个 AI”，而是三件事：

1. 先冻结共享文件
2. 再按命名空间和目录强切边界
3. 最后统一走 handoff 做串行集成

本目录已经为此准备好了：

- 主路线图：本文档
- 并行控制规范：`32-parallel-execution-control-spec-20260323.md`
- 跨 AI 契约矩阵：`33-cross-agent-contract-matrix-20260323.md`
- 串行集成人规范：`34-integrator-prompt-and-serial-merge-checklist-20260323.md`
- 主协调者作战手册：`35-coordinator-launch-and-delivery-runbook-20260323.md`
- 主协调者冻结签收与移交模板：`36-coordinator-freeze-signoff-and-integrator-transfer-template-20260323.md`
- worktree 初始化命令手册：`37-worktree-setup-and-branch-bootstrap-runbook-20260323.md`
- 集成人最终集成报告模板：`38-integrator-final-merge-report-template-20260323.md`
- 4 份独立 prompt：见 `31-parallel-delivery-kit-20260323/`
- 4 份 handoff 模板：见 `31-parallel-delivery-kit-20260323/`
- 1 份主协调者 prompt：见 `31-parallel-delivery-kit-20260323/Coordinator-launch-and-control-prompt.md`
- 1 份集成人 prompt：见 `31-parallel-delivery-kit-20260323/Integrator-serial-merge-prompt.md`

下一步不需要再想抽象方案了，直接把 4 份执行 prompt 分发给 4 个 AI，把 1 份 `Coordinator` prompt 分发给主协调者，再把 1 份 `Integrator` prompt 分发给串行集成人即可。
