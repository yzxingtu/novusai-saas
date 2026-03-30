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
- ✅ `InternalAIService`（`app/ai/internal_ai_service.py`）— 仅基础设施级内部 AI 网关入口，用于替代旧 `SystemAgentService`
- ✅ 引擎装配：编排层创建 `AIGateway(db)` 注入 Engine 构造函数，但**禁止直接调用** gateway LLM 方法

## 二、Agent 核心规则

- **执行模式**：`conversation`（多轮对话）/ `task`（单次）/ `batch`（批量）/ `api`（外部集成）
- **资源作用域**：`ResourceScopeEnum` 仅五类：`global_shared` / `admin_only` / `all_tenants` / `admin_and_selected_tenants` / `selected_tenants`
- **可编辑/归属**：看 **`owner_tenant_id`**（列表 API 常序列化为 `tenant_id`），**禁止**再用「`all_tenants` + 是否带 tenant」旧双重语义推断
- **权限/菜单端别**：`PermissionScope`（admin/tenant/user/both），与资源作用域无关
- `is_system=True` → 不可删除/禁用
- 技能授权通过 `AgentSkillGrant`（Agent 直接授权 Skill），禁止使用废弃的 `tool_bindings` JSON 字段
- `routing_config`（JSON）：多模型路由 → 详见 [../skills/novusai-saas/references/ai-routing.md](../skills/novusai-saas/references/ai-routing.md)

## 三、Agent↔Skill 绑定规则

- Agent 运行时通过 `AgentSkillGrant` 直接持有 Skill 授权
- SkillPackage 仍可作为管理端/企业端的归组、来源与目录单元，但**不是**运行时绑定真相
- **授权模式**（`consent_mode`）：`auto`（自动）/ `ask`（需用户确认）/ `reject`（禁止）
- 写操作类工具（`data_create` / `data_update` / `data_delete`）**建议**设为 `ask`
- `AgentSkillGrant` 上的 override/config 字段仅作用于该条直接授权，不重新引入包级自动绑定语义

## 四、技能体系核心规则

- Skill **必须**归属 SkillPackage（`package_id` 必填）
- SkillPackage 是**归组 / 来源 / 目录**单元，不是运行时自动绑定单元
- `SkillPackage` / `Skill` 的**目录可见性与归属**主要由 **`tenant_id`、`package_id`、Skill 的 `tenant_id`（归属列）及仓储层过滤**表达；**`ResourceScopeEnum` 只适用于带 `scope` 列的其它资源，不得直接套用到 `skill_packages` / `skills`**。**运行时是否给某个 Agent 生效，只看 `AgentSkillGrant`**
- **前端入口**：管理端使用 `/admin/ai/skill-packages`；企业端允许只读目录 `/tenant/ai/skill-packages`，但禁止 tenant 侧 SkillPackage CRUD / valves 编辑 / 包级运行绑定
- **6 种 SkillTypeEnum 技能类型**：`toolkit` / `data_intelligence` / `builtin` / `http` / `email` / `code_execution`，`knowledge_base` 类型已退役，相关功能由 `AgentKnowledgeBaseBinding` + `Agent.rag_config` 直接管理。
- **SkillResolver** 是唯一合法的 Skill→ToolDefinition 转换器，禁止使用 `ToolRegistry`

### Toolkit 安全扫描

非 `is_system` 的 Toolkit 执行前进行 AST 安全扫描：
- 禁止 import：`os` / `subprocess` / `sys` / `pickle` / `socket` / `pathlib` 等（完整列表见 `_BLOCKED_MODULES`）
- 禁止调用：`eval()` / `exec()` / `compile()` / `__import__()` / `open()` 等（`_BLOCKED_BUILTINS`）

## 五、系统 Agent

- `is_system=True`，不可删除/禁用，通过 seed migration 创建
- 系统 Agent：`system_chat_agent` / `system_embedding_agent`
- 历史 `SystemAgentService` 已被 `InternalAIService` 替代；仅基础设施级内部调用允许经 `InternalAIService → AIGateway`

## 六、新增 AI 功能标准流程

1. 定义/复用 Skill 类型 → 2. 实现 Executor（继承 `BaseToolExecutor`）→ 3. 注册 SkillResolver 映射 → 4. 创建/同步 SkillPackage（作为目录与来源单元）→ 5. 创建 Skill 记录 → 6. 通过 `AgentSkillGrant` 直接授权 Agent → 7. 通过 Agent 触发

**禁止跳过步骤直接调用 AIGateway。**

## 六-0、企业 AI 配额与限速规则

- **硬配额 / Hard quota**：超限后必须直接拒绝请求，返回 `HTTP 429`，业务码 `4291`；页面文案、诊断接口、运行时拦截三者必须一致。
- **软配额 / Soft quota**：超限后**不允许**阻断请求；必须继续累计用量，并保留告警通知语义。若页面显示“允许超额”，运行时也必须确实放行。
- **速率限制 / Rate limit**：超限后必须直接拒绝请求，返回 `HTTP 429`，业务码 `4292`；RPM/TPM 任一命中都算拦截。
- **全局配额回退 / Global quota fallback**：仅当“同企业 + 同周期”不存在模型专属启用规则时，才允许命中 `model_id IS NULL` 的全局规则；模型专属规则优先级更高。
- **继承语义 / Inheritance semantics**：企业级 `rpm_limit` / `tpm_limit = null` 表示“继承模型默认值”，**不是**“把默认限速清空”。
- **诊断页职责 / Diagnostics responsibility**：`/admin/ai/quotas` 与 `/admin/ai/quotas/rate-limits` 必须展示**真实运行时生效结果**，不能只回显原始 CRUD 字段；至少要说明当前生效值、来源、超限动作、HTTP 状态与业务码。
- **临时修复禁止 / No stopgap fix**：涉及配额/限速语义时，禁止只改前端文案或只改诊断页；必须同步修正运行时检查、用量写回、错误码与测试。

## 六-1、企业 AI 配额与限速最低验证

- 新增或重构企业 AI 配额/限速后，必须同时完成 **单元测试 + 真实接口联调 + 页面验证**，三者缺一不可。
- **真实接口联调 / Live API validation** 最低要求：
  - 管理端 `summary / quotas / rate-limits` 三个诊断接口返回 `200`
  - 重复启用规则创建返回 `422`
  - 临时规则的创建、更新、删除要形成闭环，结束后汇总统计恢复原值
  - 必须至少做一次真正的运行时拦截验证：通过 `/tenant/ai/gateway/chat` 或等价真实入口触发 `4291` / `4292`
- **页面验证 / UI validation** 最低要求：
  - `http://localhost:5666/admin/ai/quotas` 能正常打开
  - 配额页与限速页切换正常，且无新增 console error
  - 表单新增至少真实提交一次，并确认列表即时刷新

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
- 当前 Redis 四分类记忆仅是 `conversation-scoped short-term memory`，不是长期记忆真源
- 长期记忆真源必须使用 `MemoryRecord`，画像只使用 `ProfileSnapshot` 派生视图
- 禁止继续把跨会话 durable memory 扩进 Redis session memory；新增 durable memory 一律走 `LongTermMemoryProvider`

→ 完整规范见 [../skills/novusai-saas/references/session-memory-spec.md](../skills/novusai-saas/references/session-memory-spec.md)

## 六-C、上下文操作系统（Context Engine）规则

- 对话上下文生命周期统一收口到 `ContextEngine`
- 固定 4 个阶段：`ingest(turn)` / `assemble(request)` / `compact(session)` / `after_turn(result)`
- 默认实现是 `LegacyContextEngine`，所有新能力必须保持对 legacy 行为零回归
- prompt 裁剪只能走 `TransientPruning`
  - 只影响当前 prompt
  - 不改数据库原始消息
  - unresolved `pending_consent / pending_confirmation / page_operation` 轮次不得被裁掉
- 持久摘要只能走 `Compaction sidecar snapshot`
  - 只写 conversation metadata sidecar
  - 第一阶段禁止直接改 conversation message 主表
- `assemble()` 必须返回：
  - `messages`
  - `estimated_tokens`
  - `system_prompt_additions`
  - `diagnostics`

## 六-D、长期记忆规则

- 长期记忆 provider 统一走 `app.ai.context.long_term_memory.get_long_term_memory_provider()`
- `MemoryRecord` 是长期记忆真源，字段语义：
  - `memory_type`: `preference / constraint / fact / decision / pattern / task_summary / correction / relationship`
  - `status`: `candidate / verified / suppressed / archived / expired`
- `ProfileSnapshot` 只是派生视图，不得当作记忆真源直接编辑
- 默认 recall 采用 `progressive disclosure`
  - 先注入 `ProfileSnapshot`
  - 再按当前用户问题做 `search / recall`
  - 禁止每轮全量 recall
- capture 默认只接 durable insight，禁止直接把原始 `tool_result`、页面快照、业务明细全文写入长期记忆
- 第一阶段 scope 固定为：
  - `user_agent`
  - `tenant_agent`
  - `tenant_shared`
  - `conversation` 仅存在于短记忆，不进长期记忆主表

## 六-E、Ephemeral / Workspace RAG 规则

- 临时资料统一走 `EphemeralRAGProvider + EphemeralDocumentService`
- 支持 3 个 scope：
  - `conversation_scoped`
  - `agent_workspace_scoped`
  - `tenant_private_scratch`
- 临时资料真源为 `EphemeralDocument`，不进入正式 `KnowledgeBase`
- citation 必须明确区分：
  - `formal_kb`
  - `ephemeral_doc`
- 允许 URL / HTML / Markdown / CSV / Text 临时摄取，但必须复用现有 parser / chunker / retriever，禁止另造算法栈
- `EphemeralDocument.promote_to_knowledge_base` 是唯一合法 promotion path
- 第一阶段 promotion 进入正式 `KnowledgeDocument + process_document` 链路，不允许绕过正式索引流程

## 六-F、技能市场 / 分发层规则

- 技能市场是分发层，不是运行时授权层
- 市场安装后落点仍然是：
  - `SkillPackage`
  - `Skill`
- 运行时真相仍然只看 `AgentSkillGrant`
- 禁止：
  - install 即 runtime
  - workspace override 平台授权
  - 社区 skill 直接进入企业生产运行时
- 管理端主入口统一走插件市场 `/admin/plugins/marketplace?catalog=skills`；技能目录 HTTP API 为 `/admin/plugins/skill-registry`
- 当前插件市场与技能市场 registry 配置统一按 GitHub raw 托管收口，不再维护 Gitee/auto 运行时切换
- GitHub-only 不只是配置约束；插件/技能包的 `download_url` 与 release 回退地址在执行下载前也必须做 GitHub 域名白名单校验

## 六-F-1、Trust / Consent 真相规则

- `trustSession` 只允许作为前端交互入口存在
- 前端本地内存或浏览器存储都不得作为最终授权真相
- 最终是否自动批准，必须以后端 `ExecutionTrustPolicy + ExecutionDecision` 判定为准
- 若前端保留临时 consent cache，也只能是当前运行时的短暂提示，不得跨刷新/跨标签页充当持久授权

## 六-G、统一审计账本规则

- 所有副作用工具必须统一写 `AIActionLog`
- 当前最低覆盖要求：
  - `data_create / data_update / data_delete`
  - `invoke_page_operation / pageop_*`
  - `http`
  - `email`
  - `toolkit`
  - `code_execution`
  - `text_to_sql`（query 类也纳入统一账本）
- `AIActionLog` 必须优先使用显式字段串联：
  - `trace_id`
  - `conversation_id`
  - `tool_call_id`
  - `execution_decision_id`
- 若某路径当前只能写到 `request_data / response_data`，视为临时兼容，不视为最终完成状态

## 七、页面感知与操作规则

- 三层架构：Layer 1（system prompt 注入）+ Layer 2（`get_page_context` 工具）+ Layer 3（`invoke_page_operation` WebSocket 执行）
- 页面操作：**tool-first** — 有 `pageop_*` 时优先直调专用 tools；不再只限富文本页，`search` / `read_visible_rows` / `get_form_state` / `fill_form` / `refresh_list` / 分页类等高频操作也应优先展开；`content_format: 'html'|'markdown'` 与迁移/前端契约一致；禁止向用户回显 HTML/JSON/tool 参数，仅返回自然语言结果
- `_PROTECTED_TOOL_NAMES` 白名单保护页面感知/操作工具不被优化器过滤
- `readonly=false` 操作必须前端用户确认后才执行
- 操作确认超时 60s；页面会话切换、离开 page_session 房间或连接断开时必须清理链式确认状态
- 前端页面操作通道必须按 `invoke_id` 做幂等保护；重复事件只能回放已缓存结果，禁止重复执行或重复弹确认
- 前端执行页面操作前必须校验 `event.page_key` 与当前活动页面一致；不一致时返回 `page_key_mismatch`
- 若后端 `page_operation_invoke` 显式携带 `auto_approved=true`，前端必须直接执行，不得再按 `readonly=false` 自行弹确认
- 页面截图能力统一使用 `capture_screenshot` 页面操作 + 附件上传链路；仅当当前运行模型明确支持视觉时才允许真正执行。截图结果必须作为内部多模态输入注入下一轮 LLM，禁止只返回图片 URL 文本假装“已看图”
- `capture_screenshot` 仅用于页面视觉/布局问题或 DOM/文本上下文不足的场景；禁止把截图当作默认读取手段，优先使用 `read_current_view` / `read_current_sections` / `get_page_context`
- 新增页面操作时必须通过 `registerPageOperations()` 注册，禁止绕过注册表直接执行

### 七-A、前端接入优先级

1. CRUD 列表页：优先 `useCrudPage` / `useCrudList`
2. 详情页：优先 `useDetailPageAi()`
3. 富文本页：优先 `useEditorPageOps()`
4. 只有在以上三类承载不了时，才允许直接使用 `usePageAIContext()` / `usePageAIOperations()`

### 七-B、统一接入规范

- 页面默认应复用平台自动 page AI 协议，**不要**在业务页重新发明注册流程
- 自定义上下文只允许追加到 `contextExtras` 或 `usePageAIContext({ contextStrategy: 'extras' })`
- 自定义页面操作只允许通过 `ai.extra`、`useDetailPageAi({ extra })` 或 `usePageAIOperations({ operationStrategy: 'append' })` 追加
- 非 CRUD 自定义页面只要使用 `usePageAIOperations()`，默认必须传 `operationStrategy: 'append'`；只有明确需要整体替换平台能力时才允许 `primary`
- 需要裁剪能力时，优先 `disabledCapabilities` / `disabledOperations` / `enabled: false`，不要复制标准操作后改名重写
- 打开 drawer/modal/panel 的操作统一用 `createOpenPageOperation()`
- 打开当前详情页已加载实体的子抽屉/子面板时，统一用 `createOpenCurrentPageOperation()`
- 若要先从当前可见列表解析记录再打开 UI，统一用 `createOpenRecordPageOperation()`
- 若要先从当前可见列表解析记录再执行动作，统一用 `createRecordActionPageOperation()`
- ref 模式表单或 `drawerApi.setData()` 需要带 `_aiPageKey` / `_defaults` 时，统一用 `buildPageAIFormExtraData()`
- 打开新建表单且带默认值的操作统一用 `createPrefilledCreatePageOperation()`
- `createPrefilledCreatePageOperation()` 的 `openCreate()` 允许直接返回 `{ success: false, message }` 处理“未选中父实体”“当前上下文不足”等前置条件失败，不要在页面外再包一层重复判断
- 富文本编辑器内部涉及 `content + content_format` 的操作统一走共享 helper；禁止各页面重复解析 markdown/html
- 富文本命令型操作（如 format/list/align/table/link）统一走共享 command builder；禁止每个命令各自手写 enum 校验和默认值逻辑

### 七-C、打开型操作规则

- handler 输入只接收稳定参数：优先 `id` / `code` / `slug`
- 在页面内部先 `findRowById()` / `findEntityByCode()`，或直接复用 `createOpenRecordPageOperation()`，再调用本地 `openXxxDrawer()` / `openXxxModal()`
- 若目标 UI 位于宿主 modal 内部，优先由宿主组件暴露 `openAddXxx()` / `openDetailXxx()` 这类意图方法，再由页面操作调用宿主方法；不要从父页直接穿透到宿主内部子组件 ref
- 不允许让 AI 直接传整个 row JSON 或组件内部数据结构
- 纯“打开 UI”动作应标记为 `readonly: true`，避免落入确认流
- success / error message 统一复用 `shared.pageOperation.msg.*` 或已有 i18n key

## 七-D、确认/拒绝/同意交互协议

- 前端确认/拒绝/同意操作**必须**通过 `interaction_updates` 结构化字段传递，**禁止**将 i18n 翻译文案作为真实 `message` 发送
- `interaction_updates` 是机器可读协议，`kind` 字段标识交互类型（`pending_confirmation` / `pending_consent` / `action_buttons`）
- 后端 `AgentChatRequest` 允许"空 message + interaction_updates"的协议型 turn，不强制要求自然语言文本
- `StreamExecutionHandler` 优先检查 `interaction_updates` 中的结构化确认信号，仅当无结构化信号时才回退到自由文本正则匹配
- `ToolUsePolicy` 推断已从强制门控降级为软信号（`mode="auto"`），优先使用 tool history 和结构信号

## 八、上传与存储规则

**所有文件上传必须通过附件系统（Attachment）完成，禁止自建上传逻辑。**

- ❌ 禁止新建上传组件，必须复用 `FilePicker` / `ImageUpload` / `smartUploadFile`
- ❌ 禁止绕过 `FileValidator` 直接写入存储
- ❌ 禁止硬编码存储路径或上传 URL 前缀

→ 完整上传存储规范见 [../skills/novusai-saas/references/upload-storage-spec.md](../skills/novusai-saas/references/upload-storage-spec.md)
