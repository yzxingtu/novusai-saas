---
name: novusai-saas
description: Umbrella skill for cross-cutting NovusAI SaaS work across FastAPI backend, Vue admin/tenant/user frontend, RBAC, AI modules, codegen, trace_id, and operations. Use when the task spans multiple subsystems or no narrower NovusAI skill fully covers it.
metadata:
  short-description: NovusAI umbrella guide
---

# NovusAI SaaS Router Skill

这是项目级路由技能，不再承载大段重复规范正文。

## 先读哪里

1. `.trellis/workflow.md`
2. `.trellis/spec/guides/trellis-paths.md`
3. 按任务类型选 canonical 索引：
   - 后端：`.trellis/spec/backend/index.md`
   - 前端：`.trellis/spec/frontend/index.md`
   - AI runtime：`.trellis/spec/ai-runtime/index.md`
   - 跨层/插件：`.trellis/spec/guides/index.md`

## 什么时候用

- 任务跨后端、前端、AI、权限、trace、插件或治理层
- 你需要先判断应该切到哪个更窄的技能
- 你要对分层边界和交付约束做总把关

## 优先切换到更窄技能

- 上传/附件：`attachment-storage`
- 页面感知/页面操作：`ai-page-awareness`
- AI 写作：`ai-writing`
- 会话记忆：`session-memory`
- 知识库/RAG：`knowledge-base-rag`
- 测试验证：`testing-validation`
- 插件开发：`plugin-development`
- WebSocket：`websocket-guide`
- 用户端：`user-endpoint`

## 最小规则

- 用最轻的 Trellis path 解决问题
- 只读取当前任务直接需要的规范和代码
- 若固定模型文案要改，统一走 prompt contracts
- 若规则冲突，以 `.trellis/spec/**` 为准
