# 管理员账号级 AI 可用性

## Goal

为平台管理员和企业管理员增加账号级 `ai_enabled` 开关，并把“命令面板入口”和“AI 对话能力”解耦。禁用 AI 的账号仍可通过 `Ctrl+K` 或顶部入口打开命令搜索，但不能使用 AI chat surface，也不能通过直连 API 绕过。

## Requirements

- 平台管理员、企业管理员模型和 API 契约新增 `ai_enabled`，历史账号默认 `true`。
- `ai_enabled=false` 对所有账号生效，包括平台超管和企业所有者。
- AI 开关管理权是可分配权限，不与普通成员编辑权限绑定：
  - 平台组织成员：`organization:manage_member_ai`。
  - 企业组织成员：`organization:manage_member_ai`。
  - 平台侧租户管理员：`tenant_admin:manage_ai`。
- 创建/更新请求显式携带 `ai_enabled` 时必须拥有对应 AI 开关管理权限；未携带时不检查该权限。
- 企业端 AI 可用性同时受租户套餐 `features.ai_enabled`、账号开关、RBAC、当前路由 AI 策略影响。
- `/admin/ai/agent-chat/**` 和 `/tenant/ai/agent-chat/**` 必须在进入 AI service/provider/runtime 前硬拦截禁用账号。
- 禁用 AI 后不允许访问 AI chat surface：chat、stream、route、conversations、memory-state、compact、timeline。
- AI 监控/审计页面不受账号 AI 使用开关影响，继续使用现有 RBAC。
- 前端 `CommandBar` 在 AI 不可用时仍可打开并搜索/跳转菜单，但不得加载智能体、最近对话或发送 AI 消息。
- 管理 UI 在现有管理员创建/编辑表单中提供紧凑 `AI 对话` Switch；无管理权限时只读展示且不提交字段。

## Acceptance Criteria

- 数据库迁移、模型、schema、auth `/me`、组织成员、租户管理员列表/详情都保留 `ai_enabled=false`。
- 新权限出现在权限树正确父节点下，并且普通编辑权限不能修改 AI 开关。
- 禁用账号直连 AI chat API 返回结构化 403，且不会进入 AI service/provider/runtime。
- 企业套餐 AI 关闭时企业管理员无法使用 AI chat，并返回套餐禁用原因。
- `Ctrl+K` 和顶部入口在 AI 不可用时仍打开命令面板；菜单搜索可用；AI 面板不打开；无 `/ai/agent-chat/*` 请求。
- 启用账号的现有 AI chat、SSE、记忆保存、Responses tool replay 行为不回退。
- 新增/修改 AI live-path 测试显式标注 `Test type: structural / behavioral / smoke`。

## Verification

- 后端：migration revision、AI route contract、identity/workflow/service tests、targeted ruff。
- 前端：auth transform、entry policy、CommandBar、management form tests、targeted vue-tsc。
- Smoke：`AI account permission` 覆盖禁用账号命令面板可用、AI 不可用；既有 AI shell smoke 继续通过。
