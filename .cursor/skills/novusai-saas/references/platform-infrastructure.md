# 平台基础设施规范

本文档覆盖：多企业体系、认证与依赖注入、异常体系、日志系统、SSE 流式请求、应用启动流程、存储系统、配置系统、前端业务组件。

## 目录

- [一、多企业体系](#一多企业体系)
- [二、认证与依赖注入](#二认证与依赖注入)
- [三、异常体系](#三异常体系)
- [四、日志系统](#四日志系统)
- [五、SSE 流式请求（前端）](#五sse-流式请求前端)
- [六、应用启动流程](#六应用启动流程)
- [七、存储系统](#七存储系统)
- [八、配置系统](#八配置系统)
- [九、前端业务组件清单](#九前端业务组件清单)

---

## 一、多企业体系

### 1.1 企业识别（TenantMiddleware）

中间件位置：`backend/app/middleware/tenant.py`

**工作流程**：每个 HTTP/WebSocket 请求经过 TenantMiddleware 时，从 Host 头解析企业：

1. 提取 Host 头 → 去掉端口号
2. 匹配子域名：`{tenant_code}.{TENANT_DOMAIN_SUFFIX}` → 返回 `(tenant_code, "subdomain")`
3. 不匹配则判为自定义域名 → 返回 `(None, "custom")`
4. 查询数据库：子域名模式按 `Tenant.code` 查询；自定义域名按 `TenantDomain.domain` 查询
5. 将结果存入 `request.state.tenant_ctx`（类型：`TenantContext`）

```python
# TenantContext 关键属性
tenant_ctx.tenant_id     # int | None
tenant_ctx.tenant_code   # str | None
tenant_ctx.tenant        # Tenant | None（完整模型实例）
tenant_ctx.domain_type   # "subdomain" | "custom" | "unknown"
tenant_ctx.is_resolved   # bool（tenant 是否已加载）
```

### 1.2 企业隔离四层体系

| 层 | 基类 | 隔离方式 |
|----|----|----------|
| Model | `TenantModel` | 自动添加 `tenant_id` 字段 + 索引 |
| Repository | `TenantRepository` | 所有查询自动注入 `WHERE tenant_id = ?` |
| Service | `TenantService` | 构造函数接收 `tenant_id`，传递给 Repository |
| Controller | `TenantController` | 从 `request.state.tenant_ctx` 或 JWT 中提取 `tenant_id` |

**关键规则**：
- 企业数据**必须**使用 `TenantModel` / `TenantRepository` / `TenantService` / `TenantController`
- 平台数据（admin 管理的全局数据）使用 `BaseModel` / `BaseRepository` / `BaseService` / `GlobalController`
- **禁止**在 TenantModel 的查询中手动拼接 `tenant_id`，Repository 会自动处理

### 1.3 在代码中获取企业

```python
# Controller 层（推荐）
from app.middleware.tenant import get_tenant_context, get_current_tenant

# 方式 1: TenantController 自动处理，无需手动获取
class MyController(TenantController):
    # self.tenant_id 在路由方法中自动可用
    pass

# 方式 2: 手动获取（非 TenantController 场景）
tenant_ctx = get_tenant_context(request)
tenant = get_current_tenant(request)  # → Tenant | None
```

---

## 二、认证与依赖注入

### 2.1 三端 Token 分离

系统支持三个独立的认证端点，Token 互不干扰：

| 端点 | Token 前缀 | 依赖类型 | 说明 |
|------|-----------|---------|------|
| admin | `admin_` | `CurrentAdmin` | 平台超级管理员 |
| tenant | `tenant_` | `CurrentTenantAdmin` | 企业管理员 |
| user | `user_` | `CurrentUser` | 终端用户 |

JWT Payload 结构：
```python
{
    "sub": str(user_id),          # 用户 ID
    "endpoint": "admin|tenant|user",  # 端点标识
    "iat": timestamp,
    "exp": timestamp,
    # admin 端额外字段：
    "is_superadmin": bool,
    # tenant 端额外字段：
    "tenant_id": int,
}
```

### 2.2 依赖注入清单（deps.py）

```python
from app.core.deps import (
    DbSession,                # AsyncSession 数据库会话
    CurrentAdmin,             # 当前 admin（必须登录，否则 401）
    CurrentTenantAdmin,       # 当前企业管理员（必须登录）
    CurrentUser,              # 当前终端用户（必须登录）
    OptionalAdmin,            # 可选 admin（未登录返回 None）
    OptionalTenantAdmin,      # 可选企业管理员
    OptionalUser,             # 可选终端用户
)
```

**Controller 中使用**：

```python
# GlobalController — admin 端
class RoleController(GlobalController):
    @action_read
    async def list(
        self,
        request: Request,
        db: DbSession,            # 注入数据库会话
        admin: CurrentAdmin,      # 注入当前 admin（自动验证 Token）
    ):
        # admin.id → 当前管理员 ID
        # admin.is_superadmin → 是否超管
        pass

# TenantController — tenant 端
class AgentController(TenantController):
    @action_read
    async def list(
        self,
        request: Request,
        db: DbSession,
        tenant_admin: CurrentTenantAdmin,  # 注入当前企业管理员
    ):
        # tenant_admin.id → 管理员 ID
        # tenant_admin.tenant_id → 企业 ID
        pass
```

### 2.3 前端多端 Token

前端 `multi-auth store` 自动管理三端 Token。请求时根据 URL 前缀自动选择：

| URL 前缀 | 使用的 Token |
|----------|-------------|
| `/admin/*` | admin Token |
| `/tenant/*` | tenant Token |
| `/user/*` | user Token |

开发者无需手动传 Token，`requestClient` 拦截器自动处理。

---

## 三、异常体系

### 3.1 异常层级

```
AppException (HTTP 500)                    # 基类
├── ValidationException (HTTP 422)         # 参数校验失败
├── NotFoundException (HTTP 404)           # 资源不存在
├── AuthenticationException (HTTP 401)     # 未认证
├── PermissionDeniedException (HTTP 403)   # 无权限
├── ConflictException (HTTP 409)           # 资源冲突（如唯一约束）
├── RateLimitException (HTTP 429)          # 频率限制
├── BusinessException (HTTP 400)           # 通用业务错误
└── StorageError (HTTP 500)               # 存储错误
    ├── StorageConfigError                 # 存储配置错误
    └── StorageNotFoundError               # 文件不存在
```

### 3.2 在 Service 层抛异常

```python
from app.exceptions import (
    NotFoundException,
    ValidationException,
    PermissionDeniedException,
    ConflictException,
    BusinessException,
)

class MyService(TenantService):
    async def do_something(self, id: int):
        item = await self.repo.get(id)
        if not item:
            raise NotFoundException(_("item.not_found"))

        if item.status == "locked":
            raise BusinessException(_("item.is_locked"))

        if await self.repo.exists_by_name(item.name):
            raise ConflictException(_("item.name_exists"))
```

### 3.3 异常自动处理

全局异常处理器在 `main.py` 注册，会自动将 `AppException` 转为 JSON 响应：

```json
{
    "success": false,
    "code": 404,
    "message": "资源不存在",
    "data": null
}
```

**规则**：
- Service 层抛 `AppException` 子类，Controller 层**不要**捕获
- 面向用户的错误消息必须使用 `_()` 国际化
- 开发者调试信息放 `detail` 参数（仅 DEBUG 模式返回）

---

## 四、日志系统

### 4.1 日志分类

| 分类 | 文件 | 说明 |
|------|------|------|
| `app` | `logs/app.log` | 应用主日志（默认） |
| `error` | `logs/error.log` | 仅 ERROR 级别以上 |
| `db` | `logs/db.log` | 数据库查询日志（SQLAlchemy 自动重定向） |
| `task` | `logs/task.log` | 定时任务日志 |
| `queue` | `logs/queue.log` | 队列/Celery 日志 |
| `auth` | `logs/auth.log` | 认证/登录日志 |
| `storage` | `logs/storage.log` | 存储操作日志 |
| `captcha` | `logs/captcha.log` | 验证码日志 |
| `impersonate` | `logs/impersonate.log` | 一键登录审计日志 |

### 4.2 使用方式

```python
# 方式 1: 便捷函数（推荐）
from app.core.logging import get_logger
logger = get_logger(__name__)
logger.info("Processing request")

# 方式 2: 分类日志器
from app.core.logging import get_auth_logger, get_storage_logger
auth_logger = get_auth_logger()
auth_logger.info("User login: %s", username)

# 方式 3: LoggerMixin 混入类（推荐用于 Service）
from app.core.logging import LoggerMixin, StorageLoggerMixin
from app.enums.log import LogCategoryEnum

class MyService(TenantService, LoggerMixin):
    _log_category = LogCategoryEnum.AUTH  # 可选：指定分类

    async def process(self):
        self.logger.info("Processing...")  # 自动延迟加载

# 方式 4: 预定义 Mixin（更简洁）
class AttachmentService(TenantService, StorageLoggerMixin):
    async def upload(self):
        self.logger.info("Uploading file...")  # → 写入 storage.log
```

可用的预定义 Mixin：`StorageLoggerMixin` / `AuthLoggerMixin` / `TaskLoggerMixin` / `QueueLoggerMixin` / `CaptchaLoggerMixin` / `DbLoggerMixin` / `ImpersonateLoggerMixin`

### 4.3 日志规范

- 新增模块**必须使用** `get_logger(__name__)` 或 `LoggerMixin`，禁止 `print()`
- 敏感信息（密码/Token/API Key）**禁止**记录到日志
- Service 层用 `self.logger`（通过 `LoggerMixin`），其他位置用 `get_logger(__name__)`
- 选择合适的日志分类：存储操作 → `StorageLoggerMixin`，认证 → `AuthLoggerMixin`

---

## 五、SSE 流式请求（前端）

### 5.1 requestSSE 方法

位置：`frontend/apps/web-antd/src/utils/request/request-client.ts`

```typescript
interface SseRequestOptions {
    method?: string;              // 默认 GET
    headers?: HeadersInit;
    onMessage?: (data: string) => void;    // 接收到数据 chunk
    onEnd?: () => void;                     // 流结束
    onError?: (error: Error) => void;       // 出错
    abortController?: AbortController;      // 取消控制器
}

// GET SSE
await requestClient.requestSSE('/tenant/ai/agent-chat/1/chat/stream', null, {
    onMessage: (chunk) => {
        // chunk 是原始 SSE 文本，需自行解析
        // 格式: "event: message\ndata: {...}\n\n"
    },
    onEnd: () => {
        // 流结束后的 UI 收尾 / Finalize UI state after stream ends
    },
    onError: (err) => console.error(err),
    abortController: controller,
});

// POST SSE（常用于 AI 对话）
await requestClient.postSSE('/tenant/ai/agent-chat/1/chat/stream',
    { message: "Hello", conversation_id: 123 },
    {
        onMessage: (chunk) => { /* 处理流式数据 */ },
        onEnd: () => { /* 完成 */ },
        abortController: new AbortController(),
    }
);
```

### 5.2 取消 SSE 请求

```typescript
const controller = new AbortController();

// 开始请求
requestClient.postSSE(url, data, { abortController: controller, onMessage });

// 用户点击"停止生成"
controller.abort();  // 自动取消，不触发 onError
```

### 5.3 Token 自动注入

`requestSSE` 内部会根据 URL 前缀自动选择对应端点的 Token（与 `requestClient` 一致），无需手动传 Authorization。

---

## 六、应用启动流程

`backend/app/main.py` 的 `lifespan` 函数定义了启动 6 步和关闭 3 步：

### 启动顺序

```
1. init_logging()              → 日志系统初始化（LogManager）
2. init_database()             → 数据库初始化
   ├── check_and_create_db()   → 检查/创建数据库
   ├── alembic upgrade heads   → 执行数据库迁移
   └── 验证异步连接             → SELECT 1
3. sync_permissions()          → 从代码扫描 Controller 权限装饰器 → 同步到 permissions 表
4. sync_config_to_db()         → ConfigRegistry 元数据 → 同步到 system_configs 表
5. RedisManager.init()         → Redis 连接池初始化
6. verify_celery()             → 检测 Celery Worker 连通性（失败不阻塞启动）
```

### 关闭顺序

```
1. RedisManager.close()        → 关闭 Redis 连接池
2. dispose engine              → 关闭数据库引擎
3. logging shutdown
```

### 新增初始化服务

如果需要在启动时初始化新的服务，在 `lifespan` 函数的对应位置添加：

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # ... 现有启动步骤 ...

    # 新增：初始化你的服务（在 Redis 之后）
    await MyService.init()

    yield

    # 新增：关闭你的服务（在 Redis 之前）
    await MyService.close()
```

---

## 七、存储系统

### 7.1 适配器模式

位置：`backend/app/storage/`

```
storage/
  base.py       → StorageDriver 抽象基类 + StorageConfig 配置类
  manager.py    → StorageManager 工厂（根据配置创建驱动实例）
  local.py      → LocalDriver（本地文件系统）
  s3.py         → S3Driver（AWS S3 / MinIO）
  oss.py        → OssDriver（阿里云 OSS）
  cos.py        → CosDriver（腾讯云 COS）
```

### 7.2 StorageDriver 接口

```python
class StorageDriver(ABC):
    async def put(self, path: str, content: bytes, **kwargs) -> str:
        """上传文件，返回存储路径"""

    async def get(self, path: str) -> bytes:
        """获取文件内容"""

    async def delete(self, path: str) -> bool:
        """删除文件"""

    async def exists(self, path: str) -> bool:
        """检查文件是否存在"""

    async def url(self, path: str, expires: int = 3600) -> str:
        """生成临时访问 URL"""

    async def size(self, path: str) -> int:
        """获取文件大小"""
```

### 7.3 使用方式

```python
from app.storage.manager import StorageManager

# 获取当前配置的存储驱动
driver = await StorageManager.get_driver()

# 上传
path = await driver.put("uploads/avatar.png", file_bytes)

# 获取临时 URL
url = await driver.url(path, expires=3600)
```

存储后端通过系统配置（`system_configs` 表）选择，管理端配置页面可切换。

---

## 八、配置系统

### 8.1 混合模式：代码定义 + 数据库存储

```
代码定义（ConfigMeta/ConfigGroupMeta）→ 注册到 ConfigRegistry（单例）
                                        ↓
                              启动时同步到 system_configs 表
                                        ↓
                              运行时从数据库读取值（支持热更新）
```

### 8.2 定义配置项

```python
# backend/app/configs/definitions/platform/general.py

from app.configs.definitions.groups import PLATFORM_GENERAL_GROUP
from app.configs.meta import ConfigMeta, max_length, min_length
from app.enums.config import ConfigScope, ConfigValueType

SITE_NAME = ConfigMeta(
    key="site_name",
    name_key="config.platform.site_name.name",
    description_key="config.platform.site_name.desc",
    scope=ConfigScope.ADMIN_ONLY,
    value_type=ConfigValueType.STRING,
    default_value="NovusAI SaaS",
    is_required=True,
    validation_rules=[
        min_length(1, "validation.min_length"),
        max_length(100, "validation.max_length"),
    ],
    sort_order=10,
)

PLATFORM_GENERAL_GROUP.configs = [SITE_NAME]
```

### 8.3 注册和使用

```python
# 注册（在 backend/app/configs/definitions/__init__.py 中统一导入并 register_all_configs）
from app.configs.definitions import register_all_configs
register_all_configs()

# 读取配置值（在 Service 中）
from app.configs.service import ConfigService
config_service = ConfigService(db)
site_name = await config_service.get_value("site_name")
```

### 8.4 作用域

| 作用域 | 说明 | 管理端点 |
|--------|------|----------|
| `ADMIN_ONLY` | 平台配置 | admin 端管理 |
| `ALL_TENANTS` | 企业级配置（每个企业独立值） | tenant 端管理 |

---

## 九、前端业务组件清单

路径：`frontend/apps/web-antd/src/components/business/`

| 组件 | 目录 | 用途 |
|------|------|------|
| ApiSelect | `api-select/` | 远程数据下拉选择器（异步加载选项） |
| Captcha | `captcha/` | 图片/滑块验证码组件 |
| ConfigForm | `config-form/` | 系统配置表单（根据 ConfigMeta 动态渲染） |
| ConfigImagePicker | `config-image-picker/` | 配置页面的图片选择器 |
| CronPicker | `cron-picker/` | Cron 可视化选择器（快捷预设 + 5次预览） |
| FilePicker | `file-picker/` | 文件选择器（集成附件管理） |
| FilePreview | `file-preview/` | 文件预览器（图片/PDF/视频） |
| IconPicker | `icon-picker/` | 图标选择器 |
| ImageUpload | `image-upload/` | 图片上传（裁剪/预览） |
| MemberPanel | `member-panel/` | 成员管理面板（角色分配） |
| OrgNodeDialog | `org-node-dialog/` | 组织节点选择对话框 |
| OrgTree | `org-tree/` | 组织架构树 |
| PermissionPreview | `permission-preview/` | 权限预览面板 |
| PermissionSelector | `permission-selector/` | 权限选择器（树形勾选） |
| RoleTree | `role-tree/` | 角色树形选择器 |

### useCrudDrawer 用法

位置：`frontend/apps/web-antd/src/composables/use-crud-form.ts`

```typescript
import { useCrudDrawer } from '#/composables/use-crud-form';

// 在表单组件中
const { Drawer, isEdit, openNew, openEdit } = useCrudDrawer<TenantInfo>({
    formApi,                           // useVbenForm 返回的 API
    schema: useFormSchema,             // (isEdit) => FormSchemaItem[]
    fields: ['name', 'contact_name'],  // 自动处理 camelCase ↔ snake_case
    apiPath: '/tenant/agents',         // 自动拼接 POST/PUT URL
    onSuccess: () => emits('success'), // 成功回调
    detailApi: getAgentDetail,         // 编辑时获取完整数据的 API
});

// 调用
openNew();                    // 打开新建抽屉
openEdit(record);             // 打开编辑抽屉
```

关键特性：
- **自动字段映射**：提供 `fields` 数组后，自动处理后端 camelCase → 表单 snake_case
- **防抖提交**：内置 `isSubmitting` 状态，防止重复提交
- **详情 API**：编辑模式可配置 `detailApi` 获取完整数据（而非列表行数据）
- **默认值**：新建模式支持 `defaults` 配置
