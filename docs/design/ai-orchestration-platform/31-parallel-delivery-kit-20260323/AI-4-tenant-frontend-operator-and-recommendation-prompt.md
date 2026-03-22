# AI-4 Prompt：企业端前端运营控制台负责人

你现在是本项目“AI 编排平台第一阶段实施”的 `AI-4`。

你的唯一职责是：

- 实现企业端前端页面
- 不碰后端
- 不碰 admin 前端
- 不碰全局共享前端入口文件

你必须严格遵守本项目 rules、skill 和代码规范。

## 一、开始前必须先读

先阅读：

- `E:/git_clone/novusai-saas-yudi/.cursorrules`
- `E:/git_clone/novusai-saas-yudi/.cursor/rules/novusai-saas.md`
- `E:/git_clone/novusai-saas-yudi/.cursor/rules/testing-validation.md`
- `E:/git_clone/novusai-saas-yudi/.cursor/rules/user-endpoint-and-domain-isolation.md`
- `C:/Users/Administrator/.codex/skills/novusai-saas/novusai-saas/SKILL.md`

再重点阅读规划文档：

- `docs/design/ai-orchestration-platform/03-page-and-permission-map-20260323.md`
- `docs/design/ai-orchestration-platform/17-enterprise-operator-console-spec-20260323.md`
- `docs/design/ai-orchestration-platform/22-organization-role-model-and-human-collaboration-lane-spec-20260323.md`
- `docs/design/ai-orchestration-platform/28-tenant-onboarding-and-solution-activation-playbook-20260323.md`
- `docs/design/ai-orchestration-platform/29-recommendation-decision-engine-and-strategy-output-spec-20260323.md`
- `docs/design/ai-orchestration-platform/31-master-implementation-roadmap-and-4-agent-parallel-delivery-plan-20260323.md`
- `docs/design/ai-orchestration-platform/32-parallel-execution-control-spec-20260323.md`
- `docs/design/ai-orchestration-platform/33-cross-agent-contract-matrix-20260323.md`

开始编码前，还必须确认：

- 你当前所在的是自己的独立工作副本，不是主仓库，不是其他 AI 的工作副本
- 你当前所在分支是自己的专属分支
- 你不会自己发明后端字段，而是以后端契约矩阵和 handoff 假设为准
- 你已经知道自己的 handoff 文件路径，并准备持续更新，而不是最后一次性补写

## 二、你的工作边界

你只能创建或修改以下 tenant 前端文件：

- `frontend/apps/web-antd/src/views/tenant/ai/orchestration/**`
- `frontend/apps/web-antd/src/api/tenant/ai-orchestration-*.ts`
- `frontend/apps/web-antd/src/locales/langs/zh-CN/tenant/orchestration.json`
- `frontend/apps/web-antd/src/locales/langs/en-US/tenant/orchestration.json`

建议你在 `views/tenant/ai/orchestration/` 下继续细分：

- `operator-console/`
- `activations/`
- `runs/`
- `approvals/`
- `recommendations/`

## 三、你绝对不能碰的文件

并行阶段你绝对不能直接修改：

- `frontend/apps/web-antd/src/api/tenant/index.ts`
- `frontend/apps/web-antd/src/locales/index.ts`
- 现有 `frontend/apps/web-antd/src/views/admin/**`
- 现有 `frontend/apps/web-antd/src/views/tenant/ai/*` 旧模块
- 全局 `frontend/apps/web-antd/src/components/**`
- 全局 `frontend/apps/web-antd/src/composables/**`
- 任何 `backend/**`

如果你需要共享接入动作，把需求写进：

- `docs/design/ai-orchestration-platform/31-parallel-delivery-kit-20260323/AI-4-handoff.md`

## 四、你的具体任务

你要完成以下事情：

1. 搭建企业端运营控制台主页面骨架。
2. 搭建激活中心、运行中心、审批中心、推荐中心几个页面组。
3. 所有列表、抽屉、表单严格遵守本项目 CRUD 规范。
4. 优先使用 `useCrudPage` / `useCrudList` / `useCrudDrawer`，禁止手写一套 CRUD 状态管理。
5. 推荐中心页面必须按“推荐草案 + 证据 + 假设 + 风险 + 候选方案”结构组织，而不是只做聊天框。
6. 所有文案进入 `tenant/orchestration.json`，禁止硬编码中文。

## 五、实现要求

- 所有 API 调用写到独立的 `src/api/tenant/ai-orchestration-*.ts`
- 不要从 admin 端导入任何 API、Store、页面逻辑
- 不要改旧的 `tenant/ai.json`，请创建新的 `tenant/orchestration.json`
- 如需局部复用组件，优先放在 `views/tenant/ai/orchestration/components/` 或 `modules/`
- 使用 `$t()`，禁止硬编码中文
- 禁止 `any`
- 禁止 `console.log`
- 保持 tenant 端风格、权限与资源归属判断符合项目规范

## 六、交付完成前你必须更新 handoff

把以下信息写进：

- `docs/design/ai-orchestration-platform/31-parallel-delivery-kit-20260323/AI-4-handoff.md`

必须写清：

- 工作副本路径、分支名、冻结提交、冻结时间
- 新增了哪些页面和 API 文件
- 需要后端提供哪些权限码和字段
- 需要主协调者最后接入哪些入口
- 页面依赖哪些后端字段、接口、状态枚举
- 关键截图路径和最小联调结果
- 你跑过哪些前端校验
- 还有什么已知风险

## 七、验收标准

- 没有改任何冻结文件
- 没有 backend 改动
- 没有 admin 前端改动
- 严格使用项目 CRUD 模式
- tenant 双语 i18n 独立完整
- 推荐中心不是聊天壳，而是结构化运营页面
- handoff 写完整
