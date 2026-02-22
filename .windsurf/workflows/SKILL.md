---
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

## 二、平台基础设施

多租户隔离、认证注入、异常体系、日志系统、SSE 流式、应用启动、上传存储、配置系统、前端业务组件。

**核心要点**：
- 四层租户隔离：`TenantModel` → `TenantRepository` → `TenantService` → `TenantController`
- 三端 Token：`ActiveAdmin` / `ActiveTenantAdmin` / `ActiveUser`
- 异常由 Service 抛出（`NotFoundException` / `BusinessException` 等），Controller 不捕获
- 日志分类器：`LogManager.get_logger("app"/"auth"/"storage"/"task"/"queue"/"db")`
- 上传必须通过 `AttachmentService`，前端用 `FilePicker` / `ImageUpload` / `smartUploadFile`

→ 完整规范：`references/platform-infrastructure.md`

---

## 三、后端开发（CRUD 7 步）

分层架构：请求 → Middleware → Controller → Service → Repository → Model/DB

1. **Model** — 继承 `TenantModel`/`BaseModel`，声明 `__filterable__`/`__sortable__`
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

→ 完整代码示例：`references/backend-crud.md`
→ 后端开发指南：`references/backend-spec.md`

---

## 四、前端开发（CRUD 4 步）

架构分层：`views → composables → store/api → utils`（禁止反向依赖）

1. **data.ts** — 列定义 `useColumns()`、搜索 `useGridFormSchema()`、表单 `useFormSchema()`
2. **list.vue** — `useCrudPage` 组装列表
3. **form.vue** — `useCrudDrawer` 组装表单
4. **路由 + i18n** — `router/routes/{endpoint}/` + `locales/langs/zh-CN/{endpoint}/`

**关键注意**：
- 搜索/表单必须用辅助函数（`searchInput` / `inputField` 等），禁止手写
- 业务预设（planSelect 等）定义在 `data.ts`，不放 adapter
- `requestClient` 导入路径：`#/utils/request`
- 权限指令：`v-access:code="['resource:action']"`

→ 完整代码示例：`references/frontend-crud.md`
→ 前端开发手册：`references/frontend-spec.md`

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
- 技能类型：`toolkit` / `knowledge_base` / `data_intelligence` / `builtin`
- 新增 AI 功能标准流程：定义类型 → 实现 Executor → 注册映射 → 创建 Skill → 绑定 Agent

→ 完整规范：`references/ai-module.md`

---

## 七、插件开发

6 种扩展点：`AdapterPlugin` / `SkillPlugin` / `StoragePlugin` / `ApiPlugin` / `HookPlugin` / `ToolPlugin`（已废弃）

- 生命周期：install → enable → disable → uninstall
- 插件目录：`backend/app/plugins/{name}/`，含 `plugin.py` + `manifest.json`
- 作用域：`platform_only` / `all_tenants` / `assigned_tenants` / `global`

→ 完整指南：`references/plugin-guide.md`

---

## 八、异步任务与定时任务

- 必须用 `@register_task` 装饰器，禁止 `@celery_app.task`
- Celery Worker 是同步进程，用 `sync_session_factory()` 获取 DB，`redis.from_url()` 获取 Redis
- 4 个队列：`default` / `high_priority` / `ai_gateway` / `scheduled`
- 定时任务通过 `periodic_tasks` 表管理，禁止硬编码 `beat_schedule`

→ 完整规范：`references/async-tasks.md`

---

## 九、删除依赖保护

任何 Model 被 FK 引用时，必须声明 `__delete_deps__`。五种策略：`BLOCK` / `CASCADE_SOFT` / `CASCADE_DELETE` / `NULLIFY` / `IGNORE`。`useCrudPage` 已集成 `DependencyBlockModal`（错误码 4221）。

→ 完整规范：`references/deletion-deps.md`

---

## 十、邮件发送

所有邮件必须通过 `send_email_task.delay()` 异步发送，禁止 Controller/Service 直接调用 `EmailService.send()`。

→ 完整规范：`references/email-spec.md`

---

## 十一、通知系统

所有业务通知统一走 `NotificationService.send()` → 渠道驱动（WS / Inbox / Email）。模板编码格式：`{category}.{event_name}`。

→ 完整规范：`references/notification-spec.md`

---

## 十二、WebSocket 实时通信

三端 namespace 隔离：`/admin` / `/tenant` / `/user`。后端用 `sio.emit()`，Celery 用 `sio_bridge.*_sync()`。

→ 完整指南：`websocket-guide.md`

---

## 十三、时间存储与显示

- **后端**：统一 `utc_now()`（`app.core.base_model`），禁止 `datetime.now()` / `datetime.utcnow()`
- **序列化**：ISO 8601 + `+00:00` 后缀
- **前端**：`formatDate()` / `formatRelativeTime()` 自动转本地时间

---

## 十四、数据库迁移

系统启动时自动执行 `alembic upgrade head`，开发者只需生成迁移文件。新 Model 必须注册到 `models/__init__.py` 和 `migrations/env.py`。

→ 完整最佳实践：`database-migration-best-practices.md`

---

## 十五、DevGenius MCP 工作流

核心流程：认领任务 → 查文档 → 开发 → 写文档 → 更新状态

→ 详细工具用法：`references/devgenius-workflow.md`

---

## 检查清单

### 后端

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
- [ ] 时间使用 `utc_now()`

### 前端

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

## 参考文件索引

| 文件 | 内容 |
|------|------|
| `references/platform-infrastructure.md` | 多租户/认证/异常/日志/SSE/启动/存储/配置/组件 |
| `references/backend-crud.md` | 后端 CRUD 7 步完整代码 + 响应/异常/权限/枚举/日志 |
| `references/frontend-crud.md` | 前端 CRUD 4 步完整代码 + 权限/搜索/i18n/图标/请求/命名 |
| `references/frontend-spec.md` | 前端开发手册完整版（含拖拽排序、列表 UI 设计、CSS 动画等） |
| `references/backend-spec.md` | 后端开发指南完整版（含存储、日志、枚举、Service 钩子等） |
| `references/async-tasks.md` | 异步任务与定时任务开发规范（Celery/Redis/队列/定时任务） |
| `references/devgenius-workflow.md` | DevGenius MCP 工作流详解（工具速查、流程图、文档管理） |
| `references/ai-module.md` | AI 模块开发规范（引擎/网关/工具/RAG/数据智能/事件/安全） |
| `references/plugin-guide.md` | 插件开发指南（6 种扩展点/生命周期/manifest/权限/示例） |
| `references/email-spec.md` | 邮件发送规范（架构/触发来源/配置/规则） |
| `references/deletion-deps.md` | 删除依赖保护规范（5 种策略/声明语法/前端弹窗/回收站） |
| `references/notification-spec.md` | 通知系统规范（渠道驱动/模板编码/队列/扩展） |
