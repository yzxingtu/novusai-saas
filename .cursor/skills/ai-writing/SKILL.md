---
name: ai-writing
description: NovusAI AI 写作技能。当需要开发或修复富文本编辑器 AI 写作、`/admin|/tenant/ai/writing/*` SSE 接口、`system.ai_writing` 智能体分配或 `useEditorAI()` 时，参考此技能。
---

# AI 写作技能

## 何时使用

- 修改富文本编辑器 AI 写作按钮、侧栏或结果插入逻辑
- 开发或修复 `/admin/ai/writing/{feature}`、`/tenant/ai/writing/{feature}`
- 调整 `system.ai_writing` 的 Agent 分配与解析逻辑
- 排查 AI 写作 SSE 输出、取消、格式化插入问题

## 核心原则

- AI 写作必须走平台级功能码 `system.ai_writing`
- 不允许在编辑器链路直接调用 `AIGateway`
- 管理端/企业端统一复用 `writing_service.stream_writing_feature()`
- 前端统一复用 `useEditorAI()`，不要在页面里复制 SSE 解析逻辑

## 标准流程

1. 先确认问题属于“编辑器 AI 写作”，不是通用 Agent Chat
2. 检查 feature 是否在 `VALID_FEATURES` 与 `_PROMPTS` 中完整注册
3. 检查 `AgentAssignmentService` 是否能解析到 `system.ai_writing`
4. 检查前端是否通过 `requestClient.postSSE()` 和 `useEditorAI()` 调用
5. 检查结果是纯文本插入还是 `withFormat` 的 Markdown -> HTML 插入

## 关键禁令

- 禁止在页面里硬编码 Agent ID
- 禁止新建第二套编辑器专用 AI 网关调用
- 禁止复制一份 SSE 解析器到具体业务页面
- 禁止把结构化格式输出写成用户可见协议文本

## 参考

- `../novusai-saas/references/ai-writing-spec.md`
- `../novusai-saas/references/ai-module.md`
- `../session-memory/SKILL.md`（若问题涉及“为什么写作场景不落会话记忆”）
