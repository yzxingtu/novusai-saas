# 后端开发指南

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
│   │   ├── tenant/                # 租户管理 /tenant/*
│   │   ├── public/                # 公开接口 /api/public/*
│   │   └── v1/                    # 业务 API  /api/v1/*
│   ├── services/                  # 业务逻辑
│   │   ├── common/                # 跨域共享服务
│   │   ├── system/                # 平台级服务
│   │   └── tenant/                # 租户级服务
│   ├── repositories/              # 数据访问层
│   │   ├── system/
│   │   └── tenant/
│   ├── models/                    # ORM 模型
│   │   ├── auth/                  # 角色、权限
│   │   ├── system/                # 管理员、配置、操作日志
│   │   └── tenant/                # 租户、附件、套餐、域名
│   ├── schemas/                   # Pydantic Schema
│   │   ├── common/                # 通用（查询、选项、排序）
│   │   ├── public/
│   │   ├── system/
│   │   └── tenant/
│   ├── enums/                     # 枚举（LabeledEnum 基类）
│   ├── exceptions/                # 异常体系
│   ├── middleware/                 # 中间件
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

## 多租户体系

项目为 SaaS 架构，每层均有租户专用基类：

| 基类 | 租户版 | 区别 |
|------|--------|------|
| `BaseModel` | `TenantModel` | 自动带 `tenant_id` 字段 |
| `BaseRepository` | `TenantRepository` | 查询自动注入 `tenant_id` 过滤 |
| `BaseService` | `TenantService` | 自动获取并注入租户上下文 |
| `BaseController` | `TenantController` | 自动解析租户上下文 |
| — | `GlobalController` | 平台管理员专用，无租户隔离 |

租户识别方式：中间件从 `Host` 请求头解析子域名或自定义域名。

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
from fastapi import Depends
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
            service = self.get_service(db, user)
            items, total = await service.query_list(query)
            return paginated(items=items, total=total, query=query, schema=NoticeResponse)

        @self.router.post("")
        @action_create("action.notice.create")
        async def create_notice(data: NoticeCreate, db: DbSession, user: ActiveTenantAdmin):
            service = self.get_service(db, user)
            notice = await service.create(data.model_dump())
            return created(data=NoticeResponse.model_validate(notice))

        @self.router.put("/{notice_id}")
        @action_update("action.notice.update")
        async def update_notice(notice_id: int, data: NoticeUpdate, db: DbSession, user: ActiveTenantAdmin):
            service = self.get_service(db, user)
            notice = await service.update(notice_id, data.model_dump(exclude_unset=True))
            return success(data=NoticeResponse.model_validate(notice))

        @self.router.delete("/{notice_id}")
        @action_delete("action.notice.delete")
        async def delete_notice(notice_id: int, db: DbSession, user: ActiveTenantAdmin):
            service = self.get_service(db, user)
            await service.delete(notice_id)
            return deleted()

        @self.router.get("/select")
        @action_read("action.notice.select")
        async def select_notices(db: DbSession, user: ActiveTenantAdmin, search: str = ""):
            service = self.get_service(db, user)
            response = await service.get_select_options(search=search)
            return success(data=response)

notice_controller = NoticeController()
router = notice_controller.router
```

### 6. 注册路由

在 `app/main.py` 或对应的路由汇总文件中引入 `router`。

### 7. 生成迁移

```bash
alembic revision --autogenerate -m "add notice table"
alembic upgrade head
```

---

## 统一响应

所有接口必须使用封装方法，禁止直接返回裸数据。

```python
from app.core.response import success, error, created, updated, deleted, paginated

success(data=obj)                       # {"code": 0, "message": "success", "data": ...}
created(data=obj)                       # {"code": 0, "message": "创建成功", "data": ...}
deleted()                               # {"code": 0, "message": "删除成功"}
paginated(items, total, query, schema)  # {"code": 0, "data": {"items": [...], "total": N, ...}}

bad_request(message)                    # 400
unauthorized(message)                   # 401
forbidden(message)                      # 403
not_found(message)                      # 404
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

快捷装饰器：`@action_read` `@action_create` `@action_update` `@action_delete`

特殊装饰器：
- `@public` — 无需认证
- `@auth_only` — 仅需登录，不检查权限

---

## 依赖注入

通过 `app/core/deps.py` 提供的类型别名进行注入：

| 别名 | 说明 |
|------|------|
| `DbSession` | 数据库 Session |
| `ActiveAdmin` | 当前活跃平台管理员 |
| `SuperAdmin` | 超级管理员 |
| `ActiveTenantAdmin` | 当前活跃租户管理员 |
| `ActiveTenantUser` | 当前活跃租户用户 |
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
| `ValidationException` | 400 | 4001 |
| `AuthenticationException` | 401 | 4010 |
| `AuthorizationException` | 403 | 4030 |
| `NotFoundException` | 404 | 4040 |
| `ConflictException` | 409 | 4090 |
| `BusinessException` | 422 | 4220 |
| `RateLimitException` | 429 | 4290 |

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
