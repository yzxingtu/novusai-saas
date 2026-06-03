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

- 默认遵循“高内聚、低耦合”：页面/组件/Composable/Controller/Service/Repository
  只承担单一主职责，跨层依赖必须通过既有 contract 或 shared helper，不能旁路直连
  对方内部实现；详见 `.trellis/spec/guides/code-reuse-thinking-guide.md`
- 仓库存在广泛并行改动时，必须先建 umbrella task、ownership matrix 和冻结
  写集，再开子代理/子任务并行推进；详见
  `.trellis/spec/guides/repo-stabilization-workstreams.md`
- 禁止把固定模型指令、工具描述、重试引导硬编码进 Python；统一走 `backend/app/ai/prompt_contracts/resources/`
- 禁止 Controller 写业务逻辑或直接查库；默认不允许在 controller/helper
  内直接 `db.execute(...)` / `session.execute(...)`
- 禁止 Service 越权承担 Repository 职责
- 禁止强制所有任务走重型 Trellis 流程
- 禁止恢复已退役的 marker loop、archive 自动提交、旧 planner 行为

## 备注

如果这里和 `.trellis/spec/**` 冲突，以 `.trellis/spec/**` 为准。
