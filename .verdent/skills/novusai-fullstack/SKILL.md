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
2. 查阅 `references/frontend-spec.md` 或 `references/backend-spec.md` 获取完整规范
3. 确认相关模块是否已有类似实现，复用已有模式

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

## 二、后端开发流程

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
7. **生成迁移** — `alembic revision --autogenerate && alembic upgrade head`

关键注意：
- `TenantController.get_service(db, tenant_id)` — 第二参数是 `int`
- `BaseController.get_service(db)` — 只需 `db`
- 分页用 `query.size` 不是 `query.page_size`

完整代码示例、响应方法、异常表、依赖注入、权限装饰器、中间件顺序、枚举、日志 → `references/backend-crud.md`

---

## 三、前端开发流程

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

## 四、前后端协作约定

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

## 五、检查清单

### 后端提交前检查

- [ ] Model 继承 `BaseModel` / `TenantModel`，声明 `__filterable__` / `__sortable__`
- [ ] Repository 继承 `BaseRepository` / `TenantRepository`
- [ ] Service 继承 `BaseService` / `TenantService` / `GlobalService`
- [ ] Controller 声明 `@permission_resource`，方法声明 `@action_*`
- [ ] 统一响应方法（`success` / `created` / `paginated` / `deleted`）
- [ ] 面向用户文本使用 `_()`
- [ ] 枚举使用 `LabeledEnum`
- [ ] Alembic 迁移已生成
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

## 六、DevGenius MCP 标准工作流

本项目通过 DevGenius MCP 管理任务和文档（集成名称：`devgenius-quanzhan`）。

核心流程：`认领任务 → 查文档 → 开发 → 更新状态`

详细工具用法、流程图、速查表见 → `references/devgenius-workflow.md`

---

## 七、参考文件

完整规范详见 references 目录：

- `references/backend-crud.md` — 后端 CRUD 7步完整代码 + 响应/异常/权限/枚举/日志
- `references/frontend-crud.md` — 前端 CRUD 4步完整代码 + 权限/搜索/i18n/图标/请求/命名
- `references/frontend-spec.md` — 前端开发手册完整版（含拖拽排序、列表 UI 设计、CSS 动画等）
- `references/backend-spec.md` — 后端开发指南完整版（含存储、日志、枚举、Service 钩子等）
- `references/devgenius-workflow.md` — DevGenius MCP 工作流详解（工具速查、流程图、文档管理）
