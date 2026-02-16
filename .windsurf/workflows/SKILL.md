---
name: novusai-fullstack
description: >
  NovusAI SaaS 全栈开发技能。当需要在本项目中开发前端页面（Vue 3 + Vben Admin + Ant Design Vue）
  或后端接口（FastAPI + SQLAlchemy + PostgreSQL）时，此技能提供完整的分层架构规范、CRUD 开发流程、
  多租户体系、权限控制、国际化、JSON:API 查询等项目专属知识。涵盖前后端协作约定、命名规范、
  代码检查清单。This skill should be used when developing any feature, fixing bugs, or reviewing
  code in the NovusAI SaaS project.
---

# NovusAI SaaS 全栈开发技能

## 适用场景

- 新增 CRUD 模块（前端页面 + 后端接口）
- 新增/修改 API 接口
- 前端页面开发（列表、表单、详情）
- 权限配置与鉴权
- 数据库模型设计与迁移
- Bug 修复与代码审查

## 项目技术栈

| 端 | 技术 |
|---|------|
| 前端 | Vue 3.5 + TypeScript + Vben Admin 5.x + Ant Design Vue + Vite 6.x + Tailwind CSS |
| 后端 | Python 3.11+ + FastAPI + SQLAlchemy 2.x (Async) + PostgreSQL + Alembic |
| 认证 | JWT (access / refresh / impersonate) |
| 查询协议 | JSON:API（filter/sort/page） |

## 开发前准备

1. 确认任务归属的端：admin / tenant / user
2. 查阅 `references/platform-infrastructure.md` 了解多租户隔离、认证注入、异常抛出方式
3. 查阅 `references/backend-spec.md` 或 `references/frontend-spec.md` 获取完整开发规范
4. 确认相关模块是否已有类似实现，复用已有组件和模式

---

## 一、全局禁令

以下规则在任何情况下不可违反：

- **禁止硬编码字符串**：前端 `$t()` / `t()`，后端 `_()`
- **禁止 `console.log`**：使用 `console.warn` / `console.error`
- **禁止 `any` 类型**：使用 `unknown` 或具体类型
- **禁止魔法字符串**：后端用 `LabeledEnum`，前端用常量/枚举
- **禁止跨端导入**：admin 页面不导入 tenant/user 的 API/Store
- **禁止层级越权**：Controller 不写业务逻辑，Service 不直接操作 DB，Repository 不写业务判断
- **禁止裸返回**：后端必须用 `success()` / `created()` / `paginated()` 等统一响应
- **禁止手写重复 Schema**：前端用 `searchInput()` / `inputField()` 等辅助函数
- **禁止敏感信息入代码**：密钥、密码、Token 通过环境变量

---

## 二、多租户体系

### 租户识别

TenantMiddleware（`middleware/tenant.py`）从 Host 头自动解析租户：子域名匹配 `{code}.{TENANT_DOMAIN_SUFFIX}`，否则按自定义域名查 `TenantDomain`。结果存入 `request.state.tenant_ctx`（类型 `TenantContext`）。

### 四层自动隔离

| 层 | 基类 | 隔离方式 |
|----|----|----------|
| Model | `TenantModel` | 自动添加 `tenant_id` 字段 + 索引 |
| Repository | `TenantRepository` | 所有查询自动注入 `WHERE tenant_id = ?` |
| Service | `TenantService` | 构造函数接收 `tenant_id`，传递给 Repository |
| Controller | `TenantController` | 从 JWT / request.state 中提取 `tenant_id` |

**关键规则**：
- 租户数据**必须**用 `TenantModel` 全套，**禁止**手动拼接 `tenant_id`
- 平台全局数据用 `BaseModel` / `BaseRepository` / `BaseService` / `GlobalController`

### 获取当前租户

```python
# TenantController 中自动可用，无需手动获取
# 非 TenantController 场景：
from app.middleware.tenant import get_tenant_context, get_current_tenant
tenant_ctx = get_tenant_context(request)  # TenantContext
tenant = get_current_tenant(request)      # Tenant | None
```

完整规范 → `references/platform-infrastructure.md` §一

---

## 三、认证与依赖注入

### 三端 Token 分离

| 端点 | 依赖类型 | 说明 |
|------|---------|------|
| admin | `CurrentAdmin` | 平台管理员（必须登录，否则 401） |
| tenant | `CurrentTenantAdmin` | 租户管理员 |
| user | `CurrentUser` | 终端用户 |

可选版本：`OptionalAdmin` / `OptionalTenantAdmin` / `OptionalUser`（未登录返回 None）

### Controller 中使用

```python
# GlobalController（admin 端）
async def list(self, request: Request, db: DbSession, admin: CurrentAdmin):
    # admin.id / admin.is_superadmin

# TenantController（tenant 端）
async def list(self, request: Request, db: DbSession, tenant_admin: CurrentTenantAdmin):
    # tenant_admin.id / tenant_admin.tenant_id
```

### 前端 Token 自动选择

`multi-auth store` 根据 URL 前缀自动选择 Token：`/admin/*` → admin Token，`/tenant/*` → tenant Token，`/user/*` → user Token。开发者无需手动传。

完整规范 → `references/platform-infrastructure.md` §二

---

## 四、异常体系

### 异常层级

```
AppException (500)
├── ValidationException (422)     # 参数校验
├── NotFoundException (404)       # 资源不存在
├── AuthenticationException (401) # 未认证
├── PermissionDeniedException (403) # 无权限
├── ConflictException (409)       # 资源冲突
├── RateLimitException (429)      # 频率限制
├── BusinessException (400)       # 通用业务错误
└── StorageError (500)           # 存储错误
```

### Service 层抛异常

```python
from app.exceptions import NotFoundException, ConflictException, BusinessException
raise NotFoundException(_("item.not_found"))
raise ConflictException(_("item.name_exists"))
raise BusinessException(_("item.is_locked"))
```

**规则**：Service 抛异常，Controller **不要**捕获（全局处理器自动转 JSON）。消息必须用 `_()`。

完整规范 → `references/platform-infrastructure.md` §三

---

## 五、日志系统

### 分类日志器

| 分类 | 文件 | Mixin |
|------|------|-------|
| `app` | `logs/app.log` | `LoggerMixin`（默认） |
| `error` | `logs/error.log` | — |
| `auth` | `logs/auth.log` | `AuthLoggerMixin` |
| `storage` | `logs/storage.log` | `StorageLoggerMixin` |
| `task` | `logs/task.log` | `TaskLoggerMixin` |
| `queue` | `logs/queue.log` | `QueueLoggerMixin` |
| `db` | `logs/db.log` | `DbLoggerMixin` |

### 使用方式

```python
# 方式 1: 便捷函数（通用场景）
from app.core.logging import get_logger
logger = get_logger(__name__)

# 方式 2: Service 中用 Mixin（推荐）
class MyService(TenantService, StorageLoggerMixin):
    async def upload(self):
        self.logger.info("Uploading...")  # → 写入 storage.log
```

**规则**：禁止 `print()`，禁止在日志中记录密码/Token/API Key。

完整规范 → `references/platform-infrastructure.md` §四

---

## 六、SSE 流式请求（前端）

```typescript
// POST SSE（AI 对话常用）
await requestClient.postSSE('/tenant/agents/1/chat/stream',
    { message: "Hello", conversation_id: 123 },
    {
        onMessage: (chunk) => { /* 处理流式数据 */ },
        onEnd: () => { /* 完成 */ },
        onError: (err) => { /* 出错 */ },
        abortController: new AbortController(),  // 停止生成
    }
);

// 取消请求
controller.abort();
```

Token 根据 URL 前缀自动注入，无需手动传。

完整规范 → `references/platform-infrastructure.md` §五

---

## 七、应用启动流程

`main.py` lifespan 启动 6 步：

```
1. init_logging()          → 日志系统
2. init_database()         → 创建库 + alembic upgrade head + 验证连接
3. sync_permissions()      → 扫描 Controller 权限 → 同步到 permissions 表
4. sync_config_to_db()     → ConfigRegistry → 同步到 system_configs 表
5. RedisManager.init()     → Redis 连接池
6. verify_celery()         → Celery 连通性检测（失败不阻塞）
```

新增初始化服务：在 lifespan 的 Redis 之后添加 `await MyService.init()`，yield 之前 `await MyService.close()`。

完整规范 → `references/platform-infrastructure.md` §六

---

## 八、存储系统

适配器模式，4 种后端：`LocalDriver` / `S3Driver` / `OssDriver` / `CosDriver`

```python
from app.storage.manager import StorageManager
driver = await StorageManager.get_driver()
path = await driver.put("uploads/avatar.png", file_bytes)
url = await driver.url(path, expires=3600)
```

接口方法：`put` / `get` / `delete` / `exists` / `url` / `size`

完整规范 → `references/platform-infrastructure.md` §七

---

## 九、配置系统

混合模式：代码定义（`ConfigMeta` + `ConfigGroupMeta`）→ 注册到 `ConfigRegistry` → 启动时同步到 `system_configs` 表 → 运行时从 DB 读取。

```python
# 读取配置
config_service = ConfigService(db)
value = await config_service.get_value("site_name")
```

作用域：`PLATFORM`（全平台）/ `TENANT`（租户级）

完整规范 → `references/platform-infrastructure.md` §八

---

## 十、前端业务组件

15 个可复用组件（`components/business/`）：

| 组件 | 用途 |
|------|------|
| `ApiSelect` | 远程数据下拉选择器 |
| `CronPicker` | Cron 可视化选择器 |
| `FilePicker` | 文件选择器（集成附件管理） |
| `FilePreview` | 文件预览器（图片/PDF/视频） |
| `ImageUpload` | 图片上传（裁剪/预览） |
| `ConfigForm` | 系统配置表单（根据 ConfigMeta 动态渲染） |
| `PermissionSelector` | 权限选择器（树形勾选） |
| `OrgTree` | 组织架构树 |
| `MemberPanel` | 成员管理面板 |
| `RoleTree` | 角色树形选择器 |
| `IconPicker` / `Captcha` / `ConfigImagePicker` / `OrgNodeDialog` / `PermissionPreview` | 其他 |

### useCrudDrawer 用法

```typescript
const { Drawer, isEdit, openNew, openEdit } = useCrudDrawer<T>({
    formApi, schema: useFormSchema, fields: ['name', 'status'],
    apiPath: '/tenant/agents', onSuccess: () => emits('success'),
});
```

完整组件清单 + useCrudDrawer 详解 → `references/platform-infrastructure.md` §九

---

## 十一、后端开发流程

### 分层架构

```
请求 → Middleware → Controller → Service → Repository → Model/DB
```

| 层 | 职责 | 禁止 |
|----|------|------|
| Controller | 路由、参数校验、调 Service、返回响应 | 写业务逻辑 |
| Service | 业务逻辑、钩子、事务编排 | 直接操作 DB |
| Repository | 数据访问、查询构建 | 写业务判断 |
| Model | 表结构定义 | 写查询逻辑 |
| Schema | 请求/响应数据结构 | — |

### CRUD 7 步流程

1. **Model** — 继承 `TenantModel`/`BaseModel`，声明 `__filterable__`/`__sortable__`
2. **Schema** — 继承 `BaseCreateSchema`/`BaseUpdateSchema`/`BaseResponseSchema`
3. **Repository** — 继承 `TenantRepository`/`BaseRepository`
4. **Service** — 继承 `TenantService`/`BaseService`，可重写钩子
5. **Controller** — 继承 `TenantController`/`GlobalController`，声明 `@permission_resource` + `@action_*`
6. **注册路由** — 引入 `router`
7. **生成迁移** — CRUD Generator 自动生成 Alembic 迁移脚本到 `migrations/versions/crud/`；手动模块用 `alembic revision --autogenerate -m "xxx"` + 注册到 `models/__init__.py` 和 `migrations/env.py`（启动时自动 upgrade）

### 菜单权限系统（新模块必读）

菜单分两层：**目录菜单**（父级分组）和**叶子菜单**（Controller 声明）。

**添加新菜单分组的步骤**：
1. 在 `backend/app/rbac/menus/admin_menus.py` 或 `tenant_menus.py` 添加 `PermissionMeta` 目录定义（无 `component` 字段 = 目录节点）
2. 在 Controller 的 `@permission_resource` 中使用 `MenuConfig(parent="分组标识")` 引用
3. 前端 i18n 添加 `menu.{scope}.{分组标识}` 翻译
4. 前端路由添加父级路由节点

**`parent` 解析规则**：`parent="ai_mgmt"` → 装饰器自动拼接为 `menu:{scope}.ai_mgmt` → 查找目录菜单的 `code`

完整机制（含目录菜单模板、叶子菜单模板、无菜单 Controller、启动同步流程） → `references/backend-crud.md` §菜单权限系统

关键注意：
- `TenantController.get_service(db, tenant_id)` — 第二参数是 `int`
- `BaseController.get_service(db)` — 只需 `db`
- 分页用 `query.size` 不是 `query.page_size`

完整代码示例、响应方法、异常表、依赖注入、权限装饰器、中间件顺序、枚举、日志 → `references/backend-crud.md`

### 数据库启动自动迁移

系统启动时 `main.py` → `init_database()` 自动执行三步：

1. **检查/创建数据库** — 连接 `postgres` 默认库，检查目标库是否存在，不存在则自动创建
2. **运行迁移** — 读取 `alembic.ini`，执行 `alembic upgrade head`，自动应用所有未执行的迁移
3. **验证连接** — 异步连接目标库执行 `SELECT 1` 验证

> **开发者无需手动 `alembic upgrade head`**，应用启动即自动执行。只需生成迁移文件即可。

### 迁移文件开发规范

```bash
# 1. 生成迁移文件（在 backend/ 目录下）
cd backend
alembic revision --autogenerate -m "add_xxx_table"

# 2. 检查生成的迁移文件（backend/migrations/versions/xxx.py）
#    确认 upgrade() 和 downgrade() 逻辑正确

# 3. 启动应用即自动执行迁移，无需手动 upgrade
```

**关键注意**：

- **新增 Model 必须注册到两个地方**：
  1. `backend/app/models/__init__.py` — 添加 import 和 `__all__` 导出
  2. `backend/migrations/env.py` — 添加 import（确保 Alembic 发现新表）
- 迁移文件命名模板：`{year}{month}{day}_{rev}_{slug}.py`
- `env.py` 中 `target_metadata = Base.metadata`，所有 Model 必须继承 `Base`
- 同步引擎 `DATABASE_URL_SYNC`（`postgresql://`）用于 Alembic，异步引擎 `DATABASE_URL`（`postgresql+asyncpg://`）用于应用

### CRUD 生成器迁移规则（重要）

**禁止任何途径直接 CREATE TABLE**。所有建表操作必须通过 Alembic 迁移脚本。

| 入口 | 正确做法 | 禁止做法 |
|------|----------|----------|
| 可视化向导 | 生成 Alembic migration `.py` 文件 | 生成 DDL / 直接建表 |
| CLI `generate` | 输出 migration 文件到 `migrations/versions/` | 执行 CREATE TABLE |
| AI 智能体 | Skill 输出 migration 脚本 | 输出 DDL 预览 |

**原因**：
1. 直接建表会断裂 Alembic 迁移链，后续新增字段无法通过迁移管理
2. 后端热重载自动执行 `alembic upgrade head`，迁移链外的表不受管理
3. 生产部署依赖迁移链的完整性进行增量升级

**已实现**（里程碑 M119/#389 — 已完成）：
- `migration.py.j2` 模板 → `generator.generate_migration()` 生成建表迁移脚本
- `migration_alter.py.j2` 模板 → `generator.generate_incremental_migration()` 生成增量迁移脚本（add_column / alter_column / drop_column）
- 迁移脚本输出到 `backend/migrations/versions/crud/` 子目录
- `alembic.ini` + `env.py` 已配置 multi-directory version_locations
- Writer 白名单已包含 `backend/migrations/versions/crud/`
- CLI `generate --down-revision` 生成建表迁移；CLI `migrate --old-config --new-config` 生成增量迁移
- AI Toolkit 已添加 `generate_migration` 和 `generate_incremental_migration` 工具
- 前端预览 DDL tab 已替换为 Migration tab

### CRUD 生成器插件化规则（重要）

**CRUD Generator（可视化向导 + CLI）不是系统核心功能，必须作为可选插件提供。**

系统核心不应包含 CRUD Generator 代码。该功能通过插件体系（`ApiPlugin` + `SkillPlugin`）动态加载：

| 组件 | 当前位置（待迁移） | 目标位置 |
|------|---------------------|----------|
| 后端引擎 | `app/codegen/` (11 .py + 14 .j2) | `app/plugins/crud-generator/codegen/` |
| 后端 API | `app/api/admin/dev_crud*.py` | 插件 `get_router()` 动态路由 |
| CLI | `python -m app.codegen.cli` | 插件 CLI 命令 |
| AI 技能 | 迁移种子数据绑定 | `SkillPlugin` 生命周期自动装配 |
| 前端页面 | `views/admin/dev/crud-generator/` (35+ 文件) | 插件前端包 + 动态路由注册 |
| i18n | 核心 `admin/dev.json` | 插件自有 locale |

**当前状态**（待重构 — 里程碑 M120/#390）：
- 后端 + 前端代码深度耦合在核心中
- 前端插件页面注册机制尚不存在（需先设计）
- 系统智能体通过迁移种子数据绑定（需改为 SkillPlugin 生命周期）

### 数据库会话获取方式

| 场景 | 方法 | 类型 |
|------|------|------|
| FastAPI 路由依赖注入 | `db: AsyncSession = Depends(get_db)` | 异步 |
| Service/非路由上下文 | `async with get_db_context() as db:` | 异步 |
| Celery Worker 内 | `self.get_db_session()` | 同步 |

---

## 十二、前端开发流程

### 架构分层

```
views → composables → store/api → utils（禁止反向依赖）
```

端隔离：admin 仅导入 `api/admin`、`store/admin`

### CRUD 4 步流程

1. **data.ts** — 列定义 `useColumns()`、搜索 `useGridFormSchema()`、表单 `useFormSchema()`
2. **list.vue** — `useCrudPage` 组装列表（api / columns / searchSchema / formComponent）
3. **form.vue** — `useCrudDrawer` 组装表单（formApi / schema / fields）
4. **路由 + i18n** — `router/routes/{endpoint}/` + `locales/langs/zh-CN/{endpoint}/`

关键注意：
- 搜索/表单必须用辅助函数（`searchInput` / `inputField` 等），禁止手写
- 业务预设（planSelect 等）定义在 `data.ts`，不放 adapter
- `requestClient` 导入路径：`#/utils/request`
- 权限指令：`v-access:code="['resource:action']"`

完整代码示例、权限、搜索、i18n、图标、HTTP 请求、命名规范、样式 Token → `references/frontend-crud.md`

---

## 十三、前后端协作约定

### JSON:API 查询协议

前端 URL 参数 ↔ 后端 QueryParams 自动解析：

- 过滤：`filter[status]=active` / `filter[name][ilike]=科技`
- 排序：`sort=-created_at,name`
- 分页：`page[number]=1&page[size]=20`

### 错误码对照

| 前端处理 | 后端错误码 |
|----------|-----------|
| 跳转登录页 | 4010 |
| 刷新 Token | 4011 |
| 弹出过期提示 | 4012 |
| 权限不足提示 | 4030 / 4031 |

### CRUD 请求约定

- 创建：`POST {resource}` + body
- 更新：`PUT {resource}/{id}` + body
- 删除：`DELETE {resource}/{id}`
- 列表：`GET {resource}` + JSON:API 查询参数
- 下拉：`GET {resource}/select?search=xxx`
- 排序：`PUT {resource}/reorder` + `{ "ids": [...] }`

---

## 十四、检查清单

### 后端提交前检查

- [ ] Model 继承 `BaseModel` / `TenantModel`，声明 `__filterable__` / `__sortable__`
- [ ] Repository 继承 `BaseRepository` / `TenantRepository`
- [ ] Service 继承 `BaseService` / `TenantService` / `GlobalService`
- [ ] Controller 声明 `@permission_resource`，方法声明 `@action_*`
- [ ] 统一响应方法（`success` / `created` / `paginated` / `deleted`）
- [ ] 面向用户文本使用 `_()`
- [ ] 枚举使用 `LabeledEnum`
- [ ] Alembic 迁移已生成
- [ ] 新 Model 已注册到 `models/__init__.py` 和 `migrations/env.py`
- [ ] 敏感信息通过环境变量

### 前端提交前检查

- [ ] 无 `any` 类型
- [ ] 无 `console.log()`
- [ ] 无中文硬编码（全部 `$t()`）
- [ ] 搜索/表单用辅助函数生成
- [ ] 业务预设在 `data.ts` 定义，不在 adapter
- [ ] 无跨端导入
- [ ] i18n JSON key 无重复、路径正确
- [ ] 中英文翻译齐全
- [ ] Props 用 `defineProps<T>()`

---

## 十五、异步任务与定时任务

本项目使用 **Celery + Redis** 实现异步任务和定时任务（P1-1 已完成）。

### 快速参考

- 任务必须使用 `@register_task` 装饰器，禁止直接用 `@celery_app.task`
- 基类选择：平台任务 → `BaseTask`，租户任务 → `TenantTask`（自动隔离）
- Celery Worker 是同步进程，用 `self.get_db_session()` 获取同步 Session
- 4 个队列：`default` / `high_priority` / `ai_gateway` / `scheduled`
- 定时任务支持三种范围：`platform` / `tenant` / `all_tenants`
- 前端 CronPicker 组件：`<CronPicker v-model="form.cron_expression" />`

完整规范、代码模板、检查清单 → `references/async-tasks.md`

---

## 十六、文档规范（DevGenius MCP）

### 强制要求

每个里程碑的功能开发完成后，**必须**编写使用文档并保存到 DevGenius MCP。

### 文档结构模板

所有功能使用文档遵循统一结构：

```
# {模块名} - 使用指南

## 一、功能概述        → 模块做什么、支持哪些能力
## 二、核心组件        → 文件结构、关键类/组件/枚举
## 三、使用方法        → 代码示例、配置说明、API 端点
## 四、启动与运维      → 环境变量、部署命令、注意事项
## 五、前端功能        → 页面路径、组件用法、交互说明
## 六、最佳实践        → 编写规范、选择指南、错误处理
## 七、故障排查        → 常见问题、日志查看、手动操作
```

### 文档分类

| 分类代码 | 名称 | 用途 |
|----------|------|------|
| `usage_guide` | 功能使用指南 | 已完成模块的使用文档 |
| `architecture` | 技术架构 | 架构设计、代码分析 |
| `api_spec` | API 设计 | 接口设计文档 |
| `guidelines` | 开发规范 | 编码规范、Git 规范 |
| `database` | 数据库设计 | 表结构、数据模型 |

### 写入流程

```
1. search_documents(query="模块关键词")     → 检查是否已存在
2. 不存在 → create_document(title, content, category="usage_guide")
3. 已存在 → update_document_by_id(document_id, content)
```

### Skill 同步规则

当新模块包含可复用的开发规范（如基类、装饰器、组件用法）时：
1. 在 `references/` 目录创建对应的 `.md` 参考文件
2. 在 `SKILL.md` 添加该章节的快速参考
3. 在参考文件列表中注册

---

## 十七、DevGenius MCP 标准工作流

本项目通过 DevGenius MCP 管理任务和文档（集成名称：`devgenius-quanzhan`）。

核心流程：`认领任务 → 查文档 → 开发 → 写文档 → 更新状态`

详细工具用法、流程图、速查表见 → `references/devgenius-workflow.md`

---

## 十八、AI 模块开发

### ⚠️ 核心架构原则：Agent→Skill 全链路（强制）

**所有 AI 功能必须通过 Agent 调度 Skill 完成，禁止直接调用 AIGateway。**

```
外部请求 → Agent.run() → Skill.execute() → AIGateway → LLM Provider
```

- ❌ 禁止在 Controller/Service 层直接实例化 `AIGateway` 发起 LLM 调用
- ❌ 禁止新增绕过 Agent→Skill 链路的 AI 端点
- ❌ 禁止在非 engine 层代码中 `from app.ai.gateway import AIGateway`
- ✅ Agent engine 内部的 LLM 调用（`conversation.py` / `base.py` / `task.py`）— 属于 Agent 实现层
- ✅ `AIGateway.test_model` — 仅限模型连通性测试，不用于业务功能

### 技能（Skill）体系规则

- **技能包（SkillPackage）是一级管理单元**，技能必须归属于某个技能包
- **前端统一入口**：`/admin/ai/skill-packages` 和 `/tenant/ai/skill-packages` 为唯一技能管理入口
- **禁止独立技能路由**：不允许存在独立的 `/admin/ai/skills` 或 `/tenant/ai/skills` 页面
- 技能包详情页内嵌技能 CRUD，技能表单自动继承当前包的 `package_id`

### 技能类型（SkillTypeEnum）

| 类型 | 说明 | Executor |
|------|------|----------|
| `toolkit` | Python 工具包（Tools 类） | ToolkitExecutor |
| `knowledge_base` | 知识库检索（RAG） | 无（RAG 注入 system_prompt） |
| `data_intelligence` | 数据智能（Text-to-SQL + CRUD） | TextToSQLExecutor |
| `builtin` | 内置函数 | BuiltinToolExecutor |

未知类型走插件解析路径（PluginExecutor）。

**Toolkit 技能（toolkit 类型）**：
- 编写 Python 源码，定义 `Tools` 类，每个公开方法自动映射为一个 LLM 可调用工具
- 字段：`toolkit_content`（Text）存储 Python 源码，`toolkit_meta`（JSON）存储解析结果
- 支持 Valves 配置：通过 `valves_schema` 动态渲染配置表单
- 前端编辑器：Monaco Editor + 实时解析预览 + ZIP 上传

### 系统 Agent 与系统 Skill

- 系统级 Agent/Skill 标记 `is_system=True`，不可删除/禁用
- 通过 seed migration 创建，scope=admin, tenant_id=NULL
- 前端管理页面中系统记录有特殊标识且操作受限

### 新增 AI 功能标准流程

```
1. 定义 Skill 类型（如已有类型可复用则跳过）
2. 新增 SkillTypeEnum 枚举值 + i18n
3. 实现 Executor（继承 BaseToolExecutor）
4. 在 resolver.py 注册类型→Executor 映射
5. 创建 Skill 记录（可通过 migration 或 API）
6. 将 Skill 绑定到 Agent（AgentSkillBinding）
7. 通过 Agent 对话或 Agent.run() 触发 Skill
```

**禁止跳过步骤直接调用 AIGateway 实现 AI 功能。**

### 架构概览

AI 模块提供三大核心能力：**Chat 对话**、**Text-to-SQL 数据查询**、**RAG 文档问答**。

```
Engine(Dispatcher → Conversation/Task/Batch)
  → Gateway(RateLimit + Quota + Cache + Failover + Adapters)
  → Tools(Registry + Security + Sandbox + Executors)
  → RAG(Parser → Chunker → Embedding → Retriever → Reranker → ContextBuilder)
  → DataIntelligence(SchemaProvider → TextToSQL → SQLSafety → TenantIsolation → Executor)
```

### 关键目录

| 目录 | 内容 |
|------|------|
| `backend/app/ai/engine/` | 执行引擎（dispatcher, conversation, task, batch） |
| `backend/app/ai/gateway.py` | AI 网关（仅由 Executor/Engine 内部调用） |
| `backend/app/ai/tools/executors/` | Skill 执行器（每个技能类型一个 Executor） |
| `backend/app/ai/skills/resolver.py` | 技能类型→Executor 注册映射 |
| `backend/app/ai/rag/` | RAG 管线（parser, chunker, embedding, retriever, reranker, context_builder） |
| `backend/app/ai/data_intelligence/` | 数据智能（text_to_sql, sql_safety, tenant_isolation, action_executor） |
| `backend/app/ai/events/` | 事件系统（types, bus, hooks） |
| `frontend/.../views/tenant/ai/` | 租户端 AI 页面（chat, agents, skill-packages, knowledge-bases 等） |
| `frontend/.../views/admin/ai/` | 管理端 AI 页面（providers, models, skill-packages, api-keys 等） |

### 新增 AI Provider 适配器

1. 创建 `backend/app/ai/adapters/my_provider.py`，继承 `BaseAdapter`
2. 实现 `chat()` / `chat_stream()` / `embedding()` 方法
3. 在 `adapters/__init__.py` 的 `ADAPTER_MAP` 注册

### 新增 RAG 分块策略

1. 在 `backend/app/ai/rag/chunker.py` 添加 `MyChunker(BaseChunker)`
2. 在 `get_chunker()` 工厂函数注册
3. 在 `enums/knowledge_base.py` 的 `ChunkStrategyEnum` 添加枚举值

### AI 模块枚举

| 枚举 | 文件 | 用途 |
|------|------|------|
| `AgentStatusEnum` | `enums/agent.py` | draft/published/disabled |
| `SkillTypeEnum` | `enums/agent.py` | toolkit/knowledge_base/data_intelligence/builtin |
| `DocumentStatusEnum` | `enums/knowledge_base.py` | pending/parsing/chunking/embedding/completed/error |
| `SearchModeEnum` | `enums/knowledge_base.py` | hybrid/vector/keyword |
| `RewriteStrategyEnum` | `enums/knowledge_base.py` | none/multi/hyde |

### SSE 对话流程

```
POST /tenant/ai/agent-chat/{agent_id}/chat/stream
  → Dispatcher → ConversationEngine
  → 渲染 prompt（变量注入 + RAG 上下文）
  → Gateway.chat_stream()（SSE 流式）
  → 工具调用循环（Tool Registry → Executor → 结果回传 LLM）
  → 前端 requestClient.postSSE() 接收
```

### AI 模块安全层

1. **SSRF 防护** — `tools/security.py` 拦截内网地址
2. **SQL 注入防护** — `tools/security.py` 验证 SQL 安全
3. **租户隔离** — `data_intelligence/tenant_isolation.py` 自动注入 `WHERE tenant_id`
4. **数据脱敏** — `data_intelligence/readonly_executor.py` 屏蔽 PII
5. **操作确认** — `data_intelligence/action_executor.py` 写操作需用户确认

完整架构文档 → MCP 文档 #274「AI Module Architecture」
完整使用指南 → MCP 文档 #275「AI Module Usage Guide」
详细规范 → `references/ai-module.md`
AI 架构规则详细版 → `.windsurf/rules/ai-architecture.md`

---

## 十九、参考文件

完整规范详见 references 目录：

- `references/platform-infrastructure.md` — 平台基础设施（多租户/认证/异常/日志/SSE/启动/存储/配置/组件）
- `references/backend-crud.md` — 后端 CRUD 7步完整代码 + 响应/异常/权限/枚举/日志
- `references/frontend-crud.md` — 前端 CRUD 4步完整代码 + 权限/搜索/i18n/图标/请求/命名
- `references/frontend-spec.md` — 前端开发手册完整版（含拖拽排序、列表 UI 设计、CSS 动画等）
- `references/backend-spec.md` — 后端开发指南完整版（含存储、日志、枚举、Service 钩子等）
- `references/async-tasks.md` — 异步任务与定时任务开发规范（Celery/Redis/队列/定时任务）
- `references/devgenius-workflow.md` — DevGenius MCP 工作流详解（工具速查、流程图、文档管理）
- `references/ai-module.md` — AI 模块开发规范（引擎/网关/工具/RAG/数据智能/事件/安全）
