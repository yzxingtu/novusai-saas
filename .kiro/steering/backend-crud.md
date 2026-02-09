---
inclusion: fileMatch
fileMatchPattern: 'backend/**/*.py'
---

# 后端 CRUD 开发完整指南

## 新增 CRUD 模块步骤

以「公告（Notice）」为例，**严格按以下 7 步执行**：

### Step 1: Model (`app/models/tenant/notice.py`)

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

必须声明 `__filterable__`、`__sortable__`。需要下拉时声明 `__selectable__`。

### Step 2: Schema (`app/schemas/tenant/notice.py`)

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

Schema 基类：`BaseCreateSchema` / `BaseUpdateSchema` / `BaseResponseSchema`（含 id, created_at, updated_at）/ `TenantResponseSchema`（额外含 tenant_id）/ `PageResponse`（分页泛型）

### Step 3: Repository (`app/repositories/tenant/notice_repository.py`)

```python
from app.core.base_repository import TenantRepository
from app.models.tenant.notice import Notice

class NoticeRepository(TenantRepository[Notice]):
    model = Notice
```

### Step 4: Service (`app/services/tenant/notice_service.py`)

```python
from app.core.base_service import TenantService
from app.models.tenant.notice import Notice
from app.repositories.tenant.notice_repository import NoticeRepository

class NoticeService(TenantService[Notice, NoticeRepository]):
    model = Notice
    repository_class = NoticeRepository
```

可重写钩子：`_before_create` / `_after_create` / `_before_update` / `_before_delete`

### Step 5: Controller (`app/api/tenant/notices.py`)

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

notice_controller = NoticeController()
router = notice_controller.router
```

关键注意：
- `TenantController.get_service(db, tenant_id)` — 第二参数是 `int`
- `BaseController.get_service(db)` — 只需 `db`
- `query.size` 不是 `query.page_size`

### Step 6: 注册路由

在 `app/main.py` 或对应路由汇总文件引入 `router`。

### Step 7: 生成迁移

```bash
alembic revision --autogenerate -m "add notice table"
alembic upgrade head
```

---

## 统一响应

```python
from app.core.response import success, error, created, updated, deleted, paginated

success(data=obj)                         # {"code": 0, "message": "success", "data": ...}
created(data=obj)                         # 创建成功
updated(data=obj)                         # 更新成功
deleted()                                 # 删除成功
paginated(items, total, page, page_size)  # 分页响应
no_content()                              # 204
bad_request(message)                      # 400
unauthorized(message)                     # 401
forbidden(message)                        # 403
not_found(message)                        # 404
validation_error(message, errors=[])      # 422
server_error(message)                     # 500
```

---

## 异常体系

```python
from app.exceptions.base import NotFoundException, BusinessException
from app.core.i18n import _

raise NotFoundException(message=_("error.notice_not_found"))
raise BusinessException(message=_("error.notice_already_published"))
```

| 异常 | HTTP | 错误码 |
|------|------|--------|
| `ValidationException` | 422 | 4001 |
| `AuthenticationException` | 401 | 4010 |
| `AuthorizationException` | 403 | 4030 |
| `NotFoundException` | 404 | 4040 |
| `ConflictException` | 409 | 4090 |
| `BusinessException` | 422 | 4220 |
| `RateLimitException` | 429 | 4290 |

---

## 依赖注入

| 别名 | 说明 |
|------|------|
| `DbSession` | AsyncSession |
| `ActiveAdmin` | 活跃平台管理员 |
| `SuperAdmin` | 超级管理员 |
| `ActiveTenantAdmin` | 活跃租户管理员 |
| `TenantOwner` | 租户所有者 |
| `ActiveTenantUser` | 活跃租户用户 |
| `QueryParams` | JSON:API 查询参数（含 page / size / filters / sorts） |

---

## 权限装饰器

```python
@permission_resource("resource_name")    # 类级：资源名
@action_read("i18n.key")                 # 读
@action_create("i18n.key")               # 创建
@action_update("i18n.key")               # 更新
@action_delete("i18n.key")               # 删除
@action_export("i18n.key")               # 导出
@action_import("i18n.key")               # 导入
@public                                   # 公开，无需认证
@auth_only                                # 仅需登录
```

---

## 枚举规范

```python
from app.enums.base import LabeledStrEnum

class NoticeStatus(LabeledStrEnum):
    DRAFT = ("draft", "enum.notice.draft")
    PUBLISHED = ("published", "enum.notice.published")
```

---

## Service 钩子

```python
class NoticeService(TenantService[Notice, NoticeRepository]):
    model = Notice
    repository_class = NoticeRepository

    def _before_create(self, data: dict):
        data["sort_order"] = data.get("sort_order", 0)

    def _after_create(self, instance):
        pass

    def _before_update(self, id: int, data: dict):
        pass

    def _before_delete(self, id: int):
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
    "tree": {
        "parent_field": "parent_id",
        "order_by": "sort_order",
    },
}
```

---

## 日志

```python
from app.core.logging import LogManager
logger = LogManager.get_logger("auth")  # app/error/db/auth/storage/task/queue/captcha/impersonate
```

---

## 开发检查清单

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
