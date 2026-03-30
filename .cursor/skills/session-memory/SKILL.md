---
name: session-memory
description: NovusAI 会话记忆技能。当需要开发或审查 AI Chat 会话记忆、`memory-state` 接口、三层记忆开关、Redis CAS/TTL/幂等、或前端记忆面板时，参考此技能。
---

# 会话记忆技能

## 何时使用

- 修改 AI Chat 的会话记忆读写逻辑
- 开发或修复 `GET/DELETE .../conversations/{id}/memory-state`
- 排查为什么某个对话没有注入记忆或没有写入记忆
- 调整 Agent 记忆三层开关、平台提取模型、前端记忆面板

## 核心原则

- 会话记忆只属于有 `conversation_id` 的 AI Chat 场景
- 记忆最终开关必须通过 `effective_memory_enabled` 解析，不能自己猜
- Redis 读写必须统一走 `SessionMemoryService`
- 清空记忆只清 Redis 状态，不删除消息历史
- AI Writing / `stream_chat_ephemeral()` 不允许落会话记忆
- Redis 四分类记忆只是 `conversation-scoped short-term memory`
- 跨会话 durable memory 不得继续塞进 Redis，会走 `LongTermMemoryProvider`
- 长期记忆真源是 `MemoryRecord`，画像是 `ProfileSnapshot`
- `trustSession` 不是记忆系统，也不是前端浏览器持久授权真相
- consent / confirmation 的最终真相必须走后端 `ExecutionTrustPolicy + ExecutionDecision`

## 标准流程

1. 先确认入口是不是 `admin_chat` 或 `ai_chat_page`
2. 检查 `AgentChatService._resolve_effective_memory_enabled()` 是否返回开启
3. 检查 `_load_session_memory_context()` 是否正确注入
4. 检查 `_persist_session_memory()` 是否抽取到 delta 并成功 upsert
5. 若开启长期记忆，检查 `_persist_session_memory()` 后是否触发 `LongTermMemoryProvider.capture`
6. 检查 `ConversationService` 的查询/清理接口与前端 `useAIChat()` 是否一致

## 关键禁令

- 禁止在 Controller 直接读写 Redis 记忆 key
- 禁止新增第二套 SQL 持久化记忆表
- 禁止在前端本地拼接记忆状态代替后端接口
- 禁止把 `trustSession` 做成 sessionStorage/localStorage 持久授权真相
- 禁止把 AI Writing 误接入会话记忆
- 禁止把长期记忆 capture 原始 tool output、页面快照、业务明细全文直接写入 durable memory

## 参考

- [../novusai-saas/references/session-memory-spec.md](../novusai-saas/references/session-memory-spec.md)
- [../novusai-saas/references/ai-module.md](../novusai-saas/references/ai-module.md)
