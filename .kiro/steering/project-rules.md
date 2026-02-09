# NovusAI SaaS 开发规则

## 项目概述

多租户 SaaS 平台。前端 Vue 3 + Vben Admin 5.x + Ant Design Vue；后端 FastAPI + SQLAlchemy 2.x + PostgreSQL。

## 全局禁令

- 禁止硬编码中文字符串，前端用 `$t()`，后端用 `_()`
- 禁止 `console.log`，使用 `console.warn` / `console.error`
- 禁止 `any` 类型，使用 `unknown` 或具体类型
- 禁止魔法字符串，使用枚举（后端 `LabeledEnum`）
- 禁止跨端导入（admin 页面不导入 tenant API/store）
- 禁止 Controller 写业务逻辑，禁止 Service 直接操作 DB
- 禁止裸返回数据，后端必须用 `success()` / `created()` / `paginated()` 等统一响应
- 禁止手写重复 Schema 配置，前端必须用 `searchInput` / `inputField` 等辅助函数
- 禁止敏感信息（密钥、密码）写入代码，通过环境变量配置

## 前端规则

### 架构

- 多端分离：admin (`/admin/*`)、tenant (`/tenant/*`)、user (`/*`)
- 依赖方向：`views → composables → store/api → utils`，禁止反向依赖
- adapter 层不依赖具体业务代码
- 请求客户端：`import { requestClient } from '#/utils/request'`

### 权限

- 指令写法：`v-access:code="['resource:action']"`
- 操作列自动鉴权：`options: ['edit', 'delete']`
- Hook：`useAccess()` 获取 `hasAccessByCodes` / `isSuperAdmin`

### 搜索（JSON:API）

- fieldName 格式：`filter[field][operator]`
- 操作符：`ilike`（模糊）、`eq`（精确）、`gte/lte`（范围）、`in`（多值）

### 国际化

- 翻译文件 key 前缀 = 文件路径（`zh-CN/admin/system.json` → `admin.system.*`）
- JSON 内不重复嵌套路径名
- 避免同一 JSON 中重复 key

### 命名

- 目录/TS 文件：kebab-case
- Vue 组件：PascalCase
- API 函数：`{action}{Resource}Api`
- Store：`use{Endpoint}AuthStore`
- Composable：`use{Name}`

## 后端规则

### 架构分层

```
请求 → Middleware → Controller → Service → Repository → Model/DB
```

- Controller：路由、参数校验、调 Service、返回响应
- Service：业务逻辑、钩子、事务编排
- Repository：数据访问、查询构建
- Model：表结构定义

### 多租户

- 租户模型继承 `TenantModel`（自动含 `tenant_id`）
- 租户仓库继承 `TenantRepository`（自动注入 `tenant_id` 过滤）
- 租户服务继承 `TenantService`
- 租户控制器继承 `TenantController`
- 平台管理用 `GlobalController`
- `TenantController.get_service(db, tenant_id)` — 第二参数是 int
- `BaseController.get_service(db)` — 只需 db

### 统一响应

```python
success(data=obj)                         # 200
created(data=obj)                         # 201 含义
paginated(items, total, page, page_size)  # 分页
deleted()                                 # 删除成功
error(message, code, status_code)         # 自定义错误
```

### 权限（RBAC）

- 类装饰器：`@permission_resource("resource_name")`
- 方法装饰器：`@action_read` / `@action_create` / `@action_update` / `@action_delete`
- 公开接口：`@public`
- 仅登录：`@auth_only`

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
- `ActiveTenantAdmin` — 活跃租户管理员
- `QueryParams` — JSON:API 查询参数
- `SuperAdmin` — 超级管理员

### 迁移

```bash
alembic revision --autogenerate -m "add xxx table"
alembic upgrade head
```

启动时自动执行 `alembic upgrade head`。

## 前后端协作

- 搜索语法统一 JSON:API：前端 `filter[field][ilike]` ↔ 后端 `QueryParams` 自动解析
- 排序统一：前端 `sort=-created_at` ↔ 后端 `__sortable__` 白名单
- 分页统一：前端 `page[number]/page[size]` ↔ 后端 `paginated()`
- Token 按 URL 前缀自动选择：`/admin/*` → admin Token，`/tenant/*` → tenant Token
- 错误码对照：前端 4010 → 跳登录，4011 → token 过期刷新，4030 → 权限不足提示

## DevGenius 治理规则

本项目使用 DevGenius（MCP 集成名称：`devgenius-quanzhan`）进行项目管理：

- **任务驱动**：所有开发必须基于认领的任务，禁止无任务编码
- **文档先行**：新功能或重大变更前，必须先通过 MCP 查询相关文档
- **状态同步**：开发完成后必须更新任务状态
- **先查后写**：写入文档前必须先搜索是否已存在
- **MCP 优先**：所有项目管理操作通过 MCP 工具完成
