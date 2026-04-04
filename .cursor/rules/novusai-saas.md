# NovusAI SaaS Rule Index

这是 `.cursor/rules` 的兼容入口。项目的 canonical 规范已经收口到
`.trellis/spec/**`，这里不再复制长篇规则正文。

## 先读哪里

1. `.trellis/workflow.md`
2. `.trellis/spec/guides/trellis-paths.md`
3. 按任务类型选择：
   - 后端：`.trellis/spec/backend/index.md`
   - 前端：`.trellis/spec/frontend/index.md`
   - AI runtime：`.trellis/spec/ai-runtime/index.md`
   - 跨层/插件：`.trellis/spec/guides/index.md`

## 主题跳转

- AI / Agent / Tool / Prompt Contract：`ai-architecture.md` + `.trellis/spec/ai-runtime/index.md`
- 上传/下载/存储：`attachments-and-storage.md`
- 异步任务 / WebSocket / 通知：`async-notification-websocket.md`
- 插件 runtime / manifest / 资源 / release：`.trellis/spec/guides/plugin-runtime-playbook.md`
- RBAC / 数据权限 / 用户端：`rbac-and-data-permission.md`、`user-endpoint-and-domain-isolation.md`
- 测试与验证：`testing-validation.md`
- Trace / 监控：`trace-and-monitoring.md`

## 不可违反

- 禁止把固定模型指令、工具描述、重试引导硬编码进 Python；统一走 `backend/app/ai/prompt_contracts/resources/`
- 禁止 Controller 写业务逻辑或直接查库
- 禁止 Service 越权承担 Repository 职责
- 禁止强制所有任务走重型 Trellis 流程
- 禁止恢复已退役的 marker loop、archive 自动提交、旧 planner 行为

## 备注

如果这里和 `.trellis/spec/**` 冲突，以 `.trellis/spec/**` 为准。
