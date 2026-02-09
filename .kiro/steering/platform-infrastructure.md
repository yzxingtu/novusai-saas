---
inclusion: manual
---

# 平台基础设施规范

## 一、多租户体系

### 租户识别（TenantMiddleware）

中间件从 Host 头解析租户：子域名匹配 `{code}.{TENANT_DOMAIN_SUFFIX}`，否则按自定义域名查 `TenantDomain`。结果存入 `request.state.tenant_ctx`（类型 `TenantContext`）。

### 四层自动隔离

| 层 | 基类 | 隔离方式 |
|----|----|----------|
| Model | `TenantModel` | 自动添加 `tenant_id` 字段 + 索引 |
| Repository | `TenantRepository` | 所有查询自动注入 `WHERE tenant_id = ?` |
| Service | `TenantService` | 构造函数接收 `tenant_id`，传递给 Repository |
| Controller | `TenantController` | 从 JWT / request.state 中提取 `tenant_id` |

规则：租户数据必须用 `TenantModel` 全套，禁止手动拼接 `tenant_id`。平台全局数据用 `BaseModel` 系列。

### 获取当前租户

```python
from app.middleware.tenant import get_tenant_context, get_current_tenant
tenant_ctx = get_tenant_context(request)
tenant = get_current_tenant(request)
```

---

## 二、认证与依赖注入

### 三端 Token 分离

| 端点 | 依赖类型 | 说明 |
|------|---------|------|
| admin | `CurrentAdmin` | 平台管理员 |
| tenant | `CurrentTenantAdmin` | 租户管理员 |
| user | `CurrentUser` | 终端用户 |

可选版本：`OptionalAdmin` / `OptionalTenantAdmin` / `OptionalUser`

前端 Token 按 URL 前缀自动选择：`/admin/*` → admin Token，`/tenant/*` → tenant Token。

---

## 三、异常体系

```
AppException (500)
├── ValidationException (422)
├── NotFoundException (404)
├── AuthenticationException (401)
├── PermissionDeniedException (403)
├── ConflictException (409)
├── RateLimitException (429)
├── BusinessException (400)
└── StorageError (500)
```

Service 抛异常，Controller 不要捕获。消息必须用 `_()`。

---

## 四、日志系统

| 分类 | 文件 | Mixin |
|------|------|-------|
| `app` | `logs/app.log` | `LoggerMixin`（默认） |
| `auth` | `logs/auth.log` | `AuthLoggerMixin` |
| `storage` | `logs/storage.log` | `StorageLoggerMixin` |
| `task` | `logs/task.log` | `TaskLoggerMixin` |
| `db` | `logs/db.log` | `DbLoggerMixin` |

```python
from app.core.logging import get_logger
logger = get_logger(__name__)
```

禁止 `print()`，禁止在日志中记录密码/Token/API Key。

---

## 五、SSE 流式请求（前端）

```typescript
await requestClient.postSSE('/tenant/agents/1/chat/stream',
    { message: "Hello", conversation_id: 123 },
    {
        onMessage: (chunk) => { /* 处理流式数据 */ },
        onEnd: () => { /* 完成 */ },
        abortController: new AbortController(),
    }
);
```

---

## 六、应用启动流程

```
1. init_logging()          → 日志系统
2. init_database()         → 创建库 + alembic upgrade head + 验证连接
3. sync_permissions()      → 扫描 Controller 权限 → 同步到 permissions 表
4. sync_config_to_db()     → ConfigRegistry → 同步到 system_configs 表
5. RedisManager.init()     → Redis 连接池
6. verify_celery()         → Celery 连通性检测
```

---

## 七、存储系统

适配器模式，4 种后端：`LocalDriver` / `S3Driver` / `OssDriver` / `CosDriver`

```python
from app.storage.manager import StorageManager
driver = await StorageManager.get_driver()
path = await driver.put("uploads/avatar.png", file_bytes)
url = await driver.url(path, expires=3600)
```

---

## 八、配置系统

混合模式：代码定义 → 注册到 `ConfigRegistry` → 启动时同步到 `system_configs` 表 → 运行时从 DB 读取。

```python
config_service = ConfigService(db)
value = await config_service.get_value("site_name")
```

---

## 九、前端业务组件

15 个可复用组件（`components/business/`）：ApiSelect、CronPicker、FilePicker、FilePreview、ImageUpload、ConfigForm、PermissionSelector、OrgTree、MemberPanel、RoleTree、IconPicker、Captcha 等。

### useCrudDrawer 用法

```typescript
const { Drawer, isEdit, openNew, openEdit } = useCrudDrawer<T>({
    formApi, schema: useFormSchema, fields: ['name', 'status'],
    apiPath: '/tenant/agents', onSuccess: () => emits('success'),
});
```
