# 🚨 给 Cline：项目规则速查

> 你是 Cline，在开发本项目前，**必须先阅读这个文件**！

## 📍 规则文件位置

### 必读（核心规则）
1. **`.verdent/rules/novusai-saas.md`** - 完整的 9 条全局禁令 + 前后端规则
2. **`.cursorrules`** - 核心规则速查（虽然我是 Cline，但内容很有用）
3. **`.verdent/skills/novusai-fullstack/SKILL.md`** - 全栈开发技能
4. **`PROJECT_GUIDE.md`** - 开发指南速查

### 详细参考文档
5. `.verdent/skills/novusai-fullstack/references/backend-crud.md` - 后端 CRUD 7 步
6. `.verdent/skills/novusai-fullstack/references/frontend-crud.md` - 前端 CRUD 4 步
7. `.verdent/skills/novusai-fullstack/references/devgenius-workflow.md` - DevGenius 工作流

---

## 🚫 9 条不可违反的规则（必须遵守）

1. ❌ 禁止硬编码中文字符串（前端 `$t()`，后端 `_()`）
2. ❌ 禁止 `console.log`（使用 `console.warn` / `console.error`）
3. ❌ 禁止 `any` 类型（使用 `unknown` 或具体类型）
4. ❌ 禁止魔法字符串（后端用 `LabeledEnum`）
5. ❌ 禁止跨端导入（admin 不导入 tenant）
6. ❌ 禁止 Controller 写业务逻辑，Service 直接操作 DB
7. ❌ 禁止裸返回数据（后端必须用统一响应）
8. ❌ 禁止手写重复 Schema（前端用辅助函数）
9. ❌ 禁止敏感信息入代码（通过环境变量）

---

## ⚡ 前端开发核心规则

- **架构**：`views → composables → store/api → utils`（禁止反向依赖）
- **端隔离**：admin 仅导入 `api/admin`、`store/admin`
- **CRUD**：列表用 `useCrudPage`，表单用 `useCrudDrawer`
- **辅助函数**：搜索用 `searchInput()`/`statusSelect()`，表单用 `inputField()`/`dateField()`
- **权限**：`v-access:code="['resource:action']"`
- **国际化**：`$t('admin.system.role.title')`
- **图标**：优先 Lucide `lucide:user`，Tailwind `icon-[lucide--user]`
- **命名**：目录/TS 文件 kebab-case，Vue 组件 PascalCase

---

## ⚡ 后端开发核心规则

- **分层**：`Middleware → Controller → Service → Repository → Model`
- **多租户**：继承 `TenantModel`/`TenantRepository`/`TenantService`/`TenantController`
- **统一响应**：`success()` / `created()` / `paginated()` / `deleted()`
- **查询**：JSON:API（`filter[field][operator]`、`sort=-created_at`）
- **权限**：`@permission_resource("resource")` + `@action_read`/`@action_create`
- **异常**：`ValidationException`(422/4001)、`AuthenticationException`(401/4010) 等
- **依赖注入**：`DbSession`、`ActiveTenantAdmin`、`QueryParams`
- **中间件顺序**：CORS → I18n → Permission → AuditLog → AccessControl → Tenant

---

## 🔄 开发流程

### 后端 CRUD 7 步
1. Model（继承 `TenantModel`/`BaseModel`）
2. Schema（继承 `BaseCreateSchema`/`BaseUpdateSchema`/`BaseResponseSchema`）
3. Repository（继承 `TenantRepository`/`BaseRepository`）
4. Service（继承 `TenantService`/`BaseService`）
5. Controller（继承 `TenantController`/`GlobalController`，声明权限装饰器）
6. 注册路由
7. 生成迁移（`alembic revision --autogenerate && alembic upgrade head`）

### 前端 CRUD 4 步
1. `data.ts` - 定义列、搜索、表单 Schema（必须用辅助函数）
2. `list.vue` - 使用 `useCrudPage`
3. `form.vue` - 使用 `useCrudDrawer`
4. 路由 + i18n

---

## ⚡ DevGenius 工作流

1. `get_project_context` → 获取项目信息、任务列表
2. `get_my_tasks` → 查看分配给自己的任务
3. `claim_task(task_id)` → 认领任务（锁定 120 分钟）
4. `search_documents(query="关键词")` → 搜索规范文档
5. 开发 → 严格遵守规则
6. `update_task_status(task_id, status="completed", notes="完成报告")` → 更新状态

---

## 🔧 技术栈

**前端：** Vue 3.5 + TypeScript + Vben Admin 5.x + Ant Design Vue + Vite 6.x + Tailwind CSS
**后端：** Python 3.11+ + FastAPI + SQLAlchemy 2.x (Async) + PostgreSQL + Alembic
**认证：** JWT (access / refresh / impersonate)
**查询：** JSON:API（filter/sort/page）

---

## ✅ Cline 工作流程

当你让我开发功能时，我应该：

1. **首先读取这个文件**（CLINE_RULES.md）
2. **然后读取** `.verdent/rules/novusai-saas.md` **获取完整规则**
3. **根据需要查阅** `references/` **下的详细文档**
4. **严格遵守所有规则**进行开发
5. **发现违反规则的地方主动提醒你**

**这样我就能记住并应用所有规则了！** ✨
