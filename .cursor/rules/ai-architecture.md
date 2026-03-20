# AI 架构规则（强制）

> 本规则适用于 NovusAI SaaS 项目中所有涉及 AI 功能的开发。违反任何一条均视为代码缺陷。
> 详细 AI 模块开发规范见 [../skills/novusai-saas/references/ai-module.md](../skills/novusai-saas/references/ai-module.md)。

## 一、核心原则：Agent→Skill 全链路

**所有 AI 功能必须通过 Agent 调度 Skill 完成，禁止直接调用 AIGateway。**

```
外部请求 → Agent.run() → Skill.execute() → AIGateway → LLM Provider
```

### 禁止事项

- ❌ 在 Controller/Service 层直接调用 `AIGateway.chat()` / `stream_chat()` / `embedding()` 发起 LLM 调用
- ❌ 新增绕过 Agent→Skill 链路的 AI 端点
- ❌ 使用已废弃的 `ToolRegistry`（`app.ai.tools.registry`）/ `tool_bindings` JSON 字段
- ❌ 硬编码 Agent name，使用枚举或常量

### 允许事项

- ✅ Agent engine 内部 LLM 调用（`conversation.py` / `base.py` / `task.py` / `dispatcher.py`）
- ✅ RAG 管道内部 LLM 调用（`rag/embedding.py` / `query_rewriter.py` / `reranker.py` / `processor.py` / `vision_describer.py`）
- ✅ `AIGateway.test_model` — 仅模型连通性测试
- ✅ `SystemAgentService`（`app/ai/system_agent.py`）— Controller 层唯一合法 AI 调用入口
- ✅ 引擎装配：编排层创建 `AIGateway(db)` 注入 Engine 构造函数，但**禁止直接调用** gateway LLM 方法

## 二、Agent 核心规则

- **执行模式**：`conversation`（多轮对话）/ `task`（单次）/ `batch`（批量）/ `api`（外部集成）
- **资源作用域**：`ResourceScopeEnum` 仅五类：`global_shared` / `admin_only` / `all_tenants` / `admin_and_selected_tenants` / `selected_tenants`
- **可编辑/归属**：看 **`owner_tenant_id`**（列表 API 常序列化为 `tenant_id`），**禁止**再用「`all_tenants` + 是否带 tenant」旧双重语义推断
- **权限/菜单端别**：`PermissionScope`（admin/tenant/user/both），与资源作用域无关
- `is_system=True` → 不可删除/禁用
- 工具绑定通过 `AgentSkillBinding`（M:N），禁止使用废弃的 `tool_bindings` JSON 字段
- `routing_config`（JSON）：多模型路由 → 详见 `references/ai-routing.md`

## 三、Agent↔Skill 绑定规则

- Agent 通过 `AgentSkillBinding` 与 `SkillPackage` 建立 M:N 关系
- **授权模式**（`consent_mode`）：`auto`（自动）/ `ask`（需用户确认）/ `reject`（禁止）
- 写操作类工具（`data_create` / `data_update` / `data_delete`）**建议**设为 `ask`
- `config_override` 可覆盖技能包的 Valves 配置

## 四、技能体系核心规则

- Skill **必须**归属 SkillPackage（`package_id` 必填）
- **绑定模式**：`auto`（按 scope 自动匹配）/ `manual`（需 AgentSkillBinding 显式绑定）
- 系统包（`is_system=True`）默认 `auto`，企业只能创建 `manual`
- **前端入口**：仅 `/admin/ai/skill-packages` 和 `/tenant/ai/skill-packages`，**禁止独立技能路由**
- **7 种技能类型**：`toolkit` / `knowledge_base` / `data_intelligence` / `builtin` / `http` / `email` / `code_execution`
- **SkillResolver** 是唯一合法的 Skill→ToolDefinition 转换器，禁止使用 `ToolRegistry`

### Toolkit 安全扫描

非 `is_system` 的 Toolkit 执行前进行 AST 安全扫描：
- 禁止 import：`os` / `subprocess` / `sys` / `pickle` / `socket` / `pathlib` 等（完整列表见 `_BLOCKED_MODULES`）
- 禁止调用：`eval()` / `exec()` / `compile()` / `__import__()` / `open()` 等（`_BLOCKED_BUILTINS`）

## 五、系统 Agent

- `is_system=True`，不可删除/禁用，通过 seed migration 创建
- 系统 Agent：`system_chat_agent` / `system_embedding_agent`
- Controller 层通过 `SystemAgentService` 调用 AI，架构：`Controller → SystemAgentService → AIGateway`

## 六、新增 AI 功能标准流程

1. 定义/复用 Skill 类型 → 2. 实现 Executor（继承 `BaseToolExecutor`）→ 3. 注册 SkillResolver 映射 → 4. 创建 Skill 记录 → 5. 绑定 Agent → 6. 通过 Agent 触发

**禁止跳过步骤直接调用 AIGateway。**

## 六-A、AI 写作规则

- 富文本编辑器 AI 写作统一走 `/admin|/tenant/ai/writing/{feature}`
- 后端必须通过 `writing_service.stream_writing_feature()` 解析 `system.ai_writing` 智能体分配
- 前端必须复用 `useEditorAI()` + `requestClient.postSSE()`，不要在业务页面手写 SSE 解析器
- 不要硬编码 Agent ID，不要在编辑器链路直接调用 `AIGateway`
- 结构化富文本输出通过 `withFormat` + `format_instruction` 约定处理，禁止把 HTML/JSON 协议文本直接回显给用户

## 六-B、会话记忆规则

- 会话记忆只允许用于真实对话场景：`ai_chat_page` / `admin_chat`
- `stream_chat_ephemeral()`、AI 写作、无对话持久化场景**禁止**启用会话记忆
- 会话记忆最终开关必须经 `AgentChatService._resolve_effective_memory_enabled()` 解析，遵守平台默认 + 管理端 Agent 开关 + 企业覆盖三层逻辑
- 会话记忆读写必须统一走 `SessionMemoryService`，禁止在 Controller/Service 手工拼 Redis key 自行写入
- 会话记忆分类固定为 `preferences` / `constraints` / `task_states` / `verified_facts`，禁止私自增加第 5 类
- 对话归档、删除、清空记忆必须统一经 `ConversationService` 清理；不要只依赖 TTL
- 前端统一复用 `useAIChat()` 的 `fetchConversationMemory()` / `clearConversationMemory()` / `memory_updated` 标记，禁止单页另写一套接口协议

→ 完整规范见 [../skills/novusai-saas/references/session-memory-spec.md](../skills/novusai-saas/references/session-memory-spec.md)

## 七、页面感知与操作规则

- 三层架构：Layer 1（system prompt 注入）+ Layer 2（`get_page_context` 工具）+ Layer 3（`invoke_page_operation` WebSocket 执行）
- 富文本页：**tool-first** — 有 pageop_* 时优先直调专用 tools；`content_format: 'html'|'markdown'` 与迁移/前端契约一致；禁止向用户回显 HTML/JSON/tool 参数，仅返回自然语言结果
- `_PROTECTED_TOOL_NAMES` 白名单保护页面感知/操作工具不被优化器过滤
- `readonly=false` 操作必须前端用户确认后才执行
- 操作超时 30s，超时后自动清理 asyncio.Future
- 新增页面操作时必须通过 `registerPageOperations()` 注册，禁止绕过注册表直接执行

## 八、上传与存储规则

**所有文件上传必须通过附件系统（Attachment）完成，禁止自建上传逻辑。**

- ❌ 禁止新建上传组件，必须复用 `FilePicker` / `ImageUpload` / `smartUploadFile`
- ❌ 禁止绕过 `FileValidator` 直接写入存储
- ❌ 禁止硬编码存储路径或上传 URL 前缀

→ 完整上传存储规范见 [../skills/novusai-saas/references/upload-storage-spec.md](../skills/novusai-saas/references/upload-storage-spec.md)
