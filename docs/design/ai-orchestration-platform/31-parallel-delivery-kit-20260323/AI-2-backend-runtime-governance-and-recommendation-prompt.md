# AI-2 Prompt：后端运行时治理与推荐域负责人

你现在是本项目“AI 编排平台第一阶段实施”的 `AI-2`。

你的唯一职责是：

- 实现后端运行时治理域
- 实现推荐、审批、运行、激活、市场运行态相关能力
- 不碰前端
- 不碰设计时域
- 不碰共享冻结文件

你必须严格遵守本项目 rules、skill 和代码规范。

## 一、开始前必须先读

先阅读：

- `E:/git_clone/novusai-saas-yudi/.cursorrules`
- `E:/git_clone/novusai-saas-yudi/.cursor/rules/novusai-saas.md`
- `E:/git_clone/novusai-saas-yudi/.cursor/rules/ai-architecture.md`
- `E:/git_clone/novusai-saas-yudi/.cursor/rules/testing-validation.md`
- `E:/git_clone/novusai-saas-yudi/.cursor/rules/trace-and-monitoring.md`
- `C:/Users/Administrator/.codex/skills/novusai-saas/novusai-saas/SKILL.md`

再重点阅读规划文档：

- `docs/design/ai-orchestration-platform/05-approval-and-risk-gate-spec-20260323.md`
- `docs/design/ai-orchestration-platform/11-observability-and-evaluation-spec-20260323.md`
- `docs/design/ai-orchestration-platform/12-runtime-policy-engine-spec-20260323.md`
- `docs/design/ai-orchestration-platform/16-runtime-execution-graph-and-recovery-spec-20260323.md`
- `docs/design/ai-orchestration-platform/20-runtime-budget-quota-and-cost-guard-spec-20260323.md`
- `docs/design/ai-orchestration-platform/21-connector-trust-and-external-action-safety-spec-20260323.md`
- `docs/design/ai-orchestration-platform/24-agent-memory-and-long-term-learning-boundary-spec-20260323.md`
- `docs/design/ai-orchestration-platform/28-tenant-onboarding-and-solution-activation-playbook-20260323.md`
- `docs/design/ai-orchestration-platform/29-recommendation-decision-engine-and-strategy-output-spec-20260323.md`
- `docs/design/ai-orchestration-platform/30-solution-marketplace-admission-review-and-commercial-governance-spec-20260323.md`
- `docs/design/ai-orchestration-platform/31-master-implementation-roadmap-and-4-agent-parallel-delivery-plan-20260323.md`
- `docs/design/ai-orchestration-platform/32-parallel-execution-control-spec-20260323.md`
- `docs/design/ai-orchestration-platform/33-cross-agent-contract-matrix-20260323.md`

开始编码前，还必须确认：

- 你当前所在的是自己的独立工作副本，不是主仓库，不是其他 AI 的工作副本
- 你当前所在分支是自己的专属分支
- 你已经理解哪些对象归 `AI-1` 所有，哪些对象归自己所有，不能跨域重定义
- 你已经知道自己的 handoff 文件路径，并准备持续更新，而不是最后一次性补写

## 二、你的工作边界

你只能创建或修改以下新增命名空间文件：

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
- 任何 `backend/app/models/business/orchestration_solution*.py`
- 任何 `backend/app/models/business/orchestration_workflow*.py`
- 任何 `backend/app/models/business/orchestration_release*.py`

如果你需要这些共享文件变化，把需求写进：

- `docs/design/ai-orchestration-platform/31-parallel-delivery-kit-20260323/AI-2-handoff.md`

## 四、你的具体任务

你要完成以下事情：

1. 建立运行实例、审批、Artifact、激活、市场运行态、推荐结果与反馈的后端模型。
2. 实现企业端运营控制台 API 所需的数据结构。
3. 实现管理端运行态、审核态、推荐态相关 API。
4. 推荐结果必须是结构化输出，不允许只返回一段随意文本。
5. 风险、审批、预算、外部动作边界要遵守前面的规划文档。
6. 所有新增错误和消息都使用 `_('orchestration.xxx')` key，不允许硬编码中文。
7. 为你负责的 Service / API 写最小测试。

## 五、实现要求

- 运行时域文件名统一 `orchestration_` 前缀。
- 严格分层，不允许把业务逻辑塞进 Controller。
- 不要去改旧的 `app/services/ai/*` 文件做“大一统”重构。
- 不要自己生成 Alembic 迁移。
- 不要自己改 `metrics.py`，把需要的指标项写进 handoff。
- 不要自己改共享 locale 文件，把需要的 key 写进 handoff。

## 六、交付完成前你必须更新 handoff

把以下信息写进：

- `docs/design/ai-orchestration-platform/31-parallel-delivery-kit-20260323/AI-2-handoff.md`

必须写清：

- 工作副本路径、分支名、冻结提交、冻结时间
- 新增了哪些文件
- 需要注册到 `models/__init__.py` 的模型
- 需要注册到 `api/admin/__init__.py` / `api/tenant/__init__.py` 的路由
- 需要合并到 `messages.json` / `menu.json` 的 key
- 需要纳入统一 Alembic 迁移的表和字段
- 建议补到 `metrics.py` 的指标点
- 提供给 `AI-3` / `AI-4` 的接口字段、状态枚举、错误码与分页口径
- 你跑过哪些测试
- 还有什么已知风险

## 七、验收标准

- 没有改任何冻结文件
- 没有前端改动
- 运行时治理域文件边界清楚
- 推荐输出是结构化方案，不是随意自然语言
- handoff 写完整
