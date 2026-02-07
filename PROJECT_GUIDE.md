# NovusAI SaaS 开发指南（速查版）

> 📌 重要：本项目有严格的开发规范，开发前请务必阅读！

## 📚 核心文档位置

```
.verdent/
├── rules/novusai-saas.md                 # 完整规则（必读！）
├── skills/novusai-fullstack/
│   ├── SKILL.md                           # 全栈技能说明
│   └── references/                        # 详细参考文档
│       ├── backend-crud.md               # 后端 CRUD 7 步
│       ├── frontend-crud.md              # 前端 CRUD 4 步
│       ├── devgenius-workflow.md         # DevGenius 工作流
│       ├── backend-spec.md                # 后端完整规范
│       └── frontend-spec.md               # 前端完整规范
```

## 🚫 9 条不可违反的规则

1. ❌ 禁止硬编码中文字符串（前端 `$t()`，后端 `_()`）
2. ❌ 禁止 `console.log`（用 `console.warn` / `console.error`）
3. ❌ 禁止 `any` 类型（用 `unknown` 或具体类型）
4. ❌ 禁止魔法字符串（后端用 `LabeledEnum`）
5. ❌ 禁止跨端导入（admin 不导入 tenant）
6. ❌ 禁止 Controller 写业务逻辑，Service 直接操作 DB
7. ❌ 禁止裸返回数据（后端必须用统一响应）
8. ❌ 禁止手写重复 Schema（前端用辅助函数）
9. ❌ 禁止敏感信息入代码（通过环境变量）

## ⚡ 快速开始

### 前端开发
- 架构：`views → composables → store/api → utils`
- CRUD：用 `useCrudPage` + `useCrudDrawer`
- 搜索/表单：用 `searchInput()` / `inputField()` 等辅助函数
- 权限：`v-access:code="['resource:action']"`
- 国际化：`$t('admin.system.role.title')`

### 后端开发
- 分层：`Middleware → Controller → Service → Repository → Model`
- 多租户：继承 `TenantModel` / `TenantRepository` / `TenantService`
- 统一响应：`success()` / `created()` / `paginated()` / `deleted()`
- 权限：`@permission_resource` + `@action_read` / `@action_create`
- 查询：JSON:API（`filter[field][operator]`、`sort=-created_at`）

### DevGenius 工作流
1. `get_project_context` → 获取项目信息
2. `get_my_tasks` → 查看任务
3. `claim_task(task_id)` → 认领任务
4. `search_documents` → 查规范文档
5. 开发 → `update_task_status(task_id, status="completed", notes="完成报告")`

## 🔧 技术栈

**前端：** Vue 3.5 + TypeScript + Vben Admin 5.x + Ant Design Vue + Vite 6.x + Tailwind CSS
**后端：** Python 3.11+ + FastAPI + SQLAlchemy 2.x (Async) + PostgreSQL + Alembic
**认证：** JWT (access / refresh / impersonate)
**查询：** JSON:API（filter/sort/page）

## 📖 完整文档

详细规则请阅读：
- `.verdent/rules/novusai-saas.md` - 完整规则
- `.verdent/skills/novusai-fullstack/SKILL.md` - 技能说明
- `.cursorrules` - 核心规则速查
