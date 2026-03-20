# 会话记忆规范

## 1. 模块定位

会话记忆（Session Memory）不是通用聊天历史，也不是长期知识库。它是围绕**单个 conversation** 的短期结构化记忆层，用于把用户在对话中反复强调的偏好、约束、任务状态、已确认事实注入后续轮次。

当前真实实现由以下链路组成：

- 入口 API：`/api/admin/ai/agent-chat/*`、`/api/tenant/ai/agent-chat/*`、`/api/user/ai/agent-chat/*`
- 编排服务：`backend/app/services/ai/agent_chat_service.py`
- 生命周期管理：`backend/app/services/ai/conversation_service.py`
- Redis 存储：`backend/app/services/ai/session_memory_service.py`
- 前端消费：`frontend/apps/web-antd/src/components/business/ai-chat-panel/use-ai-chat.ts`

**关键边界**：

- 会话记忆只服务于 `AgentChatService.chat()` / `stream_chat()` 这类“有 conversation_id 的对话”链路
- `stream_chat_ephemeral()`（如 AI Writing）**不创建对话，也不注入/写入会话记忆**
- 会话记忆不是数据库表，不要把这类状态另存一套 SQL 模型
- 会话记忆不是前端本地缓存，不要用 localStorage/sessionStorage 自行保存记忆条目

## 2. 场景开关与生效规则

### 2.1 场景边界

运行时并不是所有 AI 场景都启用记忆。`AgentChatService._resolve_memory_context()` 当前只在以下场景允许记忆生效：

- `MemorySceneEnum.AI_CHAT_PAGE`
- `MemorySceneEnum.ADMIN_CHAT`

其他场景即使传了 scene/channel/source，也会被降级为 `memory_enabled = false`。

因此：

- 用户端全页 AI Chat、企业端全局 AI 面板、管理端全局 AI 面板属于允许场景
- AI 写作、一次性工具调用、无对话持久化场景不允许启用记忆

### 2.2 三层开关

会话记忆不是简单的 Agent 布尔值，而是三层合并后的最终状态。

#### 管理端

`AdminAgentService.get_memory_config()`：

- 平台默认开关：`platform_default_memory_enabled`
- Agent 级开关：`agent.memory_enabled`
- 最终结果：`effective_memory_enabled = platform_default && admin_agent_enabled`

#### 企业端

`AgentService.resolve_memory_effective_config()`：

- 平台默认开关：`platform_default_memory_enabled`
- 管理端 Agent 开关：`agent.memory_enabled`
- 企业覆盖层：`AgentMemoryOverride.disabled`
- 最终结果：`platform_default && admin_agent_enabled && !tenant_agent_memory_disabled`

### 2.3 结论

- 任何入口都不应自行推断“记忆是否开启”
- 正确做法是通过 `AgentService.get_memory_config()` / `AdminAgentService.get_memory_config()` 获取 `effective_memory_enabled`
- 对话执行链路必须继续复用 `AgentChatService._resolve_effective_memory_enabled()`

## 3. 记忆数据结构

当前会话记忆固定分为 4 个分类，前后端都围绕这 4 个字段工作：

- `preferences`：用户偏好、喜欢/不喜欢、输出风格、工具偏好
- `constraints`：明确限制、禁止事项、边界条件
- `task_states`：当前任务进度、下一步、待办、持续中的工作
- `verified_facts`：用户已确认的身份/组织/技术栈等事实

Redis 中还会维护这些元数据：

- `tenant_id`
- `channel`
- `source`
- `agent_id`
- `user_id`
- `conversation_id`
- `version`
- `updated_at`
- `last_event_id`
- `metadata`

前端展示面板和 SSE `done` 事件只应消费：

- 4 个分类数组
- `version`
- `updated_at`
- `memory_updated`

不要擅自扩展成第 5 类记忆；若必须扩展，需要同时改后端提取提示词、Redis merge、前端 UI、API 类型。

## 4. 提取与注入链路

### 4.1 记忆提取

每一轮对话结束后，`AgentChatService._persist_session_memory()` 会调用 `_extract_memory_delta()` 从“用户消息 + 助手响应”中抽取增量记忆。

提取模型选择优先级：

1. 平台配置 `memory_extraction_provider` + `memory_extraction_model`
2. 若未配置，则回退到当前 Agent 绑定模型

平台配置定义位置：

- `backend/app/configs/definitions/platform/ai_memory.py`

约束：

- 返回值必须是 JSON，字段固定为 4 个分类数组
- 没有值得记忆的内容时，返回空数组，不要生成噪声摘要
- 提取失败必须静默降级，不能影响主对话链路

### 4.2 记忆注入

下一轮执行前，`AgentChatService._load_session_memory_context()` 会把当前会话记忆组装成 system 可注入文本：

- `Constraints: ...`
- `Preferences: ...`
- `Task States: ...`
- `Verified Facts: ...`

这是**编排层责任**。不要在 Controller、前端或单个 Executor 中手工再拼一套记忆提示词。

## 5. Redis 存储协议

`SessionMemoryService` 不是简单 `get/set`，它实现了 4 个关键保障：

### 5.1 Key 命名

Key 格式：

`mem:sess:{tenant_id}:{channel}:{source}:{agent_id}:{user_id}:{conversation_id}`

相关常量与辅助函数位于：

- `backend/app/ai/constants.py`

### 5.2 CAS 版本控制

`update_state_cas()` 通过 Redis `WATCH/MULTI` 做 compare-and-set：

- 只在 `expected_version == current_version` 时写入
- 冲突时返回最新 state，由 `upsert_state()` 自动重试一次

### 5.3 幂等控制

同一轮写入通过 `last_event_id` 防重：

- 相同 `event_id` 再次写入时直接返回成功
- 避免 SSE 回调重入时把同一批记忆重复累计

### 5.4 TTL 与降级

- TTL：`SESSION_MEMORY_TTL_SECONDS = 86400`（24h）
- Redis 未初始化或不可用时，服务降级返回空状态，不阻断主链路

结论：

- 禁止直接在业务代码里 `redis.set()` 手工写会话记忆
- 必须统一走 `SessionMemoryService`

## 6. 清理与生命周期

会话记忆不应只依赖 TTL，被归档/删除的会话需要主动清理。

当前真实清理点：

- `ConversationService.archive_conversation()`
- `ConversationService.batch_archive()`
- `ConversationService._after_delete()`
- 管理端/企业端/用户端 `DELETE .../conversations/{id}/memory-state`

因此：

- 会话归档后要同步清理记忆
- 删除对话后要同步清理记忆
- 前端“清空记忆”操作只清记忆，不删除消息历史

## 7. API 与前端契约

### 7.1 后端接口

三端都已提供统一接口：

- `GET /api/admin/ai/agent-chat/conversations/{conversation_id}/memory-state`
- `DELETE /api/admin/ai/agent-chat/conversations/{conversation_id}/memory-state`
- `GET /api/tenant/ai/agent-chat/conversations/{conversation_id}/memory-state`
- `DELETE /api/tenant/ai/agent-chat/conversations/{conversation_id}/memory-state`
- `GET /api/user/ai/agent-chat/conversations/{conversation_id}/memory-state`
- `DELETE /api/user/ai/agent-chat/conversations/{conversation_id}/memory-state`

入口统一经 `ConversationService.get_conversation_memory_state()` / `clear_conversation_memory_state()`，不要在 Controller 直接访问 Redis。

### 7.2 前端消费

前端统一经 `useAIChat()` 暴露以下能力：

- `fetchConversationMemory()`
- `clearConversationMemory()`
- `memoryState`
- `memoryLoading`
- `lastMemoryUpdated`

共享 API 封装在：

- `frontend/apps/web-antd/src/api/shared/ai-chat.ts`

用户端全页与全局侧滑面板都复用这套能力：

- `frontend/apps/web-antd/src/views/user/ai-chat/index.vue`
- `frontend/apps/web-antd/src/components/business/ai-slide-panel/AIChatSlidePanel.vue`

### 7.3 `memory_updated` 约定

当一轮对话写入了新的记忆增量时：

- SSE `done` 事件会带 `memory_updated: true`
- `ConversationService.mark_memory_updated()` 会把最后一条 assistant 消息的 metadata 标记为 `memory_updated`
- 前端加载历史消息时会恢复该标记，用于展示“本轮更新了记忆”

不要再在前端另外维护一套“是否更新记忆”的本地标识。

## 8. 开发禁令

- 禁止在 Controller 直接读写 Redis 会话记忆 key
- 禁止在 AI Writing、ephemeral chat 中启用会话记忆
- 禁止把会话记忆建成 SQL 表做第二套持久化
- 禁止在前端把记忆分类名、文案、接口路径写死成与后端不同的值
- 禁止扩展自定义记忆字段而不同步更新提取、存储、接口和 UI
- 禁止绕过 `ConversationService` 直接在删除/归档逻辑里遗漏记忆清理

## 9. 审查清单

- [ ] 入口场景是否真的属于 `ai_chat_page` / `admin_chat`
- [ ] 是否通过 `AgentChatService` 统一解析 `memory_scene` / `memory_channel` / `memory_source`
- [ ] 是否通过 `get_memory_config()` / `_resolve_effective_memory_enabled()` 解析最终开关
- [ ] 是否复用 `SessionMemoryService`，而不是手写 Redis 访问
- [ ] 是否沿用 4 个固定分类：`preferences` / `constraints` / `task_states` / `verified_facts`
- [ ] 会话归档、删除、清空记忆时是否同步清理 Redis key
- [ ] 前端是否复用 `useAIChat()` 的 memory API，而不是单页手写请求
- [ ] SSE `done` 与历史消息 metadata 是否正确透传 `memory_updated`

## 10. 已知代码基线风险

以下是本轮审计发现的**代码本身**不一致点，不应被 `.cursor` 文档继续放大：

- `backend/app/ai/constants.py` 中 `MEMORY_ENABLED_SCENE` 的注释仍写“仅该场景允许启用会话记忆”，但运行时 `AgentChatService._resolve_memory_context()` 实际同时允许 `ai_chat_page` 与 `admin_chat`
- `frontend/apps/web-antd/src/components/business/ai-chat-panel/use-ai-chat.ts` 的顶部注释仍把 `apiPrefix` 描述成 `'/admin' or '/tenant'`，但当前用户端已真实复用该 composable，并传入 `/api/user`

这些属于代码注释/常量说明漂移，后续若做代码治理，应以运行时实现为准统一修复。
