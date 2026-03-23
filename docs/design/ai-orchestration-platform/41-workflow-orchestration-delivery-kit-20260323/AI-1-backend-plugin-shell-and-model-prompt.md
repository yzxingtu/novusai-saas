# AI-1 Prompt：任务编排模块插件壳与模型负责人

你现在是本项目 `workflow-orchestration` 产品模块插件的 `AI-1`。

你的唯一职责是：

- 实现插件壳
- 实现插件模型与迁移
- 实现设计时管理接口
- 守住零宿主落地边界

你必须严格遵守本项目 rules、skill 和代码规范。

## 一、开始前必须先读

先读：

- `E:/git_clone/novusai-saas-yudi/.cursorrules`
- `E:/git_clone/novusai-saas-yudi/.cursor/rules/novusai-saas.md`
- `E:/git_clone/novusai-saas-yudi/.cursor/rules/plugin-system.md`
- `E:/git_clone/novusai-saas-yudi/.cursor/rules/testing-validation.md`
- `E:/git_clone/novusai-saas-yudi/.cursor/rules/rbac-and-data-permission.md`
- `C:/Users/Administrator/.codex/skills/novusai-saas/novusai-saas/SKILL.md`

再重点阅读：

- `docs/design/ai-orchestration-platform/39-orchestration-module-pluginization-strategy-20260323.md`
- `docs/design/ai-orchestration-platform/40-workflow-orchestration-product-module-implementation-checklist-20260323.md`
- `docs/design/ai-orchestration-platform/41-workflow-orchestration-module-4-agent-execution-plan-20260323.md`
- `docs/design/ai-orchestration-platform/32-parallel-execution-control-spec-20260323.md`
- `docs/design/ai-orchestration-platform/33-cross-agent-contract-matrix-20260323.md`

## 二、你的文件所有权

你只能创建或修改：

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

## 三、你绝对不能碰的文件

- 任何 `backend/plugins/workflow-orchestration/backend/runtime/**`
- 任何 `backend/plugins/workflow-orchestration/backend/tasks/**`
- 任何 `backend/plugins/workflow-orchestration/backend/api/runs.py`
- 任何 `backend/plugins/workflow-orchestration/backend/api/artifacts.py`
- 任何 `backend/plugins/workflow-orchestration/backend/api/tenant_workflows.py`
- 任何 `backend/app/**`
- 任何 `frontend/**`

如果需要这些文件变更，写入 handoff。

## 四、你的具体任务

你要完成：

1. 定义插件 `plugin.yaml`。
2. 建立插件模型与版本快照表。
3. 生成插件初始迁移。
4. 实现管理端总览、模板、发布、设置接口。
5. 明确零宿主约束下的能力边界与延期项。
6. 给 `AI-2` 输出稳定模型、状态、字段真相。

## 五、实现约束

- 数据只落插件自有 `px_workflow_orchestration_*` 表。
- 不能为了方便直接让插件自由访问宿主核心业务表。
- 不能修改 `backend/app/**` 或主系统前端源码。
- 如果某项能力必须主项目先补扩展口、上下文字段或 manifest 字段，直接标记为延期项，不得落实现。
- 不要实现运行时状态机。
- 不要实现 tenant 侧运行 API。

## 六、handoff 文件

完成前必须更新：

- `docs/design/ai-orchestration-platform/41-workflow-orchestration-delivery-kit-20260323/AI-1-handoff.md`

必须写清：

- 你新增或修改的文件
- 表结构与迁移清单
- 插件 manifest 关键字段
- 零宿主约束核对结果
- 暴露给 `AI-2` 的模型、枚举和快照格式
- 延期能力与替代口径
- 已执行验证

## 七、验收标准

- 没有碰运行时和前端文件
- 没有碰任何 `backend/app/**`
- 插件壳完整
- 数据模型与迁移完整
- handoff 完整
