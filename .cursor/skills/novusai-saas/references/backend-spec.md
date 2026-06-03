# 后端开发指南

## 目录

- [技术栈](#技术栈)
- [目录结构](#目录结构)
- [代码注释与文档字符串](#代码注释与文档字符串)
- [类型注解规范](#类型注解规范)
- [架构分层](#架构分层)
- [多企业体系](#多企业体系)
- [快速上手：新增一个 CRUD 模块](#快速上手新增一个-crud-模块)
- [统一响应](#统一响应)
- [查询规范 (JSON:API)](#查询规范-jsonapi)
- [权限体系 (RBAC)](#权限体系-rbac)
- [依赖注入](#依赖注入)
- [异常处理](#异常处理)
- [枚举规范](#枚举规范)
- [多语言 (i18n)](#多语言-i18n)
- [Service 钩子](#service-钩子)
- [远程下拉 (Select)](#远程下拉-select)
- [排序 API](#排序-api)
- [存储](#存储)
- [日志](#日志)
- [中间件注册顺序](#中间件注册顺序)
- [Health Check](#health-check)
- [IP 速率限制](#ip-速率限制)
- [ConfigService 内存缓存](#configservice-内存缓存)
- [开发检查清单](#开发检查清单)

## 技术栈

| 项 | 选型 |
|---|------|
| 语言 | Python 3.11+ |
| 框架 | FastAPI |
| ORM | SQLAlchemy 2.x (Async) |
| 数据库 | PostgreSQL |
| 迁移 | Alembic |
| 认证 | JWT (access / refresh / impersonate) |
| 密码 | bcrypt |
| i18n | 自研（JSON 翻译文件） |

---

## 目录结构

```
backend/
├── app/
│   ├── main.py                    # 应用入口，中间件 & 路由注册
│   ├── core/                      # 核心基类 & 基础设施
│   │   ├── base_controller.py     # BaseController / TenantController / GlobalController
│   │   ├── base_service.py        # BaseService / TenantService / GlobalService
│   │   ├── base_model.py          # BaseModel / TenantModel
│   │   ├── base_repository.py     # BaseRepository / TenantRepository
│   │   ├── base_schema.py         # BaseSchema / PageParams / PageResponse
│   │   ├── response.py            # 统一响应 success / error / paginated ...
│   │   ├── deps.py                # 依赖注入 DbSession / ActiveAdmin / ActiveTenantAdmin ...
│   │   ├── query_parser.py        # JSON:API 查询解析 filter / sort / page
│   │   ├── security.py            # JWT & 密码工具
│   │   ├── database.py            # 数据库连接 & Alembic 自动迁移
│   │   ├── i18n.py                # 翻译 _() / get_locale()
│   │   ├── config.py              # 应用配置（环境变量）
│   │   └── logging.py             # 分类日志 LogManager
│   ├── api/                       # 路由层（按作用域分）
│   │   ├── admin/                 # 平台管理 /admin/*
│   │   ├── public/                # 公开接口 /api/public/*
│   │   ├── shared/                # 供 admin / tenant / user 复用的通用控制器
│   │   ├── tenant/                # 企业管理 /tenant/*
│   │   └── user/                  # 用户端 API  /api/user/*
│   ├── services/                  # 业务逻辑
│   │   ├── ai/                    # AI / 智能体相关服务（agents、skills、toolkit）
│   │   ├── business/              # 跨 scope 的业务服务（workflow、billing）
│   │   ├── common/                # 跨域共享服务
│   │   ├── system/                # 平台级服务
│   │   └── tenant/                # 企业级服务
│   ├── repositories/              # 数据访问层
│   │   ├── ai/
│   │   ├── business/
│   │   ├── common/
│   │   ├── system/
│   │   └── tenant/
│   ├── models/                    # ORM 模型
│   │   ├── ai/
│   │   ├── auth/                  # 角色、权限
│   │   ├── business/
│   │   ├── common/
│   │   ├── org/
│   │   ├── system/                # 管理员、配置、操作日志
│   │   └── tenant/                # 企业、附件、套餐、域名
│   ├── schemas/                   # Pydantic Schema
│   │   ├── ai/
│   │   ├── business/
│   │   ├── common/                # 通用（查询、选项、排序）
│   │   ├── public/
│   │   ├── system/
│   │   └── tenant/
│   ├── enums/                     # 枚举（LabeledEnum 基类）
│   ├── exceptions/                # 异常体系
│   ├── middleware/                # 中间件
│   ├── rbac/                      # 权限体系
│   ├── configs/                   # 声明式系统配置
│   ├── locales/                   # i18n 翻译 JSON
│   ├── storage/                   # 存储驱动
│   ├── captcha/                   # 验证码
│   └── utils/
├── migrations/                    # Alembic 迁移
└── tests/
```

---

## 代码注释与文档字符串

本仓库对**新增**注释的要求与前端一致：**禁止单语注释**（只写中文或只写英文均违规），须在同一说明中同时体现中文与英文语义。

### 违规与合规

| 情形 | 说明 |
|------|------|
| 违规 | 仅中文、仅英文、或两行各写一种语言但**未形成一条可读的双语说明**（例如上一行全英、下一行全中且互不对应） |
| 合规 | `# 限流：按 IP / Rate limit by IP`、`"""Resolve tenant scope / 解析企业作用域"""`、``TODO: add cache invalidation / TODO：补充缓存失效`` |
| 优先 | 代码已自解释则**不写注释** |

### 写法建议

- **行内注释**：`# 中文 / English` 或 `# English / 中文`
- **Docstring**：首行双语摘要，必要时 body 用中英分段说明复杂行为
- **类型旁备注**（若必须）：同上，避免只写一种语言

### ORM 字段 `comment=`

与 [codegen-spec.md](codegen-spec.md) 一致：可使用 `"中文 / English"` 单字符串，便于 codegen 拆分为 `comment` 与 `comment_en`；若手写模型且无意拆分，仍须满足「字符串内双语」而非单语。

### 例外

- 第三方 LICENSE、vendor 拷贝、机器生成文件头可保持原样
- **存量**单语注释不强制一次性全改；**新写或本次修改到的注释**必须符合双语要求

### 治理方式（禁止批量脚本）

**禁止**用脚本对全仓库做批量替换或机翻批量「修复」注释。请在编辑器中**逐行**补全另一语种，或提交**小范围、已审阅**的 diff。`backend/scripts/bilingual_comment_audit.py` 仅可用于人工对照的清单扫描，**不得**自动改文件。

---

## 类型注解规范

所有后端文件**必须**在文件头部加 `from __future__ import annotations`，避免运行时循环引用报错。

```python
from __future__ import annotations   # 必须放第一行（docstring 后）

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.ai.agent import Agent   # 仅用于类型注解，不产生运行时导入
```

- `from __future__ import annotations` 使所有注解变为字符串（延迟求值），解决循环导入问题
- 只用于类型注解的导入放在 `if TYPE_CHECKING:` 块中
- 运行时需要的导入放在模块顶层（不在 TYPE_CHECKING 块内）

---

## 架构分层

```
请求 → Middleware → Controller → Service → Repository → Model/DB
                        ↓            ↓           ↓
                    Schema       Hooks      QueryParser
```

| 层 | 职责 | 禁止 |
|----|------|------|
| **Controller** | 路由、参数校验、调用 Service、返回响应 | 写业务逻辑 |
| **Service** | 业务逻辑、钩子、事务编排 | 直接操作 DB |
| **Repository** | 数据访问、查询构建 | 写业务判断 |
| **Model** | 表结构定义 | 写查询逻辑 |
| **Schema** | 请求/响应数据结构 | — |

---

## 多企业体系

项目为 SaaS 架构，每层均有企业专用基类：

| 基类 | 企业版 | 区别 |
|------|--------|------|
| `BaseModel` | `TenantModel` | 自动带 `tenant_id` 字段 |
| `BaseRepository` | `TenantRepository` | 查询自动注入 `tenant_id` 过滤 |
| `BaseService` | `TenantService` | 自动获取并注入企业上下文 |
| `BaseController` | `TenantController` | 自动解析企业上下文 |
| — | `GlobalController` | 平台管理员专用，无企业隔离 |

企业识别方式：中间件从 `Host` 请求头解析子域名或自定义域名。

---

## 快速上手：新增一个 CRUD 模块

以「公告（Notice）」为例，展示完整开发流程。

### 1. 模型 `app/models/tenant/notice.py`

```python
from sqlalchemy import Column, String, Text, Boolean, Integer
from app.core.base_model import TenantModel

class Notice(TenantModel):
    title = Column(String(200), nullable=False)
    content = Column(Text, nullable=False)
    is_published = Column(Boolean, default=False)
    sort_order = Column(Integer, default=0)

    __filterable__ = ["id", "title", "is_published", "created_at"]
    __sortable__ = ["created_at", "sort_order"]
    __selectable__ = {
        "label": "title",
        "value": "id",
        "search": ["title"],
    }
```

### 2. Schema `app/schemas/tenant/notice.py`

```python
from typing import Optional
from app.core.base_schema import BaseCreateSchema, BaseUpdateSchema, BaseResponseSchema

class NoticeCreate(BaseCreateSchema):
    title: str
    content: str
    is_published: bool = False

class NoticeUpdate(BaseUpdateSchema):
    title: Optional[str] = None
    content: Optional[str] = None
    is_published: Optional[bool] = None

class NoticeResponse(BaseResponseSchema):
    title: str
    content: str
    is_published: bool
    sort_order: int
```

> Schema 基类说明：
> - `BaseCreateSchema` — 创建请求
> - `BaseUpdateSchema` — 更新请求
> - `BaseResponseSchema` — 通用响应（含 id, created_at, updated_at）
> - `TenantResponseSchema` — 企业级响应（额外含 tenant_id）
> - `PageResponse` — 分页响应泛型

### 3. Repository `app/repositories/tenant/notice_repository.py`

```python
from app.core.base_repository import TenantRepository
from app.models.tenant.notice import Notice

class NoticeRepository(TenantRepository[Notice]):
    model = Notice
```

### 4. Service `app/services/tenant/notice_service.py`

```python
from app.core.base_service import TenantService
from app.models.tenant.notice import Notice
from app.repositories.tenant.notice_repository import NoticeRepository

class NoticeService(TenantService[Notice, NoticeRepository]):
    model = Notice
    repository_class = NoticeRepository
```

### 5. Controller `app/api/tenant/notices.py`

```python
from app.core.base_controller import TenantController
from app.core.deps import DbSession, ActiveTenantAdmin, QueryParams
from app.core.response import success, created, deleted, paginated
from app.rbac.decorators import permission_resource, action_read, action_create, action_update, action_delete
from app.services.tenant.notice_service import NoticeService
from app.schemas.tenant.notice import NoticeCreate, NoticeUpdate, NoticeResponse

@permission_resource("notice")
class NoticeController(TenantController):
    prefix = "/notices"
    tags = ["公告管理"]
    service_class = NoticeService

    def _register_routes(self):

        @self.router.get("")
        @action_read("action.notice.list")
        async def list_notices(db: DbSession, user: ActiveTenantAdmin, query: QueryParams):
            service = self.get_service(db, user.tenant_id)
            items, total = await service.query_list(query)
            return paginated(items=items, total=total, page=query.page, page_size=query.size)

        @self.router.post("")
        @action_create("action.notice.create")
        async def create_notice(data: NoticeCreate, db: DbSession, user: ActiveTenantAdmin):
            service = self.get_service(db, user.tenant_id)
            notice = await service.create(data.model_dump())
            return created(data=NoticeResponse.model_validate(notice))

        @self.router.put("/{notice_id}")
        @action_update("action.notice.update")
        async def update_notice(notice_id: int, data: NoticeUpdate, db: DbSession, user: ActiveTenantAdmin):
            service = self.get_service(db, user.tenant_id)
            notice = await service.update(notice_id, data.model_dump(exclude_unset=True))
            return success(data=NoticeResponse.model_validate(notice))

        @self.router.delete("/{notice_id}")
        @action_delete("action.notice.delete")
        async def delete_notice(notice_id: int, db: DbSession, user: ActiveTenantAdmin):
            service = self.get_service(db, user.tenant_id)
            await service.delete(notice_id)
            return deleted()

        @self.router.get("/select")
        @action_read("action.notice.select")
        async def select_notices(db: DbSession, user: ActiveTenantAdmin, search: str = ""):
            service = self.get_service(db, user.tenant_id)
            response = await service.get_select_options(search=search)
            return success(data=response)

notice_controller = NoticeController()
router = notice_controller.router
```

> **注意**：`TenantController.get_service(db, tenant_id)` 第二参数是 `tenant_id: int`，不是 user 对象。`BaseController.get_service(db)` 只需 db。

### 6. 注册路由

在 `app/main.py` 或对应的路由汇总文件中引入 `router`。

### 7. 生成迁移

```bash
alembic revision --autogenerate -m "add notice table"
# 启动/热重载时会自动执行 alembic upgrade heads，一般无需手动 upgrade
```

---

## 统一响应

所有接口必须使用封装方法，禁止直接返回裸数据。

```python
from app.core.response import success, error, created, updated, deleted, paginated

# 成功响应（200）
success(data=obj)                           # {"code": 0, "message": "success", "data": ...}
created(data=obj)                           # {"code": 0, "message": "创建成功", "data": ...}
updated(data=obj)                           # {"code": 0, "message": "更新成功", "data": ...}
deleted()                                   # {"code": 0, "message": "删除成功"}
paginated(items, total, page, page_size)    # {"code": 0, "data": {"items": [...], "total": N, "page": 1, "page_size": 20}}
no_content()                                # 204

# 错误响应
error(message, code=4000, status_code=400)  # 自定义错误
bad_request(message)                        # 400
unauthorized(message)                       # 401
forbidden(message)                          # 403
not_found(message)                          # 404
validation_error(message, errors=[...])     # 422
server_error(message)                       # 500
```

### 时间序列化规范

- `utc_now()` 只用于 `TIMESTAMP WITHOUT TIME ZONE` 的 naive UTC 列，例如 `BaseModel.created_at` / `updated_at`。
- `DateTime(timezone=True)` / PostgreSQL `timestamptz` 字段必须写入 aware UTC，例如 `datetime.now(timezone.utc)`。
- 手工组装 API dict 时，不要直接对 ORM 时间字段调用 `.isoformat()`；对 naive UTC 值这样做会丢掉 `+00:00`，浏览器会把它当成本地时间解析，上海时区会直接偏 `8` 小时。
- 优先把原始 `datetime` 交给 `success()` / `paginated()` / `created()` / `updated()` 统一序列化；若必须手工转字符串，统一使用 `serialize_datetime_for_api()`。

```python
from datetime import datetime, timezone

from app.core.response import serialize_datetime_for_api, success

# ✅ timestamptz 字段写 aware UTC
record.last_login_at = datetime.now(timezone.utc)

# ✅ 手工响应时走统一序列化
return success(
    data={
        "created_at": record.created_at,
        "last_login_at": record.last_login_at,
        "expires_at": serialize_datetime_for_api(record.expires_at),
    }
)

# ❌ 错误：naive UTC 直接 isoformat，会丢失 +00:00
payload = {"created_at": record.created_at.isoformat()}
```

---

## 查询规范 (JSON:API)

前端通过 URL 参数控制筛选、排序、分页，后端使用 `QueryParams` 依赖自动解析。

### 筛选

```
filter[status]=active              # 等值
filter[name][ilike]=科技            # 模糊（不区分大小写）
filter[created_at][gte]=2025-01-01 # 大于等于
filter[id][in]=1,2,3               # IN 查询
filter[created_at][between]=2025-01-01,2025-12-31
```

支持操作符：`eq` `ne` `lt` `lte` `gt` `gte` `like` `ilike` `in` `between` `isnull` `notnull`

### 排序

```
sort=-created_at,name    # 先按 created_at 降序，再按 name 升序
```

### 分页

```
page[number]=1&page[size]=20
```

模型中通过 `__filterable__` 和 `__sortable__` 声明允许的字段。

---

## 权限体系 (RBAC)

使用装饰器声明权限，启动时自动注册到权限表。

```python
from app.rbac.decorators import permission_resource, action_read, action_create

@permission_resource("notice")       # 资源名
class NoticeController(TenantController):
    ...
    @action_read("action.notice.list")     # 读权限
    @action_create("action.notice.create") # 创建权限
```

快捷装饰器：`@action_read` `@action_create` `@action_update` `@action_delete` `@action_export` `@action_import`

自定义权限：`@permission_action("custom_action_key", "描述")`

特殊装饰器：
- `@public` — 无需认证
- `@auth_only` — 仅需登录，不检查权限

---

## 依赖注入

通过 `app/core/deps.py` 提供的类型别名进行注入：

| 别名 | 说明 |
|------|------|
| `DbSession` | 数据库 AsyncSession |
| `CurrentAdmin` | 当前平台管理员（含未激活） |
| `ActiveAdmin` | 当前活跃平台管理员 |
| `SuperAdmin` | 超级管理员 |
| `CurrentTenantAdmin` | 当前企业管理员（含未激活） |
| `ActiveTenantAdmin` | 当前活跃企业管理员 |
| `TenantOwner` | 企业所有者 |
| `CurrentTenantUser` | 当前企业用户（含未激活） |
| `ActiveTenantUser` | 当前活跃企业用户 |
| `QueryParams` | JSON:API 查询参数 |

```python
async def list_items(db: DbSession, user: ActiveTenantAdmin, query: QueryParams):
    ...
```

---

## 异常处理

统一异常基类 `AppException`，全局异常处理器自动捕获。

```python
from app.exceptions.base import NotFoundException, BusinessException

raise NotFoundException(message=_("error.notice_not_found"))
raise BusinessException(message=_("error.notice_already_published"))
```

| 异常类 | 状态码 | 错误码 |
|--------|--------|--------|
| `ValidationException` | 422 | 4001 |
| `AuthenticationException` | 401 | 4010 |
| `AuthorizationException` | 403 | 4030 |
| `NotFoundException` | 404 | 4040 |
| `ConflictException` | 409 | 4090 |
| `BusinessException` | 422 | 4220 |
| `RateLimitException` | 429 | 4290 |
| `ExternalServiceException` | 502 | 5020 |
| `ServiceUnavailableException` | 503 | 5030 |

---

## 枚举规范

所有状态枚举继承 `LabeledEnum`，支持 i18n 标签。

```python
from app.enums.base import LabeledStrEnum

class NoticeStatus(LabeledStrEnum):
    DRAFT = ("draft", "enum.notice.draft")
    PUBLISHED = ("published", "enum.notice.published")

# 使用
notice.status = NoticeStatus.DRAFT
```

禁止魔法字符串：`status = "draft"` -> `status = NoticeStatus.DRAFT`

---

## 多语言 (i18n)

所有面向用户的文本必须使用翻译函数。

```python
from app.core.i18n import _

raise BusinessException(message=_("error.user_not_found"))
```

翻译文件位于 `app/locales/{lang}/` 目录，JSON 格式，支持嵌套键。

---

## Service 钩子

`BaseService` 提供生命周期钩子，子类重写即可：

```python
class NoticeService(TenantService[Notice, NoticeRepository]):
    model = Notice
    repository_class = NoticeRepository

    def _before_create(self, data: dict):
        """创建前：数据校验、默认值"""
        data["sort_order"] = data.get("sort_order", 0)

    def _after_create(self, instance):
        """创建后：发事件、记日志"""
        pass

    def _before_update(self, id: int, data: dict):
        """更新前"""
        pass

    def _before_delete(self, id: int):
        """删除前：关联检查"""
        pass
```

---

## 远程下拉 (Select)

模型配置 `__selectable__` 后，BaseService 自动提供 `get_select_options()` 方法。

```python
__selectable__ = {
    "label": "title",
    "value": "id",
    "search": ["title"],
    "extra": ["status"],
    "tree": {                         # 可选，树形结构
        "parent_field": "parent_id",
        "order_by": "sort_order",
    },
}
```

API 端点：`GET /select?search=xxx&tree=false&page=0&page_size=20`

---

## 排序 API

对需要拖拽排序的资源，提供 reorder 端点：

```
PUT /reorder
Body: { "ids": [3, 1, 5, 2, 4], "parent_id": 1 }
```

后端自动按步长 1000 重新分配 `sort_order`。

---

## 存储

平台托管模式下，文件路径规范：

```
{tenant_id}/{YYYY}/{MM}/{DD}/{uuid}{suffix}
```

存储驱动抽象为 `StorageDriver`，支持本地和对象存储（S3/OSS）。

---

## 日志

日志按模块分文件，通过 `LogManager` 获取：

| 类别 | 文件 | 用途 |
|------|------|------|
| app | `logs/app.log` | 通用 |
| error | `logs/error.log` | 错误汇总 |
| db | `logs/db.log` | SQL 日志 |
| auth | `logs/auth.log` | 认证 |
| storage | `logs/storage.log` | 存储操作 |
| task | `logs/task.log` | 异步任务 |
| queue | `logs/queue.log` | 消息队列 |
| captcha | `logs/captcha.log` | 验证码 |
| impersonate | `logs/impersonate.log` | 模拟登录 |

Service 中使用日志：

```python
from app.core.logging import LogManager

logger = LogManager.get_logger("auth")
logger.info("User login success", extra={"user_id": user.id})
```

---

## 中间件注册顺序

FastAPI 的 `add_middleware` 是栈式的——**后注册的先执行**。当前主干 `backend/app/main.py` 的中间件栈不是旧版的“CORS 最外层 + Tenant 最内层”简化模型，而是包含 `NoCacheAPIMiddleware`、`MaintenanceMiddleware` 与最外层 `TraceIdMiddleware` 的实际运行顺序。

```python
# main.py 当前中间件注册（后注册 = 先执行）
app.add_middleware(NoCacheAPIMiddleware)
app.add_middleware(I18nMiddleware)
app.add_middleware(MaintenanceMiddleware)
app.add_middleware(PermissionMiddleware)
app.add_middleware(AuditLogMiddleware)
app.add_middleware(AccessControlMiddleware)
app.add_middleware(TenantMiddleware)
app.add_middleware(CORSMiddleware, ...)
app.add_middleware(TraceIdMiddleware)
```

请求处理顺序：

```
Request → TraceId → CORS → Tenant → AccessControl → AuditLog → Permission → Maintenance → I18n → NoCache → Route
```

> **注意**：如果 CORS 不在最外层，preflight OPTIONS 请求会被内层中间件拦截，导致浏览器报跨域错误。

---

> **注意**：当前主干为了动态子域名 / 自定义域名场景，确实使用 `allow_origins=["*"]` + `allow_credentials=True`。审计或改造时应以运行时代码为准，不要沿用旧文档把这套配置直接判成错误；若未来调整 CORS 策略，必须同步验证 tenant / user 域名链路。

## Health Check

```
GET /api/public/health    # @public，无需认证
```

- 检查 DB（`SELECT 1`）+ Redis（`ping`）
- 200 `{status:'ok', timestamp, checks:{db,redis}}` 或 503 `{status:'error'}`
- 文件：`app/api/public/health.py`，注册于 `app/api/public/__init__.py`

---

## IP 速率限制

```python
from app.core.rate_limit import login_limiter, captcha_limiter, IPRateLimiter

# 在端点中使用
rate_resp = login_limiter.check(request)
if rate_resp:
    return rate_resp  # 429 Too Many Requests
```

| 实例 | 限制 | 用途 |
|------|------|------|
| `login_limiter` | 10 req/min/IP | admin/tenant 登录 |
| `captcha_limiter` | 20 req/min/IP | 验证码端点 |

自定义：`IPRateLimiter(max_requests=30, window_seconds=60)`

超限返回 429 `{error, code: 4290, retry_after}`。内存滑动窗口，5 分钟周期清理过期 IP。

---

## ConfigService 内存缓存

`app/configs/service.py` 对配置读取使用进程级 TTL 缓存：

| 缓存 | TTL | 用途 |
|------|-----|------|
| `_config_id_cache` | 300s | key → config_id 映射（极少变动） |
| `_config_value_cache` | 60s | tenant_id:key → 配置值 |

- 读取时先查缓存，命中直接返回，未命中查 DB 并写入缓存
- 写入时（`_set_config_value`）立即 `pop` 失效缓存
- 无需手动管理，自动过期

---

## 开发检查清单

- [ ] 模型继承 `BaseModel` 或 `TenantModel`
- [ ] 声明 `__filterable__`、`__sortable__`、`__selectable__`
- [ ] Repository 继承 `BaseRepository` 或 `TenantRepository`
- [ ] Service 继承 `BaseService` / `TenantService` / `GlobalService`
- [ ] Controller 继承对应基类，声明 `@permission_resource`
- [ ] 所有接口使用统一响应方法
- [ ] 面向用户文本使用 `_()`
- [ ] 枚举使用 `LabeledEnum`，禁止魔法字符串
- [ ] 生成并执行 Alembic 迁移
- [ ] 敏感信息通过环境变量配置
- [ ] 新 Service 有对应 `tests/services/test_{name}.py`
- [ ] 公开敏感端点有 `IPRateLimiter` 保护
