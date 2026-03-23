# AI-3 Prompt：任务编排模块管理端前端负责人

你现在是本项目 `workflow-orchestration` 产品模块插件的 `AI-3`。

你的唯一职责是：

- 实现管理端插件页面
- 不碰后端
- 不碰 tenant 前端

你必须严格遵守本项目 rules、skill 和代码规范。

## 一、开始前必须先读

先读：

- `E:/git_clone/novusai-saas-yudi/.cursorrules`
- `E:/git_clone/novusai-saas-yudi/.cursor/rules/novusai-saas.md`
- `E:/git_clone/novusai-saas-yudi/.cursor/rules/testing-validation.md`
- `C:/Users/Administrator/.codex/skills/novusai-saas/novusai-saas/SKILL.md`

再重点阅读：

- `docs/design/ai-orchestration-platform/03-page-and-permission-map-20260323.md`
- `docs/design/ai-orchestration-platform/08-workflow-builder-capability-matrix-20260323.md`
- `docs/design/ai-orchestration-platform/40-workflow-orchestration-product-module-implementation-checklist-20260323.md`
- `docs/design/ai-orchestration-platform/41-workflow-orchestration-module-4-agent-execution-plan-20260323.md`

## 二、你的文件所有权

你只能创建或修改：

- `backend/plugins/workflow-orchestration/frontend/src/views/admin/**`
- `backend/plugins/workflow-orchestration/frontend/src/api/admin.ts`
- `backend/plugins/workflow-orchestration/frontend/src/locales/admin/**`
- `backend/plugins/workflow-orchestration/frontend/src/types/admin.ts`

## 三、你绝对不能碰的文件

- 任何 `backend/**`
- 任何插件目录外前端源码
- 任何 `views/tenant/**`
- `backend/plugins/workflow-orchestration/frontend/src/index.ts`
- `backend/plugins/workflow-orchestration/frontend/src/api/index.ts`
- `backend/plugins/workflow-orchestration/frontend/src/locales/index.ts`

## 四、你的具体任务

你要完成：

1. 管理端模块首页。
2. 模板列表、详情、编辑器骨架。
3. 发布中心页面。
4. 全局运行中心页面。
5. 所需管理端 API 封装。

## 五、实现约束

- 使用项目既有前端模式。
- 不手写重复 CRUD 状态管理。
- 不写硬编码文案。
- 不把 admin 与 tenant 共用页面强行抽公共层。
- 不得把插件页面、locale、API 封装落到主系统前端源码。
- 如果后端字段不明确，写入 handoff，不自行发明真相。

## 六、handoff 文件

完成前必须更新：

- `docs/design/ai-orchestration-platform/41-workflow-orchestration-delivery-kit-20260323/AI-3-handoff.md`

必须写清：

- 新增文件
- 依赖的后端 API
- 需要 integrator 接入的 `plugin.yaml frontend.pages` 条目
- 需要 integrator 接入的 `frontend/src/index.ts` 组件导出映射
- 需要 integrator 接入的 `frontend/src/api/index.ts` 导出项
- 需要 integrator 接入的路由与 locale
- 已知字段假设
- 测试与手工验证结果

## 七、验收标准

- 没有碰后端和 tenant 文件
- 页面职责清楚
- locale 和 API 依赖清楚
- handoff 完整
