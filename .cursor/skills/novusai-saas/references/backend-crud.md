# 后端 CRUD 开发完整指南

## 目录

- [新增 CRUD 模块步骤](#新增-crud-模块步骤)
- [统一响应](#统一响应)
- [异常体系](#异常体系)
- [依赖注入](#依赖注入)
- [权限装饰器](#权限装饰器)
- [菜单权限系统](#菜单权限系统)
- [中间件顺序](#中间件顺序)
- [枚举规范](#枚举规范)
- [日志](#日志)

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

#### 已退役：`__ai_policy__`

`__ai_policy__`、AI 表策略和 `data_intelligence` 已于 2026-04 退役。
新增或维护 Model 时不要再声明 `__ai_policy__`，也不要设计依赖 `/admin/ai/table-policies` 的链路。

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
from app.rbac.decorators import permission_resource, MenuConfig, action_read, action_create, action_update, action_delete
from app.enums.rbac import PermissionScope
from app.services.tenant.notice_service import NoticeService
from app.schemas.tenant.notice import NoticeCreate, NoticeUpdate, NoticeResponse

@permission_resource(
    resource="notice",
    name="menu.tenant.notice",  # i18n key
    scope=PermissionScope.TENANT,
    menu=MenuConfig(
        icon="lucide:megaphone",
        path="/system-mgmt/notices",
        component="tenant/system-mgmt/notices/index",
        parent="system_mgmt",  # 父菜单资源标识（对应目录菜单的 code 后缀）
        sort_order=10,
    ),
)
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
# 启动/热重载时会自动执行 alembic upgrade heads，一般无需手动 upgrade
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
| `ActiveTenantAdmin` | 活跃企业管理员 |
| `TenantOwner` | 企业所有者 |
| `ActiveTenantUser` | 活跃企业用户 |
| `QueryParams` | JSON:API 查询参数（含 page / size / filters / sorts） |

---

## 权限装饰器

```python
@permission_resource(
    resource="resource_name",              # 资源标识（生成权限码: menu:{scope}.{resource}）
    name="menu.{scope}.{resource}",        # i18n key
    scope=PermissionScope.TENANT,          # ADMIN / TENANT
    menu=MenuConfig(                       # 可选，无则不生成菜单
        icon="lucide:xxx",                 # Lucide 图标
        path="/parent/child",              # 路由路径
        component="scope/parent/child/index",  # 前端组件路径
        parent="parent_resource",          # 父菜单资源标识（对应目录菜单 code 的后缀）
        sort_order=10,                     # 排序（数字越小越靠前）
        hidden=False,                      # True = 仅做权限控制，不显示菜单
    ),
    parent_resource="xxx",                 # 可选，无菜单时操作权限挂载到此父资源下
)
@action_read("i18n.key")                 # 读
@action_create("i18n.key")               # 创建
@action_update("i18n.key")               # 更新
@action_delete("i18n.key")               # 删除
@action_export("i18n.key")               # 导出
@action_import("i18n.key")               # 导入
@public                                   # 公开，无需认证
@auth_only                                # 仅需登录
```

## 菜单权限系统

### 架构概览

菜单分两层：**目录菜单**（父级分组）和**叶子菜单**（实际功能页面）。

```
目录菜单 (admin_menus.py / tenant_menus.py)
├── system (权限管理)
│   ├── organization (叶子，由 roles.py Controller 声明)
│   └── admin_user (叶子，由 admin_users.py Controller 声明)
├── ai_mgmt (AI 网关管理)
│   ├── ai_provider (叶子，由 ai_providers.py Controller 声明)
│   └── ai_model (叶子，由 ai_models.py Controller 声明)
```

### 目录菜单（父级分组）

定义位置：`backend/app/rbac/menus/admin_menus.py` 和 `tenant_menus.py`

```python
# 无 API 端点的纯分组节点，使用 PermissionMeta 直接定义
from app.enums.rbac import PermissionType, PermissionScope
from app.rbac.decorators import PermissionMeta

ADMIN_DIRECTORY_MENUS: list[PermissionMeta] = [
    PermissionMeta(
        code="menu:admin.ai_mgmt",           # 唯一标识，格式: menu:{scope}.{resource}
        name="menu.admin.ai_mgmt",            # i18n key
        type=PermissionType.MENU,
        scope=PermissionScope.ADMIN,
        resource="menu",                       # 固定为 "menu"
        action="admin.ai_mgmt",               # 格式: {scope}.{resource}
        icon="lucide:brain-circuit",           # Lucide 图标
        path="/ai",                            # 路由路径前缀
        sort_order=35,                         # 无 component 字段 = 目录节点
    ),
]
```

**关键规则**：
- 目录菜单**无 `component` 字段**（区别于叶子菜单）
- `code` 格式必须为 `menu:{scope}.{resource}`
- 启动时由 `register_directory_menus()` 注册到 `permission_registry`

### 叶子菜单（Controller 声明）

叶子菜单通过 Controller 的 `@permission_resource` 装饰器自动声明：

```python
@permission_resource(
    resource="ai_provider",
    name="menu.admin.ai_provider",
    scope=PermissionScope.ADMIN,
    menu=MenuConfig(
        icon="lucide:cpu",
        path="/ai/providers",
        component="admin/ai/providers/List",
        parent="ai_mgmt",                     # ← 引用目录菜单的资源标识后缀
        sort_order=10,
    ),
)
class AdminAIProviderController(GlobalController): ...
```

**`parent` 解析规则**：装饰器自动将 `parent="ai_mgmt"` 转换为 `parent_code="menu:admin.ai_mgmt"`（拼接 `menu:{scope}.` 前缀），然后在权限同步时查找对应的目录菜单。

### 无菜单的 Controller

不需要菜单但需要操作权限的 Controller，使用 `parent_resource` 将权限挂载到父资源下：

```python
@permission_resource(
    resource="tenant_domain",
    name="menu.admin.tenant_domain",
    scope=PermissionScope.ADMIN,
    parent_resource="tenant",  # 操作权限挂载到 tenant 菜单下，但不生成菜单项
)
class AdminTenantDomainController(GlobalController): ...
```

### 新增菜单分组步骤

1. 在 `admin_menus.py` / `tenant_menus.py` 添加 `PermissionMeta` 目录定义
2. 在对应 Controller 的 `MenuConfig(parent="新分组标识")` 引用
3. **后端 i18n**：在 `backend/app/locales/{zh_CN,en}/menu.json` 的 `menu.admin` 或 `menu.tenant` 节点下添加菜单翻译
4. **前端 i18n（Fallback 静态路由用）**：在 `frontend/.../locales/langs/{zh-CN,en-US}/{scope}/xxx.json` 添加对应翻译
5. 在前端路由添加父级路由节点（hideInMenu 模式，作为动态路由的 fallback）

### 菜单翻译链路（重要）

后端 `PermissionMeta.name` 和 `@permission_resource.name` 字段存储的是 **i18n key**（如 `menu.admin.ai_mgmt`），**不是最终显示文本**。

翻译发生在**后端 API 返回时**：
1. 数据库中存储 i18n key：`menu.admin.ai_mgmt`
2. `PermissionService._translate_name()` 方法在构建菜单树时自动调用 `_(key)` 翻译
3. 翻译文件位置：`backend/app/locales/{zh_CN,en}/menu.json`
4. 前端收到的 `name` 字段已经是**翻译后的文本**（如 "AI 网关管理"）
5. 前端 `menu-transformer.ts` 将翻译后的 `name` 赋值给 `route.meta.title`

**翻译文件格式**：
```json
// backend/app/locales/zh_CN/menu.json
{
  "menu": {
    "admin": {
      "ai_mgmt": "AI 网关管理",
      "ai_provider": "AI 供应商"
    },
    "tenant": {
      "ai_mgmt": "AI 管理",
      "ai_config": "AI 配置"
    }
  }
}
```

**新增菜单时必须同步更新**：
- `backend/app/locales/zh_CN/menu.json` — 中文翻译
- `backend/app/locales/en/menu.json` — 英文翻译
- 遗漏任何一项会导致菜单显示为 key 的最后一段（如 `ai_mgmt`）

### 启动同步流程

```
1. register_directory_menus() — 注册目录菜单到 permission_registry
2. include_router() — 注册控制器路由，触发 @permission_resource，注册叶子菜单
3. sync_permissions_on_startup() — 拓扑排序 → 父级先入库 → 子级关联 parent_id
```

**注意**：sync 使用 `(code, scope)` 组合作为唯一键。如果数据库中已有旧记录，会更新而非重建。

---

## 中间件顺序

实际注册顺序（后注册先执行）：

```
CORS → I18n → Permission → AuditLog → AccessControl → Tenant
```

请求处理顺序：

```
Request → Tenant → AccessControl → AuditLog → Permission → I18n → Route
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

## 日志

```python
from app.core.logging import LogManager
logger = LogManager.get_logger("auth")  # app/error/db/auth/storage/task/queue/captcha/impersonate
```
