# AI 模块开发规范

## 一、模块架构

AI 模块位于 `backend/app/ai/`，提供三大核心能力：

1. **Chat 对话** — 多轮对话 + SSE 流式 + 工具调用
2. **Text-to-SQL** — 自然语言转 SQL 查询/操作 + 租户隔离
3. **RAG 文档问答** — 知识库检索增强生成

### 目录结构

```
backend/app/ai/
├── engine/                    # 执行引擎
│   ├── dispatcher.py          # 路由分发（根据 execution_mode 选择引擎）
│   ├── base.py                # 基础引擎（prompt 渲染、RAG 注入、工具解析）
│   ├── conversation.py        # 对话引擎（多轮历史 + SSE）
│   ├── task.py                # 任务引擎（单次执行）
│   ├── batch.py               # 批处理引擎
│   ├── output_parser.py       # 结构化输出解析
│   └── types.py               # ChatMessage, EngineResult 等类型
│
├── adapters/                  # AI 供应商适配器
│   ├── base.py                # BaseAdapter 抽象基类
│   ├── openai_adapter.py      # OpenAI / 兼容 API
│   └── __init__.py            # ADAPTER_MAP 注册
│
├── tools/                     # 工具系统
│   ├── registry.py            # 工具注册、解析、OpenAI function schema
│   ├── security.py            # SSRF 防护 + SQL 注入检测
│   ├── sandbox.py             # 沙箱代码执行
│   ├── types.py               # ToolDefinition, ToolResult, ToolParameter
│   └── executors/             # 工具执行器
│       ├── http_executor.py       # HTTP API 调用
│       ├── database_executor.py   # 数据库查询
│       ├── email_executor.py      # 邮件发送
│       ├── code_executor.py       # 沙箱 Python 执行
│       ├── text_to_sql_executor.py # NL → SQL
│       ├── api_action_executor.py  # 业务操作（含确认流程）
│       ├── builtin_executor.py    # 内置工具（日期、数学等）
│       └── page_operation_executor.py # 页面操作执行（WebSocket 双向通信）
│
├── rag/                       # RAG 管线
│   ├── parser.py              # 文件解析（PDF/DOCX/TXT/MD/CSV/QA/PPTX/图片）
│   ├── vision_describer.py    # Vision 图片描述服务（M263 多模态RAG）
│   ├── chunker.py             # 文本分块（recursive/semantic/paragraph）
│   ├── embedding.py           # 向量嵌入
│   ├── processor.py           # 索引编排（断点续传）
│   ├── query_rewriter.py      # 查询改写（multi-query/HyDE）
│   ├── retriever.py           # 混合检索（向量+关键词+RRF 融合）
│   ├── reranker.py            # 结果重排序
│   └── context_builder.py     # Token 预算上下文拼接
│
├── routing/                   # 多模型路由（M264）
│   ├── complexity_classifier.py # 对话复杂度分类（SIMPLE/MEDIUM/COMPLEX）
│   └── router.py              # ModelRouter 路由引擎（7级优先级）
│
├── data_intelligence/         # 数据智能
│   ├── schema_provider.py     # DB schema 元数据提取
│   ├── text_to_sql.py         # LLM NL→SQL 生成
│   ├── sql_safety.py          # SQL 安全验证
│   ├── tenant_isolation.py    # 租户隔离（自动注入 WHERE tenant_id）
│   ├── readonly_executor.py   # 只读查询执行 + PII 脱敏
│   ├── action_executor.py     # 写操作执行 + 用户确认
│   ├── action_registry.py     # 业务操作注册表
│   └── result_formatter.py    # 结果格式化（表格/图表/摘要）
│
├── events/                    # 事件系统
│   ├── types.py               # 事件数据类
│   ├── bus.py                 # 异步事件总线
│   └── hooks.py               # 钩子扩展
│
├── gateway.py                 # AI 网关（统一 LLM 调用入口）
├── cache.py                   # Redis 响应缓存
├── quota.py                   # Token 配额管理
├── rate_limiter.py            # RPM/TPM 限流
├── failover.py                # 模型故障转移
├── agent_quota.py             # 智能体级配额
├── agent_stats.py             # 智能体使用统计
├── sse.py                     # SSE 流式助手
├── constants.py               # 模块常量
├── exceptions.py              # AI 异常层级
└── types.py                   # 共享类型
```

---

## 二、核心组件详解

### AI Gateway (`gateway.py`)

所有 LLM 调用的统一入口，职责：

| 功能 | 说明 |
|------|------|
| 适配器分发 | 根据 provider code 选择适配器 |
| 限流 | Redis 原子操作，RPM/TPM 双维度 |
| 配额 | 软限制（告警）+ 硬限制（拒绝） |
| 缓存 | temperature=0 时缓存响应 |
| 故障转移 | 自动切换备用模型 |
| 重试 | 可配置重试 + API Key 轮换 |

**关键方法**：
```python
gateway = AIGateway(db)
# 同步调用
response = await gateway.chat(messages, model, provider_code, tenant_id=tid)
# 流式调用
async for chunk in gateway.chat_stream(messages, model, provider_code, tenant_id=tid):
    yield chunk
# 嵌入
vectors = await gateway.embedding(texts, model, provider_code, tenant_id=tid)
```

### 执行引擎 (`engine/`)

```python
# Dispatcher 自动选择引擎
from app.ai.engine.dispatcher import EngineDispatcher
dispatcher = EngineDispatcher(db, tenant_id)
result = await dispatcher.execute(agent, message, conversation_id=conv_id)
```

**引擎选择逻辑**：
- `AgentExecutionModeEnum.CONVERSATION` → `ConversationEngine`
- `AgentExecutionModeEnum.TASK` → `TaskEngine`
- `AgentExecutionModeEnum.BATCH` → `BatchEngine`

### 工具注册 (`tools/registry.py`)

```python
registry = ToolRegistry(db, tenant_id)
# 加载智能体绑定的工具
await registry.load_agent_tools(agent_id)
# 注册平台内置工具
registry.register_platform_tools(agent)
# 获取 OpenAI function schema
tools_schema = registry.get_openai_tools()
# 执行工具调用
result = await registry.execute_tool(tool_name, arguments)
```

### 页面感知与页面操作（Page Awareness & Operations）

页面感知采用方案 C（混合），三层架构：

- **Layer 1**：`page_context` 通过 `input_variables` 注入 system prompt，提供基础感知
- **Layer 2**：系统级 builtin skill `get_page_context` 进入 LLM function calling tools schema，提供深度上下文
- **Layer 3**：系统级 builtin skill `invoke_page_operation` 通过 WebSocket 双向通信执行前端页面操作（M310 新增）

#### 前端接入点

- 页面通过 `registerPageContext(key, resolver)` 注册页面上下文解析器
- 页面通过 `registerPageOperations(key, operations)` 注册页面可执行操作（含 `handler` 回调）
- 路由通过 `route.meta.ai` 声明页面 AI 策略，例如 `mode`、`pageContextKey`、`pageOperationsKey`
- 发送消息前统一调用 `resolvePageContext()`，将结果作为 `page_context` 写入聊天请求体
- 发送消息时携带 `page_session_id`，用于 WebSocket 操作通道定位
- `PageSessionManager` 监听 `page_operation_invoke` 事件，执行操作后通过 `page_operation_result` 回传

#### 后端接入点

- `AgentChatService.chat()` / `stream_chat()` 接收 `page_context` + `page_session_id`
- `PageContext.normalize_variables()` 将其收口到 `ExecutionRequest.input_variables["page_context"]`
- `resolve_for_agent()` 负责加载 auto-bind 的系统级 SkillPackage
- `SkillResolver._resolve_builtin()` 从 `config.tools` 生成 `ToolDefinition`（含 `get_page_context` 和 `invoke_page_operation`）
- `BaseEngine._prepare_execution()` 收集 `skill_result.tools`
- `to_openai_tools()` 将工具转为模型可见的 function schema
- `PageOperationExecutor` 通过 `invoke_page_operation()` 创建 asyncio.Future，经 Socket.IO 下发操作指令到前端
- `PageSessionMixin` 管理 page_session 房间加入/离开，处理操作结果回调

#### 关键规则

- **仅注册 Executor 不算完成** — 必须同时存在 `SkillPackage + builtin Skill + auto-bind`
- `_PROTECTED_TOOL_NAMES` 白名单保护 `get_page_context`、`invoke_page_operation`、`list_page_operations` 不被工具优化器过滤
- `readonly=true` 操作直接执行，`readonly=false` 操作前端弹出确认对话框
- 操作超时 30s，超时后自动清理 Future
- 已覆盖 29 页面（Admin 19 + Tenant 10），标准操作类型：`refresh_list`、`refresh_dashboard`、`export_data`、`navigate_to`

#### `_load_auto_bind_packages` scope 审计（2026-03）

优化前：`agent_scope` 参数未参与过滤，仅依赖 `tenant_id` 是否为 `None` 分流。

优化后（+22/-6 行精确修改）：
- **`tenant_id IS NULL` 基础条件**：auto-bind 仅加载系统级包，排除租户自建包
- **管理端分支**（`tenant_id is None`）：增加 `agent_scope` 守卫，非管理端作用域直接返回空
- **租户端分支**（`tenant_id` 有值）：`ADMIN_ONLY` agent 直接返回空；仅当 `agent_scope` 为 `ASSIGNED_TENANTS` / `ADMIN_AND_ALL` / `ADMIN_AND_ASSIGNED` 时才查分配表
- 与 `AgentSkillBindingService._validate_scope()` 保持一致的兼容规则

#### P0 修复（2026-03 审计后落地）

**1. 工具优化器保护机制** (`optimizer.py`)

`optimize_tools()` 在工具数 >6 时按关键词相关性筛选，`get_page_context` 作为基础设施工具与用户消息无关键词关联，会被误删。

修复：新增 `_PROTECTED_TOOL_NAMES` 白名单，保护工具始终保留，优化名额仅用于剩余工具。扩展时只需往 frozenset 加工具名。

**2. `page_data` 大小限制** (`agent_chat.py` + `page_context_executor.py`)

- Schema 层：`PageContext` 添加 `@model_validator` 校验 `page_data` 序列化后 ≤ 4KB（`MAX_PAGE_DATA_BYTES=4096`），超限返回 422
- Executor 层：输出截断保护 `MAX_OUTPUT_CHARS=6000`，防御绕过 schema 的内部路径

#### 测试覆盖（31 项全通过）

| 测试 | 覆盖点 |
|------|--------|
| `test_load_auto_bind_tenant_scope_excludes_assigned_when_all_tenants` | ALL_TENANTS agent 不查 assigned 作用域 |
| `test_load_auto_bind_admin_scope_only_admin_visible` | ADMIN_ONLY agent 只查管理端可见作用域 |
| `test_load_auto_bind_returns_empty_for_mismatched_scope` | 不匹配的 scope+tenant_id 组合直接返回空 |
| `test_conversation_engine_injects_tools_into_gateway` | skill_result.tools → _prepare_execution → _call_llm → gateway.chat(tools=...) 完整链路 |

#### 典型数据流

```text
前端页面
  ├── registerPageContext(key, resolver)
  ├── registerPageOperations(key, operations)  ← 含 handler 回调
  └── route.meta.ai = { mode, pageContextKey }
 
用户发消息
  → resolvePageContext() → page_context
  → POST /chat/stream { page_context, page_session_id }
  → AgentChatService.chat()
  → PageContext.normalize_variables()
  → ExecutionRequest.input_variables["page_context"]
  → resolve_for_agent()
  → SkillResolver._resolve_builtin()
  → to_openai_tools()

Layer 2（上下文读取）:
  → LLM 调用 get_page_context
  → ToolSandbox → PageContextExecutor
  → 返回页面结构化数据

Layer 3（操作执行）:
  → LLM 调用 invoke_page_operation
  → ToolSandbox → PageOperationExecutor
  → invoke_page_operation() 创建 asyncio.Future
  → Socket.IO emit("page_operation_invoke") → page_session 房间
  → 前端 PageSessionManager 执行 handler
  → Socket.IO emit("page_operation_result") 回传
  → Future resolve → ToolResult 返回给 LLM
```

### RAG 检索 (`rag/retriever.py`)

```python
retriever = HybridRetriever(db, tenant_id)
results = await retriever.search(
    query="用户问题",
    knowledge_base=kb,
    kb_ids=[1, 2],
    mode=SearchModeEnum.HYBRID.value,
    top_k=5,
    score_threshold=0.5,
    rewrite_strategy=RewriteStrategyEnum.MULTI.value,
)
```

---

## 三、枚举速查

### 智能体相关 (`enums/agent.py`)

| 枚举 | 值 |
|------|------|
| `AgentStatusEnum` | `draft` / `published` / `disabled` |
| `AgentExecutionModeEnum` | `conversation` / `task` / `batch` / `api` |
| `ToolTypeEnum` | `http` / `database` / `email` / `code` / `builtin` / `text_to_sql` / `api_action` |
| `ConversationStatusEnum` | `active` / `archived` |
| `MessageRoleEnum` | `system` / `user` / `assistant` / `tool` |
| `BatchRunStatusEnum` | `pending` / `running` / `completed` / `partial_failed` / `failed` / `cancelled` |

### 知识库相关 (`enums/knowledge_base.py`)

| 枚举 | 值 |
|------|------|
| `KBStatusEnum` | `active` / `disabled` |
| `DocumentStatusEnum` | `pending` / `parsing` / `chunking` / `embedding` / `completed` / `error` |
| `DocumentTypeEnum` | `pdf` / `docx` / `txt` / `md` / `csv` / `qa` / `url` |
| `ChunkStrategyEnum` | `recursive` / `semantic` / `paragraph` |
| `SearchModeEnum` | `hybrid` / `vector` / `keyword` |
| `RewriteStrategyEnum` | `none` / `multi` / `hyde` |

---

## 四、安全机制

### 1. SSRF 防护 (`tools/security.py`)

工具执行 HTTP 请求前，自动检查：
- 协议白名单（仅 http/https）
- 内网地址拦截（127.0.0.1, 10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16）
- 可选域名白名单模式

### 2. SQL 安全 (`tools/security.py` + `data_intelligence/sql_safety.py`)

- 仅允许 `SELECT` / `WITH` 开头的只读查询
- 拦截危险关键字：`DROP` / `TRUNCATE` / `ALTER` / `GRANT` 等
- 限制结果行数

### 3. 租户隔离 (`data_intelligence/tenant_isolation.py`)

- 解析 SQL AST，提取所有表引用
- 自动注入 `WHERE tenant_id = ?` 条件
- 如果表无 `tenant_id` 列则拒绝查询

### 4. 数据脱敏 (`data_intelligence/readonly_executor.py`)

自动检测并脱敏：
- 邮箱：`abc***@example.com`
- 手机号：`138****1234`
- IP 地址：`***.***.***123`

### 5. 操作确认 (`data_intelligence/action_executor.py`)

写操作流程：
```
用户请求 → LLM 生成操作方案 → 前端展示确认弹窗 → 用户确认/取消 → 执行/放弃
```

---

## 五、i18n 键前缀

| 前缀 | 用途 | 文件 |
|------|------|------|
| `ai.*` | AI 网关错误/日志 | `locales/*/messages.json` |
| `ai.rag.*` | RAG 上下文构建 | `locales/*/messages.json` |
| `agent.*` | 智能体操作/错误 | `locales/*/messages.json` |
| `knowledge_base.*` | 知识库操作/错误 | `locales/*/messages.json` |
| `tool_definition.*` | 工具操作/错误 | `locales/*/messages.json` |
| `agent_chat.*` | 对话操作/错误 | `locales/*/messages.json` |
| `conversation.*` | 对话管理 | `locales/*/messages.json` |
| `data_intelligence.*` | 数据智能 | `locales/*/messages.json` |
| `tool.*` | 工具安全错误 | `locales/*/messages.json` |

---

## 六、开发检查清单

### 新增 AI 功能

- [ ] 使用项目枚举，禁止魔法字符串
- [ ] 错误消息使用 `_()`
- [ ] 使用 `LogManager.get_logger("ai.xxx")` 记录日志
- [ ] 异常使用项目异常类（`NotFoundException`, `BusinessException` 等）
- [ ] 租户数据使用 `TenantModel` 全套
- [ ] 工具执行通过 Security 层校验
- [ ] SQL 操作通过 TenantIsolation 校验

### AI 相关前端页面

- [ ] 所有文本使用 `$t()`
- [ ] SSE 请求使用 `requestClient.postSSE()`
- [ ] 权限指令 `v-access:code="['resource:action']"`
- [ ] 搜索字段用 JSON:API 格式
- [ ] 无 `console.log` / `any` 类型

---

## 七、M37 审计修复清单（2026-02）

| ID | 修复内容 | 文件 |
|----|---------|------|
| B2 | `test_model()` 流式 async generator 泄漏 → `aclose()` | `gateway.py` |
| B4+B5 | 缓存 key 缺 kb_ids/rewrite/reranker → 重构 key | `retriever.py` |
| B6 | `_hybrid_search` 串行 → `asyncio.gather` 并行 | `retriever.py` |
| B7 | SqlValidator 误拦 UNION → 移除 | `security.py` |
| B8 | `_stream_llm_chunks` 绕过 gateway → 加限流/配额/计量 | `conversation.py` |
| B12 | TPM 跨分钟调整 → `request_minute_key` 参数 | `rate_limiter.py` |
| B13 | `code_template.format()` 注入 → 变量注入 exec_globals | `code_executor.py` |
| B14 | 文档解析逻辑 3x 重复 → `_load_and_parse_document()` | `processor.py` |
| B16 | EventBus 单例非线程安全 → double-checked locking | `bus.py` |
| B17 | 对话接口未校验 agent_id 归属 → 添加校验 | `agent_chat.py` |
| B18 | `== True/False` 全局 → `.is_(True/False)` (257 处) | 全局 |
| B19 | LIKE 通配符未转义 → 添加 escape | `base_repository.py` |
| B20 | `batch_update_sort_order` N 次 SQL → CASE WHEN 单次 | `base_repository.py` |
| B22 | JWT 双解码 → 单次 `decode_token` + scope 分发 | `permission.py` |
| B23 | 软删除用户可登录 → `is_deleted` 过滤 | `auth_service.py` |
| F7+F9 | `Optional[X]` → `X \| None` (59 处) | AI 核心+仓库 |

---

## 八、Skill 作用域规则（完整版）

### 作用域矩阵

| 包的 scope | tenant_id | 含义 | 租户可见 | 租户可编辑 |
|-----------|-----------|------|---------|-----------|
| `all_tenants` | `null` | 平台全局包（管理端创建） | ✅ 全部租户 | ❌ |
| `all_tenants` | `X` | 租户 X 自有包（租户 X 创建） | ✅ 仅租户 X | ✅ 仅租户 X |
| `admin_only` | `null` | 仅管理端可见 | ❌ | ❌ |
| `admin_and_all` | `null` | 管理端 + 全部租户（全局共享） | ✅ 全部租户 | ❌ |
| `admin_and_assigned` | `null` | 管理端 + 指定租户 | ✅ 指定租户 | ❌ |

### 前端判断是否可编辑

```typescript
// ✅ 正确 — 必须同时检查 scope 和 tenant_id
function isTenantOwned(pkg): boolean {
  return !!pkg && pkg.scope === 'all_tenants' && pkg.tenant_id !== null;
}

// ❌ 错误 — 仅检查 scope，平台全局包（tenant_id=null）也会被误判为可编辑
function isTenantOwned(pkg): boolean {
  return !!pkg && pkg.scope === 'all_tenants';
}
```

### 后端所有权保护

```python
# Service._before_update / _before_delete
if pkg.tenant_id != self.tenant_id:  # ✅ 同时覆盖 null（平台包）和其他租户的包
    raise BusinessException(message=_("skill_package.error.readonly"))

# ❌ 错误：仅检查 scope — 平台全局包也会被误放行
if pkg.scope != ResourceScopeEnum.ALL_TENANTS.value:
    raise BusinessException(...)
```

### Skill 无独立 scope

- **Skill 本身没有 `scope` 字段**，可见性和操作权限完全继承自所属 `SkillPackage`
- 判断 Skill 是否可编辑时，检查其所属 SkillPackage 的 `scope + tenant_id`
