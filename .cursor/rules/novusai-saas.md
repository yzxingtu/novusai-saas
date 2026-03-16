# NovusAI SaaS 开发规则

## 项目概述

多企业 SaaS 平台。前端 Vue 3 + Vben Admin 5.x + Ant Design Vue；后端 FastAPI + SQLAlchemy 2.x + PostgreSQL。

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
- 禁止手写重复 Schema 配置，前端必须用 `searchInput` / `inputField` 等辅助函数
- 禁止敏感信息（密钥、密码）写入代码，通过环境变量配置

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

### 企业端资源操作按鈕显示规则

**禁止仅检查 `scope === 'all_tenants'`**，必须同时检查 `tenant_id !== null`：

```typescript
// ✅ 正确
const canEdit = row.scope === 'all_tenants' && row.tenant_id !== null;
// ❌ 错误：平台全局包（scope=all_tenants, tenant_id=null）会被误判为可编辑
const canEdit = row.scope === 'all_tenants';
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
- `ActiveUser` — 活跃用户（用户端接口）

### Service 基类选择

| 场景 | 继承 |
|------|------|
| 企业级资源 | `TenantService` |
| 平台级资源（无企业隔离） | `GlobalService` |
| 跨企业共享 | `BaseService` |

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

**Scope 保护模式**（企业端必须在 `_before_update` / `_before_delete` 中实现）：

```python
# 必须同时检查 tenant_id（不能只检查 scope）
if obj.tenant_id != self.tenant_id:
    raise BusinessException(message=_("平台资源不可修改"))
# 错误：仅检查 scope 会误放行平台全局包（scope='all_tenants', tenant_id=null）
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
from app.core.logging import LogManager
logger = LogManager.get_logger("auth")  # app/error/db/auth/storage/task/queue/captcha/impersonate
```

Loguru 使用 `{}` 风格，禁止 `%s`/`%d`：`logger.info("id={}", x)` 而不是 `logger.info("id=%s", x)`。

### 安全配置

- `DEBUG` 默认值必须为 `False`
- CORS 禁止 `allow_origins=["*"]` 且 `allow_credentials=True`
- 登录、注册、忘记密码等公开认证端点必须使用 `check_login_rate_limit` 进行 IP 限流
- 非 DEBUG 环境启动时，若 `SECRET_KEY` 仍为默认值，必须输出 SECURITY WARNING 日志
- 依赖以 `pyproject.toml` 为单一事实来源，与 `requirements.txt` 同步
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

> 完整规范见 `.windsurf/rules/ai-architecture.md`（本节仅保留最关键禁令，避免与详细规则文件重复维护）

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

**多模型路由（M264）：** 通过 `routing_config` 在 Agent 上启用智能路由 → 详见 `.windsurf/workflows/references/ai-routing.md`

**多模态 RAG（M263）：** KnowledgeBase 支持 `vision_model_id` + `extract_images` → 详见 `.windsurf/workflows/references/multimodal-rag.md`

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
