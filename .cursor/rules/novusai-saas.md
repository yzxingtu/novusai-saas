# NovusAI SaaS 开发规则

## 项目概述

多企业 SaaS 平台。前端 Vue 3 + Vben Admin 5.x + Ant Design Vue；后端 FastAPI + SQLAlchemy 2.x + PostgreSQL。

## 规则入口

`.cursor/rules/novusai-saas.md` 是总览规则，以下文件是必须配套阅读的专题规则：

- `ai-architecture.md` — AI / Agent / Skill / 页面操作
- `attachments-and-storage.md` — 上传、下载、附件可见性、存储驱动
- `async-notification-websocket.md` — Celery、通知、邮件、Socket.IO
- `plugin-system.md` — 插件 manifest、生命周期、权限同步、菜单注册
- `rbac-and-data-permission.md` — `parent_resource`、`messages.json`、数据权限
- `user-endpoint-and-domain-isolation.md` — `/api/user/*`、UserLayout、域名隔离
- `testing-validation.md` — 后端单元测试、浏览器验证
- `alembic-migration-authoring.md` — Alembic 迁移写法规范（空库 `upgrade heads` 必过）
- `trace-and-monitoring.md` — `X-Trace-ID`、LogManager、Prometheus/Grafana
- `tenant-architecture.md` — 企业端能力边界
- `menu-i18n.md` — 动态菜单多语言职责边界

## 全局禁令

- 禁止 `except Exception: pass/continue`（至少 `logger.debug` 记录）
- 禁止未经 `DOMPurify.sanitize()` 的 `v-html`
- 禁止迁移脚本中 `text(f"...")` 拼接 SQL，必须用 `text(...).bindparams()`
- 禁止 Loguru 日志使用 `%s`/`%d` 风格，必须用 `{}` 风格
- 禁止硬编码中文字符串，前端用 `$t()`，后端用 `_()`
- 禁止 `console.log`，使用 `console.warn` / `console.error`
- 禁止 `any` 类型，使用 `unknown` 或具体类型
- 新增代码注释或备注时，**必须中英双语同时存在**，禁止只写中文注释，禁止只写英文注释；若无必要，优先不加注释
- 禁止魔法字符串，使用枚举（后端 `LabeledEnum`）
- 禁止跨端导入（admin 页面不导入 tenant API/store）。后端跨端共享逻辑放 `app/api/shared/`（如 `_skill_helpers.py`）
- 禁止 Controller 写业务逻辑或直接 DB 查询，禁止 Service 直接操作 DB。统计/Dashboard 查询必须在 Service 层
- 禁止裸返回数据，后端必须用 `success()` / `created()` / `paginated()` 等统一响应
- **指标埋点**：新增 AI/Celery/WebSocket 等关键路径时，需在 `app/core/metrics.py` 对应指标处埋入 `*.labels(...).inc()` / `.observe()` / `.set()`，并用 `try/except` 包裹，避免影响主流程
- 禁止手写重复 Schema 配置，前端必须用 `searchInput` / `inputField` 等辅助函数

### 指标监控（Prometheus 埋点）

新增 AI、Celery、WebSocket 等关键路径时，**必须**在 `app/core/metrics.py` 对应指标处埋点：

- **AI 调用**：`ai_gateway_calls_total`、`ai_gateway_tokens_total`、`ai_gateway_latency_seconds`（AIGateway / ai/gateway.py）
- **Celery 任务**：`celery_tasks_total`（成功/失败，tasks/base.py）
- **WebSocket**：`ws_connections_total`（admin/tenant/user namespace 的 connect/disconnect）
- 埋点需用 `try/except` 包裹，禁止因指标异常影响主流程

- 禁止敏感信息（密钥、密码）写入代码，通过环境变量配置

---

## 前端规则

### 架构

- 多端分离：admin (`/admin/*`)、tenant (`/tenant/*`)、user (`/*`)
- 依赖方向：`views → composables → store/api → utils`，禁止反向依赖
- adapter 层不依赖具体业务代码
- 请求客户端：`import { requestClient } from '#/utils/request'`

### CRUD 开发

- 表格列表页用 `useCrudPage`，自定义布局（卡片/面板/Master-Detail）用 `useCrudList`
- 表单用 `useCrudDrawer`（标准模式）或 ref 模式（`openNew()`/`openEdit()`）
- 搜索表单用 `searchInput()` / `statusSelect()` 等辅助函数生成
- 编辑表单用 `inputField()` / `dateField()` / `textareaField()` 等
- 业务预设（如 planSelect）定义在业务模块 `data.ts`，不放 adapter
- 字段映射用 `fields` 选项自动处理 camelCase ↔ snake_case
- **禁止手写 CRUD 数据管理**（手动 loading/list/page/total + fetchList + watch 分页 + 手写删除确认 + 手写回收站）
- 软删除资源的列表页开启 `recycleBin: true`，`useCrudList`/`useCrudPage` 自动处理回收站切换

### 统一资源作用域（ResourceScopeEnum）与归属

- **五类资源作用域**：`global_shared` | `admin_only` | `all_tenants` | `admin_and_selected_tenants` | `selected_tenants`（见后端 `ResourceScopeEnum`）。
- **可编辑/企业自有**只看 **`owner_tenant_id`**（列表 API 常序列化为 `tenant_id`，语义为归属企业）。
- **禁止**用 `scope === 'all_tenants' && tenant_id !== null` 判断企业自有（旧双重语义已废除）。
- **权限/菜单端别**用 `PermissionScope`（admin / tenant / user / both），与资源作用域分离。

```typescript
// ✅ 企业端：仅当资源归属当前企业时可编辑（示例）
const canEdit = row.tenant_id != null && row.tenant_id === currentTenantId;
```

### 权限

- 指令写法：`v-access:code="['resource:action']"`
- 操作列自动鉴权：`options: ['edit', 'delete']`
- Hook：`useAccess()` 获取 `hasAccessByCodes` / `isSuperAdmin`

### 搜索（JSON:API）

- fieldName 格式：`filter[field][operator]`
- 操作符：`ilike`（模糊）、`eq`（精确）、`gte/lte`（范围）、`in`（多值）

### 国际化

- 翻译文件 key 前缀 = 文件路径（`zh-CN/admin/system.json` → `admin.system.*`）
- 共享业务组件用 `shared/` 命名空间（如 `shared/memberPanel.json` → `shared.memberPanel.*`）
- JSON 内不重复嵌套路径名
- 避免同一 JSON 中重复 key
- zh-CN 和 en-US 的 key 必须完全对齐，新增 key 必须同时添加两种语言
- **菜单多语言禁止在前端维护**：侧边栏菜单（admin/tenant/user 动态菜单）的标题由后端权限系统翻译，通过 `backend/app/locales/{en|zh_CN}/menu.json` 维护，API 返回时已带翻译后的 `name`。禁止在 `frontend/.../locales/.../menu.json` 中重复维护菜单翻译；用户端静态路由（如 ai-chat、settings）的页面标题用 `user.aiChat.title`、`user.settings.title` 等，不放 menu 命名空间

### 图标

- 优先 Lucide：`lucide:user`
- 组件：统一用 `IconifyIcon`
- Tailwind 类：`icon-[lucide--user]`（`--` 代替 `:`）

### Vue 应用启动

- 必须在 `bootstrap.ts` 配置 `app.config.errorHandler`，统一捕获组件渲染异常，避免白屏

### AI 页面操作

- 页面操作 handler 返回的 `message` 必须用 `$t('shared.pageOperation.msg.xxx')`，禁止硬编码中英文
- **pageop_ 优先**：有 `pageop_*` 专用工具时优先使用，仅不可用时回退到 `invoke_page_operation`
- **JSON 参数容错**：`invoke_page_operation` 参数 JSON 解析失败连续 3 次后中止 tool loop，避免无限重试

### 命名

- 目录/TS 文件：kebab-case
- Vue 组件：PascalCase
- API 函数：`{action}{Resource}Api`
- Store：`use{Name}Store`（通用）/ `use{Endpoint}AuthStore`（仅限认证 Store）
- Composable：`use{Name}`

### 样式

- 主色调：Vben 设计 Token（`text-foreground` / `bg-primary/10` / `text-muted-foreground`）
- 状态色：`bg-success/10` / `bg-destructive/10` / `bg-warning/10`
- 动画：`transform` + `opacity` 优先，禁止对 width/height 做动画

## 后端规则

### 架构分层

```
请求 → Middleware → Controller → Service → Repository → Model/DB
```

- Controller：路由、参数校验、调 Service、返回响应
- Service：业务逻辑、钩子、事务编排
- Repository：数据访问、查询构建
- Model：表结构定义

### 多企业

- 企业模型继承 `TenantModel`（自动含 `tenant_id`）
- 企业仓库继承 `TenantRepository`（自动注入 `tenant_id` 过滤）
- 企业服务继承 `TenantService`
- 企业控制器继承 `TenantController`
- 平台管理用 `GlobalController`
- `TenantController.get_service(db, tenant_id)` — 第二参数是 int
- `BaseController.get_service(db)` — 只需 db

### 统一响应

```python
success(data=obj)                         # 200 GET/POST 成功
created(data=obj)                         # HTTP 201 创建成功
updated(data=obj)                         # HTTP 200 更新成功（PUT）
paginated(items, total, page, page_size)  # 分页列表
deleted()                                 # 删除成功
error(message, code, status_code)         # 自定义错误
```

### 查询（JSON:API）

- 过滤：`filter[field][operator]=value`
- 排序：`sort=-created_at,name`
- 分页：`page[number]=1&page[size]=20`
- 模型声明 `__filterable__` / `__sortable__` / `__selectable__` / `__delete_deps__`（被 FK 引用的父 Model 必须声明）
- 分页参数用 `query.size`，不是 `query.page_size`
- 新 Model 必须注册到 `models/__init__.py` 和 `migrations/env.py`

### 权限（RBAC）

- 类装饰器：`@permission_resource("resource_name")`
- 方法装饰器：`@action_read` / `@action_create` / `@action_update` / `@action_delete`
- 公开接口：`@public`
- 仅登录：`@auth_only`
- **导入顺序影响权限注册**：`admin/__init__.py` 中父资源 Controller 必须先于子资源导入，否则权限树 parent_id 可能为 null

### 异常

| 异常 | 状态码 | 错误码 |
|------|--------|--------|
| `ValidationException` | 422 | 4001 |
| `AuthenticationException` | 401 | 4010 |
| `AuthorizationException` | 403 | 4030 |
| `NotFoundException` | 404 | 4040 |
| `BusinessException` | 422 | 4220 |

### 依赖注入

- `DbSession` — AsyncSession
- `ActiveAdmin` — 活跃平台管理员
- `ActiveTenantAdmin` — 活跃企业管理员
- `QueryParams` — JSON:API 查询参数
- `SuperAdmin` — 超级管理员
- `ActiveTenantUser` — 活跃用户（用户端接口）

### Service 基类选择

| 场景 | 继承 |
|------|------|
| 企业级资源 | `TenantService` |
| 平台级资源（无企业隔离） | `GlobalService` |
| 跨企业共享 | `BaseService` |

### Codegen 代码生成器

- **codegen 管理页面**：仅 DEBUG 模式可用（通过路由或权限控制）
- **UI 真实形态**：`/admin/system/codegen/new|:id/edit` 对应 `builder.vue` 三栏可视化构建器，不是旧版 6 步 wizard
- **生成代码命名**：resource 用 snake_case（category、notice）；module 用单数（system、tenant、business）
- **生成后必须审查**：生成的代码需人工 review，尤其权限、数据隔离、软删除等

### Service 钩子方法（写操作保护必用）

```python
async def _before_create(self, data: dict) -> dict:
    """POST 前验证，返回修改后的 data"""
async def _before_update(self, obj, data: dict) -> dict:
    """PUT 前检查权限/业务处理"""
async def _before_delete(self, obj) -> None:
    """DELETE 前检查（如有依赖则抛 BusinessException）"""
async def _before_delete_check(self, obj) -> None:
    """DELETE 前提前检查（不修改数据）"""
```

**归属保护模式**（企业端必须在 `_before_update` / `_before_delete` 中实现）：

```python
# 以归属企业为准：平台资源 owner_tenant_id 为 NULL，或归属非本企业则禁止写
_owner = getattr(obj, "owner_tenant_id", None)
if _owner is None or _owner != self.tenant_id:
    raise BusinessException(message=_("平台资源不可修改"))
# 若模型仍暴露 tenant_id 列名但语义为归属，可与 owner_tenant_id 等价判断
```

### 中间件顺序

后注册先执行。实际注册顺序：CORS → I18n → Permission → AuditLog → AccessControl → Tenant

请求处理：`Tenant → AccessControl → AuditLog → Permission → I18n → Route`

### 枚举

继承 `LabeledStrEnum`，支持 i18n。禁止 `status = "draft"`，用 `status = NoticeStatus.DRAFT`。
比较也必须用枚举：禁止 `scope == "all_tenants"`，用 `scope == ResourceScopeEnum.ALL_TENANTS.value`。

### 时间存储与显示

**后端**：
- 必须用 `utc_now()`（`app.core.base_model`），禁止 `datetime.now()` / `datetime.utcnow()`
- 序列化输出为 ISO 8601 + `+00:00` 后缀（由 Pydantic 自动处理）
- 禁止 `str(datetime)` 手动序列化，应由 Pydantic schema 统一处理
- 手动构造 dict 时必须用 `dt.isoformat()`；若 datetime 无时区信息（naive），先 `dt.replace(tzinfo=timezone.utc)` 再 `.isoformat()`
- `app.core.response._serialize()` 已统一处理 `paginated()` / `success()` 中的 naive datetime

**前端**：
- 禁止使用原生 `toLocaleString` / `toLocaleDateString` / `toLocaleTimeString`
- 必须使用 `#/utils/common` 中的工具函数：
  - `formatDate(date, options?)` — 默认 `YYYY-MM-DD HH:mm:ss`
  - `formatDateOnly(date)` — `YYYY-MM-DD`
  - `formatTimeOnly(date)` — `HH:mm:ss`
  - `formatRelativeTime(date)` — 相对时间（刚刚、X 分钟前...）
- 列表页时间列标准模式：`formatRelativeTime` 为主显示 + `formatDate` 为 Tooltip
- 详情页/抽屉：使用 `formatDate` 显示完整时间
- 仅日期场景（如过期日期）：`formatDateOnly`
- 仅时间场景（如消息时间戳）：`formatTimeOnly`

### 日志

```python
from app.core.logging import get_logger
logger = get_logger(__name__)
```

分类日志或按模块拆文件场景可继续使用 `LogManager.get_logger("auth")`；Service 优先使用 `LoggerMixin` / `self.logger`。禁止直接 `from loguru import logger`。

Loguru 使用 `{}` 风格，禁止 `%s`/`%d`：`logger.info("id={}", x)` 而不是 `logger.info("id=%s", x)`。

### CLI 管理

- 统一使用 `novusai` CLI 入口（`pip install -e .` 后可用）
- 禁止新增独立脚本；新命令必须在 `app/cli.py` 中注册子命令
- 日常操作：`novusai run`、`novusai celery dev`、`novusai db autogenerate -m "..."`、`novusai check`

### 安全配置

- `DEBUG` 默认值必须为 `False`
- CORS 禁止 `allow_origins=["*"]` 且 `allow_credentials=True`
- 登录、注册、忘记密码等公开认证端点必须使用 `check_login_rate_limit` 进行 IP 限流
- 非 DEBUG 环境启动时，若 `SECRET_KEY` 仍为默认值，必须输出 SECURITY WARNING 日志
- 依赖以 `pyproject.toml` + `uv.lock` 为单一事实来源；安装推荐 `uv sync --extra dev`
- 列表/导出 API 必须有合理 `.limit()` 上限
- 文件句柄必须用 `with` 或确保关闭

### 迁移

```bash
# 只需生成迁移文件，系统启动时自动执行 upgrade
alembic revision --autogenerate -m "add xxx table"
# ⚠️ 无需手动运行 alembic upgrade head，uvicorn reload 会自动触发
```

- 系统启动（含 uvicorn reload）时 `main.py lifespan` → `init_database()` → `alembic upgrade heads` 自动执行
- 新建迁移文件后，保存任意 `app/` 内文件触发 reload 即可让迁移生效
- **FK 约束命名**：`create_foreign_key` 必须传显式名称（禁止传 `None`），否则 `downgrade` 无法找到约束

## 前后端协作

- 搜索语法统一 JSON:API：前端 `filter[field][ilike]` ↔ 后端 `QueryParams` 自动解析
- 排序统一：前端 `sort=-created_at` ↔ 后端 `__sortable__` 白名单
- 分页统一：前端 `page[number]/page[size]` ↔ 后端 `paginated()`
- Token 按 URL 前缀自动选择：`/admin/*` → admin Token，`/tenant/*` → tenant Token
- 错误码对照：前端 4010 → 跳登录，4011 → token 过期刷新，4030 → 权限不足提示

## AI 架构规则（强制）

> 完整规范见 [ai-architecture.md](ai-architecture.md)。

**核心禁令（任何情况不可违反）：**
- ❌ 禁止在 Controller/Service 层直接调用 `AIGateway.chat()` / `embedding()`
- ❌ 禁止绕过 Agent→Skill 链路新增 AI 端点
- ❌ 禁止使用已废弃的 `ToolRegistry` / `tool_bindings` JSON 字段

**合法 AI 调用入口：**
- ✅ `SystemAgentService`（Controller 层唯一 AI 入口）：`Controller → SystemAgentService → AIGateway`
- ✅ Agent engine 内部（`conversation.py` / `base.py`）— 属于 Agent 实现层
- ✅ RAG 管道内部（`rag/embedding.py` 等）— 属于 Skill 内部实现
- ✅ `AIGateway.test_model` — 仅模型连通性测试

**技能类型（7 种）：** `toolkit` / `knowledge_base` / `data_intelligence` / `builtin` / `http` / `email` / `code_execution`

**多模型路由（M264）：** 通过 `routing_config` 在 Agent 上启用智能路由 → 详见 [../skills/novusai-saas/references/ai-routing.md](../skills/novusai-saas/references/ai-routing.md)

**多模态 RAG（M263）：** KnowledgeBase 支持 `vision_model_id` + `extract_images` → 详见 [../skills/novusai-saas/references/multimodal-rag.md](../skills/novusai-saas/references/multimodal-rag.md)

**会话记忆：** 仅 `ai_chat_page` / `admin_chat` 这类真实对话场景允许启用；必须复用 `AgentChatService` + `SessionMemoryService` + `ConversationService`，禁止在 Controller 或前端手工管理 `memory-state`

## 上传与下载

- 所有上传必须经过 `AttachmentService`，前端统一走 `smartUploadFile` / `FilePicker` / `ImageUpload` / `ConfigImagePicker`
- 业务页面禁止 `requestClient.upload('/xxx/upload')` 直连端点，禁止自建上传组件；仅富文本编辑器等基础设施封装可在内部直接调用标准附件上传端点
- 文件下载统一用 `requestClient.download` + `downloadBlob`；插件必须用 `NovusPluginShared.downloadBlob`
- 展示类图片走 `/api/public/attachments/{id}/image`，禁止在前端拼接 `base_url + path`
- `public` / `private` 可见性必须按用途区分，不能把展示图片错误标成 `private`

→ 详见 [attachments-and-storage.md](attachments-and-storage.md)

## 异步任务、通知与实时通信

- 业务任务模块必须用 `@register_task`，禁止直接写 `@celery_app.task` / `@shared_task`；插件注册器这类框架桥接层可在内部动态注册 Celery task
- Worker 为同步进程，DB 访问必须用 `self.get_db_session()`，不要在任务函数里写 `async def`
- 定时任务优先通过 `periodic_tasks` 表管理，系统级兜底才使用静态 `beat_schedule`
- 业务通知统一走 `NotificationService.send()` / `notify()`，业务代码不能直接发通知邮件
- 通知偏好统一走 `NotificationPreferenceService` / `NotificationSettings.vue`，全局修改后需精确清除个人覆盖
- 所有业务邮件默认异步发送；通知邮件走 `notification` 队列，普通邮件走 `default`
- WebSocket namespace 固定为 `/admin` / `/tenant` / `/user`；Celery 侧推送必须用 `sio_bridge.*_sync()`

→ 详见 [async-notification-websocket.md](async-notification-websocket.md)

## RBAC 与数据权限

- 每个 Controller 的 `@permission_resource` 都必须声明 `parent_resource`
- `backend/app/locales/{zh_CN,en}/messages.json` 的现有 `"action"` 节点必须补齐翻译，禁止新建第二个顶层 `"action"`
- 插件权限同步必须调用 `sync_plugin_permissions(plugin.name)`，不要在插件事务里跑全量同步
- 需要行级过滤的模型通过 `__data_permission__ = True` 声明式启用，禁止在 Service 层手工拼部门过滤
- 新增页面时必须同时保证后端菜单注册和前端页面落点一致，避免 `[MenuCheck]` / `[DynamicMenu] [CRITICAL]`

→ 详见 [rbac-and-data-permission.md](rbac-and-data-permission.md)

## 用户端与域名隔离

- 用户端 API 前缀固定为 `/api/user/*`，依赖注入使用 `ActiveTenantUser`
- 用户端布局固定为 `UserLayout`，无侧边栏，移动端优先
- 当前前端静态主路由为 `/home`、`/ai-chat`、`/settings/*`，认证页在共享 `/auth/*`
- 企业域名与平台域名由 Host header 和 `detectDomainType()` 协同判定，禁止回退到 `tenant_code` 查询参数主导
- 品牌与验证码统一走公开配置：`/api/public/platform|tenant/config` + `usePublicConfigStore` + `CaptchaProvider`
- 平台域名禁止访问 tenant / user 端，企业域名禁止访问 admin 端
- `impersonate` 仅传 token，不要拼接无效 `tenant_code`

→ 详见 [user-endpoint-and-domain-isolation.md](user-endpoint-and-domain-isolation.md)

## 插件系统

- 插件必须零侵入，代码只能位于 `backend/plugins/{name}/`
- `plugin.yaml` 的 capabilities / extensions / permissions 必须如实声明，不能偷跑主系统能力
- 插件 Skill 类型只能使用系统既有 7 种，禁止自定义 SkillType
- 插件表名必须 `px_{name}_*`，迁移 `branch_labels` 必须是 `plugin_{name_underscored}`
- 插件前端通过 UMD 动态加载，权限和菜单注册必须与 manifest 声明保持一致

→ 详见 [plugin-system.md](plugin-system.md)

## 测试、追踪与监控

- 新增或重构 Service 必须补 `tests/services/test_{name}.py`，不依赖真实 DB / Redis / 网络
- 浏览器验证优先 `chrome-devtools` MCP，文件上传再用 `playwright`，一次流程不要混用
- 所有请求链路自动携带 `X-Trace-ID`，日志统一通过 `app.core.logging` 暴露的封装（`get_logger` / `LoggerMixin` / `LogManager` 分类日志）
- AI 工具与页面操作审计统一写入 `AIActionLog`，状态用 `pending_confirm`，耗时字段用 `duration_ms`
- 新增 AI / Celery / WebSocket 关键路径时，必须同步埋入 `app/core/metrics.py` 指标
- 监控页面与接口仅允许 Admin 端暴露

→ 详见 [testing-validation.md](testing-validation.md)
→ 详见 [trace-and-monitoring.md](trace-and-monitoring.md)

## DevGenius 治理规则

本项目使用 DevGenius（MCP 集成名称：`devgenius-quanzhan`）进行项目管理，以下规则每次对话均生效：

- **任务驱动**：所有开发必须基于认领的任务，禁止无任务编码
- **文档先行**：新功能或重大变更前，必须先通过 MCP 查询相关文档；无文档则引导创建
- **状态同步**：开发完成后必须更新任务状态，禁止不实施就更新
- **先查后写**：写入文档前必须先搜索是否已存在，禁止重复创建相同主题
- **规范遵守**：必须先查询并阅读规范文档再开发，禁止跳过
- **MCP 优先**：所有项目管理操作（任务、文档、里程碑）通过 MCP 工具完成，确保可追溯
- 禁止不认领任务直接开发
- 禁止硬编码敏感信息
- 禁止忽略文档要求

## 开发环境自动重载

**无需手动重启前后端，修改代码后自动生效：**

### 后端（FastAPI + uvicorn）
- 启动命令：`uvicorn app.main:app --reload --reload-dir app`
- 监听目录：`backend/app/`，任意 `.py` 文件保存后**自动热重载**（约 1-2 秒）
- **不监听**：`migrations/`、`plugins/`、`.venv/` — 这些目录改动不会触发 reload
- **数据库迁移自动执行**：`main.py` lifespan 启动时调用 `init_database()` → `run_migrations()` → `alembic upgrade heads`，每次 uvicorn reload 均自动执行，**无需手动运行迁移命令**
- ⚠️ 新建迁移文件在 `migrations/versions/` 后，该目录不被监听，需保存任意 `app/` 内文件触发 reload 才能让新迁移生效

### 前端（Vite + Vue 3）
- 启动命令：`pnpm dev`（在 `frontend/` 目录下）
- 任意 `.vue`、`.ts`、`.json`（含 i18n 翻译文件）保存后 **Vite HMR 即时热更新**，浏览器无需刷新
- **路由/store 等全局状态变更**有时需要手动刷新浏览器（Ctrl+R），但不需要重启 dev server

### AI 助手行为规范
- **禁止**在代码变更后建议"重启后端/前端"，正确说法是"保存后自动生效"
- 仅以下情况**确实需要重启**：
  1. 修改了 `.env` 环境变量
  2. 安装了新的 Python 包（`pip install`）
  3. 安装了新的前端依赖（`pnpm install`）
  4. 修改了 `backend/app/main.py` 中的中间件注册顺序（极少情况）
