# AI 模块开发规范

## 一、模块架构

AI 模块位于 `backend/app/ai/`，当前核心能力聚焦于：

1. **Chat 对话** — 多轮对话 + SSE 流式 + 工具调用
2. **RAG 文档问答** — 知识库检索增强生成

> **退役说明（2026-04）**：`Text-to-SQL` / `data_intelligence` 已退役。下文若提到相关目录或能力，均仅作历史参考。

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
│       ├── api_action_executor.py  # 业务操作（含确认流程）
│       └── builtin_executor.py    # 内置工具（日期、数学等）
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
├── data_intelligence/         # 数据智能（2026-04 退役，以下内容为历史参考）
│   ├── schema_provider.py     # DB schema 元数据提取
│   ├── text_to_sql.py         # LLM NL→SQL 生成
│   ├── sql_safety.py          # SQL 安全验证
│   ├── tenant_isolation.py    # 企业隔离（自动注入 WHERE tenant_id）
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

### Context Engine / 上下文操作系统

- 当前对话上下文能力统一收口到 `backend/app/ai/context/`
- 固定生命周期：
  - `ingest(turn)`
  - `assemble(request)`
  - `compact(session)`
  - `after_turn(result)`
- 默认实现为 `LegacyContextEngine`
- 共享约束：
  - Prompt 裁剪只允许通过 `TransientPruning`
  - 持久摘要只允许通过 conversation metadata sidecar snapshot
  - unresolved `pending_consent / pending_confirmation` 工具轮次不得被 compact / prune

### Long-Term Memory / 长期记忆

- 短记忆仍为 Redis 四分类 session memory：`preferences / constraints / task_states / verified_facts`
- 长期记忆真源改为：
  - `MemoryRecord`
  - `ProfileSnapshot`（派生视图）
- 运行时通过 `LongTermMemoryProvider` 接入：
  - `capture`
  - `recall`
  - `search`
  - `profile`
- 默认 recall 是 `progressive disclosure`
  - 先 `ProfileSnapshot`
  - 再按当前问题 recall / search
  - 不做每轮全量 recall

### Ephemeral / Workspace RAG / 临时资料侧车

- 临时资料统一经 `EphemeralRAGProvider`
- 真源模型为 `EphemeralDocument`
- 支持 scope：
  - `conversation_scoped`
  - `agent_workspace_scoped`
  - `tenant_private_scratch`
- 临时资料不进入正式 `KnowledgeBase`
- promotion 必须走 `EphemeralDocument -> KnowledgeDocument -> process_document`
- citation 必须区分：
  - `formal_kb`
  - `ephemeral_doc`

### Skill Registry / 技能分发层

- 技能市场是“分发层”，不是运行时授权层
- 安装后仅落地到：
  - `SkillPackage`
  - `Skill`
- 运行时仍由 `AgentSkillGrant` 决定是否进入 Agent tool 集
- 管理端主入口统一在插件市场：
  - `/admin/plugins/marketplace?catalog=skills`
- 当前插件市场与技能市场 registry 默认按 GitHub raw 托管，不再维护 Gitee/auto 源切换
- GitHub-only 必须落实到执行期下载校验，不能只停留在配置层或 UI 层
- 允许：
  - 搜索
  - 安装
  - 安装预览
  - 更新检查
  - 升级预览
  - 单个升级 / 批量升级
- 不允许：
  - install 即 runtime
  - 跳过来源锁做任意来源升级
  - 社区 skill 自动进入企业生产运行时

### Trust / Consent / 后端真相

- `trustSession` 只是前端发起“希望按会话信任”的交互入口
- 最终自动批准必须以后端 `ExecutionTrustPolicy` 为准
- 所有 consent / confirmation 的落账必须进入 `ExecutionDecision`
- 前端临时 consent cache 只能是当前运行时内存态，不得再依赖浏览器存储充当持久授权真相

### Unified Audit / 统一行为账本

- `AIActionLog` 不再只记录 data actions
- 当前必须覆盖：
  - CRUD data ops
  - http
  - email
  - toolkit
  - code execution
  - text-to-sql query
- 串联主键优先使用显式字段：
  - `trace_id`
  - `conversation_id`
  - `tool_call_id`
  - `execution_decision_id`

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

### 企业 AI 配额与限速运行时语义 / Tenant AI quota and rate-limit runtime semantics

- **计量入口 / Metering entry**：`AIGateway.chat()` / `stream_chat()` 在企业租户调用时，先经过 `UsageRecorder.check_rate_and_quota()`，再进入实际模型调用。
- **硬配额 / Hard quota**：
  - 命中后立即拒绝请求
  - 返回 `HTTP 429`
  - 业务码 `4291`
  - 错误文案来自 `ai.error.quota_exceeded`
- **软配额 / Soft quota**：
  - 命中后不拒绝请求
  - 继续累计真实用量
  - 允许通知系统发出超额告警
- **速率限制 / Rate limit**：
  - 命中 RPM 或 TPM 任一上限即拒绝
  - 返回 `HTTP 429`
  - 业务码 `4292`
  - 错误文案来自 `ai.error.rpm_limit_exceeded` / `ai.error.tpm_limit_exceeded`
- **全局配额回退 / Global quota fallback**：
  - 同企业、同周期若存在模型专属启用规则，则优先命中模型专属规则
  - 只有该周期不存在模型专属规则时，才回退到 `model_id IS NULL` 的全局规则
- **限速继承 / Rate-limit inheritance**：
  - 企业级 `rpm_limit` / `tpm_limit = null` 表示继承模型默认值
  - 不能把 `null` 解释成“无限制”或“清空默认限速”
- **诊断页要求 / Diagnostics page requirement**：
  - `GET /admin/ai/quotas/summary`
  - `GET /admin/ai/quotas`
  - `GET /admin/ai/quotas/rate-limits`
  - 上述接口必须返回**真实运行时语义**，包括当前生效值、来源、超限动作、HTTP 状态、业务码与文案预览

### 配额诊断页重构约束 / Quota diagnostics page refactor constraints

- `admin/ai/quotas` 必须被当作**诊断页 / diagnostics page**，不是普通表单列表页。
- 配额卡片至少要展示：
  - 当前使用量 / Usage
  - 剩余额度 / Remaining
  - 运行状态 `healthy / warning / exceeded / inactive`
  - 超限动作 `allow / deny`
  - 若为拒绝，还要展示 `HTTP 429` 与业务码
- 限速卡片至少要展示：
  - 企业配置值
  - 模型默认值
  - 运行时生效值
  - 来源 `tenant / model / none`
  - 当前 RPM / TPM
  - 拒绝返回 `HTTP 429 / 4292`
- 页面筛选必须围绕实际可用过滤字段组织：
  - 配额：`tenant_id` / `model_id` / `period` / `quota_type` / `is_active`
  - 限速：`tenant_id` / `model_id` / `is_active`
- 任何“只是把页面文案改对、但运行时没改”的提交都算不合格。

### 配额与限速验证闭环 / Quota and rate-limit validation loop

修改 `quota.py`、`rate_limiter.py`、`usage_recorder.py`、`admin/ai/quotas` 后，至少执行以下验证：

1. 单元测试 / Unit tests
   - 覆盖硬配额、软配额、全局回退、限速继承、预扣减失败回滚
2. 真实管理端接口 / Live admin APIs
   - `GET /admin/ai/quotas/summary`
   - `GET /admin/ai/quotas`
   - `GET /admin/ai/quotas/rate-limits`
   - 验证重复启用规则创建返回 `422`
3. 真实运行时拦截 / Live runtime blocking
   - 用企业管理员身份创建临时硬配额或临时限速
   - 通过 `/tenant/ai/gateway/chat` 触发真实调用
   - 确认硬配额返回 `4291`，限速返回 `4292`
   - 软配额不得拦截请求
4. 页面验证 / UI validation
   - `http://localhost:5666/admin/ai/quotas` 打开正常
   - 至少真实提交一次新增表单并观察列表刷新
   - 无新增 console error
5. 环境清理 / Cleanup
   - 删除临时测试规则
   - 确认 summary 恢复到测试前状态

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

### 技能解析与工具装配（`ai/skills/resolver.py`）

```python
from app.ai.skills.resolver import resolve_for_agent

skill_result = await resolve_for_agent(db, agent, tenant_id)
tools_schema = skill_result.to_openai_tools()
```

- 运行时工具集合来自 `AgentSkillGrant -> Skill -> SkillResolver`
- `SkillPackage` 仅作为归组 / 来源 / 目录单元参与展示与管理，不再承担运行时 auto-bind 语义
- `ToolRegistry` 属于历史概念，新增实现不要再依赖它

#### SkillPackage 目录与资源作用域规则

- 统一以 **ResourceScopeEnum**（五类）+ **`owner_tenant_id`** + **`resource_tenant_assignments`**（RTA）表达投放面。
- **企业端上下文**（当前企业 `tenant_id` 有值）：`admin_only` 资源不向企业端暴露；`selected_tenants` / `admin_and_selected_tenants` 必须存在针对该企业的有效 RTA。
- **平台/管理端上下文**：按资源是否允许管理端消费及绑定关系过滤；系统级包与企业自建包通过 `owner_tenant_id` 区分。
- tenant 侧允许只读目录 `/tenant/ai/skill-packages`，可查看包来源、包含技能与解析工具，但不允许 tenant CRUD / valves 编辑 / 包级运行绑定。

#### P0 修复（2026-03 审计后落地）

**1. 工具优化器 & 统一族解析** (`optimizer.py`, `semantic_defaults.py`)

`optimize_tools()` 在工具数 >6 时按 token 相关性筛选。基础设施工具通过 `_PROTECTED_TOOL_NAMES` 白名单始终保留。

工具族推断已统一到 `semantic_defaults.tool_family_from_name()`，optimizer 和 BaseEngine 均复用此单一真相源。`_infer_tool_use_policy()` 中的语义提示（web_research / time_ops 等）已从强制门控降级为软信号（`mode="auto"`），优先依赖 tool history 和结构信号。

#### 测试覆盖

| 测试 | 覆盖点 |
|------|--------|
| `test_load_auto_bind_tenant_scope_excludes_assigned_when_all_tenants` | ALL_TENANTS agent 不查 assigned 作用域 |
| `test_load_auto_bind_admin_scope_only_admin_visible` | ADMIN_ONLY agent 只查管理端可见作用域 |
| `test_load_auto_bind_returns_empty_for_mismatched_scope` | 不匹配的 scope+tenant_id 组合直接返回空 |
| `test_conversation_engine_injects_tools_into_gateway` | skill_result.tools → _prepare_execution → _call_llm → gateway.chat(tools=...) 完整链路 |

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
| `ToolTypeEnum` | 以当前 `enums/agent.py` 为准；`text_to_sql` 等退役值不再适用 |
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

- ### 2. SQL 安全 (`tools/security.py` + `data_intelligence/sql_safety.py`)
> ⚠️ `data_intelligence/sql_safety.py` 及同目录下模块已退役，以下说明仅保留为历史参考，删除该功能后平台依赖其他安全策略。

- 仅允许 `SELECT` / `WITH` 开头的只读查询
- 拦截危险关键字：`DROP` / `TRUNCATE` / `ALTER` / `GRANT` 等
- 限制结果行数

### 3. 企业隔离 (`data_intelligence/tenant_isolation.py`)
> ⚠️ `tenant_isolation.py` 如同其他 `data_intelligence` 执行器已出库，本节仅保留作为历史，实际企业隔离不再由该模块提供。

- 解析 SQL AST，提取所有表引用
- 自动注入 `WHERE tenant_id = ?` 条件
- 如果表无 `tenant_id` 列则拒绝查询

### 4. 数据脱敏 (`data_intelligence/readonly_executor.py`)
> ⚠️ 此仅读执行器与脱敏逻辑已随 `data_intelligence` 退役而移除，当前无对应模块在仓库中运行。

自动检测并脱敏：
- 邮箱：`abc***@example.com`
- 手机号：`138****1234`
- IP 地址：`***.***.***123`

### 5. 操作确认 (`data_intelligence/action_executor.py`)
> ⚠️ `action_executor.py` 及 `data_intelligence` 的写操作确认流程已退役，以下流程仅作历史记录。

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
| `tool.*` | 工具安全错误 | `locales/*/messages.json` |

---

## 六、开发检查清单

### 新增 AI 功能

- [ ] 使用项目枚举，禁止魔法字符串
- [ ] 错误消息使用 `_()`
- [ ] 使用 `LogManager.get_logger("ai.xxx")` 记录日志
- [ ] 异常使用项目异常类（`NotFoundException`, `BusinessException` 等）
- [ ] 企业数据使用 `TenantModel` 全套
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

## 八、SkillPackage 目录 vs 其它资源的 scope（当前模型）

### SkillPackage 表结构（现行）

- **当前 `SkillPackage` ORM 无 `scope` 列**；目录可见性由 `tenant_id`（`NULL` = 平台级目录项，对所有租户目录可见）、`is_active`、`source_plugin` / `is_system` 等与 `SkillPackageRepository.get_catalog_list` 过滤共同决定。
- **API 摘要字段**：`package_role_key`、`source_summary`、`runtime_binding_mode`（固定 `direct_agent_skill_grant`）、`valves_*_count` — 与 `bind_mode`、包级运行时绑定无关。
- **企业端 HTTP**：`/tenant/ai/skill-packages*` 只读；不要在 tenant 侧把 SkillPackage 当作运行绑定入口。

### 其它资源上的 ResourceScopeEnum（勿与 SkillPackage 混写）

- **Agent / KnowledgeBase 等**仍可能使用 **`ResourceScopeEnum` 五类** + `resource_tenant_assignments` 表达投放面；该模型**不**映射为 `skill_packages` 上的列名 `scope`，文档与代码引用时分开表述。

### 前端：判断是否企业自有包（管理端等场景）

```typescript
// ✅ 正确：归属企业 = 当前企业（SkillPackage API 使用 tenant_id）
function isTenantOwned(pkg: { tenant_id?: null | number }, currentTenantId: number): boolean {
  return pkg.tenant_id != null && pkg.tenant_id === currentTenantId;
}
```

### 后端：企业侧写操作归属保护（示例）

```python
# SkillPackageService._before_update / _before_delete：非本企业自有包不可改删
if pkg.tenant_id != self.tenant_id:
    raise BusinessException(message=_("skill_package.error.system_protected"))
```

### 受众 / 发布（非 ResourceScopeEnum）

- **`target_audience`**、智能体 **`TenantAgentPublication`** 等描述「谁在用」，**不属于** `ResourceScopeEnum`，不得与资源 scope 混写进同一套规则。

### Skill 无独立 scope 列

- **Skill ORM 无 `scope` 字段**；可见性与归属语境继承所属 **SkillPackage** 的 `tenant_id` / 目录规则（非「整包绑定到 Agent」语义）。
