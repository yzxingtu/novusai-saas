---
trigger: always_on
---
# AI 架构规则（强制）

> 本规则适用于 NovusAI SaaS 项目中所有涉及 AI 功能的开发。违反任何一条均视为代码缺陷。

## 一、核心原则：Agent→Skill 全链路

**所有 AI 功能必须通过 Agent 调度 Skill 完成，禁止直接调用 AIGateway。**

```
外部请求 → Agent.run() → Skill.execute() → AIGateway → LLM Provider
```

### 禁止事项

- ❌ 在 Controller/Service 层直接调用 `AIGateway.chat()` / `stream_chat()` / `embedding()` 发起 LLM 调用
- ❌ 新增绕过 Agent→Skill 链路的 AI 端点
- ❌ 使用已废弃的 `ToolRegistry`（`app.ai.tools.registry`）注册新工具，必须通过 Skill 体系

### 允许事项

- ✅ Agent engine 内部的 LLM 调用（`conversation.py` / `base.py` / `task.py` / `dispatcher.py`）— 属于 Agent 实现层
- ✅ RAG 管道内部的 LLM 调用（`rag/embedding.py` / `query_rewriter.py` / `reranker.py` / `processor.py` / `vision_describer.py`）— 属于 Agent 技能内部实现
- ✅ `AIGateway.test_model` — 仅限模型连通性测试，不用于业务功能
- ✅ `SystemAgentService`（`app/ai/system_agent.py`）— 系统 Agent 调度服务，Controller 层唯一合法的 AI 调用入口
- ✅ **引擎装配（Engine Wiring）**：编排层（`AgentChatService` / Celery Task）创建 `AIGateway(db)` 并注入给 Engine 构造函数，但**禁止直接调用** gateway 的 LLM 方法

## 二、Agent（智能体）定义规范

### Agent 模型必填字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `name` | String(100) | 唯一标识名（英文 snake_case） |
| `description` | Text | 面向用户的描述（可选） |
| `model_id` | FK → AIModel | 绑定的 LLM 模型 |
| `system_prompt` | Text | 系统提示词 |
| `status` | AgentStatusEnum | `draft` / `published` / `disabled` |
| `execution_mode` | AgentExecutionModeEnum | 执行模式 |

### 执行模式（AgentExecutionModeEnum）

| 模式 | 说明 | 适用场景 |
|------|------|----------|
| `conversation` | 多轮对话（默认） | 客服、问答、数据查询 |
| `task` | 单次任务执行 | 文档生成、批量处理 |
| `batch` | 批量任务 | 数据清洗、批量翻译 |
| `api` | API 调用模式 | 外部集成、Webhook |

### Agent 作用域与多租户

作用域使用统一的 `ResourceScopeEnum`（5 值）：

| scope 值 | 含义 | tenant_id | 说明 |
|----------|------|-----------|------|
| `admin_only` | 仅管理端可见 | NULL | 平台创建，租户不可见 |
| `all_tenants` | 视 tenant_id 而定 | NULL **或** X | `NULL`=平台创建，全部租户可见（只读）；`X`=租户 X 创建，仅租户 X 可见/编辑 |
| `admin_and_all` | 管理端 + 全部租户 | NULL | 平台创建，全局共享 |
| `admin_and_assigned` | 管理端 + 部分租户 | NULL | 需 `ResourceTenantAssignment` 记录 |
| `assigned_tenants` | 仅指定租户 | NULL | 需 `ResourceTenantAssignment` 记录 |

> ⚠️ **`all_tenants` 的双重语义**：`tenant_id=NULL` 表示平台全局资源（租户只读），`tenant_id=X` 表示租户 X 自有资源。判断资源是否可编辑时**必须同时检查 `scope + tenant_id`**，仅检查 `scope` 会误放行平台全局资源。

- `is_system=True` → 系统 Agent，**不可删除/禁用**
- `visibility`：控制 Agent 对终端用户的可见性
- `assigned_tenants` / `admin_and_assigned` 需要 `ResourceTenantAssignment` 分配表记录

### Agent 可配置参数

- `temperature` / `max_tokens` / `top_p`：LLM 推理参数
- `quota_config`（JSON）：用量限制配置
- `welcome_message`：对话开场白
- `suggested_questions`（JSON array）：建议问题列表
- `knowledge_base_ids` / `rag_config`：RAG 能力配置（Agent 级别）
- `routing_config`（JSON）：多模型路由配置，字段包括：`enable_routing`（开关）/ `max_tier`（fast/standard/premium/null）/ `vision_model_id`（Vision模型 ID）/ `long_context_model_id`（长上下文模型 ID）/ `long_context_threshold`（token 阈值，默认 32000）— 详见 `.windsurf/workflows/references/ai-routing.md`

### 禁止事项

- ❌ 使用已废弃的 `tool_bindings` JSON 字段绑定工具，必须使用 `AgentSkillBinding`
- ❌ 硬编码 Agent name，使用枚举或常量

## 三、Agent↔Skill 绑定（AgentSkillBinding）

Agent 通过 `AgentSkillBinding` 模型与 `SkillPackage` 建立 M:N 关系。

### 绑定字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `agent_id` | FK → Agent | 智能体 |
| `package_id` | FK → SkillPackage | 技能包 |
| `enabled` | Boolean | 是否启用此绑定 |
| `config_override` | JSON | 覆盖技能包的默认配置 |
| `sort_order` | Integer | 绑定排序（影响工具注册顺序） |
| `consent_mode` | ToolConsentModeEnum | 工具执行授权模式 |

### 授权模式（ToolConsentModeEnum）

| 模式 | 行为 |
|------|------|
| `auto` | LLM 自动调用工具，无需用户确认 |
| `ask` | 工具调用前向用户展示预览，需用户点击「确认执行」 |
| `reject` | 禁止此绑定的工具被调用 |

### 确认流程（consent_mode=ask）

```
LLM tool_call → Executor 生成预览（requires_confirmation=true）→ SSE confirmation_request 事件
→ 前端展示确认卡片 → 用户点击「确认执行」→ 后端检测确认文本
→ _find_pending_confirmation() 查找待确认工具调用 → 直接执行（bypass LLM）→ 返回结果
```

### 规则

- 写操作类工具（`data_create` / `data_update` / `data_delete`）**建议**设为 `ask` 模式
- `config_override` 可覆盖技能包的 Valves 配置、超时时间等
- 一个 Agent 可绑定多个 SkillPackage，一个 SkillPackage 可被多个 Agent 共享

## 四、技能（Skill）体系

### 技能包是一级管理单元

- 技能（Skill）**必须**归属于某个技能包（SkillPackage）
- `package_id` 为必填外键，不可为空
- SkillPackage 拥有 `scope`（5 值 ResourceScopeEnum）、`bind_mode`（auto/manual）、`valves_schema`、`valves_config`

### 技能包绑定模式（SkillBindModeEnum）

| bind_mode | 行为 |
|-----------|------|
| `auto` | 自动绑定 — 按 scope 匹配规则自动对所有匹配的 Agent 生效，无需 AgentSkillBinding 记录 |
| `manual` | 手动绑定 — 需通过 AgentSkillBinding 显式绑定（默认） |

- `bind_mode=auto` 的包不写入 `AgentSkillBinding` 表，零数据膨胀
- 如果用户对 auto 包创建了显式 `AgentSkillBinding`（如改 consent_mode），显式绑定优先
- 系统技能包（`is_system=True`）默认 `bind_mode=auto`
- 租户端只能创建 `bind_mode=manual` 的包
- 自动绑定匹配规则见 `_load_auto_bind_packages()` 和 `ScopeChecker`

### 前端统一入口（禁止独立技能路由）

- `/admin/ai/skill-packages` — 管理端唯一技能管理入口
- `/tenant/ai/skill-packages` — 租户端唯一技能管理入口
- **禁止**存在独立的 `/admin/ai/skills` 或 `/tenant/ai/skills` 页面
- 技能包详情页内嵌技能 CRUD（新增/编辑/删除/排序）
- 新建技能时 `package_id` 自动填充，用户无需手动选择

### 技能类型（SkillTypeEnum）— 7 种

| 类型 | 说明 | Executor | ToolDefinition 数量 |
|------|------|----------|---------------------|
| `toolkit` | Python 工具包（Tools 类） | ToolkitExecutor | N（每个公开方法 1 个） |
| `knowledge_base` | 知识库检索（RAG） | 无（RAG 注入 system_prompt） | 0 |
| `data_intelligence` | 数据智能（Text-to-SQL + CRUD） | TextToSQLExecutor + CrudExecutor | 1~4 |
| `builtin` | 内置函数 | BuiltinToolExecutor | 1~N |
| `http` | 声明式 HTTP API 调用 | HttpExecutor | 1 |
| `email` | 邮件发送 | EmailExecutor | 1 |
| `code_execution` | 代码沙箱执行 | CodeExecutor | 1 |

### Toolkit 技能（toolkit 类型）

- 编写 Python 源码，定义 `Tools` 类，每个公开方法自动映射为一个 LLM 可调用工具
- 字段：`toolkit_content`（Text）存储 Python 源码，`toolkit_meta`（JSON）存储解析结果
- 支持 Valves 配置：通过 `valves_schema` 动态渲染配置表单
- 前端编辑器：Monaco Editor + 实时解析预览 + ZIP 上传
- 解析器：`app.ai.skills.toolkit_parser.parse_toolkit()` — AST 解析，提取方法签名、docstring、类型注解
- 校验器：`validate_toolkit_source()` — 检查 Tools 类存在且有公开方法
- **安全扫描**：非 `is_system` 的 Toolkit 执行前会进行 AST 安全扫描（`_scan_toolkit_security`）
  - 禁止 import：`os` / `subprocess` / `sys` / `pickle` / `socket` / `pathlib` / `shutil` / `ctypes` / `importlib` / `marshal` / `sqlite3` / `io` / `tempfile` / `multiprocessing` / `threading` 等（完整列表见 `_BLOCKED_MODULES`）
  - 禁止 import 前缀：`app.*` / `config.*`（`_BLOCKED_MODULE_PREFIXES`）
  - 禁止调用：`eval()` / `exec()` / `compile()` / `__import__()` / `open()` / `breakpoint()` / `exit()` / `quit()`（`_BLOCKED_BUILTINS`）
  - `is_system=True` 的 Toolkit 标记为 trusted，跳过安全扫描

### Knowledge Base 技能（knowledge_base 类型）

- 不生成 ToolDefinition，通过 RAG 注入 system_prompt
- `config.knowledge_base_ids`：关联的知识库 ID 列表
- `config.rag_config`：RAG 参数（`top_k` / `score_threshold` / `search_mode` / `rewrite_strategy` / `reranker_enabled`）

### Data Intelligence 技能（data_intelligence 类型）

- 生成 1~4 个 ToolDefinition：`data_query`（始终）+ `data_create` / `data_update` / `data_delete`（按 Table Policy 开关）
- `config.table_policy_ids`：关联的表策略 ID 列表
- CRUD 权限由 `/admin/ai/table-policies` 页面的每表 `allow_create/update/delete` 开关控制
- 写操作工具采用两阶段确认：先预览后确认（`confirmed=true`）

### Builtin 技能（builtin 类型）

- **单工具模式**（默认）：Skill 本身即为一个工具，使用 `input_schema` 定义参数
- **多工具模式**：`config.tools` 为工具列表，每项含 `name` / `description` / `parameters`
- 默认内置函数：`get_current_time` / `calculate` / `format_json`

### HTTP 技能（http 类型）

- 声明式 HTTP API 调用：用户填写 URL / Method / Headers / Body 模板，无需编写代码
- 自动从 `body_template` / URL / `query_params` 提取 `{{variable}}` 占位符作为 LLM 参数
- `config` 结构：`url` / `method` / `headers` / `body_template` / `query_params` / `auth_type`（none|bearer|api_key|basic）/ `auth_config` / `response_path`（JSONPath）/ `timeout`
- Executor：`HttpExecutor`（`app.ai.tools.executors.http_executor`）

### Email 技能（email 类型）

- 生成 `send_email` 工具，利用已有 `EmailService` 发送邮件
- 默认 `consent_mode=ask`（发邮件需用户确认）
- `config` 结构：`subject_prefix` / `allowed_domains` / `max_recipients` / `require_confirmation` / `allow_cc` / `allow_attachments`
- Executor：`EmailExecutor`（`app.ai.tools.executors.email_executor`）

### Code Execution 技能（code_execution 类型）

- 生成 `execute_code` 工具，在安全沙箱中执行用户提供的代码
- `config` 结构：`language`（默认 python）/ `timeout` / `memory_limit_mb` / `allowed_modules`
- 默认允许模块：`math` / `json` / `datetime` / `re` / `collections` / `itertools` / `functools` / `statistics` / `decimal` 等
- Executor：`CodeExecutor`（`app.ai.tools.executors.code_executor`）

## 五、Skill 解析链路（SkillResolver）

```
Agent 对话请求
  → 加载 Agent.skill_bindings（含 SkillPackage + Skills）
  → SkillResolver.resolve(skills, config_overrides)
  → 按 SkillTypeEnum 分发到 _resolve_xxx 方法
  → 输出 SkillResolveResult { tools, knowledge_base_ids, rag_config, tool_consent_modes }
  → tools 转换为 OpenAI function calling 格式传给 LLM
```

- `SkillResolver`（`app.ai.skills.resolver`）是唯一合法的 Skill→ToolDefinition 转换器
- `ToolRegistry`（`app.ai.tools.registry`）**已废弃**，将在后续版本移除
- 新代码**禁止**使用 `get_tool_registry()` / `ToolRegistry.register()`

## 六、系统 Agent 与系统 Skill

- 系统级 Agent/Skill/SkillPackage 标记 `is_system=True`，**不可删除/禁用**
- 通过 seed migration 创建，`scope=admin`，`tenant_id=NULL`
- 前端管理页面中系统记录显示紫色「系统」标签，删除按钮隐藏，状态开关禁用
- 系统 Agent：`system_chat_agent`（通用聊天）、`system_embedding_agent`（向量化）
- 系统 Skill：`llm_chat`（LLM 聊天能力）、`llm_embedding`（Embedding 能力）
- 系统 SkillPackage：`系统聊天技能包`、`系统向量化技能包`

### SystemAgentService（外部 AI 调用入口）

```python
from app.ai.system_agent import SystemAgentService

service = SystemAgentService(db)
result = await service.chat(provider_code=..., messages=..., model=...)
result = await service.embedding(provider_code=..., texts=..., model=...)
```

- Controller 层通过 `SystemAgentService` 调用 AI 能力，不直接实例化 `AIGateway`
- 服务会验证系统 Agent 存在且未被删除，然后委托给 AIGateway 执行
- 架构：`Controller → SystemAgentService → AIGateway`

## 七、对话引擎与 SSE 流程

### 对话执行链路

```
POST /tenant/ai/agent-chat/{agent_id}/chat/stream
  → Dispatcher → ConversationEngine
  → 渲染 prompt（变量注入 + RAG 上下文）
  → Gateway.stream_chat()（SSE 流式）
  → 工具调用循环（最多 MAX_TOOL_CALL_ROUNDS 轮）
  → 前端 requestClient.postSSE() 接收
```

### SSE 事件类型

| 事件 | 说明 |
|------|------|
| `message` | LLM 文本流式输出（`delta` 字段） |
| `thinking` | LLM 正在执行工具调用（工具循环开始前） |
| `tool_start` | 工具开始执行（含 `name` + `arguments`） |
| `tool_call` | 工具执行完成（含 `success` / `duration_ms` / `output` / `error`） |
| `tool_consent_request` | consent_mode=ask 时的工具授权请求（含 `name` + `arguments`） |
| `confirmation_request` | CRUD 写操作预览确认（含 `action` / `table` / `preview`） |
| `optimizing_tools` | 工具优化事件（含 `total` / `selected`） |
| `rag_sources` | RAG 知识库引用来源（含 `sources` 列表） |
| `done` | 对话完成（含 `conversation_id` / `total_tokens` / `duration_ms`） |
| 错误 | 格式：`{"error": true, "message": "..."}` |

### 前端 AI 对话组件

- `AIChatPanel`（`components/business/ai-chat-panel/`）— 统一对话面板，支持 page/drawer 两种模式
- 通过 `AgentItem` 传入 Agent 信息（含 `welcome_message` / `suggested_questions`）
- 工具执行卡片：显示运行中 spinner → 成功/失败图标 + 耗时 + 可展开的参数/输出

## 八、新增 AI 功能标准流程

```
1. 定义 Skill 类型（如已有类型可复用则跳过）
2. 新增 SkillTypeEnum 枚举值 + i18n
3. 实现 Executor（继承 BaseToolExecutor，实现 execute + validate）
4. 在 SkillResolver._resolve_one 中注册类型→转换方法映射
5. 创建 Skill 记录（可通过 migration 或 API）
6. 将 Skill 绑定到 Agent（通过 AgentSkillBinding）
7. 通过 Agent 对话或 Agent.run() 触发 Skill
```

**禁止跳过步骤直接调用 AIGateway 实现 AI 功能。**

### 新增 Executor 检查清单

- [ ] 继承 `BaseToolExecutor`，实现 `execute()` 和 `validate()`
- [ ] `execute()` 返回 `ToolResult`（含 `tool_call_id` / `name` / `success` / `output` / `error` / `duration_ms`）
- [ ] 使用 `time.perf_counter()` 计时
- [ ] 异常捕获并返回 `ToolResult(success=False, error=str(exc))`，禁止让异常冒泡
- [ ] 日志使用 `LogManager.get_logger("ai.tool.xxx")`

## 九、关键文件索引

| 文件 | 说明 |
|------|------|
| `backend/app/enums/agent.py` | AgentStatusEnum / AgentExecutionModeEnum / SkillTypeEnum / ToolTypeEnum / ToolConsentModeEnum |
| `backend/app/models/ai/agent.py` | Agent ORM 模型 |
| `backend/app/models/ai/skill.py` | Skill ORM 模型 |
| `backend/app/models/ai/skill_package.py` | SkillPackage ORM 模型 |
| `backend/app/models/ai/agent_skill_binding.py` | AgentSkillBinding ORM 模型（M:N） |
| `backend/app/ai/skills/resolver.py` | SkillResolver — Skill→ToolDefinition 唯一转换器 |
| `backend/app/ai/skills/toolkit_parser.py` | Toolkit Python 源码 AST 解析器 |
| `backend/app/ai/tools/executors/base.py` | BaseToolExecutor 抽象基类 |
| `backend/app/ai/tools/executors/toolkit_executor.py` | ToolkitExecutor（动态加载 Python + 安全扫描） |
| `backend/app/ai/tools/executors/builtin_executor.py` | BuiltinToolExecutor（进程内安全函数） |
| `backend/app/ai/tools/executors/crud_executor.py` | CrudExecutor（数据智能 CRUD） |
| `backend/app/ai/tools/executors/text_to_sql_executor.py` | TextToSQLExecutor（数据智能查询） |
| `backend/app/ai/tools/types.py` | ToolDefinition / ToolParameter / ToolResult / ExecutionContext |
| `backend/app/ai/tools/registry.py` | ToolRegistry（**已废弃**，勿用） |
| `backend/app/ai/engine/conversation.py` | Agent 对话引擎（允许内部 LLM 调用） |
| `backend/app/ai/engine/base.py` | BaseEngine 基类 |
| `backend/app/ai/engine/dispatcher.py` | 执行模式分发器 |
| `backend/app/ai/system_agent.py` | 系统 Agent 服务（Controller 层 AI 调用入口） |
| `backend/app/ai/gateway.py` | AI 网关（仅由 SystemAgentService/Executor/Engine 调用） |
| `backend/app/ai/routing/router.py` | ModelRouter 路由引擎（7 级优先级，包含健康检查 + 兑底）（M264） |
| `backend/app/ai/routing/complexity_classifier.py` | 对话复杂度分类器（SIMPLE/MEDIUM/COMPLEX）（M264） |
| `backend/app/ai/rag/vision_describer.py` | Vision 图片描述服务（RAG 内部，静默处理所有异常）（M263） |
| `backend/app/enums/ai.py` | `ModelTierEnum`（fast/standard/premium）（M264） |
| `backend/migrations/versions/20260214_seed_system_agents_skills.py` | 系统 Agent/Skill 种子数据迁移 |

## 十、上传与存储系统规则（强制）

### 核心原则

**所有文件上传必须通过统一的附件系统（Attachment）完成，禁止自建上传逻辑。**

### 后端架构

```
Controller (UploadFile) → AttachmentService.upload_file() → FileValidator → QuotaService → StorageDriver → Attachment 落库
```

| 层 | 文件 | 职责 |
|---|------|------|
| Controller | `api/admin/attachments.py` / `api/tenant/attachments.py` | 接收 `UploadFile`，调 Service |
| Service | `services/tenant/attachment_service.py` | 上传逻辑、配额检查、哈希去重、分片管理 |
| Service | `services/system/attachment_service.py` | 平台端上传（跨租户，无配额限制） |
| Validator | `services/common/file_validator.py` | 文件类型/大小验证（平台+租户两级配置） |
| Quota | `services/common/storage_quota_service.py` | 存储配额查询（租户套餐驱动） |
| Storage | `app/storage/` | 存储驱动抽象层（local / s3） |
| Model | `models/tenant/attachment.py` | Attachment ORM（TenantModel，含 hash/driver/base_url） |
| Task | `tasks/upload_cleanup.py` | 分片上传临时文件清理（Celery Beat，每 6h） |

### 前端统一组件

**禁止新建上传组件**，必须复用以下已有组件：

| 组件 | 路径 | 用途 | 使用方式 |
|------|------|------|----------|
| `FilePicker` | `components/business/file-picker/FilePicker.vue` | 通用文件选择+上传（Modal 弹窗） | 选择已有附件或拖拽上传新文件 |
| `ImageUpload` | `components/business/image-upload/ImageUpload.vue` | 图片上传（内联） | `<ImageUpload v-model="form.avatar" />` |
| `smartUploadFile` | `api/tenant/attachment.ts` | 智能上传函数（自动切换普通/分片） | 在自定义场景中调用 |

#### FilePicker 使用方式

```vue
<script setup lang="ts">
import { useVbenModal } from '@vben/common-ui';
const [FilePickerModal, filePickerApi] = useVbenModal({
  connectedComponent: () => import('#/components/business/file-picker/FilePicker.vue'),
});
function openPicker() { filePickerApi.open(); }
</script>
<template>
  <FilePickerModal @select="handleSelect" :image-only="false" :multiple="true" />
</template>
```

#### ImageUpload 使用方式

```vue
<ImageUpload v-model="formValues.avatar" upload-url="/tenant/attachments/upload" />
```

- 默认 `uploadUrl` 为 `/admin/attachments/upload`
- 租户端使用时需传 `upload-url="/tenant/attachments/upload"`

#### smartUploadFile 使用方式（程序化上传）

```typescript
import { smartUploadFile } from '#/api/tenant/attachment';
const result = await smartUploadFile(
  { file: myFile, visibility: 'private', business_type: 'avatar' },
  (progress) => { /* percent: 0-100 */ },
);
// result.attachment — AttachmentInfoRaw
// result.url — 访问 URL
```

- 文件 ≤ 10MB：自动走普通上传
- 文件 > 10MB：自动走分片上传（5MB/片）
- 支持 AbortController 取消

### 前端 API 层

| 端 | 文件 | 导出函数 |
|----|------|----------|
| tenant | `api/tenant/attachment.ts` | `uploadAttachmentApi` / `smartUploadFile` / `initChunkUploadApi` / `uploadChunkApi` / `completeChunkUploadApi` |
| admin | `api/admin/attachment.ts` | `uploadAttachmentApi` / `getAttachmentListApi` / `getAttachmentStatsApi` |

### 禁止事项

- ❌ **禁止新建上传组件**（如 `MyUpload.vue`），必须复用 `FilePicker` / `ImageUpload`
- ❌ **禁止直接调用后端上传端点**（如 `requestClient.upload('/xxx/upload', ...)`），必须通过 `smartUploadFile` 或 `uploadAttachmentApi`
- ❌ **禁止绕过 FileValidator**（如后端直接写入存储而不经过 Service）
- ❌ **禁止硬编码存储路径**（如 `"/uploads/avatar.png"`），由 Service 自动生成 `{tenant_id}/{date}/{uuid}.ext`
- ❌ **禁止在前端硬编码上传 URL 前缀**（admin/tenant 由组件 props 或 API 函数区分）

### 知识库文档上传

知识库文档上传复用附件系统：
```python
attachment_service = AttachmentService(db, tenant_id)
upload_result = await attachment_service.upload_file(
    content=io.BytesIO(file_bytes),
    filename=filename,
    business_type="knowledge_document",
    business_id=kb_id,
)
```

### 存储驱动

当前内置驱动：`LocalDriver`（本地文件系统）、`S3Driver`（兼容 S3 协议）。

### 关键文件索引

| 文件 | 说明 |
|------|------|
| `backend/app/api/admin/attachments.py` | 平台端附件 Controller（上传/分片/管理/统计） |
| `backend/app/api/tenant/attachments.py` | 租户端附件 Controller（上传/分片/管理/配额） |
| `backend/app/services/tenant/attachment_service.py` | 租户端上传 Service（配额+去重+分片） |
| `backend/app/services/system/attachment_service.py` | 平台端上传 Service（跨租户） |
| `backend/app/services/common/file_validator.py` | 文件类型/大小验证（两级配置） |
| `backend/app/services/common/storage_quota_service.py` | 存储配额查询 |
| `backend/app/models/tenant/attachment.py` | Attachment ORM 模型 |
| `backend/app/schemas/tenant/attachment.py` | 上传/配额响应 Schema |
| `backend/app/enums/attachment.py` | AttachmentVisibility / AttachmentStatus / AttachmentSource |
| `backend/app/tasks/upload_cleanup.py` | 分片上传临时文件清理 Celery 任务 |
| `frontend/.../api/tenant/attachment.ts` | 租户端上传 API（含 smartUploadFile） |
| `frontend/.../api/admin/attachment.ts` | 平台端上传 API |
| `frontend/.../components/business/file-picker/FilePicker.vue` | 通用文件选择+上传组件 |
| `frontend/.../components/business/image-upload/ImageUpload.vue` | 图片上传组件 |
| `frontend/.../types/attachment.ts` | AttachmentInfo / StorageQuotaInfo 类型定义 |
