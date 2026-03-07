---
name: novusai-saas
description: NovusAI SaaS 全栈开发技能。当需要开发前端页面（Vue 3 + Vben Admin）或后端接口（FastAPI + SQLAlchemy + PostgreSQL）时，提供分层架构、CRUD 流程、多租户、权限、国际化等项目专属规范。
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
   - 租户端（`/tenant/login`）：`adminsss` / `admin123456`

---

## 一、全局禁令

以下规则在任何情况下不可违反：

- **禁止硬编码字符串**：前端 `$t()` / `t()`，后端 `_()`
- **禁止 `console.log`**：使用 `console.warn` / `console.error`
- **禁止 `any` 类型**：使用 `unknown` 或具体类型
- **禁止魔法字符串**：后端用 `LabeledEnum`，前端用常量/枚举
- **禁止跨端导入**：admin 页面不导入 tenant/user 的 API/Store。后端跨端共享逻辑放 `app/api/shared/`（如 `_skill_helpers.py`）
- **禁止层级越权**：Controller 不写业务逻辑或直接 DB 查询，Service 不直接操作 DB，Repository 不写业务判断。统计/Dashboard 查询必须在 Service 层
- **禁止裸返回**：后端必须用 `success()` / `created()` / `paginated()` 等统一响应
- **禁止手写重复 Schema**：前端用 `searchInput()` / `inputField()` 等辅助函数
- **禁止敏感信息入代码**：密钥、密码、Token 通过环境变量
- **禁止在主系统中写入插件代码**：插件组件/逻辑/locale 只能在 `backend/plugins/{name}/` 内，前端通过 UMD 动态加载

---

## 二、平台基础设施

多租户隔离、认证注入、异常体系、日志系统、SSE 流式、应用启动、上传存储、配置系统、前端业务组件。

**核心要点**：
- 四层租户隔离：`TenantModel` → `TenantRepository` → `TenantService` → `TenantController`
- 三端 Token：`ActiveAdmin` / `ActiveTenantAdmin` / `ActiveTenantUser`
- 异常由 Service 抛出（`NotFoundException` / `BusinessException` 等），Controller 不捕获
- 日志分类器：`LogManager.get_logger("app"/"auth"/"storage"/"task"/"queue"/"db")`
- 上传必须通过 `AttachmentService`，前端用 `FilePicker` / `ImageUpload` / `smartUploadFile`

→ 完整规范：[references/platform-infrastructure.md](references/platform-infrastructure.md)

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
- `TenantController.get_service(db, tenant_id)` — 第二参数是 `int`
- `BaseController.get_service(db)` — 只需 `db`
- 分页用 `query.size` 不是 `query.page_size`
- 新 Model 必须注册到 `models/__init__.py` 和 `migrations/env.py`

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

// ✅ 租户端判断资源是否可编辑（必须同时检查 scope + tenant_id）
show: (row) => row.scope === 'all_tenants' && row.tenant_id !== null
```

**`useScopeFields` 关键选项：**
- `allowedScopes` — 限制可选 scope（如 `['admin_only', 'all_tenants']`）
- `scopeDisabled` — 编辑时锁定（`(values) => values._mode === 'edit'`）
- `showTenantId` — 仅当 `all_tenants` 语义为"指定租户"时传 `true`（如定时任务），普通资源不传

### 禁令

- **禁止手写 CRUD 数据管理**：禁止手动管理 `loading`/`list`/`page`/`total` + `fetchList` + `watch` 分页 + 手写删除确认 + 手写回收站。必须使用 `useCrudPage` 或 `useCrudList`
- 搜索/表单必须用辅助函数（`searchInput` / `inputField` 等），禁止手写 Schema
- **禁止手写 scope 选项数组**：必须使用 `useScopeFields` / `getScopeOptions()` / `ScopeSelect`
- **禁止仅用 `scope === 'all_tenants'` 做租户资源判断**：必须同时检查 `tenant_id !== null`
- 业务预设（planSelect 等）定义在 `data.ts`，不放 adapter
- `requestClient` 导入路径：`#/utils/request`
- 权限指令：`v-access:code="['resource:action']"`

→ 完整代码示例：[references/frontend-crud.md](references/frontend-crud.md)
→ 前端开发手册：[references/frontend-spec.md](references/frontend-spec.md)

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
- **仅注册 Executor 不算完成**，必须同时存在 `SkillPackage + builtin Skill + auto-bind`，让工具进入 LLM function calling tools schema
- `_PROTECTED_TOOL_NAMES` 白名单保护 `get_page_context`、`invoke_page_operation`、`list_page_operations` 不被工具优化器过滤
- 页面感知标准接入点：前端 `registerPageContext()` / `registerPageOperations()` / `route.meta.ai`，后端 `PageContext.normalize_variables()` / `PageOperationExecutor` / `PageSessionMixin`
- 操作安全：`readonly=true` 直接执行，`readonly=false` 前端弹出确认对话框，超时 30s

### Skill 作用域规则（摘要）

- `all_tenants + tenant_id=null`：平台全局包，全部租户可见，**不可编辑**
- `all_tenants + tenant_id=X`：租户 X 自有包，仅租户 X 可见且可编辑
- `admin_only`：仅管理端，租户不可见
- **Skill 无独立 `scope`**，权限完全继承自所属 SkillPackage

**关键规则**：前端判断可编辑时必须**同时检查 `scope === 'all_tenants' && tenant_id !== null`**，仅检查 `scope` 会误放行平台全局包。后端 `_before_update/_before_delete` 检查 `pkg.tenant_id != self.tenant_id`。

→ 完整代码示例（isTenantOwned + 后端保护）：[references/ai-module.md](references/ai-module.md) § 八

---

## 七、异步任务与定时任务

- 必须用 `@register_task` 装饰器，禁止 `@celery_app.task`
- Celery Worker 是同步进程，用 `sync_session_factory()` 获取 DB，`redis.from_url()` 获取 Redis
- 5 个队列：`default` / `high_priority` / `ai_gateway` / `scheduled` / `notification`
- 定时任务通过 `periodic_tasks` 表管理，禁止硬编码 `beat_schedule`

→ 完整规范：[references/async-tasks.md](references/async-tasks.md)

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

---

## 十一、WebSocket 实时通信

三端 namespace 隔离：`/admin` / `/tenant` / `/user`。后端用 `sio.emit()`，Celery 用 `sio_bridge.*_sync()`。

→ 完整指南：[websocket-guide.md](websocket-guide.md)

---

## 十二、时间存储与显示

- **后端**：统一 `utc_now()`（`app.core.base_model`），禁止 `datetime.now()` / `datetime.utcnow()`
- **序列化**：ISO 8601 + `+00:00` 后缀
- **前端**：`formatDate()` / `formatRelativeTime()` 自动转本地时间

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

→ 完整最佳实践：[database-migration-best-practices.md](database-migration-best-practices.md)

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
- [ ] 统一响应方法（`success` / `created` / `paginated` / `deleted`）
- [ ] 面向用户文本使用 `_()`
- [ ] 枚举使用 `LabeledEnum`
- [ ] Alembic 迁移已生成
- [ ] 新 Model 已注册到 `models/__init__.py` 和 `migrations/env.py`
- [ ] 敏感信息通过环境变量
- [ ] 时间使用 `utc_now()`
- [ ] 新 Service 有对应 `tests/services/test_{name}.py`（≥ 6 cases）
- [ ] 公开敏感端点有 `IPRateLimiter` 保护
- [ ] AI 功能通过 Agent→Skill 链路，禁止直接调用 AIGateway
- [ ] 新增 AIModel 后已更新 `__filterable__`（含能力字段 supports_vision 等）
- [ ] 迁移文件 `create_foreign_key` 使用显式名称（不传 `None`），否则 downgrade 找不到约束
- [ ] 循环引用类型使用 `from __future__ import annotations` + `TYPE_CHECKING`

### 前端

- [ ] 无 `any` 类型
- [ ] 无 `console.log()`
- [ ] 无中文硬编码（全部 `$t()`，包括 Tooltip/Popconfirm/Alert/Empty 等组件 props）
- [ ] 搜索/表单用辅助函数生成
- [ ] 业务预设在 `data.ts` 定义，不在 adapter
- [ ] 无跨端导入
- [ ] 含 scope 字段的表单使用 `useScopeFields()`，不手写选项数组
- [ ] 租户端资源操作按钮同时检查 `scope === 'all_tenants' && tenant_id !== null`
- [ ] i18n JSON key 无重复、路径正确
- [ ] 中英文翻译齐全（zh-CN 和 en-US 的 key 必须完全对齐）
- [ ] Props 用 `defineProps<T>()`

---

## 十六、RBAC 权限注册

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

---

## 十七、用户端（User Endpoint）开发

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
- 用户端 RBAC 使用 `PermissionScope.USER` scope，菜单定义在 `user_menus.py`
- 域名→租户→品牌加载：Router Guard → `loadTenantConfig()` → 应用 Logo/主色调/站点名
- 公开端点用 `@public`，登录后端点用 `@auth_only`
- 注册/忘记密码端点需 `IPRateLimiter` 保护
- Token 选择：前端 `/api/user/*` URL 自动选择 user Token

→ 完整规范：[references/user-endpoint-spec.md](references/user-endpoint-spec.md)

---

## 十八、插件开发

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
python scripts/plugin_cli.py create my-plugin --template=minimal      # 纯后端
python scripts/plugin_cli.py create my-plugin --template=skill        # + Skill/Executor
python scripts/plugin_cli.py create my-plugin --template=full-module  # + 前端 + API + 迁移
python scripts/plugin_cli.py validate plugins/my-plugin               # 校验
python scripts/plugin_cli.py pack plugins/my-plugin                   # 打包 zip
```

→ 完整规范 + 代码示例：[references/plugin-spec.md](references/plugin-spec.md)

---

## 参考文件索引

| 文件 | 内容 |
|------|------|
| [platform-infrastructure.md](references/platform-infrastructure.md) | 多租户/认证/异常/日志/SSE/启动/存储/配置/组件 |
| [backend-crud.md](references/backend-crud.md) | 后端 CRUD 7 步完整代码 + 响应/异常/权限/枚举/日志 |
| [frontend-crud.md](references/frontend-crud.md) | 前端 CRUD 完整代码（useCrudPage 表格 + useCrudList 自定义布局 + useCrudDrawer 表单） |
| [frontend-spec.md](references/frontend-spec.md) | 前端开发手册完整版（含拖拽排序、列表 UI 设计、CSS 动画等） |
| [detail-page-patterns.md](references/detail-page-patterns.md) | 资源详情页 UI 模式（Hero Header / 带图标 Tabs / 信息卡片 / 表单区块 / 功能开关卡片 / 绑定行 / 只读横幅） |
| [backend-spec.md](references/backend-spec.md) | 后端开发指南完整版（含存储、日志、枚举、Service 钩子等） |
| [async-tasks.md](references/async-tasks.md) | 异步任务与定时任务开发规范（Celery/Redis/队列/定时任务） |
| [devgenius-workflow.md](references/devgenius-workflow.md) | DevGenius MCP 工作流详解（工具速查、流程图、文档管理） |
| [ai-module.md](references/ai-module.md) | AI 模块开发规范（引擎/网关/工具/RAG/数据智能/事件/安全） |
| [email-spec.md](references/email-spec.md) | 邮件发送规范（架构/触发来源/配置/规则） |
| [deletion-deps.md](references/deletion-deps.md) | 删除依赖保护规范（5 种策略/声明语法/前端弹窗/回收站） |
| [notification-spec.md](references/notification-spec.md) | 通知系统规范（渠道驱动/模板编码/队列/扩展） |
| [plugin-spec.md](references/plugin-spec.md) | 插件系统开发规范（manifest/生命周期/Context/扩展点/迁移/安全） |
| [rbac-permission-spec.md](references/rbac-permission-spec.md) | RBAC 权限注册规范（parent_resource/i18n 翻译/插件权限同步/权限树结构） |
| [ai-routing.md](references/ai-routing.md) | 多模型路由规范（M264：Tier枚举/路由优先级/ComplexityClassifier/routing_config） |
| [multimodal-rag.md](references/multimodal-rag.md) | 多模态RAG规范（M263：VisionDescriber/ImageParser/PptxParser/KB配置） |
| [upload-storage-spec.md](references/upload-storage-spec.md) | 上传与存储系统规范（附件系统/FilePicker/ImageUpload/smartUploadFile/分片上传） |
| [plugin-menu-registration.md](references/plugin-menu-registration.md) | 插件菜单注册全链路规范（plugin.yaml/后端注册/权限同步/前端路由/管理员配置） |
| [user-endpoint-spec.md](references/user-endpoint-spec.md) | 用户端开发规范（UserLayout/认证流程/RBAC/Token路由/响应式设计） |
| [browser-testing-spec.md](references/browser-testing-spec.md) | 浏览器测试规范（MCP 工具优先级/登录凭据/租户端进入方式/测试步骤） |
