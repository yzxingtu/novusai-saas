---
name: novusai-saas
description: NovusAI SaaS 全栈开发技能。当需要开发前端页面（Vue 3 + Vben Admin）或后端接口（FastAPI + SQLAlchemy + PostgreSQL）时，提供分层架构、CRUD 流程、多企业、权限、国际化等项目专属规范。
---

# NovusAI SaaS 全栈开发技能

> 本文件是精简索引。每节仅保留核心要点 + 指向详细 reference 文件的链接。
> 所有 reference 文件位于 `references/` 目录。

## 技术栈

| 端 | 技术 |
|---|------|
| 前端 | Vue 3.5 + TypeScript + Vben Admin 5.x + Ant Design Vue + Vite 6.x + Tailwind CSS |
| 后端 | Python 3.11+ + FastAPI + SQLAlchemy 2.x (Async) + PostgreSQL + Alembic |
| 认证 | JWT (access / refresh / impersonate) |
| 查询协议 | JSON:API（filter/sort/page） |

## 开发前准备

1. 确认任务归属的端：admin / tenant / user
2. 查阅对应 reference 文件了解规范
3. 确认相关模块是否已有类似实现，复用已有组件和模式
4. **禁止启动前端/后端开发服务器**：用户已预先启动，直接使用即可（后端 `localhost:8000`，前端 `localhost:5666`）
5. **开发环境登录凭据**（仅用于本地调试/测试）：
   - 管理端（`/admin/login`）：`admin` / `admin123456`
   - 企业端（`/tenant/login`）：`adminsss` / `admin123456`
6. 涉及图标时，必须同步查阅 `references/icon-spec.md`

---

## 一、全局禁令

以下规则在任何情况下不可违反：

- **禁止硬编码字符串**：前端 `$t()` / `t()`，后端 `_()`
- **禁止 `console.log`**：使用 `console.warn` / `console.error`
- **禁止业务代码使用 `any` 类型**：使用 `unknown` 或具体类型（adapter/拦截器等框架层可酌情保留）
- **新增代码注释或备注必须中英双语同时存在**：禁止只写中文注释/备注，禁止只写英文注释/备注；若无必要，优先不加注释
- **禁止魔法字符串**：后端用 `LabeledEnum`，前端用常量/枚举
- **禁止跨端导入**：admin 页面不导入 tenant/user 的 API/Store。后端跨端共享逻辑放 `app/api/shared/`（如 `_skill_helpers.py`）
- **禁止层级越权**：Controller 不写业务逻辑或直接 DB 查询，Service 不直接操作 DB，Repository 不写业务判断。统计/Dashboard 查询必须在 Service 层
- **禁止裸返回**：后端必须用 `success()` / `created()` / `paginated()` 等统一响应
- **禁止手写重复 Schema**：前端用 `searchInput()` / `inputField()` 等辅助函数
- **禁止敏感信息入代码**：密钥、密码、Token 通过环境变量
- **禁止在主系统中写入插件代码**：插件组件/逻辑/locale 只能在 `backend/plugins/{name}/` 内，前端通过 UMD 动态加载
- **禁止依赖在线图标 API**：平台功能图标统一用本地 `lucide:*` 或自托管 `svg:*`，插件元数据图标只允许 `icon.png`

---

## 二、平台基础设施

多企业隔离、认证注入、异常体系、日志系统、SSE 流式、应用启动、上传存储、配置系统、前端业务组件。

**核心要点**：
- 四层企业隔离：`TenantModel` → `TenantRepository` → `TenantService` → `TenantController`
- 三端 Token：`ActiveAdmin` / `ActiveTenantAdmin` / `ActiveTenantUser`
- 异常由 Service 抛出（`NotFoundException` / `BusinessException` 等），Controller 不捕获
- 日志统一通过 `app.core.logging` 封装使用：常规模块优先 `get_logger(__name__)`，Service 优先 `LoggerMixin` / `self.logger`，分类日志再用 `LogManager.get_logger(...)`
- trace_id：请求头 `X-Trace-ID` 贯穿全链路，`trace_id_var.get()` 获取
- 公开配置、品牌与验证码统一走 `usePublicConfigStore` + `/api/public/platform|tenant/config` + `CaptchaProvider`，不要在登录页或 Layout 再写一套品牌/验证码逻辑
- 上传必须通过 `AttachmentService`；前端业务页面必须用 `smartUploadFile` 或封装了它的 `FilePicker` / `ImageUpload` / `ConfigImagePicker`；仅富文本编辑器等基础设施封装可在内部直接调用标准附件上传端点
- **文件下载**：必须用 `requestClient.download`（含 `responseReturn: 'raw'`）+ `downloadBlob`；插件通过 `NovusPluginShared.downloadBlob`

→ 完整规范：[references/platform-infrastructure.md](references/platform-infrastructure.md)
→ 公开配置/品牌/验证码：[references/public-config-branding-captcha.md](references/public-config-branding-captcha.md)
→ 下载规范：[references/download-spec.md](references/download-spec.md)
→ trace_id 与日志：[references/trace-id-logging-spec.md](references/trace-id-logging-spec.md)
→ 上传下载专题技能：[../attachment-storage/SKILL.md](../attachment-storage/SKILL.md)

---

## 三、后端开发（CRUD 7 步）

分层架构：请求 → Middleware → Controller → Service → Repository → Model/DB

1. **Model** — 继承 `TenantModel`/`BaseModel`，声明 `__filterable__`/`__sortable__`/`__delete_deps__`（被 FK 引用时）
2. **Schema** — 继承 `BaseCreateSchema`/`BaseUpdateSchema`/`BaseResponseSchema`
3. **Repository** — 继承 `TenantRepository`/`BaseRepository`
4. **Service** — 继承 `TenantService`/`BaseService`，可重写钩子
5. **Controller** — 继承 `TenantController`/`GlobalController`，声明 `@permission_resource` + `@action_*`
6. **注册路由** — 引入 `router`
7. **生成迁移** — `alembic revision --autogenerate -m "xxx"`（启动时自动 upgrade）

**关键注意**：
- 如需此表对 AI 可见（数据智能/Text-to-SQL），Model 必须声明 `__ai_policy__`（详见 backend-crud.md Step 1）
- `TenantController.get_service(db, tenant_id)` — 第二参数是 `int`
- `BaseController.get_service(db)` — 只需 `db`
- 分页用 `query.size` 不是 `query.page_size`
- 新 Model 必须注册到 `models/__init__.py` 和 `migrations/env.py`（codegen 生成的模块已自动注册，仅手写 CRUD 时需手动）

→ 完整代码示例：[references/backend-crud.md](references/backend-crud.md)
→ 后端开发指南：[references/backend-spec.md](references/backend-spec.md)

---

## 四、前端开发（CRUD）

架构分层：`views → composables → store/api → utils`（禁止反向依赖）

### 模式选择

| 场景 | Composable | 渲染方式 |
|------|-----------|---------|
| 数据密集型列表（日志、配置、用户管理） | `useCrudPage` | VxeTable 表格 |
| 卡片网格（知识库、智能体、插件） | `useCrudList` | 自定义卡片模板 |
| Master-Detail（技能包：左列表+右详情） | `useCrudList` × 2 | 自定义分栏模板 |
| 配置面板（域名管理、配额管理） | `useCrudList` | 自定义卡片/列表 |

### 模式 A：表格（useCrudPage）

1. **data.ts** — 列定义 `useColumns()`、搜索 `useGridFormSchema()`、表单 `useFormSchema()`
2. **index.vue** — `useCrudPage` 组装列表（返回 `Grid` + `FormDrawer`）
3. **form.vue** — `useCrudDrawer` 组装表单
4. **路由 + i18n**

### 模式 B：自定义布局（useCrudList）

1. **data.ts** — 搜索/表单辅助函数、状态/颜色辅助函数
2. **index.vue** — `useCrudList` 获取数据能力（`list`/`loading`/`loadList`/`onCreate`/`onEdit`/`onDelete`/`onSearch`/`onPageChange`），自定义模板渲染
3. **form.vue** — `useCrudDrawer` 或 ref 模式（`openNew()`/`openEdit()`）
4. **路由 + i18n**

```typescript
// useCrudList 声明式配置示例
const { list, total, loading, FormDrawer, loadList, onCreate, onSearch, onPageChange, handleMenuAction } =
  useCrudList<ItemType>({
    api: { list: getListApi, delete: deleteApi, resource: '/admin/items' },
    formComponent: Form,
    i18nPrefix: 'admin.module',
    pageSize: 12,
    recycleBin: true,
  });
```

### 统一作用域组件

所有涉及资源作用域（`scope`）的场景必须使用统一组件，禁止手写 scope 选项数组或自定义选择器。

| 场景 | 必须使用 | 位置 |
|------|---------|------|
| **表单中的 scope 选择字段** | `useScopeFields(options)` | `#/components/business/scope-select` |
| **搜索过滤器中的 scope 下拉** | `getScopeOptions()` | `#/utils/scope-helpers` |
| **列表/卡片中显示 scope 标签** | `getScopeText()` / `getScopeColor()` / `getScopeIcon()` | `#/utils/scope-helpers` |
| **独立的 scope 选择控件** | `<ScopeSelect />` 组件 | `#/components/business/scope-select` |

```typescript
// ✅ 表单中的 scope 字段（管理端表单）
...useScopeFields({
  scopeHelp: $t('admin.ai.agent.help.scope'),
  scopeDisabled: (values) => values._mode === 'edit', // 编辑时锁定
  showTenantId: false, // 默认 false；仅定时任务等特殊场景传 true
})

// ✅ 搜索过滤器 scope 下拉
select('filter[scope][eq]', $t('...'), {
  options: getScopeOptions(), // 从 scope-helpers.ts 统一获取
})

// ✅ 企业端判断资源是否可编辑：看归属企业（API 常序列化为 tenant_id，语义同 owner_tenant_id）
show: (row) => row.tenant_id != null && row.tenant_id === currentTenantId
```

**`useScopeFields` 关键选项：**
- `allowedScopes` — 限制可选 scope（五类 ResourceScopeEnum 子集）
- `scopeDisabled` — 编辑时锁定（`(values) => values._mode === 'edit'`）
- `showTenantId` — 仅当 `all_tenants` 需选「所属企业」时传 `true`（如定时任务）
- `ownerTenantWhenScopes` — 如 API Key：`selected_tenants` 时选归属企业
- `hideTenantIdsField` — 不需要 RTA 多选分配时传 `true`（如 API Key）

### 禁令

- **禁止手写 CRUD 数据管理**：禁止手动管理 `loading`/`list`/`page`/`total` + `fetchList` + `watch` 分页 + 手写删除确认 + 手写回收站。必须使用 `useCrudPage` 或 `useCrudList`
- 搜索/表单必须用辅助函数（`searchInput` / `inputField` 等），禁止手写 Schema
- **禁止手写 scope 选项数组**：必须使用 `useScopeFields` / `getScopeOptions()` / `ScopeSelect`
- **禁止用 `scope` 推断归属**：企业自有/可编辑只看 `tenant_id`（owner）是否等于当前企业
- 业务预设（planSelect 等）定义在 `data.ts`，不放 adapter
- `requestClient` 导入路径：`#/utils/request`
- 权限指令：`v-access:code="['resource:action']"`

→ 完整代码示例：[references/frontend-crud.md](references/frontend-crud.md)
→ 前端开发手册：[references/frontend-spec.md](references/frontend-spec.md)
→ 图标规范：[references/icon-spec.md](references/icon-spec.md)

---

## 五、前后端协作约定

- **过滤**：`filter[status]=active` / `filter[name][ilike]=科技`
- **排序**：`sort=-created_at,name`
- **分页**：`page[number]=1&page[size]=20`
- **错误码**：4010→跳登录，4011→刷新 Token，4030→权限不足
- **CRUD 请求**：POST 创建 / PUT 更新 / DELETE 删除 / GET 列表

---

## 六、AI 模块

**核心架构原则：所有 AI 功能必须通过 Agent → Skill → AIGateway 链路完成，禁止直接调用 AIGateway。**

- 技能包（SkillPackage）是一级管理单元，技能必须归属于某个技能包
- 技能类型：`toolkit` / `knowledge_base` / `data_intelligence` / `builtin` / `http` / `email` / `code_execution`
- 新增 AI 功能标准流程：定义类型 → 实现 Executor → 注册映射 → 创建 Skill → 绑定 Agent
- **技能（Skill）无独立 `scope` 字段**，可见性和操作权限完全继承自所属 SkillPackage
- 页面感知与操作遵循三层架构：Layer 1 通过 `page_context -> input_variables -> system prompt` 注入基础感知，Layer 2 通过 builtin skill `get_page_context` 提供深度上下文，Layer 3 通过 builtin skill `invoke_page_operation` 经 WebSocket 双向通信执行前端页面操作
- **RAG 运行时配置中心是 `Agent.rag_config`**：KB 表上的 `search_mode/top_k/score_threshold` 仅作兼容；多 KB 检索默认按 KB 独立召回再融合，绑定权重进入融合层而非摆设字段
- **仅注册 Executor 不算完成**，必须同时存在 `SkillPackage + builtin Skill + auto-bind`，让工具进入 LLM function calling tools schema
- `_PROTECTED_TOOL_NAMES` 白名单保护 `get_page_context`、`invoke_page_operation`、`list_page_operations` 不被工具优化器过滤
- 页面感知标准接入点：`useCrudList` 的 `ai` 配置自动注册 context + operations；ref 模式页面需传递 `_aiPageKey`
- 页面感知 `page_context` 字节预算由平台配置 `ai_page_context_max_bytes` 控制；入口在 **管理端 → 系统配置 → AI Toolkit 与页面上下文**，默认 `8192` bytes，**不是**模型输入/输出 token 限制
- 操作安全：`readonly=true` 直接执行，`readonly=false` 前端弹出确认对话框，超时 30s
- **禁止手动 `registerPageContext` 与 `useCrudList` 的 `ai` 配置共存**——会覆盖增强 context，使用 `contextExtras` 合并自定义数据

### 资源作用域 vs 技能包（摘要）

- **资源作用域**仅五类：`global_shared` / `admin_only` / `all_tenants` / `admin_and_selected_tenants` / `selected_tenants`（`ResourceScopeEnum`）。
- **投放面**由 `scope` + `resource_tenant_assignments` 表达；**企业是否可编辑**由 **`owner_tenant_id`（或模型仍名为 `tenant_id` 的归属列）** 判定，禁止再用「`all_tenants` + tenant 是否为空」旧双重语义。
- **Skill 无独立 `scope`**，继承所属 **SkillPackage** 的 scope + 归属列。
- **受众/发布**（`target_audience`、`TenantAgentPublication` 等）不属于上述五类资源作用域。

**模型多模态**：对话适配器根据模型的 `supports_vision` / `supports_audio` / `supports_video` 决定附件转 image_url、input_audio 或文字提示；知识库可配置 vision/audio/video 可选模型，RAG 描述器选型优先级为 KB 显式配置 → 平台首个对应能力模型。

**AI Writing**：富文本编辑器 AI 写作统一走 `/admin|/tenant/ai/writing/{feature}` -> `writing_service.stream_writing_feature()` -> `system.ai_writing` 智能体分配 -> `AgentChatService.stream_chat_ephemeral()`；不要在编辑器链路直接调 AIGateway 或硬编码 Agent ID。

**Session Memory**：会话记忆只在 `ai_chat_page` / `admin_chat` 这类真实对话场景生效，统一通过 `AgentChatService` 注入/提取，通过 `SessionMemoryService` 落 Redis（CAS + 幂等 + TTL），通过 `ConversationService` 暴露 `memory-state` 查询/清理接口；不要在 Controller、前端或 AI Writing 链路手工管理记忆。

→ 完整代码示例（isTenantOwned + 后端保护）：[references/ai-module.md](references/ai-module.md) § 八
→ AI 写作规范：[references/ai-writing-spec.md](references/ai-writing-spec.md)
→ 会话记忆规范：[references/session-memory-spec.md](references/session-memory-spec.md)
→ 页面感知系统接入规范：[references/page-awareness-spec.md](references/page-awareness-spec.md)
→ 模型多模态使用规范（Adapter/KB/RAG 选型与前端约定）：[references/multimodal-model-usage.md](references/multimodal-model-usage.md)
→ 多模态 RAG / Agent 级 RAG 配置规范：[references/multimodal-rag.md](references/multimodal-rag.md)
→ 知识库 / RAG 专题技能：[../knowledge-base-rag/SKILL.md](../knowledge-base-rag/SKILL.md)
→ AI 写作专题技能：[../ai-writing/SKILL.md](../ai-writing/SKILL.md)
→ 会话记忆专题技能：[../session-memory/SKILL.md](../session-memory/SKILL.md)
→ 页面感知专题技能：[../ai-page-awareness/SKILL.md](../ai-page-awareness/SKILL.md)
→ **AI 调用日志与用量账本**（`AICallLog`、Celery `tasks.ai.log_ai_call`、`billing_context`、Worker 版本一致）：[../ai-call-log-usage-ledger/SKILL.md](../ai-call-log-usage-ledger/SKILL.md)

---

## 七、异步任务与定时任务

- 业务任务模块必须用 `@register_task` 装饰器；插件注册器这类框架桥接层可在内部动态注册 Celery task
- Celery Worker 是同步进程，用 `sync_session_factory()` 获取 DB，`redis.from_url()` 获取 Redis
- 5 个队列：`default` / `high_priority` / **`ai_gateway`**（含 **`tasks.ai.log_ai_call`** AI 调用日志落库） / `scheduled` / `notification`
- 业务可运维定时任务优先通过 `periodic_tasks` 表管理；系统级兜底任务才静态注册 `beat_schedule`

→ 完整规范：[references/async-tasks.md](references/async-tasks.md)

---

## 七-A、可观测性监控

Prometheus + Grafana 可观测性集成，**仅限 Admin 端**。

- **自定义指标**：AI 调用、Celery 任务、WebSocket、DB 连接池等（`app/core/metrics.py`）
- **埋点位置**：AIGateway、BaseTask、Socket.IO namespace 的 connect/disconnect
- **端点**：`/metrics`（IP 白名单）、`/admin/monitoring/metrics-summary`、`/admin/monitoring/grafana-config`
- **前端**：`/admin/system-maintenance/monitoring`，Tab 实时概览 + Grafana iframe
- **Docker**：`docker-compose.dev.yml` 含 Prometheus + Grafana，预置 3 个 Dashboard

→ 完整规范：[references/monitoring-spec.md](references/monitoring-spec.md)

---

## 八、删除依赖保护

任何 Model 被 FK 引用时，**必须**声明 `__delete_deps__`。五种策略：`BLOCK` / `CASCADE_SOFT` / `CASCADE_DELETE` / `NULLIFY` / `IGNORE`。`useCrudPage` 已集成 `DependencyBlockModal`（错误码 4221）。

> 当前已声明 `__delete_deps__` 的 Model 列表见 `references/deletion-deps.md`（勿在此处维护静态列表，易过时）。

→ 完整规范：[references/deletion-deps.md](references/deletion-deps.md)

---

## 九、邮件发送

所有邮件必须通过 `send_email_task.delay()` 异步发送，禁止 Controller/Service 直接调用 `EmailService.send()`。

→ 完整规范：[references/email-spec.md](references/email-spec.md)

---

## 十、通知系统

所有业务通知统一走 `NotificationService.send()` → 渠道驱动（WS / Inbox / Email）。模板编码格式：`{category}.{event_name}`。

→ 完整规范：[references/notification-spec.md](references/notification-spec.md)
→ 通知偏好治理：[references/notification-preference-spec.md](references/notification-preference-spec.md)

## 十-A、通知偏好治理

admin / tenant 端通知偏好使用分层继承：`global preference -> individual override -> default fallback`，统一通过 `NotificationPreferenceService` 与 `NotificationSettings.vue` 管理。

- 全局偏好修改后，会精确清除受影响分类的个人覆盖
- 个人模式支持“跟随全局 / 已自定义”状态与 reset to global
- 不要把通知偏好逻辑混入 `UserPreferenceService` 的 UI 偏好三层模型

→ 完整规范：[references/notification-preference-spec.md](references/notification-preference-spec.md)

---

## 十一、WebSocket 实时通信

三端 namespace 隔离：`/admin` / `/tenant` / `/user`。后端用 `sio.emit()`，Celery 用 `sio_bridge.*_sync()`。

→ 完整指南：[../websocket-guide/SKILL.md](../websocket-guide/SKILL.md)

---

## 十二、时间存储与显示

**后端**：
- 统一 `utc_now()`（`app.core.base_model`），禁止 `datetime.now()` / `datetime.utcnow()`
- 序列化：ISO 8601 + `+00:00` 后缀（由 Pydantic 自动处理，禁止 `str(datetime)` 手动序列化）
- 手动构造 dict 时必须用 `dt.isoformat()`；若 datetime 无时区信息（naive），先 `dt.replace(tzinfo=timezone.utc)` 再 `.isoformat()`
- `app.core.response._serialize()` 已统一处理 `paginated()` / `success()` 中的 naive datetime

**前端**（`#/utils/common`）：
- 禁止原生 `toLocaleString` / `toLocaleDateString` / `toLocaleTimeString`
- `formatDate(date, options?)` — 默认 `YYYY-MM-DD HH:mm:ss`，详情页/抽屉完整时间
- `formatDateOnly(date)` — `YYYY-MM-DD`，仅日期场景（如过期日期）
- `formatTimeOnly(date)` — `HH:mm:ss`，仅时间场景（如消息时间戳）
- `formatRelativeTime(date)` — 相对时间（刚刚、X 分钟前...），列表页主显示
- 列表页标准模式：`formatRelativeTime` 为主显示 + `formatDate` 为 Tooltip

---

## 十三、数据库迁移

系统启动时自动执行 `alembic upgrade head`，开发者只需生成迁移文件。新 Model 必须注册到 `models/__init__.py` 和 `migrations/env.py`。

### 迁移文件卫生规则

1. **禁止残留垃圾迁移** — 创建种子数据（seed）迁移前，先确认该数据确实被代码引用（如 `resolve('feature_code')`）。未被引用的占位数据不要写入迁移。
2. **禁止删除链中的迁移文件** — Alembic 依赖 `revision → down_revision` 链，删除中间文件会导致 `alembic history` / `upgrade` 报错。如果迁移已失效，将其转为 **no-op**（`upgrade`/`downgrade` 改为 `pass`），并在 docstring 中标注 `[NO-OP]` 及原因。
3. **纯数据迁移要评估生命周期** — 如果插入的种子数据后续可能被删除，优先使用应用层初始化（如 `on_startup` seed 函数）而非迁移文件。迁移文件一旦写入链就无法干净移除。
4. **autogenerate 后必须检查** — `alembic revision --autogenerate` 生成的文件可能是空的（`pass`），必须检查并补充实际逻辑，或删除空文件（未执行前可删）。
5. **合并分支及时处理** — 出现多 head 时立即 `alembic merge`，不要留多个 head 长期共存。
6. **命名规范** — 文件名格式：`YYYYMMDD_<revision_id>_<description>.py`。描述用英文 snake_case，清晰表达迁移目的。
7. **FK 约束显式命名** — `op.create_foreign_key()` 第一个参数必须传显式名称（如 `'fk_table_col_ref'`），**禁止传 `None`**。传 `None` 会让 PostgreSQL 自动生成约束名，导致 `downgrade` 中 `op.f('fk_...')` 找不到约束而报错。

→ 完整最佳实践：[../database-migration-best-practices/SKILL.md](../database-migration-best-practices/SKILL.md)

---

## 十四、DevGenius MCP 工作流

核心流程：认领任务 → 查文档 → 开发 → 写文档 → 更新状态

→ 详细工具用法：[references/devgenius-workflow.md](references/devgenius-workflow.md)

---

## 十五、后端单元测试

使用 pytest + unittest.mock，所有测试不依赖真实 DB/Redis/网络。

**核心要点**：
- 共享 fixtures 在 `tests/services/conftest.py`：`mock_db`、`mock_redis`、`mock_celery`、sample data factories
- Mock 工厂：`make_mock_model()` / `make_scalar_result()` / `make_scalars_result()` / `make_row_result()`
- Service 实例化用 `__new__` 跳过 `__init__`，手动设置 `db` / `tenant_id` / `repo`
- 每个 Service 一个测试文件，≥ 6 个用例，覆盖正常流程 + 边界 + 错误
- 运行：`cd backend && pytest tests/services/ -v`

→ 详细规范 + 示例：[references/testing-spec.md](references/testing-spec.md)
→ 测试专题技能：[../testing-validation/SKILL.md](../testing-validation/SKILL.md)

---

## 十六、运维就绪

### Health Check

- 端点：`GET /api/public/health`（`@public`，无需认证）
- 检查 DB（`SELECT 1`）+ Redis（`ping`）
- 返回 200 `{status:'ok', timestamp, checks}` 或 503 `{status:'error'}`
- 文件：`app/api/public/health.py`

### IP 速率限制

- 工具类：`app/core/rate_limit.py` → `IPRateLimiter`（内存滑动窗口 + 定期清理）
- 预置实例：`login_limiter`（10 req/min/IP）、`captcha_limiter`（20 req/min/IP）
- 用法：在端点中 `rate_resp = login_limiter.check(request); if rate_resp: return rate_resp`
- 超限返回 429 `{error, code: 4290, retry_after}`

### ConfigService 内存缓存

- `_config_id_cache`：key→id 映射，TTL 300s
- `_config_value_cache`：配置值，TTL 60s
- 写入时立即失效缓存（`_set_config_value` 中 `pop`）

### NovusAI CLI 工具

统一入口 `novusai`（`app/cli.py`），整合 run / celery / db / plugin / license / check / info。

- `novusai run` — 启动 FastAPI（uvicorn）
- `novusai celery worker|beat|dev|flower|purge` — Celery 管理
- `novusai db upgrade|revision|current|heads|history|stamp|merge|autogenerate` — 迁移
- `novusai plugin create|validate|pack|list` — 插件管理
- `novusai license generate|verify|keygen` — License 管理
- `novusai check [db|redis|celery]` — 环境检查
- `novusai info` — 版本/环境/配置摘要

→ 完整规范：[references/cli-spec.md](references/cli-spec.md)

---

## 十七、RBAC 权限注册

**新增任何 Controller 时，以下两项必须同步完成，否则权限树出现孤立节点或显示英文原始 action 名。**

### 1. `parent_resource` 必填

```python
@permission_resource(
    "my_resource",
    parent_resource="system_maintenance",  # ← 必须声明，否则 parent_id=null（孤立）
)
class MyController(GlobalController): ...
```

常用父资源对照：`ai_infra` / `ai_provider` / `ai_quota_mgmt` / `system_maintenance` / `platform_mgmt`

### 2. `messages.json` 必须同步添加翻译

在 `backend/app/locales/zh_CN/messages.json` 现有 `"action"` 对象内追加（**禁止新建第二个 `"action"` 顶层 key**，会静默覆盖导致翻译丢失）：

```json
"action": {
  "my_resource": {
    "list": "查看列表",
    "create": "创建",
    "update": "更新",
    "delete": "删除"
  }
}
```

缺失翻译时 `_translate_name()` 回退返回原始英文 action 名（如 `list`、`delete`）。

### 3. 插件权限同步用 `sync_plugin_permissions()`

```python
# ✅ 插件安装/修复场景：仅同步该插件的权限
await perm_sync.sync_plugin_permissions(plugin.name)

# ❌ 错误：全量 sync 在插件事务中会产生副作用
await perm_sync.sync_permissions()
```

→ 完整规范：[references/rbac-permission-spec.md](references/rbac-permission-spec.md)

### 4. 新增页面标准流程（菜单一致性）

系统内置双向校验机制，开发模式下自动在控制台报告以下两类问题：

| 方向 | 检查内容 | 控制台标识 |
|------|---------|-----------|
| 正向 | 后端注册了菜单但前端无对应 Vue 组件 | `[DynamicMenu] [CRITICAL]` |
| 反向 | 前端存在 Vue 页面但无菜单入口/静态路由 | `[MenuCheck]` |

**新增页面必须同时完成以下步骤：**

1. **创建 Vue 页面组件** — `views/{endpoint}/.../{name}/index.vue`
2. **注册菜单** — 二选一：
   - 在 `admin_menus.py` / `tenant_menus.py` 中添加 `PermissionMeta`（目录菜单或叶子菜单）
   - 在 Controller 上声明 `@permission_resource(menu=MenuConfig(icon=..., path=..., component=...))`
3. **如果是无菜单页面**（详情页、弹窗页）— 在前端静态路由（`router/routes/admin/index.ts`）中注册并标记 `hideInMenu: true`
4. **验证** — 启动开发服务器，检查控制台是否有 `[MenuCheck]` 或 `[DynamicMenu]` 警告

---

## 十七-A、偏好设置

admin / tenant 端 UI 偏好使用三层模型：`SYSTEM_DEFAULTS -> global preferences -> individual overrides`，统一通过 `UserPreferenceService`、`useUserPreferenceStore`、`usePreferenceSync` 管理。

**核心要点**：
- 全局偏好更新后，会把变更 key 从个人覆盖中精确清除
- `preference:global_updated` 通过 Socket.IO 推送到 `admins` 或 `tenant:{tenant_id}` 房间
- 全局偏好页必须复用 `useGlobalPreferencePage`，支持实时预览与离开回滚
- `watermark_*` 属于 `GLOBAL_ONLY_KEYS`，个人偏好不可覆盖

→ 完整规范：[references/preferences-spec.md](references/preferences-spec.md)
→ 偏好设置专题技能：[../preferences-governance/SKILL.md](../preferences-governance/SKILL.md)

---

## 十八、用户端（User Endpoint）开发

用户端面向 C 端业务用户，架构与 admin/tenant 端有显著差异：

| 维度 | admin/tenant | user |
|------|-------------|------|
| API 前缀 | `/api/admin/*` / `/api/tenant/*` | **`/api/user/*`**（ADR-2） |
| Token Scope | `admin` / `tenant_admin` | `tenant_user` |
| 依赖注入 | `ActiveAdmin` / `ActiveTenantAdmin` | **`ActiveTenantUser`** |
| Layout | `BasicLayout`（侧边栏） | **`UserLayout`**（Layout A - Top Nav, 无侧边栏） |
| 移动端 | 次要 | **核心支持**（responsive-first, >=375px） |

**核心要点**：
- UserLayout = 56px 水平导航栏 + 居中内容区（max-width: 1100px）+ 移动端 hamburger drawer
- 当前前端静态主路由是 `/home`、`/ai-chat`、`/settings/*`；认证页在共享 `/auth/*` 路由下
- 用户端菜单与权限仍由 `user_menus.py` 提供，但部分资源码保留 legacy `dashboard` 命名，新增功能不要继续扩散旧命名
- 域名→企业→品牌加载：Router Guard `detectDomainType()` → `loadTenantConfig()` → `applyBrandConfig()`
- 公开端点用 `@public`，登录后端点用 `@auth_only`
- 注册/忘记密码端点需 `IPRateLimiter` 保护
- 用户端验证码使用企业公开配置 + 独立 `userLoginFailCount`，前端统一走 `CaptchaProvider`
- Token 选择：前端 `/api/user/*` URL 自动选择 user Token

→ 完整规范：[references/user-endpoint-spec.md](references/user-endpoint-spec.md)
→ 公开配置/品牌/验证码：[references/public-config-branding-captcha.md](references/public-config-branding-captcha.md)
→ 用户端专题技能：[../user-endpoint/SKILL.md](../user-endpoint/SKILL.md)

---

## 十九、插件开发

插件系统采用**零侵入架构**：plugin.yaml 声明式清单 + PluginBase 生命周期钩子 + PluginContext 沙箱 API + UMD 前端动态加载。

**核心原则：插件代码（后端逻辑、前端组件、国际化文件）只能存在于 `backend/plugins/{name}/` 内，严禁写入主系统代码中。**

> 完整规范（目录结构/manifest/config_schema/菜单注册/HookPoints/EventBus/前端加载/命名规范）见 [references/plugin-spec.md](references/plugin-spec.md)。

### 生命周期（必须实现）

```python
from app.plugins.base import PluginBase

class MyPlugin(PluginBase):
    async def on_install(self, ctx):   ...  # 初始化种子数据
    async def on_enable(self, ctx):    ...  # 启动后台任务
    async def on_disable(self, ctx):   ...  # 清理后台任务
    async def on_uninstall(self, ctx): ...  # 清理自定义数据
    async def on_upgrade(self, ctx, old_version): ...
```

### PluginContext 核心 API

```python
await ctx.get_config()                      # 读取配置（自动解密 x-encrypted）
db = ctx.get_db()                           # PluginDbProxy（仅 px_{name}_* 表）
await ctx.http_request("GET", url)          # 需 http:outbound capability
await ctx.call_ai_feature("code", messages) # 非流式，需 ai:call
async for delta in ctx.call_ai_feature_stream("code", messages): ...  # 流式
```

### 关键命名规则

| 项目 | 格式 | 示例 |
|------|------|------|
| DB 表 | `px_{name_underscored}_*` | `px_novusdoc_documents` |
| Alembic 分支 | `plugin_{name_underscored}` | `plugin_novusdoc` |
| API 路径 | `/admin/plugins/{name}/api/*` | `/admin/plugins/novusdoc/api/` |

### 关键禁令

- ❌ 禁止自定义技能类型（必须用 7 种内置 type，通过 `source_plugin` 区分）
- ❌ 禁止在主系统代码写入插件组件/逻辑/i18n
- ❌ 禁止操作非 `px_{name}_*` 前缀的表（PluginDbProxy 拦截）
- ❌ 禁止 `eval/exec/subprocess`（安全扫描检测）
- ❌ `Alembic 迁移必须声明 `branch_labels = ('plugin_{name_underscored}',)`

### CLI 工具

```bash
novusai plugin create my-plugin --template=minimal      # 纯后端
novusai plugin create my-plugin --template=skill        # + Skill/Executor
novusai plugin create my-plugin --template=full-module  # + 前端 + API + 迁移
novusai plugin validate plugins/my-plugin               # 校验
novusai plugin pack plugins/my-plugin                   # 打包 zip
```

→ 完整规范 + 代码示例：[references/plugin-spec.md](references/plugin-spec.md)
→ 插件专题技能：[../plugin-development/SKILL.md](../plugin-development/SKILL.md)

---

## 二十、请求追踪（trace_id）

每个请求自动生成或继承 `X-Trace-ID`，贯穿中间件、日志、Celery、审计日志。前端请求自动带 header，5xx 错误弹窗显示追踪 ID 供反馈。

→ 完整规范：[references/trace-id-logging-spec.md](references/trace-id-logging-spec.md)

## 二十-A、AI 操作审计日志

AI 工具执行、页面操作和确认流统一写入 `AIActionLog`，必须通过 `write_ai_action_log()` 与 `resolve_action_level()`，禁止在 Controller/Executor 中直接拼装 `AIActionLog`。

- 状态固定 `success` / `failed` / `rejected` / `pending_confirm`
- 耗时字段统一用 `duration_ms`
- 管理端全局审计页：`/admin/ai/action-logs`
- 企业端租户审计页：`/tenant/ai/action-logs`

→ 完整规范：[references/ai-action-log-spec.md](references/ai-action-log-spec.md)

---

## 二十一、Token 吊销与强制下线

JWT 含 `jti`，Redis `token_blacklist:{jti}` 记录吊销，`active_tokens:{user_type}:{user_id}` 记录活跃 token。登出/强制下线均调用 `revoke_token`，Socket.IO 推送 `force_logout` 事件。

→ 完整规范：[references/token-force-logout-spec.md](references/token-force-logout-spec.md)

---

## 二十二、数据权限过滤

角色表含 `data_scope`、`custom_dept_ids`，Model 声明 `__data_permission__ = True` 后，`TenantRepository` 自动按部门/自己范围过滤查询，创建时自动填充 `created_by`、`dept_id`。

→ 完整规范：[references/data-permission-spec.md](references/data-permission-spec.md)

---

## 二十三、CRUD 代码生成器

通过 YAML 配置生成 Model / Schema / Repository / Service / Controller / Test 及前端骨架。

**使用方式**：
- **UI**：管理端 `/admin/system/codegen` 为配置列表；`/admin/system/codegen/new|:id/edit` 为三栏 `builder.vue` 可视化构建器，不是旧版 6 步向导
- **CLI**：`novusai codegen generate --config codegen_configs/xxx.yaml` / `--id N` / `--resource xxx`

**生成物**：backend models/schemas/repositories/services/api，tests；前端骨架（按模板）

**自动化能力**（无需手动）：
- 路由注册（import + include_router + `__all__`）
- Model 注册（module/__init__ + root/__init__ + env.py）
- 后端 i18n（messages.json 深度合并）
- 数据库迁移（`--auto-migrate`）
- 子表 Model 注册

**回滚**：`novusai codegen rollback --resource xxx` 按 manifest 逆向操作

→ 完整规范（YAML 配置 / 类型映射 / CLI 参考）：[references/codegen-spec.md](references/codegen-spec.md)
→ Builder/WYSIWYG 规范：[references/codegen-builder-spec.md](references/codegen-builder-spec.md)
→ Codegen Builder 专题技能：[../codegen-builder/SKILL.md](../codegen-builder/SKILL.md)

---

## 检查清单

### 后端

- [ ] Model 继承 `BaseModel` / `TenantModel`，声明 `__filterable__` / `__sortable__`
- [ ] 被 FK 引用的父 Model 声明 `__delete_deps__`
- [ ] 枚举比较用 `.value`（禁止硬编码字符串）
- [ ] Controller 无直接 DB 查询（全部下沉到 Service/Repository）
- [ ] Repository 继承 `BaseRepository` / `TenantRepository`
- [ ] Service 继承 `BaseService` / `TenantService` / `GlobalService`
- [ ] Controller 声明 `@permission_resource`，方法声明 `@action_*`
- [ ] `@permission_resource` 声明了 `parent_resource`（缺失→权限 parent_id=null，出现孤立节点）
- [ ] `messages.json` 的 `"action"` 段内追加了新 Controller 的翻译（不是新建第二个顶层 `"action"` key）
- [ ] 插件场景权限同步用 `sync_plugin_permissions(plugin_name)`，不用全量 `sync_permissions()`
- [ ] 新增叶子菜单页面在 `admin_menus.py` / `tenant_menus.py` 或 `@permission_resource(menu=MenuConfig(...))` 中注册，启动日志无 `_validate_menu_components` 警告
- [ ] 统一响应方法（`success` / `created` / `paginated` / `deleted`）
- [ ] 面向用户文本使用 `_()`（含 API `Query`/`Form`/`File` 的 `description`，用 `api.param.*` 键）
- [ ] 枚举使用 `LabeledEnum`
- [ ] Alembic 迁移已生成
- [ ] 新 Model 已注册到 `models/__init__.py` 和 `migrations/env.py`（codegen 已自动，手写时需检查）
- [ ] 敏感信息通过环境变量
- [ ] 时间使用 `utc_now()`
- [ ] 新 Service 有对应 `tests/services/test_{name}.py`（≥ 6 cases）
- [ ] 公开敏感端点有 `IPRateLimiter` 保护
- [ ] AI 功能通过 Agent→Skill 链路，禁止直接调用 AIGateway
- [ ] 新增 AIModel 后已更新 `__filterable__`（含能力字段 supports_vision 等）
- [ ] 迁移文件 `create_foreign_key` 使用显式名称（不传 `None`），否则 downgrade 找不到约束
- [ ] Loguru 日志使用 `{}` 风格（不用 `%s`/`%d`）
- [ ] 迁移脚本中无 `text(f"...")`，全部使用 `text(...).bindparams()` 参数化 SQL
- [ ] 无 `except Exception: pass`，异常至少 `logger.debug` 记录
- [ ] 列表/导出查询有 `.limit(N)` 上限（分页用 page[size]；单条/主键/小表豁免）
- [ ] `open()` 使用 `with` 语句或确保关闭，禁止返回裸文件句柄（或用 `BytesIO`）
- [ ] 依赖变更后已运行 `uv lock` 并提交 `uv.lock`
- [ ] 循环引用类型使用 `from __future__ import annotations` + `TYPE_CHECKING`
- [ ] 启用数据权限的 Model 声明 `__data_permission__ = True` 且有 created_by / dept_id 字段
- [ ] 新增 Controller 端点的 force-logout 类操作有 `@action_create` 权限保护
- [ ] 业务任务使用 `@register_task`（trace_id 自动传播）；仅插件注册器等基础设施层允许内部动态注册 Celery task
- [ ] CLI 新子命令已注册到 `app/cli.py`
- [ ] 新增 AI/Celery/WebSocket 关键路径时，已在 `app/core/metrics.py` 埋入对应指标（Counter/Histogram/Gauge）

### 前端

- [ ] 无 `any` 类型
- [ ] 无 `console.log()`
- [ ] 新增代码注释/备注为中英双语，禁止单语注释
- [ ] 无中文硬编码（全部 `$t()`，包括 Tooltip/Popconfirm/Alert/Empty、entityName、entityDescription 等）
- [ ] 业务页面上传用 `smartUploadFile` 或 `FilePicker` / `ImageUpload` / `ConfigImagePicker`；仅富文本编辑器等基础设施封装允许内部直连标准附件上传端点；禁止自建上传组件
- [ ] 文件下载用 `requestClient.download` + `downloadBlob`；插件用 `NovusPluginShared.downloadBlob`；禁止用 `window.open(apiUrl)` 触发下载或手写 blob 点击
- [ ] 搜索/表单用辅助函数生成
- [ ] 业务预设在 `data.ts` 定义，不在 adapter
- [ ] 无跨端导入
- [ ] 含 scope 字段的表单使用 `useScopeFields()`，不手写选项数组
- [ ] 企业端资源操作按钮按 **归属企业**（`tenant_id` / `owner_tenant_id`）判断，禁止用 `scope === 'all_tenants'` 推断可编辑
- [ ] i18n JSON key 无重复、路径正确
- [ ] 中英文翻译齐全（zh-CN 和 en-US 的 key 必须完全对齐）
- [ ] Props 用 `defineProps<T>()`
- [ ] 新增页面后启动开发服务器，控制台无 `[MenuCheck]`（孤儿页面）或 `[DynamicMenu] [CRITICAL]`（菜单组件缺失）警告
- [ ] 5xx 错误弹窗显示追踪 ID（notification 组件，非 message）
- [ ] 强制下线按钮有权限校验（v-access）且仅在线时显示
- [ ] `v-html` 绑定值经 `DOMPurify.sanitize()` 净化
- [ ] 事件监听用 `addEventListener`，不用属性赋值（如 `img.onerror = ...`）

---

## 参考文件索引

| 文件 | 内容 |
|------|------|
| [platform-infrastructure.md](references/platform-infrastructure.md) | 多企业/认证/异常/日志/SSE/启动/存储/配置/组件 |
| [backend-crud.md](references/backend-crud.md) | 后端 CRUD 7 步完整代码 + 响应/异常/权限/枚举/日志 |
| [frontend-crud.md](references/frontend-crud.md) | 前端 CRUD 完整代码（useCrudPage 表格 + useCrudList 自定义布局 + useCrudDrawer 表单） |
| [frontend-spec.md](references/frontend-spec.md) | 前端开发手册完整版（含拖拽排序、列表 UI 设计、CSS 动画等） |
| [detail-page-patterns.md](references/detail-page-patterns.md) | 资源详情页 UI 模式（Hero Header / 带图标 Tabs / 信息卡片 / 表单区块 / 功能开关卡片 / 绑定行 / 只读横幅） |
| [backend-spec.md](references/backend-spec.md) | 后端开发指南完整版（含存储、日志、枚举、Service 钩子等） |
| [async-tasks.md](references/async-tasks.md) | 异步任务与定时任务开发规范（Celery/Redis/队列/定时任务） |
| [devgenius-workflow.md](references/devgenius-workflow.md) | DevGenius MCP 工作流详解（工具速查、流程图、文档管理） |
| [ai-module.md](references/ai-module.md) | AI 模块开发规范（引擎/网关/工具/RAG/数据智能/事件/安全） |
| [ai-writing-spec.md](references/ai-writing-spec.md) | 富文本编辑器 AI 写作规范（SSE 端点/system.ai_writing/useEditorAI） |
| [session-memory-spec.md](references/session-memory-spec.md) | 会话记忆规范（三层开关/Redis CAS/`memory-state` 接口/历史 `memory_updated` 标记） |
| [email-spec.md](references/email-spec.md) | 邮件发送规范（架构/触发来源/配置/规则） |
| [deletion-deps.md](references/deletion-deps.md) | 删除依赖保护规范（5 种策略/声明语法/前端弹窗/回收站） |
| [notification-spec.md](references/notification-spec.md) | 通知系统规范（渠道驱动/模板编码/队列/扩展） |
| [notification-preference-spec.md](references/notification-preference-spec.md) | 通知偏好治理（全局/个人分层继承/NotificationSettings/精确清除个人覆盖） |
| [preferences-spec.md](references/preferences-spec.md) | UI 偏好设置规范（三层模型/全局预览/WS 同步/flat->Vben 映射） |
| [plugin-spec.md](references/plugin-spec.md) | 插件系统开发规范（manifest/生命周期/Context/扩展点/迁移/安全） |
| [rbac-permission-spec.md](references/rbac-permission-spec.md) | RBAC 权限注册规范（parent_resource/i18n 翻译/插件权限同步/权限树结构） |
| [ai-routing.md](references/ai-routing.md) | 多模型路由规范（M264：Tier枚举/路由优先级/ComplexityClassifier/routing_config） |
| [multimodal-rag.md](references/multimodal-rag.md) | 多模态RAG规范（M263：VisionDescriber/ImageParser/PptxParser/KB配置） |
| [multimodal-model-usage.md](references/multimodal-model-usage.md) | 模型多模态使用规范（AIModel 能力字段/对话 Adapter/KB 可选模型/RAG 描述器选型/前端约定） |
| [upload-storage-spec.md](references/upload-storage-spec.md) | 上传与存储系统规范（附件系统/FilePicker/ImageUpload/smartUploadFile/分片上传） |
| [download-spec.md](references/download-spec.md) | 文件下载规范（requestClient.download + downloadBlob/插件 NovusPluginShared/responseReturn:raw/Content-Disposition） |
| [plugin-menu-registration.md](references/plugin-menu-registration.md) | 插件菜单注册全链路规范（plugin.yaml/后端注册/权限同步/前端路由/管理员配置） |
| [public-config-branding-captcha.md](references/public-config-branding-captcha.md) | 公开配置/品牌/验证码规范（域名识别/品牌注入/CaptchaProvider/registry） |
| [user-endpoint-spec.md](references/user-endpoint-spec.md) | 用户端开发规范（UserLayout/认证流程/RBAC/Token路由/响应式设计） |
| [browser-testing-spec.md](references/browser-testing-spec.md) | 浏览器测试规范（MCP 工具优先级/登录凭据/企业端进入方式/测试步骤） |
| [tenant-domain-isolation.md](references/tenant-domain-isolation.md) | 企业域名隔离规范（TenantMiddleware/前端检测/路由守卫隔离规则/菜单剪枝/安全清单） |
| [page-awareness-spec.md](references/page-awareness-spec.md) | 页面感知系统规范（三层架构/pageKey/formComponent模式/ref模式/contextExtras/标准操作/检查清单/visual_state/useModalDetector/DOM语义快照/fill_form读回验证/context_diff/list_summary/AgentLoop链式确认/page_data大小保护） |
| [trace-id-logging-spec.md](references/trace-id-logging-spec.md) | trace_id 请求追踪（中间件/ContextVar/日志注入/前端 header/Celery 传播/WebSocket/Loguru 禁令） |
| [monitoring-spec.md](references/monitoring-spec.md) | Prometheus 指标监控规范（指标定义/埋点/端点/配置/Docker/前端） |
| [ai-action-log-spec.md](references/ai-action-log-spec.md) | AI 操作审计日志（`write_ai_action_log`/状态枚举/租户隔离/管理端与企业端只读审计页） |
| [cli-spec.md](references/cli-spec.md) | NovusAI CLI 工具规范（子命令/参数/新增流程/弃用脚本） |
| [codegen-spec.md](references/codegen-spec.md) | CRUD 代码生成器规范（YAML 配置/类型映射/CLI 参考） |
| [codegen-builder-spec.md](references/codegen-builder-spec.md) | Codegen 可视化构建器规范（三栏 Builder/WYSIWYG/属性面板/store） |
| [token-force-logout-spec.md](references/token-force-logout-spec.md) | Token 吊销与强制下线（Redis key 格式/revoke_token/强制下线 API/Socket.IO force_logout/兼容性） |
| [data-permission-spec.md](references/data-permission-spec.md) | 数据权限过滤（DataScope 枚举/__data_permission__/自动填充/DataPermissionFilter/OrgNodeDialog） |
