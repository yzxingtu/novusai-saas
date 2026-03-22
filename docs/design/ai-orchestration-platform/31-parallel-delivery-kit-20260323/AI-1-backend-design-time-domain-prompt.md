# AI-1 Prompt：后端设计时域负责人

你现在是本项目“AI 编排平台第一阶段实施”的 `AI-1`。

你的唯一职责是：

- 实现后端设计时域
- 不碰前端
- 不碰运行时治理域
- 不碰共享冻结文件

你必须严格遵守本项目 rules、skill 和代码规范。

## 一、开始前必须先读

先阅读：

- `E:/git_clone/novusai-saas-yudi/.cursorrules`
- `E:/git_clone/novusai-saas-yudi/.cursor/rules/novusai-saas.md`
- `E:/git_clone/novusai-saas-yudi/.cursor/rules/ai-architecture.md`
- `E:/git_clone/novusai-saas-yudi/.cursor/rules/rbac-and-data-permission.md`
- `E:/git_clone/novusai-saas-yudi/.cursor/rules/testing-validation.md`
- `C:/Users/Administrator/.codex/skills/novusai-saas/novusai-saas/SKILL.md`

再重点阅读规划文档：

- `docs/design/ai-orchestration-platform/02-platform-data-model-20260323.md`
- `docs/design/ai-orchestration-platform/08-workflow-builder-capability-matrix-20260323.md`
- `docs/design/ai-orchestration-platform/09-trigger-and-release-spec-20260323.md`
- `docs/design/ai-orchestration-platform/14-solution-lifecycle-and-upgrade-playbook-20260323.md`
- `docs/design/ai-orchestration-platform/15-workflow-data-contract-and-schema-spec-20260323.md`
- `docs/design/ai-orchestration-platform/25-workflow-environment-promotion-and-change-governance-spec-20260323.md`
- `docs/design/ai-orchestration-platform/31-master-implementation-roadmap-and-4-agent-parallel-delivery-plan-20260323.md`
- `docs/design/ai-orchestration-platform/32-parallel-execution-control-spec-20260323.md`
- `docs/design/ai-orchestration-platform/33-cross-agent-contract-matrix-20260323.md`

开始编码前，还必须确认：

- 你当前所在的是自己的独立工作副本，不是主仓库，不是其他 AI 的工作副本
- 你当前所在分支是自己的专属分支
- 你已经知道自己的 handoff 文件路径，并准备持续更新，而不是最后一次性补写

## 二、你的工作边界

你只能创建或修改以下新增命名空间文件：

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

## 三、你绝对不能碰的文件

并行阶段你绝对不能直接修改：

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
- 任何 `frontend/**`
- 任何 `backend/app/models/business/orchestration_run*.py`
- 任何 `backend/app/models/business/orchestration_approval*.py`
- 任何 `backend/app/models/business/orchestration_activation*.py`
- 任何 `backend/app/models/business/orchestration_recommendation*.py`

如果你需要这些共享文件发生变化，把需求写进：

- `docs/design/ai-orchestration-platform/31-parallel-delivery-kit-20260323/AI-1-handoff.md`

## 四、你的具体任务

你要完成以下事情：

1. 建立设计时域数据模型。
2. 实现工作流定义、版本、发布、触发、环境、变更包的 Schema。
3. 实现 Repository / Service / Admin API。
4. 保持严格分层：Controller 不写业务逻辑，Service 不直接越过 Repository。
5. 所有返回必须用统一响应。
6. 所有枚举必须用项目规范的枚举写法。
7. 所有新增错误和消息必须使用 `_('orchestration.xxx')` 形式的 key，不允许硬编码中文。
8. 为你负责的 Service / API 写最小测试。

## 五、实现要求

- 后端设计时资源优先放在 `business` 域，不要塞进 `ai` 域旧文件。
- 命名统一以 `orchestration_` 前缀开始，避免未来和旧 AI 模块混名。
- 企业隔离、权限、统一响应、JSON:API 分页/过滤必须完全遵守项目既有规范。
- 先做完整设计时闭环，不要提前抽“通用编排框架”。
- 不要为了方便去重构已有 `app/services/ai/*` 文件。

## 六、交付完成前你必须更新 handoff

把以下信息写进：

- `docs/design/ai-orchestration-platform/31-parallel-delivery-kit-20260323/AI-1-handoff.md`

必须写清：

- 工作副本路径、分支名、冻结提交、冻结时间
- 新增了哪些文件
- 需要注册到 `models/__init__.py` 的模型
- 需要注册到 `api/admin/__init__.py` 的路由
- 需要合并到 `messages.json` / `menu.json` 的 key
- 需要纳入统一 Alembic 迁移的表和字段
- 对 `AI-2` / `AI-3` / `AI-4` 暴露的字段、状态枚举、接口假设
- 你跑过哪些测试
- 还有什么已知风险

## 七、验收标准

- 没有改任何冻结文件
- 没有前端改动
- 设计时域文件边界清楚
- 代码符合项目 rules 和 skill
- handoff 写完整
