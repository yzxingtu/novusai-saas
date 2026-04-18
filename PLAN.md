# 六子代理并行执行的 AI 模块重写与拆分总计划

## 摘要

- 本计划采用“六个执行子代理并行开发，主代理只做架构守卫、代码审计、集成、验证、最终提交到 `main`”的执行模式。
- 目标不是继续在现有巨型文件上打补丁，而是把 AI 模块重构成“高内聚、低耦合、可替换、可测试”的模块化系统。
- 本计划覆盖全 AI 模块，而不是只覆盖会话主链。范围包括：
  - 对话 runtime、provider adapter、gateway、intent、context、memory、RAG
  - skills、tools、page runtime、web search、AI writing
  - agent chat、conversation、monitoring、diagnostics、quota、analytics、call logs、router、inventory
  - 前端 AI chat panel、slide panel、AI runtime、user chat、admin/tenant AI 页面、monitoring 页面
- 外部 HTTP API、SSE 事件名、数据库表结构、日志口径、主要前端交互，在重写期间默认保持兼容。
- 所有超过 1000 行的 AI 生产文件必须进入本计划，能拆就拆，不允许继续增长；拆分完成后默认目标如下：
  - Python 生产文件目标不超过 600 行
  - Provider 协议实现目标不超过 400 行
  - Vue SFC 目标不超过 450 行
  - TS composable 目标不超过 500 行
  - 任何保留超过 800 行的生产文件，必须写 ADR 说明为什么无法继续拆

## 项目规范与架构硬约束

- 必须遵循本项目 Trellis 与 AI runtime 规范：
  - `.trellis/spec/backend/index.md`
  - `.trellis/spec/guides/index.md`
  - `.trellis/spec/ai-runtime/index.md`
  - `C:\Users\Administrator\.codex\skills\novusai-saas\novusai-saas\references\ai-module.md`
- 必须遵守以下工程约束：
  - Controller 不写业务逻辑
  - Service 不直接承担跨层拼装的大总管职责
  - Repository 不写业务判断
  - Prompt 文本不内嵌到运行时代码，统一走 `prompt_contracts/resources/`
  - 后端用户可见文本统一 `_()`，前端统一 `t()` / `$t()`
  - 日志统一走 `app.core.logging`
  - 不允许新建跨域巨型“工具箱”文件
  - 不允许以“共享方便”为理由把多种职责塞进同一文件
- 高内聚低耦合具体定义：
  - 一个模块只能围绕一个稳定变化轴组织
  - 模块边界必须通过 typed contract 通信，不允许隐式 metadata 猜测
  - 跨模块只依赖接口/DTO，不依赖对方内部 helper
  - 不允许双向依赖
  - 不允许 runtime 策略同时在两层以上重复实现
  - 前端页面层不允许直接复刻后端业务推断逻辑
- 主代理拥有最终架构裁决权，任何子代理实现若破坏边界，主代理必须拒收并要求回改。

## 当前必须纳入重写与拆分的超大模块

### 后端超大模块

| 行数 | 文件 |
|---|---|
| 3887 | `backend/app/ai/engine/base.py` |
| 3188 | `backend/app/services/ai/conversation_service.py` |
| 3177 | `backend/app/ai/adapters/openai_adapter.py` |
| 2269 | `backend/app/services/ai/agent_chat_service.py` |
| 2041 | `backend/app/ai/engine/stream_handler.py` |
| 1950 | `backend/app/ai/gateway.py` |
| 1694 | `backend/app/ai/engine/conversation.py` |
| 1613 | `backend/app/services/ai/monitoring_service.py` |
| 1378 | `backend/app/ai/engine/turn_executor.py` |
| 1366 | `backend/app/ai/tools/executors/builtin_executor.py` |
| 1310 | `backend/app/services/ai/agent_service.py` |
| 1276 | `backend/app/ai/engine/recovery_manager.py` |
| 1260 | `backend/app/services/ai/runtime_diagnostics_service.py` |
| 1244 | `backend/app/services/ai/agent_router_service.py` |
| 1207 | `backend/app/ai/skills/resolver.py` |
| 1203 | `backend/app/ai/engine/intent_planner.py` |
| 1165 | `backend/app/ai/engine/tool_processor.py` |
| 1137 | `backend/app/ai/context/engine.py` |
| 1133 | `backend/app/ai/web_search/orchestrator.py` |
| 1006 | `backend/app/ai/rag/retriever.py` |

### 前端超大模块

| 行数 | 文件 |
|---|---|
| 3296 | `frontend/apps/web-antd/src/components/business/ai-chat-panel/use-ai-chat.ts` |
| 3023 | `frontend/apps/web-antd/src/components/business/ai-chat-panel/ChatMessageItem.vue` |
| 2173 | `frontend/apps/web-antd/src/views/admin/ai/agents/detail.vue` |
| 2072 | `frontend/apps/web-antd/src/views/tenant/ai/agents/detail.vue` |
| 1796 | `frontend/apps/web-antd/src/views/user/ai-chat/index.vue` |
| 1769 | `frontend/apps/web-antd/src/components/business/ai-slide-panel/AIChatSlidePanel.vue` |
| 1246 | `frontend/apps/web-antd/src/features/ai-monitoring/pages/MonitoringConversationDrawer.vue` |
| 1161 | `frontend/apps/web-antd/src/features/ai-monitoring/pages/MonitoringUsagePage.vue` |

- 历史条目 `frontend/apps/web-antd/src/composables/use-ai-operations.ts` 已在后续重构中拆分清退，现由 `use-page-ai-operation-helpers*.ts` 系列承接。

## 新架构目标

### 核心分层

- `application services`
  - 只做用例编排，不做协议策略、不做 UI read model 推断。
- `runtime kernel`
  - 只负责 turn 执行、protocol plan、round loop、failure policy。
- `protocol layer`
  - 只负责单协议执行，不拥有跨协议 fallback 权限。
- `intent pipeline`
  - 只负责分类，不直接触发 KB/memory side effect。
- `context pipeline`
  - 只消费 intent 和 runtime context，输出显式 contribution。
- `tool runtime`
  - 负责技能解析、工具目录、页面运行时、工具执行。
- `observability/read models`
  - 负责 diagnostics、monitoring projection、conversation projection。
- `frontend shell`
  - 只做视图组合；状态、流式解析、错误、工具状态、诊断全部拆到 composable/store。

### 内部 contract

- 新增内部类型与 contract，作为所有子代理必须共同遵守的稳定接口：
  - `TurnCommand`
  - `ProtocolCapabilities`
  - `ProtocolExecutionPlan`
  - `ProviderProtocolClient`
  - `IntentSet`
  - `ContextContribution`
  - `TurnExecutionResult`
  - `ConversationReadModel`
  - `MonitoringConversationReadModel`
  - `MonitoringUsageReadModel`
- 外部 API 默认不变，先通过 compatibility facade 迁移。
- 新 contract 生效后，旧 giant file 只能做委托，不允许继续保留核心逻辑。

## 六个子代理的固定分工

### 总体协作规则

- 六个子代理全部使用“独立写集”并行开发。
- 主代理不把关键共享文件写权限下放给子代理。
- 子代理禁止修改他人 owned scope 内文件。
- 子代理之间允许新增接口依赖，但接口签名必须由主代理确认后统一冻结。
- 每个子代理交付物必须包含：
  - 新目录结构与模块图
  - compatibility facade
  - 单元测试与集成测试
  - 风险与兼容性说明
  - 待主代理接线的清单
- 主代理负责：
  - 冻结 contract
  - 审计所有 patch
  - 处理共享 wiring
  - 跑回归
  - 最终提交到 `main`

### 子代理 1：Runtime Kernel Worker

- 负责范围：
  - `backend/app/ai/engine/base.py`
  - `backend/app/ai/engine/conversation.py`
  - `backend/app/ai/engine/stream_handler.py`
  - `backend/app/ai/engine/turn_executor.py`
  - `backend/app/ai/engine/recovery_manager.py`
  - `backend/app/ai/engine/execution_state_machine.py`
  - `backend/app/ai/engine/tool_processor.py`
  - `backend/app/ai/runtime/query_engine.py`
  - `backend/app/ai/runtime/` 下新增 kernel 相关模块
- 不允许修改：
  - `backend/app/ai/adapters/**`
  - `backend/app/services/ai/**`
  - 前端任何文件
- 必做拆分：
  - `engine/base.py` 拆成 `engine_shared/` 包
