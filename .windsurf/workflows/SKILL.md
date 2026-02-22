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
2. 查阅 `references/platform-infrastructure.md` 了解多租户隔离、认证注入、异常抛出方式
3. 查阅 `references/backend-spec.md` 或 `references/frontend-spec.md` 获取完整开发规范
4. 确认相关模块是否已有类似实现，复用已有组件和模式

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

## 二、多租户体系

### 租户识别

TenantMiddleware（`middleware/tenant.py`）从 Host 头自动解析租户：子域名匹配 `{code}.{TENANT_DOMAIN_SUFFIX}`，否则按自定义域名查 `TenantDomain`。结果存入 `request.state.tenant_ctx`（类型 `TenantContext`）。

### 四层自动隔离

| 层 | 基类 | 隔离方式 |
|----|----|----------|
| Model | `TenantModel` | 自动添加 `tenant_id` 字段 + 索引 |
| Repository | `TenantRepository` | 所有查询自动注入 `WHERE tenant_id = ?` |
| Service | `TenantService` | 构造函数接收 `tenant_id`，传递给 Repository |
| Controller | `TenantController` | 从 JWT / request.state 中提取 `tenant_id` |

**关键规则**：
- 租户数据**必须**用 `TenantModel` 全套，**禁止**手动拼接 `tenant_id`
- 平台全局数据用 `BaseModel` / `BaseRepository` / `BaseService` / `GlobalController`

### 获取当前租户

```python
# TenantController 中自动可用，无需手动获取
# 非 TenantController 场景：
from app.middleware.tenant import get_tenant_context, get_current_tenant
tenant_ctx = get_tenant_context(request)  # TenantContext
tenant = get_current_tenant(request)      # Tenant | None
```

完整规范 → `references/platform-infrastructure.md` §一

---

## 三、认证与依赖注入

### 三端 Token 分离

| 端点 | 依赖类型 | 说明 |
|------|---------|------|
| admin | `CurrentAdmin` | 平台管理员（必须登录，否则 401） |
| tenant | `CurrentTenantAdmin` | 租户管理员 |
| user | `CurrentUser` | 终端用户 |

可选版本：`OptionalAdmin` / `OptionalTenantAdmin` / `OptionalUser`（未登录返回 None）

### Controller 中使用

```python
# GlobalController（admin 端）
async def list(self, request: Request, db: DbSession, admin: CurrentAdmin):
    # admin.id / admin.is_superadmin

# TenantController（tenant 端）
async def list(self, request: Request, db: DbSession, tenant_admin: CurrentTenantAdmin):
    # tenant_admin.id / tenant_admin.tenant_id
```

### 前端 Token 自动选择

`multi-auth store` 根据 URL 前缀自动选择 Token：`/admin/*` → admin Token，`/tenant/*` → tenant Token，`/user/*` → user Token。开发者无需手动传。

完整规范 → `references/platform-infrastructure.md` §二

---

## 四、异常体系

### 异常层级

```
AppException (500)
├── ValidationException (422)     # 参数校验
├── NotFoundException (404)       # 资源不存在
├── AuthenticationException (401) # 未认证
├── PermissionDeniedException (403) # 无权限
├── ConflictException (409)       # 资源冲突
├── RateLimitException (429)      # 频率限制
├── BusinessException (400)       # 通用业务错误
└── StorageError (500)           # 存储错误
```

### Service 层抛异常

```python
from app.exceptions import NotFoundException, ConflictException, BusinessException
raise NotFoundException(_("item.not_found"))
raise ConflictException(_("item.name_exists"))
raise BusinessException(_("item.is_locked"))
```

**规则**：Service 抛异常，Controller **不要**捕获（全局处理器自动转 JSON）。消息必须用 `_()`。

完整规范 → `references/platform-infrastructure.md` §三

---

## 五、日志系统

### 分类日志器

| 分类 | 文件 | Mixin |
|------|------|-------|
| `app` | `logs/app.log` | `LoggerMixin`（默认） |
| `error` | `logs/error.log` | — |
| `auth` | `logs/auth.log` | `AuthLoggerMixin` |
| `storage` | `logs/storage.log` | `StorageLoggerMixin` |
| `task` | `logs/task.log` | `TaskLoggerMixin` |
| `queue` | `logs/queue.log` | `QueueLoggerMixin` |
| `db` | `logs/db.log` | `DbLoggerMixin` |

### 使用方式

```python
# 方式 1: 便捷函数（通用场景）
from app.core.logging import get_logger
logger = get_logger(__name__)

# 方式 2: Service 中用 Mixin（推荐）
class MyService(TenantService, StorageLoggerMixin):
    async def upload(self):
        self.logger.info("Uploading...")  # → 写入 storage.log
```

**规则**：禁止 `print()`，禁止在日志中记录密码/Token/API Key。

完整规范 → `references/platform-infrastructure.md` §四

---

## 六、SSE 流式请求（前端）

```typescript
// POST SSE（AI 对话常用）
await requestClient.postSSE('/tenant/agents/1/chat/stream',
    { message: "Hello", conversation_id: 123 },
    {
        onMessage: (chunk) => { /* 处理流式数据 */ },
        onEnd: () => { /* 完成 */ },
        onError: (err) => { /* 出错 */ },
        abortController: new AbortController(),  // 停止生成
    }
);

// 取消请求
controller.abort();
```

Token 根据 URL 前缀自动注入，无需手动传。

完整规范 → `references/platform-infrastructure.md` §五

---

## 七、应用启动流程

`main.py` lifespan 启动 6 步：

```
1. init_logging()          → 日志系统
2. init_database()         → 创建库 + alembic upgrade head + 验证连接
3. sync_permissions()      → 扫描 Controller 权限 → 同步到 permissions 表
4. sync_config_to_db()     → ConfigRegistry → 同步到 system_configs 表
5. RedisManager.init()     → Redis 连接池
6. verify_celery()         → Celery 连通性检测（失败不阻塞）
```

新增初始化服务：在 lifespan 的 Redis 之后添加 `await MyService.init()`，yield 之前 `await MyService.close()`。

完整规范 → `references/platform-infrastructure.md` §六

---

## 八、上传与存储系统

### 核心原则

**所有文件上传必须通过统一的附件系统（Attachment）完成，禁止自建上传逻辑。**

### 后端上传链路

```
Controller (UploadFile)
  → AttachmentService.upload_file()
    → FileValidator（扩展名 + 大小）
    → QuotaService（租户配额）
    → _save_to_temp() → MD5 哈希去重
    → StorageDriver.put() → Attachment 落库
```

| 层 | 文件 | 职责 |
|---|------|------|
| Controller | `api/admin/attachments.py` / `api/tenant/attachments.py` | 接收 UploadFile，调 Service |
| Service | `services/tenant/attachment_service.py` | 上传+配额+去重+分片 |
| Service | `services/system/attachment_service.py` | 平台端上传（跨租户，无配额限制） |
| Validator | `services/common/file_validator.py` | 文件类型/大小验证（平台+租户两级配置） |
| Storage | `app/storage/manager.py` | 驱动注册表（单例），`register_driver` / `get_driver` |
| Task | `tasks/upload_cleanup.py` | 分片上传临时文件清理（Celery Beat，每 6h） |

### 后端使用方式

```python
# 租户端上传（自动配额检查 + 去重）
service = AttachmentService(db, tenant_id)
result = await service.upload_file(
    content=file.file,
    filename=file.filename,
    file_size=file.size,
    mime_type=file.content_type,
    visibility=AttachmentVisibility.PRIVATE,
    source=AttachmentSource.TENANT_ADMIN,
    uploader_id=admin.id,
    business_type="knowledge_document",  # 业务分类
    business_id=kb_id,                   # 关联业务 ID
)
# result = { "attachment": Attachment, "url": str, "used_bytes": int }
```

### 前端统一组件（禁止新建）

| 组件 | 用途 | 使用方式 |
|------|------|----------|
| `FilePicker` | 通用文件选择+上传（Modal 弹窗，支持网格/列表/拖拽/分片/并发） | `<FilePickerModal @select="handleSelect" />` |
| `ImageUpload` | 图片上传（内联，v-model 绑定 URL） | `<ImageUpload v-model="form.avatar" upload-url="/tenant/attachments/upload" />` |
| `smartUploadFile` | 程序化智能上传（≤10MB 普通 / >10MB 自动分片） | `await smartUploadFile({ file, business_type })` |

#### smartUploadFile 使用

```typescript
import { smartUploadFile } from '#/api/tenant/attachment';

const result = await smartUploadFile(
  { file: myFile, visibility: 'private', business_type: 'avatar' },
  (progress) => console.warn('progress:', progress.percent),
);
// result.attachment — AttachmentInfoRaw（后端原始格式）
// result.url — 访问 URL
// result.used_bytes — 已用存储
```

#### 图片显示（附件 ID → 可访问 URL）

工具文件：`utils/image.ts`（文档 ID: 258）

| 函数 | 参数 | 用途 |
|------|------|------|
| `getProcessedImageUrl(id, options?)` | 附件 ID (number) | 只有 ID 时生成图片 URL，支持 preset/width/height/quality/format |
| `getAttachmentUrl(attachment, options?)` | 附件对象 (含 id/driver/path/baseUrl) | 有完整附件对象时使用，自动区分 local/远程驱动 |

```typescript
import { getProcessedImageUrl, getAttachmentUrl } from '#/utils/image';

// 场景 1：只有附件 ID（如系统配置存储的 site_logo = "10"）
const logoUrl = getProcessedImageUrl(10);
// → http://127.0.0.1:8000/api/public/attachments/10/image

// 场景 2：需要缩略图/指定尺寸
const thumbUrl = getProcessedImageUrl(10, { preset: 'thumb' });
// → .../10/image?p=thumb
const customUrl = getProcessedImageUrl(10, { width: 200, height: 200, format: 'webp', quality: 80 });
// → .../10/image?w=200&h=200&f=webp&q=80

// 场景 3：有完整附件对象（如列表页的 AttachmentInfo）
const url = getAttachmentUrl(row, { preset: 'medium' });
// local driver → /api/public/attachments/{id}/image?p=medium
// 远程 driver → {baseUrl}/{path}（直接拼接外部 URL）
```

**预设尺寸**：`thumb` | `small` | `medium` | `large` | `preview` | `avatar` | `banner`

**注意**：配置项（如 `site_logo`）存储的是附件 ID 字符串，在 `api/public/config.ts` 的 `transformPlatformConfig` / `transformTenantConfig` 中已通过 `attachmentIdToUrl()` 自动转换为图片 URL。

### 前端 API 层

| 端 | 文件 | 关键导出 |
|----|------|----------|
| tenant | `api/tenant/attachment.ts` | `uploadAttachmentApi` / `smartUploadFile` / `initChunkUploadApi` / `completeChunkUploadApi` |
| admin | `api/admin/attachment.ts` | `uploadAttachmentApi` / `getAttachmentListApi` / `getAttachmentStatsApi` |

### 禁止事项

- ❌ 禁止新建上传组件（必须复用 `FilePicker` / `ImageUpload`）
- ❌ 禁止直接 `requestClient.upload('/xxx/upload')`（必须通过 `smartUploadFile` 或 `uploadAttachmentApi`）
- ❌ 禁止绕过 FileValidator 直接写入存储
- ❌ 禁止硬编码存储路径（Service 自动生成 `{tenant_id}/{date}/{uuid}.ext`）

### 存储驱动与插件扩展

当前内置驱动：`LocalDriver`（本地）、`S3Driver`（S3 兼容）、`OssDriver`（阿里云 OSS）。

#### StoragePlugin 插件对接链路

```
1. 开发者编写插件：继承 StoragePlugin + StorageDriver
2. 安装插件 → PluginManager.install()
3. 启用插件 → PluginManager.enable_platform()
   → PluginLoader 实例化插件类
   → resolve_plugin_type() 识别为 STORAGE 类型
   → ExtensionRegistry.register()
     → instance.get_driver_name()  → "cos"
     → instance.get_driver_class() → CosStorageDriver
     → storage_manager.register_driver(CosStorageDriver)
   → 系统配置页面可选 driver="cos"
4. 用户在系统配置中选择新驱动 + 填写配置
5. AttachmentService → storage_manager.get_driver(config) → CosStorageDriver 实例
6. 禁用插件 → ExtensionRegistry.unregister()
   → storage_manager.unregister_driver("cos")
```

#### 编写 StoragePlugin 示例

```python
# my_cos_plugin/plugin.py
from app.plugins.extensions.storage_plugin import StoragePlugin

class TencentCosPlugin(StoragePlugin):
    @property
    def name(self) -> str:
        return "novusai-tencent-cos"

    @property
    def display_name(self) -> str:
        return "Tencent Cloud COS"

    @property
    def version(self) -> str:
        return "1.0.0"

    def get_driver_name(self) -> str:
        return "cos"

    def get_driver_class(self):
        from .cos_driver import CosStorageDriver
        return CosStorageDriver

    def get_config_schema(self) -> dict:
        return {
            "secret_id": {"type": "string", "required": True, "description": "SecretId"},
            "secret_key": {"type": "string", "required": True, "sensitive": True},
            "bucket": {"type": "string", "required": True},
            "region": {"type": "string", "required": True, "default": "ap-guangzhou"},
        }

    async def test_connection(self, config: dict) -> bool:
        driver = self.get_driver_class()(StorageConfig(driver="cos", root_path="", options=config))
        return await driver.exists("__test__")
```

#### 编写 StorageDriver 示例

```python
# my_cos_plugin/cos_driver.py
from app.storage.base import StorageDriver, UploadResult, StorageVisibility

class CosStorageDriver(StorageDriver):
    name = "cos"
    display_name = "Tencent COS"

    def __init__(self, config):
        super().__init__(config)
        # 从 config.options 读取 secret_id/secret_key/bucket/region
        # 初始化 COS SDK 客户端

    async def put(self, path, content, mime_type=None, visibility=StorageVisibility.PRIVATE, metadata=None) -> UploadResult:
        # 上传到 COS → 返回 UploadResult

    async def get(self, path):
        # 从 COS 下载

    async def delete(self, path) -> bool:
        # 从 COS 删除

    async def exists(self, path) -> bool:
        # 检查 COS 对象是否存在

    async def get_url(self, path, expires=3600, visibility=None) -> str:
        # 生成预签名 URL

    def get_base_url(self) -> str:
        # 返回 COS bucket 公开访问 URL 前缀
```

#### StoragePlugin 接口方法

| 方法 | 必实现 | 说明 |
|------|--------|------|
| `get_driver_name()` | ✅ | 驱动标识（如 `"cos"` / `"qiniu"` / `"minio"`） |
| `get_driver_class()` | ✅ | 返回 StorageDriver 子类 |
| `get_config_schema()` | 可选 | 配置项 Schema（前端动态渲染表单，`sensitive=True` 字段加密） |
| `get_default_config()` | 可选 | 默认配置 |
| `validate_config(config)` | 可选 | 配置验证，返回错误列表 |
| `test_connection(config)` | 可选 | 连接测试 |

### 关键文件索引

| 文件 | 说明 |
|------|------|
| `backend/app/storage/manager.py` | StorageManager 单例（`register_driver` / `unregister_driver` / `get_available_drivers`） |
| `backend/app/storage/base.py` | StorageDriver 抽象基类 / StorageConfig / UploadResult |
| `backend/app/plugins/extensions/storage_plugin.py` | StoragePlugin 插件扩展点抽象类 |
| `backend/app/plugins/extension_registry.py` | 插件启用时自动注册驱动到 StorageManager |
| `backend/app/services/tenant/attachment_service.py` | 租户端上传 Service（配额+去重+分片） |
| `backend/app/tasks/upload_cleanup.py` | 分片上传临时文件清理 Celery 任务 |
| `frontend/.../api/tenant/attachment.ts` | 租户端上传 API（含 smartUploadFile） |
| `frontend/.../components/business/file-picker/FilePicker.vue` | 通用文件选择+上传组件 |
| `frontend/.../components/business/image-upload/ImageUpload.vue` | 图片上传组件 |

完整规则详见 → `.windsurf/rules/ai-architecture.md` §十一

---

## 九、配置系统

混合模式：代码定义（`ConfigMeta` + `ConfigGroupMeta`）→ 注册到 `ConfigRegistry` → 启动时同步到 `system_configs` 表 → 运行时从 DB 读取。

```python
# 读取配置
config_service = ConfigService(db)
value = await config_service.get_value("site_name")
```

作用域：`PLATFORM`（全平台）/ `TENANT`（租户级）

完整规范 → `references/platform-infrastructure.md` §八

---

## 十、前端业务组件

15 个可复用组件（`components/business/`）：

| 组件 | 用途 |
|------|------|
| `ApiSelect` | 远程数据下拉选择器 |
| `CronPicker` | Cron 可视化选择器 |
| `FilePicker` | 文件选择器（集成附件管理） |
| `FilePreview` | 文件预览器（图片/PDF/视频） |
| `ImageUpload` | 图片上传（裁剪/预览） |
| `ConfigForm` | 系统配置表单（根据 ConfigMeta 动态渲染） |
| `PermissionSelector` | 权限选择器（树形勾选） |
| `OrgTree` | 组织架构树 |
| `MemberPanel` | 成员管理面板 |
| `RoleTree` | 角色树形选择器 |
| `IconPicker` / `Captcha` / `ConfigImagePicker` / `OrgNodeDialog` / `PermissionPreview` | 其他 |

### useCrudDrawer 用法

```typescript
const { Drawer, isEdit, openNew, openEdit } = useCrudDrawer<T>({
    formApi, schema: useFormSchema, fields: ['name', 'status'],
    apiPath: '/tenant/agents', onSuccess: () => emits('success'),
});
```

完整组件清单 + useCrudDrawer 详解 → `references/platform-infrastructure.md` §九

---

## 十一、后端开发流程

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
7. **生成迁移** — CRUD Generator 自动生成 Alembic 迁移脚本到 `migrations/versions/crud/`；手动模块用 `alembic revision --autogenerate -m "xxx"` + 注册到 `models/__init__.py` 和 `migrations/env.py`（启动时自动 upgrade）

### 菜单权限系统（新模块必读）

菜单分两层：**目录菜单**（父级分组）和**叶子菜单**（Controller 声明）。

**添加新菜单分组的步骤**：
1. 在 `backend/app/rbac/menus/admin_menus.py` 或 `tenant_menus.py` 添加 `PermissionMeta` 目录定义（无 `component` 字段 = 目录节点）
2. 在 Controller 的 `@permission_resource` 中使用 `MenuConfig(parent="分组标识")` 引用
3. 前端 i18n 添加 `menu.{scope}.{分组标识}` 翻译
4. 前端路由添加父级路由节点

**`parent` 解析规则**：`parent="ai_mgmt"` → 装饰器自动拼接为 `menu:{scope}.ai_mgmt` → 查找目录菜单的 `code`

完整机制（含目录菜单模板、叶子菜单模板、无菜单 Controller、启动同步流程） → `references/backend-crud.md` §菜单权限系统

关键注意：
- `TenantController.get_service(db, tenant_id)` — 第二参数是 `int`
- `BaseController.get_service(db)` — 只需 `db`
- 分页用 `query.size` 不是 `query.page_size`

完整代码示例、响应方法、异常表、依赖注入、权限装饰器、中间件顺序、枚举、日志 → `references/backend-crud.md`

### 数据库启动自动迁移

系统启动时 `main.py` → `init_database()` 自动执行三步：

1. **检查/创建数据库** — 连接 `postgres` 默认库，检查目标库是否存在，不存在则自动创建
2. **运行迁移** — 读取 `alembic.ini`，执行 `alembic upgrade head`，自动应用所有未执行的迁移
3. **验证连接** — 异步连接目标库执行 `SELECT 1` 验证

> **开发者无需手动 `alembic upgrade head`**，应用启动即自动执行。只需生成迁移文件即可。

### 迁移文件开发规范

```bash
# 1. 生成迁移文件（在 backend/ 目录下）
cd backend
alembic revision --autogenerate -m "add_xxx_table"

# 2. 检查生成的迁移文件（backend/migrations/versions/xxx.py）
#    确认 upgrade() 和 downgrade() 逻辑正确

# 3. 启动应用即自动执行迁移，无需手动 upgrade
```

**关键注意**：

- **新增 Model 必须注册到两个地方**：
  1. `backend/app/models/__init__.py` — 添加 import 和 `__all__` 导出
  2. `backend/migrations/env.py` — 添加 import（确保 Alembic 发现新表）
- 迁移文件命名模板：`{year}{month}{day}_{rev}_{slug}.py`
- `env.py` 中 `target_metadata = Base.metadata`，所有 Model 必须继承 `Base`
- 同步引擎 `DATABASE_URL_SYNC`（`postgresql://`）用于 Alembic，异步引擎 `DATABASE_URL`（`postgresql+asyncpg://`）用于应用

### CRUD 生成器迁移规则（重要）

**禁止任何途径直接 CREATE TABLE**。所有建表操作必须通过 Alembic 迁移脚本。

| 入口 | 正确做法 | 禁止做法 |
|------|----------|----------|
| 可视化向导 | 生成 Alembic migration `.py` 文件 | 生成 DDL / 直接建表 |
| CLI `generate` | 输出 migration 文件到 `migrations/versions/` | 执行 CREATE TABLE |
| AI 智能体 | Skill 输出 migration 脚本 | 输出 DDL 预览 |

**原因**：
1. 直接建表会断裂 Alembic 迁移链，后续新增字段无法通过迁移管理
2. 后端热重载自动执行 `alembic upgrade head`，迁移链外的表不受管理
3. 生产部署依赖迁移链的完整性进行增量升级

**已实现**（里程碑 M119/#389 — 已完成）：
- `migration.py.j2` 模板 → `generator.generate_migration()` 生成建表迁移脚本
- `migration_alter.py.j2` 模板 → `generator.generate_incremental_migration()` 生成增量迁移脚本（add_column / alter_column / drop_column）
- 迁移脚本输出到 `backend/migrations/versions/crud/` 子目录
- `alembic.ini` + `env.py` 已配置 multi-directory version_locations
- Writer 白名单已包含 `backend/migrations/versions/crud/`
- CLI `generate --down-revision` 生成建表迁移；CLI `migrate --old-config --new-config` 生成增量迁移
- AI Toolkit 已添加 `generate_migration` 和 `generate_incremental_migration` 工具
- 前端预览 DDL tab 已替换为 Migration tab

### CRUD 生成器插件化规则（重要）

**CRUD Generator（可视化向导 + CLI）不是系统核心功能，必须作为可选插件提供。**

系统核心不应包含 CRUD Generator 代码。该功能通过插件体系（`ApiPlugin` + `SkillPlugin`）动态加载：

| 组件 | 当前位置（待迁移） | 目标位置 |
|------|---------------------|----------|
| 后端引擎 | `app/codegen/` (11 .py + 14 .j2) | `app/plugins/crud-generator/codegen/` |
| 后端 API | `app/api/admin/dev_crud*.py` | 插件 `get_router()` 动态路由 |
| CLI | `python -m app.codegen.cli` | 插件 CLI 命令 |
| AI 技能 | 迁移种子数据绑定 | `SkillPlugin` 生命周期自动装配 |
| 前端页面 | `views/admin/dev/crud-generator/` (35+ 文件) | 插件前端包 + 动态路由注册 |
| i18n | 核心 `admin/dev.json` | 插件自有 locale |

**当前状态**（待重构 — 里程碑 M120/#390）：
- 后端 + 前端代码深度耦合在核心中
- 前端插件页面注册机制尚不存在（需先设计）
- 系统智能体通过迁移种子数据绑定（需改为 SkillPlugin 生命周期）

### 数据库会话获取方式

| 场景 | 方法 | 类型 |
|------|------|------|
| FastAPI 路由依赖注入 | `db: AsyncSession = Depends(get_db)` | 异步 |
| Service/非路由上下文 | `async with get_db_context() as db:` | 异步 |
| Celery Worker 内 | `self.get_db_session()` | 同步 |

---

## 十二、前端开发流程

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

## 十三、前后端协作约定

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

## 十四、检查清单

### 后端提交前检查

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

## 十五、异步任务与定时任务

本项目使用 **Celery + Redis** 实现异步任务和定时任务（P1-1 已完成）。

### 快速参考

- 任务必须使用 `@register_task` 装饰器，禁止直接用 `@celery_app.task`
- 基类选择：平台任务 → `BaseTask`，租户任务 → `TenantTask`（自动隔离）
- Celery Worker 是同步进程，用 `self.get_db_session()` 获取同步 Session
- 4 个队列：`default` / `high_priority` / `ai_gateway` / `scheduled`
- 定时任务支持三种范围：`platform` / `tenant` / `all_tenants`
- 前端 CronPicker 组件：`<CronPicker v-model="form.cron_expression" />`

完整规范、代码模板、检查清单 → `references/async-tasks.md`

---

## 十六、文档规范（DevGenius MCP）

### 强制要求

每个里程碑的功能开发完成后，**必须**编写使用文档并保存到 DevGenius MCP。

### 文档结构模板

所有功能使用文档遵循统一结构：

```
# {模块名} - 使用指南

## 一、功能概述        → 模块做什么、支持哪些能力
## 二、核心组件        → 文件结构、关键类/组件/枚举
## 三、使用方法        → 代码示例、配置说明、API 端点
## 四、启动与运维      → 环境变量、部署命令、注意事项
## 五、前端功能        → 页面路径、组件用法、交互说明
## 六、最佳实践        → 编写规范、选择指南、错误处理
## 七、故障排查        → 常见问题、日志查看、手动操作
```

### 文档分类

| 分类代码 | 名称 | 用途 |
|----------|------|------|
| `usage_guide` | 功能使用指南 | 已完成模块的使用文档 |
| `architecture` | 技术架构 | 架构设计、代码分析 |
| `api_spec` | API 设计 | 接口设计文档 |
| `guidelines` | 开发规范 | 编码规范、Git 规范 |
| `database` | 数据库设计 | 表结构、数据模型 |

### 写入流程

```
1. search_documents(query="模块关键词")     → 检查是否已存在
2. 不存在 → create_document(title, content, category="usage_guide")
3. 已存在 → update_document_by_id(document_id, content)
```

### Skill 同步规则

当新模块包含可复用的开发规范（如基类、装饰器、组件用法）时：
1. 在 `references/` 目录创建对应的 `.md` 参考文件
2. 在 `SKILL.md` 添加该章节的快速参考
3. 在参考文件列表中注册

---

## 十七、DevGenius MCP 标准工作流

本项目通过 DevGenius MCP 管理任务和文档（集成名称：`devgenius-quanzhan`）。

核心流程：`认领任务 → 查文档 → 开发 → 写文档 → 更新状态`

详细工具用法、流程图、速查表见 → `references/devgenius-workflow.md`

---

## 十八、AI 模块开发

### ⚠️ 核心架构原则：Agent→Skill 全链路（强制）

**所有 AI 功能必须通过 Agent 调度 Skill 完成，禁止直接调用 AIGateway。**

```
外部请求 → Agent.run() → Skill.execute() → AIGateway → LLM Provider
```

- ❌ 禁止在 Controller/Service 层直接实例化 `AIGateway` 发起 LLM 调用
- ❌ 禁止新增绕过 Agent→Skill 链路的 AI 端点
- ❌ 禁止在非 engine 层代码中 `from app.ai.gateway import AIGateway`
- ✅ Agent engine 内部的 LLM 调用（`conversation.py` / `base.py` / `task.py`）— 属于 Agent 实现层
- ✅ `AIGateway.test_model` — 仅限模型连通性测试，不用于业务功能

### 技能（Skill）体系规则

- **技能包（SkillPackage）是一级管理单元**，技能必须归属于某个技能包
- **前端统一入口**：`/admin/ai/skill-packages` 和 `/tenant/ai/skill-packages` 为唯一技能管理入口
- **禁止独立技能路由**：不允许存在独立的 `/admin/ai/skills` 或 `/tenant/ai/skills` 页面
- 技能包详情页内嵌技能 CRUD，技能表单自动继承当前包的 `package_id`

### 技能类型（SkillTypeEnum）

| 类型 | 说明 | Executor |
|------|------|----------|
| `toolkit` | Python 工具包（Tools 类） | ToolkitExecutor |
| `knowledge_base` | 知识库检索（RAG） | 无（RAG 注入 system_prompt） |
| `data_intelligence` | 数据智能（Text-to-SQL + CRUD） | TextToSQLExecutor |
| `builtin` | 内置函数 | BuiltinToolExecutor |

未知类型走插件解析路径（PluginExecutor）。

**Toolkit 技能（toolkit 类型）**：
- 编写 Python 源码，定义 `Tools` 类，每个公开方法自动映射为一个 LLM 可调用工具
- 字段：`toolkit_content`（Text）存储 Python 源码，`toolkit_meta`（JSON）存储解析结果
- 支持 Valves 配置：通过 `valves_schema` 动态渲染配置表单
- 前端编辑器：Monaco Editor + 实时解析预览 + ZIP 上传

### 系统 Agent 与系统 Skill

- 系统级 Agent/Skill 标记 `is_system=True`，不可删除/禁用
- 通过 seed migration 创建，scope=admin, tenant_id=NULL
- 前端管理页面中系统记录有特殊标识且操作受限

### 新增 AI 功能标准流程

```
1. 定义 Skill 类型（如已有类型可复用则跳过）
2. 新增 SkillTypeEnum 枚举值 + i18n
3. 实现 Executor（继承 BaseToolExecutor）
4. 在 resolver.py 注册类型→Executor 映射
5. 创建 Skill 记录（可通过 migration 或 API）
6. 将 Skill 绑定到 Agent（AgentSkillBinding）
7. 通过 Agent 对话或 Agent.run() 触发 Skill
```

**禁止跳过步骤直接调用 AIGateway 实现 AI 功能。**

### 架构概览

AI 模块提供三大核心能力：**Chat 对话**、**Text-to-SQL 数据查询**、**RAG 文档问答**。

```
Engine(Dispatcher → Conversation/Task/Batch)
  → Gateway(RateLimit + Quota + Cache + Failover + Adapters)
  → Tools(Registry + Security + Sandbox + Executors)
  → RAG(Parser → Chunker → Embedding → Retriever → Reranker → ContextBuilder)
  → DataIntelligence(SchemaProvider → TextToSQL → SQLSafety → TenantIsolation → Executor)
```

### 关键目录

| 目录 | 内容 |
|------|------|
| `backend/app/ai/engine/` | 执行引擎（dispatcher, conversation, task, batch） |
| `backend/app/ai/gateway.py` | AI 网关（仅由 Executor/Engine 内部调用） |
| `backend/app/ai/tools/executors/` | Skill 执行器（每个技能类型一个 Executor） |
| `backend/app/ai/skills/resolver.py` | 技能类型→Executor 注册映射 |
| `backend/app/ai/rag/` | RAG 管线（parser, chunker, embedding, retriever, reranker, context_builder） |
| `backend/app/ai/data_intelligence/` | 数据智能（text_to_sql, sql_safety, tenant_isolation, action_executor） |
| `backend/app/ai/events/` | 事件系统（types, bus, hooks） |
| `frontend/.../views/tenant/ai/` | 租户端 AI 页面（chat, agents, skill-packages, knowledge-bases 等） |
| `frontend/.../views/admin/ai/` | 管理端 AI 页面（providers, models, skill-packages, api-keys 等） |

### 新增 AI Provider 适配器

1. 创建 `backend/app/ai/adapters/my_provider.py`，继承 `BaseAdapter`
2. 实现 `chat()` / `chat_stream()` / `embedding()` 方法
3. 在 `adapters/__init__.py` 的 `ADAPTER_MAP` 注册

### 新增 RAG 分块策略

1. 在 `backend/app/ai/rag/chunker.py` 添加 `MyChunker(BaseChunker)`
2. 在 `get_chunker()` 工厂函数注册
3. 在 `enums/knowledge_base.py` 的 `ChunkStrategyEnum` 添加枚举值

### AI 模块枚举

| 枚举 | 文件 | 用途 |
|------|------|------|
| `AgentStatusEnum` | `enums/agent.py` | draft/published/disabled |
| `SkillTypeEnum` | `enums/agent.py` | toolkit/knowledge_base/data_intelligence/builtin |
| `DocumentStatusEnum` | `enums/knowledge_base.py` | pending/parsing/chunking/embedding/completed/error |
| `SearchModeEnum` | `enums/knowledge_base.py` | hybrid/vector/keyword |
| `RewriteStrategyEnum` | `enums/knowledge_base.py` | none/multi/hyde |

### SSE 对话流程

```
POST /tenant/ai/agent-chat/{agent_id}/chat/stream
  → Dispatcher → ConversationEngine
  → 渲染 prompt（变量注入 + RAG 上下文）
  → Gateway.chat_stream()（SSE 流式）
  → 工具调用循环（Tool Registry → Executor → 结果回传 LLM）
  → 前端 requestClient.postSSE() 接收
```

### AI 模块安全层

1. **SSRF 防护** — `tools/security.py` 拦截内网地址
2. **SQL 注入防护** — `tools/security.py` 验证 SQL 安全
3. **租户隔离** — `data_intelligence/tenant_isolation.py` 自动注入 `WHERE tenant_id`
4. **数据脱敏** — `data_intelligence/readonly_executor.py` 屏蔽 PII
5. **操作确认** — `data_intelligence/action_executor.py` 写操作需用户确认

完整架构文档 → MCP 文档 #274「AI Module Architecture」
完整使用指南 → MCP 文档 #275「AI Module Usage Guide」
详细规范 → `references/ai-module.md`
AI 架构规则详细版 → `.windsurf/rules/ai-architecture.md`

---

## 十九、插件开发指南

### 插件体系概述

NovusAI 插件系统支持 **6 种扩展点**，每种对应一个抽象基类：

| 扩展点 | 基类 | 用途 | 示例 |
|--------|------|------|------|
| `AdapterPlugin` | AI 适配器 | 注册新的 LLM Provider（如 Anthropic、Google） | OpenAI Adapter |
| `SkillPlugin` | 技能扩展 | 自动创建 SkillPackage + Skill，Agent 可绑定 | CRUD Generator |
| `StoragePlugin` | 存储驱动 | 注册新的对象存储后端（如 COS、七牛） | Aliyun OSS |
| `ApiPlugin` | API 端点 | 动态挂载 FastAPI 路由到 `/plugins/{name}/` | 自定义 Webhook |
| `HookPlugin` | 事件钩子 | 订阅 EventBus 事件 | 操作通知 |
| `ToolPlugin` | 工具执行器 | 注册 ToolDefinition（已废弃，用 SkillPlugin 替代） | — |

一个插件可以同时继承多个扩展点（`COMPOSITE` 类型）。

### 插件生命周期

```
install → (installed) → enable → (enabled) → disable → (disabled) → uninstall
                                    ↓
                                 upgrade → (enabled, new version)
```

| 钩子 | 触发时机 | 典型用途 |
|------|----------|----------|
| `on_install(ctx)` | 安装时 | 创建数据库表、初始化数据 |
| `on_enable(ctx)` | 启用时 | 注册事件处理器、初始化连接 |
| `on_disable(ctx)` | 禁用时 | 注销事件处理器、释放资源 |
| `on_uninstall(ctx)` | 卸载时 | 清理数据库表、删除文件 |
| `on_upgrade(ctx, from_version)` | 升级时 | 数据迁移、配置兼容 |
| `health_check(ctx)` | 健康检查 | 外部 API 连通性测试 |

### 插件目录结构

```
backend/app/plugins/my_plugin/
├── __init__.py
├── plugin.py          # 插件入口类（继承 BasePlugin + 扩展点）
├── manifest.json      # 插件元数据（name, version, entry_point, frontend）
├── requirements.txt   # Python 依赖（仅白名单内的包）
├── locales/           # i18n 资源
│   ├── zh-CN.json
│   └── en-US.json
├── migrations/        # 插件数据库迁移（可选）
│   └── 001_create_tables.py
└── frontend/          # 前端资源（可选）
    ├── views/
    └── api/
```

### 插件作用域（Scope）

插件通过 `scope` 字段控制在哪些端可见/可用。所有插件控制权归管理端，租户端无插件管理功能。

| Scope | 含义 | 新租户自动绑定 | 租户可见 |
|-------|------|---------------|---------|
| `platform_only` | 仅管理端生效 | ❌ | ❌ |
| `all_tenants` | 所有租户可用（默认） | ✅ | ✅ |
| `assigned_tenants` | 仅管理员分配的租户 | ❌ | 仅白名单 |
| `global` | 全局自动生效 | ✅ | ✅ |

**管理端操作：**
- 平台启用 `scope=global/all_tenants` 的插件 → 自动为所有现存租户创建 `tenant_plugins` 记录
- 平台禁用插件 → 联动禁用所有租户的 `tenant_plugins` 记录
- `scope=assigned_tenants` → 通过 `/admin/plugins/{id}/assign-tenants` API 手动分配

**新租户创建时：** 自动绑定 `scope=global` 和 `scope=all_tenants` 的已启用插件。`assigned_tenants` 需管理员手动分配。

**关联表：** `plugin_tenant_assignments`（scope=assigned_tenants 时记录分配关系，FK 级联删除）。

### manifest.json 示例

```json
{
  "name": "my-awesome-plugin",
  "display_name": "My Awesome Plugin",
  "version": "1.0.0",
  "description": "A plugin that does awesome things",
  "author": "NovusAI Team",
  "scope": "all_tenants",
  "entry_point": "plugin.MyAwesomePlugin",
  "is_system": false,
  "required_permissions": ["db:read", "http:outbound"],
  "frontend": {
    "endpoint": "admin",
    "menus": [
      {
        "code": "my_plugin_page",
        "name": "admin.myPlugin.title",
        "component": "admin/plugins/my-plugin/index",
        "path": "/plugins/my-plugin",
        "icon": "lucide:puzzle",
        "parent": "system_maintenance",
        "sort_order": 80
      }
    ],
    "routes": []
  }
}
```

### 权限声明

插件通过 `required_permissions` 声明所需权限，平台管理员安装时需确认：

| 权限 | 说明 | 注入的能力 |
|------|------|-----------|
| `db:read` / `db:write` | 数据库访问 | `ctx.db` (AsyncSession) |
| `event:subscribe` / `event:publish` | 事件总线 | `ctx.event_bus` (EventBus) |
| `tool:register` | 工具注册 | `ctx.tool_registry` (ToolRegistry) |
| `http:outbound` | 出站 HTTP | 无限制（声明式） |
| `api:register` | API 路由 | 自动挂载路由 |
| `skill:register` | 技能注册 | 自动装配 SkillPackage |
| `storage:register` | 存储驱动 | 注册到 StorageManager |
| `config:read` / `config:write` | 系统配置 | 声明式 |
| `storage:read` / `storage:write` | 文件存储 | 声明式 |

未声明的权限对应能力为 `None`（如未声明 `db:read` 则 `ctx.db` 为 `None`）。

### 开发插件：标准流程

```
1. 在 backend/app/plugins/ 下创建插件目录
2. 编写 plugin.py 继承 BasePlugin + 所需扩展点
3. 编写 manifest.json
4. 实现扩展点必要方法
5. 添加 i18n（locales/ 目录）
6. 测试：启动后在管理端 /admin/system/plugins 安装并启用
7. 前端页面（可选）：放入 frontend/ 目录，manifest 声明路由
```

### 开发 AdapterPlugin（AI 适配器）

```python
from app.plugins.extensions.adapter_plugin import AdapterPlugin

class MyLLMPlugin(AdapterPlugin):
    @property
    def name(self) -> str:
        return "novusai-my-llm"

    @property
    def display_name(self) -> str:
        return "My LLM Provider"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def required_permissions(self) -> list[str]:
        return ["http:outbound"]

    def get_provider_info(self) -> dict:
        return {
            "name": "my_llm",
            "display_name": "My LLM",
            "icon": "lucide:brain",
            "supports_streaming": True,
        }

    def get_adapter_class(self):
        from .adapter import MyLLMAdapter  # 继承 BaseAdapter
        return MyLLMAdapter
```

**对接链路**：`enable → AdapterRegistry.register(provider_type, adapter_class) → AI 模型管理页面可选新 Provider → Gateway 自动路由`

### 开发 SkillPlugin（技能扩展）

```python
from app.plugins.extensions.skill_plugin import SkillPlugin

class MyToolPlugin(SkillPlugin):
    @property
    def name(self) -> str:
        return "novusai-weather-tool"

    @property
    def display_name(self) -> str:
        return "Weather Tool"

    @property
    def version(self) -> str:
        return "1.0.0"

    def get_skill_type(self) -> str:
        return "weather"  # 新的 skill type

    def get_skill_display_name(self) -> str:
        return "Weather Query"

    def get_skill_icon(self) -> str:
        return "lucide:cloud-sun"

    def resolve(self, config: dict) -> list:
        """返回 ToolDefinition 列表"""
        from app.ai.tools.types import ToolDefinition, ToolParameter
        return [ToolDefinition(
            name="get_weather",
            description="Get current weather",
            parameters=[
                ToolParameter(name="city", type="string", required=True),
            ],
            tool_type="plugin",
            config=config,
        )]

    async def execute(self, tool_name: str, arguments: dict, context) -> dict:
        """执行工具调用"""
        city = arguments.get("city", "")
        # ... 调用天气 API ...
        return {"success": True, "output": f"Weather in {city}: Sunny 25°C"}
```

**对接链路**：`enable → SkillPluginProvisioner.provision() 自动创建 SkillPackage + Skill → Agent 可绑定 → PluginExecutor 执行`

### 开发 StoragePlugin（存储驱动）

```python
from app.plugins.extensions.storage_plugin import StoragePlugin

class MinioPlugin(StoragePlugin):
    @property
    def name(self) -> str:
        return "novusai-minio"

    @property
    def display_name(self) -> str:
        return "MinIO Storage"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def required_permissions(self) -> list[str]:
        return ["storage:register"]

    def get_driver_name(self) -> str:
        return "minio"

    def get_driver_class(self):
        from .minio_driver import MinioStorageDriver
        return MinioStorageDriver

    def get_config_schema(self) -> dict:
        return {
            "endpoint": {"type": "string", "required": True},
            "access_key": {"type": "string", "required": True},
            "secret_key": {"type": "string", "required": True, "sensitive": True},
            "bucket": {"type": "string", "required": True},
            "secure": {"type": "boolean", "default": True},
        }
```

**对接链路**：`enable → storage_manager.register_driver(MinioStorageDriver) → 系统配置可选 driver="minio" → AttachmentService 自动使用`

### 开发 ApiPlugin（API 端点）

```python
from fastapi import APIRouter
from app.plugins.extensions.api_plugin import ApiPlugin

class MyApiPlugin(ApiPlugin):
    @property
    def name(self) -> str:
        return "novusai-webhook"

    @property
    def display_name(self) -> str:
        return "Webhook Plugin"

    @property
    def version(self) -> str:
        return "1.0.0"

    def get_router(self) -> APIRouter:
        router = APIRouter()

        @router.post("/receive")
        async def receive_webhook(request):
            # 处理 webhook
            return {"status": "ok"}

        return router

    def get_route_prefix(self) -> str:
        return "/webhook"  # 最终路径: /plugins/novusai-webhook/webhook/receive

    def get_auth_level(self) -> str:
        return "public"  # public / auth_only / admin_only
```

**对接链路**：`enable → PluginRouteManager.mount_plugin_routes() → /plugins/{name}{prefix}/ 可访问 → disable 时自动卸载`

### 开发 HookPlugin（事件钩子）

```python
from app.plugins.extensions.hook_plugin import HookPlugin

class NotifyPlugin(HookPlugin):
    @property
    def name(self) -> str:
        return "novusai-notify"

    @property
    def display_name(self) -> str:
        return "Event Notification"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def required_permissions(self) -> list[str]:
        return ["event:subscribe", "http:outbound"]

    def get_event_handlers(self) -> list[tuple]:
        from app.ai.events.types import AgentChatCompletedEvent
        return [
            (AgentChatCompletedEvent, self._on_chat_completed, 10),
        ]

    async def _on_chat_completed(self, event):
        # 发送通知...
        pass
```

**对接链路**：`enable → EventBus.subscribe(event_type, handler) → 事件触发时自动回调 → disable 时 unsubscribe`

### 敏感配置加密

`config_schema` 中 `"format": "password"` 的字段自动加密存储：

```json
{
  "properties": {
    "api_key": {
      "type": "string",
      "format": "password",
      "title": "API Key"
    }
  }
}
```

- 安装/配置时：`encrypt_sensitive_config()` 加密后以 `enc:` 前缀存储到 DB
- 运行时：`decrypt_sensitive_config()` 自动解密注入 `ctx.config`
- API 返回：`mask_sensitive_config()` 替换为 `******`
- 前端回传 `******`：保留 DB 中原加密值，不覆盖

### 插件检查清单

- [ ] 继承 `BasePlugin` + 所需扩展点
- [ ] 实现 `name` / `display_name` / `version` 三个必要属性
- [ ] `name` 符合 `^[a-z][a-z0-9-]*[a-z0-9]$` 格式
- [ ] `version` 符合 semver 格式
- [ ] `manifest.json` 包含 `name` / `display_name` / `version` / `entry_point`
- [ ] `required_permissions` 仅声明实际需要的权限
- [ ] 敏感配置字段标记 `"format": "password"`
- [ ] i18n 文件放在 `locales/` 目录（zh-CN.json + en-US.json）
- [ ] Python 依赖仅使用白名单内的包（见 `security.py` ALLOWED_PACKAGES）
- [ ] 生命周期钩子中的异常不应冒泡（内部捕获并记录）
- [ ] 前端页面放在 `frontend/views/` 目录，manifest 中声明路由

### 关键文件索引

| 文件 | 说明 |
|------|------|
| `backend/app/plugins/base.py` | BasePlugin 抽象基类（生命周期钩子 + 元数据） |
| `backend/app/plugins/context.py` | PluginContext（运行时上下文：config/db/event_bus/logger） |
| `backend/app/plugins/manager.py` | PluginManager 门面类（install/enable/disable/uninstall/upgrade） |
| `backend/app/plugins/extension_registry.py` | 6 种扩展点的注册/注销 |
| `backend/app/plugins/loader.py` | 动态导入 + 实例缓存 + 类型推断 |
| `backend/app/plugins/discovery.py` | 本地目录扫描 + DB 加载 + 内置插件注册 |
| `backend/app/plugins/security.py` | Manifest 校验 + 加密/解密/脱敏 + 审计日志 + 包白名单 |
| `backend/app/plugins/config_manager.py` | 配置合并 + JSON Schema 校验 + Context 构建 |
| `backend/app/plugins/skill_provisioner.py` | SkillPlugin 自动装配（创建/停用/软删 SkillPackage+Skill） |
| `backend/app/plugins/route_manager.py` | ApiPlugin 路由挂载/卸载（含认证依赖注入） |
| `backend/app/plugins/extensions/` | 6 个扩展点抽象类 |
| `backend/app/enums/plugin.py` | PluginTypeEnum（adapter/tool/hook/api/skill/storage/composite） |
| `backend/app/api/admin/plugins.py` | 管理端 API（安装/卸载/启用/禁用/上传/导出/健康检查） |
| `backend/app/api/tenant/plugins.py` | 租户端 API（可用列表/启用/禁用/配置） |

---

## 二十一、Celery 定时任务开发规范

### 核心原则

**所有定时任务必须通过 `periodic_tasks` 数据库表管理**，禁止在 `celery_app.py` 硬编码 `beat_schedule`。
任务通过 Alembic seed migration 写入 `periodic_tasks` 表，由 `scheduler.py` 在 Beat 启动时从 DB 加载。

### 架构约束

| 约束 | 说明 |
|------|------|
| **禁止 async Redis** | Celery Worker 不走 FastAPI lifespan，`RedisManager` 不会初始化。必须用 `redis.from_url(settings.REDIS_URL)` 同步客户端 |
| **禁止 async DB** | 优先使用 `sync_session_factory()` 同步会话。仅涉及复杂 async Service 时才用 `asyncio.new_event_loop()` + `async_session_factory()` |
| **禁止 logger kwargs** | Python 标准 `logging` 不接受 `error=`/`count=` 等关键字参数，必须用 `logger.info("%s count=%d", msg, val)` 位置参数格式 |
| **禁止 ignore_result** | 所有任务必须返回 `dict` 结果，`BaseTask` 自动写入 `task_logs` 表。`ignore_result=True` 会导致日志无法追溯 |
| **必须指定 queue** | 每个 `@register_task` 必须显式声明 `queue="scheduled"` 或 `queue="default"`。禁止依赖默认队列 |

### 标准写法模板

```python
"""
任务模块说明

注意：Celery Worker 是独立的同步进程，不经过 FastAPI lifespan，
因此 RedisManager 不会被初始化。所有 Redis 操作必须使用同步 redis 客户端。
"""

import redis

from app.core.config import settings
from app.core.database import sync_session_factory
from app.core.i18n import _
from app.core.logging import LogManager
from app.tasks.base import register_task, BaseTask
from app.core.base_model import utc_now

logger = LogManager.get_logger("task")


def _get_sync_redis() -> redis.Redis:
    """获取同步 Redis 客户端（Celery Worker 专用）"""
    return redis.from_url(settings.REDIS_URL, decode_responses=True)


@register_task(
    queue="scheduled",               # 必须指定队列
    description="任务描述（中文）",      # 必须有描述
    max_retries=1,                    # 明确重试次数
)
def my_task(self: BaseTask) -> dict:  # 必须有类型标注 + 返回 dict
    try:
        # 业务逻辑...
        return {"key": "value"}       # 必须返回 dict
    except Exception as e:
        logger.error("%s error=%s", _("task.log.xxx_failed"), str(e))
        return {"error": str(e)}      # 失败也要返回 dict
```

### 注册到 periodic_tasks 表

每个定时任务必须有对应的 Alembic seed migration 将其写入 `periodic_tasks` 表：

```python
# migrations/versions/20260221_seed_xxx_task.py
op.execute(sa.text("""
    INSERT INTO periodic_tasks (
        name, task_path, schedule_type, cron_expression,
        interval_seconds, is_active, description, scope,
        is_locked, is_editable, max_retries, retry_delay, timeout,
        notify_on_failure, created_at, updated_at, is_deleted
    ) VALUES (
        '任务中文名',
        'app.tasks.module.function_name',  -- 必须与函数自动生成名一致
        'interval',                         -- 或 'cron'
        NULL,                               -- cron 表达式（interval 时为 NULL）
        300,                                -- 间隔秒数（cron 时为 NULL）
        true, '描述', 'platform',
        true, false, 1, 60, 3600,
        false, NOW(), NOW(), false
    ) ON CONFLICT DO NOTHING
"""))
```

**关键**：`task_path` 必须与函数的自动命名完全一致（`app.tasks.{module}.{function_name}`），否则 Beat 调度找不到任务。

### 任务文件清单

| 文件 | 队列 | 内容 |
|------|------|------|
| `tasks/scheduled.py` | scheduled | 系统维护任务（健康检查、Redis 清理、日志清理） |
| `tasks/recycle_bin.py` | scheduled | 回收站自动清理 |
| `tasks/upload_cleanup.py` | scheduled | 分片上传临时文件清理 |
| `tasks/ai_health_check.py` | scheduled | AI 供应商健康探测 |
| `tasks/ssl_tasks.py` | default/scheduled | SSL 证书签发/续期/巡检 |
| `tasks/agent_batch.py` | ai_gateway | 智能体批处理 |

### 重试与超时配置（DB 驱动）

`periodic_tasks` 表中的 `max_retries`、`retry_delay`、`timeout` 会被 `BaseTask` 在任务启动时**动态读取并覆盖** Celery 参数。

**优先级**：DB 配置 > `@register_task` 硬编码值 > Celery 默认值

| 字段 | 生效方式 | 说明 |
|------|----------|------|
| `max_retries` | `self.max_retries = db_config["max_retries"]` | 覆盖 Celery 最大重试次数 |
| `retry_delay` | `self.get_retry_countdown()` 返回 DB 值 | 任务函数内调用获取重试间隔 |
| `timeout` | `self.soft_time_limit = db_config["timeout"]` | 覆盖 Celery 软超时 |

任务函数中使用 `self.get_retry_countdown()` 获取重试间隔：

```python
raise self.retry(
    exc=exc,
    countdown=self.get_retry_countdown() * (self.request.retries + 1),
)
```

**注意**：配置在 Worker 进程内按 task_path 缓存，修改 DB 后需**重启 Worker** 才能生效。

### 失败通知机制

`periodic_tasks` 表的 `notify_on_failure` 和 `notify_emails` 字段由 `BaseTask._notify_failure()` 在 `on_failure` 中自动调用。

| 字段 | 说明 |
|------|------|
| `notify_on_failure` | `bool`，是否启用失败通知 |
| `notify_emails` | `str`，逗号分隔的通知邮箱列表 |

**当前已实现**：
- ✅ 日志记录（`logger.warning` 输出通知信息）

**预留接口**：
- ✅ WebSocket 实时推送：`sio_bridge.notify_admins_sync({ type: "task_failure", ... })`（见§二十五）
- 🔲 邮件通知：`send_task_failure_email.delay(emails=..., task_name=..., error=...)`

通知仅在 `on_failure`（任务最终失败）时触发，`on_retry`（重试中）不触发。

### 代码检查清单

- [ ] `@register_task` 有 `queue`、`description`、`max_retries`
- [ ] 函数签名：`def xxx(self: BaseTask, ...) -> dict:`
- [ ] Redis 用 `redis.from_url()` 同步客户端，不用 `RedisManager` / `get_redis_client()`
- [ ] DB 用 `sync_session_factory()`，session 在 finally 中 close
- [ ] logger 用 `"%s key=%d"` 格式化，不用 `key=value` kwargs
- [ ] 返回 `dict`，失败时包含 `"error"` 字段
- [ ] 有对应的 `periodic_tasks` seed migration
- [ ] `task_path` 与函数自动命名一致
- [ ] 重试使用 `self.get_retry_countdown()` 而非硬编码 countdown

---

## 二十二、时间存储与显示规范

### 后端时间存储

| 规则 | 说明 |
|------|------|
| **统一使用 `utc_now()`** | 来自 `app.core.base_model`，返回 naive UTC datetime。**禁止** `datetime.now()`、`datetime.utcnow()` |
| **DB 列类型** | `TIMESTAMP WITHOUT TIME ZONE`，存储 naive UTC |
| **Model default** | `default=utc_now`，不用 `server_default` |
| **Celery 任务** | 同样使用 `utc_now()`，禁止 `datetime.utcnow()` 或 `datetime.now()` |

### 后端时间序列化（base_schema.py）

| 规则 | 说明 |
|------|------|
| **DB → Schema** | `parse_datetime_fields` 将 naive datetime 标记为 `timezone.utc`（因为 DB 存的是 UTC） |
| **前端字符串 → Schema** | `parse_datetime_fields` 将前端输入字符串标记为 `settings.tz`（Asia/Shanghai，因为用户输入是本地时间） |
| **Schema → JSON** | `json_encoders` 使用 `isoformat()` 输出 ISO 8601 格式（含时区偏移 `+00:00`） |

输出示例：`"2026-02-21T05:07:00+00:00"` — 浏览器 `new Date()` 自动转为本地时间。

### 前端时间显示

| 场景 | 函数 | 说明 |
|------|------|------|
| 绝对时间 | `formatDate(val)` | `new Date(val)` 自动处理 `+00:00` 偏移，显示本地时间 |
| 相对时间 | `formatRelativeTime(val)` | 计算与 `Date.now()` 的差值，显示"X 分钟前/后" |
| 仅日期 | `formatDateOnly(val)` | `YYYY-MM-DD` 格式 |
| Tooltip | 绝对时间作为 Tooltip，相对时间作为主显示 | 鼠标悬浮可看完整时间 |

### 禁止事项

```python
# ❌ 禁止
datetime.now()             # 本地时间，不是 UTC
datetime.utcnow()          # 已废弃，返回 naive 且无标记
datetime.now(timezone.utc)  # 返回 aware datetime，与 DB 列类型不兼容

# ✅ 正确
from app.core.base_model import utc_now
utc_now()                   # 返回 naive UTC datetime，与 DB 兼容
```

### 检查清单

- [ ] 所有 `datetime.now()` / `datetime.utcnow()` 替换为 `utc_now()`
- [ ] API 返回的时间字符串包含 `+00:00` 后缀
- [ ] 前端使用 `formatDate()` / `formatRelativeTime()` 显示，不手动格式化
- [ ] Tooltip 显示完整绝对时间，主文本显示相对时间

---

## 二十三、邮件发送规范

### 架构

```
Controller/Service → send_email_task.delay() → Celery Worker → EmailService → SMTP
                                                     ↓
                                              EmailLog（自动记录）
```

- **禁止在 Controller/Service 中直接调用 `EmailService.send()`**（会阻塞请求）
- **所有邮件必须通过 `send_email_task.delay()` 异步发送**
- 唯一例外：管理端测试邮件 API（同步调用，需要实时返回结果）

### 发送方式

```python
# ✅ 异步发送（推荐，所有业务场景）
from app.tasks.email import send_email_task

send_email_task.delay(
    to=["user@example.com"],
    subject="邮件主题",
    html_body="<h1>HTML 内容</h1>",
    text_body="纯文本回退",
    triggered_by="task_failure",  # manual/task_failure/password_reset/test/welcome/ssl_expiry
    tenant_id=tenant_id,          # 可选，关联租户
)
```

### 配置来源

| 配置项 | 存储位置 | 说明 |
|--------|----------|------|
| `email_enabled` | `system_config_values` (平台配置) | 全局开关，False 时静默跳过 |
| `email_smtp_host/port/encryption/username/password` | 同上 | SMTP 服务器参数 |
| `email_from_address/from_name` | 同上 | 发件人信息 |
| `tenant_email_notification` | 同上 (租户配置) | 租户级开关（T11 待实现） |

### 触发来源枚举（triggered_by）

| 值 | 说明 | 模板 |
|----|------|------|
| `manual` | 管理端手动发送 | 用户自定义内容 |
| `test` | 测试邮件 | test_email.html |
| `task_failure` | 定时任务失败通知 | task_failure.html |
| `password_reset` | 密码重置 | password_reset.html |
| `welcome` | 租户创建欢迎邮件 | welcome.html |
| `ssl_expiry` | SSL 证书到期提醒 | ssl_expiry.html |

### 关键文件

| 文件 | 说明 |
|------|------|
| `services/common/email_service.py` | EmailService (async) + send_email_sync (Celery 专用) |
| `tasks/email.py` | send_email_task Celery 任务 |
| `models/system/email_log.py` | EmailLog 发送日志模型 |
| `api/admin/email_logs.py` | 管理端 API（日志列表 + 手动发送 + 测试） |
| `configs/definitions/platform/email.py` | 8 个平台配置项定义 |

### 规则

- 邮件发送失败**不影响主业务流程**（try/except 包裹，仅记录日志）
- 所有邮件自动记录到 `email_logs` 表（成功/失败/触发来源）
- `email_enabled=False` 时静默跳过，不报错
- 邮件内容禁止包含敏感信息（密码明文、Token 等）
- i18n：邮件相关错误消息使用 `email.error.*` key

---

## 二十四、删除依赖保护规范

### 24.1 何时需要声明 `__delete_deps__`

任何 Model 只要有 **其他 Model 通过 FK 引用它**，就必须在被引用方声明 `__delete_deps__`。
声明的是"谁引用了我，删我时怎么办"。

### 24.2 五种策略选择标准

| 策略 | 行为 | 选择标准 | 典型场景 |
|------|------|---------|---------|
| `BLOCK` | 有依赖就拒绝删除 | 子记录有独立业务价值，不应随父消失 | Provider→Model, Model→Agent, Role→Admin |
| `CASCADE_SOFT` | 子记录跟着软删除进回收站 | 子记录依附父记录，父删子也该进回收站 | Provider→ApiKey, Model→Quota, Agent→Conversation |
| `CASCADE_DELETE` | 子记录物理删除 | 子记录是纯关联/绑定，无独立价值 | Agent→SkillBinding |
| `NULLIFY` | FK 字段置 NULL | FK 是可选的引用 | AIModel→fallback_model_id |
| `IGNORE` | 不处理 | 日志/统计类，不影响数据完整性 | CallLog, UsageStat |

### 24.3 声明语法

```python
# backend/app/models/xxx.py
from app.core.deletion import DeletionDep, DeletionStrategy

class MyModel(BaseModel):
    __delete_deps__ = [
        DeletionDep("ChildModel", "parent_id", DeletionStrategy.BLOCK,
                    label_field="name", i18n_key="child_model"),
        DeletionDep("RelatedModel", "my_model_id", DeletionStrategy.CASCADE_SOFT,
                    label_field="id", i18n_key="related_model"),
    ]
```

**参数说明：**
- `model`: 引用本模型的目标模型类名（字符串）
- `fk_field`: 目标模型中的 FK 字段名
- `strategy`: 五种策略之一
- `label_field`: 用于前端展示的字段（默认 `"name"`）
- `i18n_key`: 前端 `common.dependency.model.{i18n_key}` 的翻译 key

### 24.4 前端 DependencyBlockModal

`useCrudPage` 已自动集成：删除被 4221 阻止时自动弹出依赖详情弹窗。

**非 useCrudPage 页面手动使用：**

```vue
<script setup>
import DependencyBlockModal from '#/components/business/dependency-block-modal/index.vue';
const depBlockRef = ref<InstanceType<typeof DependencyBlockModal> | null>(null);

async function onDelete(record) {
  try {
    await requestClient.delete(`/resource/${record.id}`, { showCodeMessage: false });
  } catch (error) {
    const resp = error?.response?.data;
    if (resp?.code === 4221 && resp?.dependencies) {
      depBlockRef.value?.open(resp.dependencies, record.name);
    }
  }
}
</script>
<template>
  <DependencyBlockModal ref="depBlockRef" />
</template>
```

### 24.5 useCrudPage 回收站配置

```typescript
const { Grid } = useCrudPage({
  // ... 其他配置
  recycleBin: true,  // 启用回收站（使用默认配置）
  // 或自定义：
  recycleBin: {
    nameField: 'title',
    columns: [{ title: '标题', dataIndex: 'title', width: 200 }],
  },
});
```

### 24.6 新模块 Checklist

每次新增模块时，按以下清单逐项完成：

- [ ] **Model 声明 `__delete_deps__`** — 分析所有引用此模型的 FK，选择合适策略
- [ ] **Service 验证** — 尝试删除有依赖的记录，确认返回 4221 + 依赖详情
- [ ] **useCrudPage 启用 `recycleBin`** — 列表页配置 `recycleBin: true`
- [ ] **RECYCLABLE_MODELS 注册** — `backend/app/tasks/recycle_bin.py` 添加模型路径，注意顺序（叶子先父后）
- [ ] **总回收站模块注册** — `backend/app/api/admin/recycle_bin.py` 的 `RECYCLABLE_MODULES` 添加条目
- [ ] **i18n 模型名称** — 后端 `deletion.model.xxx` + 前端 `common.dependency.model.xxx`（zh-CN + en-US）

### 24.7 错误码

| 错误码 | 含义 | 前端处理 |
|--------|------|---------|
| 4221 | 删除被依赖阻止 | 弹出 DependencyBlockModal |

---

## 二十五、WebSocket 实时通信（Socket.IO）

### 架构概览

```
前端 socket.io-client → /sio (ASGI) → AsyncServer(Redis Manager) → Namespace(/admin, /tenant, /user)
Celery Worker → sio_bridge(RedisManager write_only) → Redis Pub/Sub → AsyncServer → 前端
```

三端分离 namespace：`/admin`（平台管理员）、`/tenant`（租户管理员）、`/user`（租户业务用户）。

### 关键目录

| 文件 | 说明 |
|------|------|
| `backend/app/core/socketio_server.py` | AsyncServer 单例（Redis Manager 多 Worker 同步） |
| `backend/app/core/sio_bridge.py` | 同步桥接（Celery Worker 中发 Socket.IO 消息） |
| `backend/app/sio/__init__.py` | Namespace 注册 |
| `backend/app/sio/admin_ns.py` | /admin namespace（连接认证、房间管理、在线状态） |
| `backend/app/sio/tenant_ns.py` | /tenant namespace |
| `backend/app/sio/user_ns.py` | /user namespace |
| `backend/app/sio/presence.py` | PresenceManager（Redis Hash + Lua 原子操作） |
| `backend/app/sio/notification_seeds.py` | 32 个通知模板种子数据 |
| `backend/app/api/admin/ws.py` | 在线状态 HTTP API（admin 端） |
| `backend/app/api/tenant/ws.py` | 在线状态 HTTP API（tenant 端） |
| `frontend/.../composables/use-socketio.ts` | Socket.IO 连接 composable |
| `frontend/.../store/shared/socketio.ts` | 全局连接管理 Store |
| `frontend/.../store/shared/notification.ts` | 通知 Store（HTTP + Socket.IO） |
| `frontend/.../store/shared/presence.ts` | 在线状态 Store |

### 后端：Namespace 连接流程

```python
# on_connect 流程（以 admin_ns 为例）：
1. auth.token → Bearer 提取 → verify_token_with_scope(raise_on_expired=True)
2. TokenExpiredError → raise ConnectionRefusedError("token_expired")
3. 无效 Token → raise ConnectionRefusedError("authentication_failed")
4. check_connect_rate（Lua 原子限流，60s/20次）
5. DB 查询用户 → 验证 is_active + is_deleted
6. save_session + _sid_sessions 备份
7. enter_room("user:{user_id}", "admins")
8. PresenceManager.set_online → 首次连接广播 presence:online
9. emit("presence:list", online_ids, to=sid)
```

### 后端：发送通知

```python
# FastAPI 异步环境
from app.core.socketio_server import get_sio
sio = get_sio()
await sio.emit("notification", data, room="user:5", namespace="/admin")

# Celery 同步环境（通过 Redis Pub/Sub 桥接）
from app.core.sio_bridge import notify_user_sync, notify_admins_sync, notify_tenant_sync

notify_user_sync("admin", user_id=5, notification_data={...})
notify_admins_sync(notification_data={...})          # 广播所有管理员
notify_tenant_sync(tenant_id=1, notification_data={...})  # 广播指定租户
```

### 后端：事件与房间

| 事件 | 方向 | 数据 | 说明 |
|------|------|------|------|
| `notification` | S→C | `{type, category, title, body, data, link, priority}` | 通知推送 |
| `presence:online` | S→C | `{user_id, user_type, tenant_id?}` | 用户上线 |
| `presence:offline` | S→C | `{user_id, user_type, tenant_id?}` | 用户下线 |
| `presence:list` | S→C | `{online_ids: number[]}` | 连接时推送在线列表 |
| `tenant_presence:online` | S→C(/admin) | `{user_id, tenant_id}` | 租户管理员上线（跨 namespace） |
| `tenant_presence:offline` | S→C(/admin) | `{user_id, tenant_id}` | 租户管理员下线（跨 namespace） |

| 房间 | Namespace | 说明 |
|------|-----------|------|
| `user:{user_id}` | 全部 | 指定用户的所有设备 |
| `admins` | /admin | 所有平台管理员 |
| `tenant:{tenant_id}` | /tenant, /user | 该租户的所有在线用户 |

### 前端：连接管理

```typescript
// 自动连接（basic.vue onMounted 中调用）
socketIOStore.connect();  // 自动检测 endpoint、从 TokenStorage 读 token

// 手动断开（logout 时调用）
socketIOStore.disconnect();  // 断开 socket + 清理 handlers

// 事件注册（notification/presence store 的 initSocketHandlers 中）
socketIOStore.registerHandler('notification', handler);
socketIOStore.registerHandler('presence:online', handler);
```

**Token 同步机制**：socketio store 使用 getter 函数 `() => TokenStorage.getToken(ep)` 实时读取最新 token。axios 拦截器刷新 token 后 `TokenStorage` 自动更新，Socket.IO 在 `connect_error` 时通过 `getToken()` 读取最新值并自动重连。

### 前端：连接状态 UI

`basic.vue` 中：
- 用户头像旁的绿/黄/灰点表示连接状态
- 断连时显示 warning toast（`duration: 0`），重连后自动销毁
- 登出时不显示断连警告（通过检查 `currentEndpoint` 判断）

### 在线状态 HTTP API

| 端点 | 方法 | 说明 |
|------|------|------|
| `GET /admin/ws/presence` | admin | 所有管理员在线状态 |
| `GET /admin/ws/presence/tenant/{id}` | admin | 指定租户管理员在线状态 |
| `GET /tenant/ws/presence` | tenant | 当前租户管理员在线状态 |

### PresenceManager 存储结构

Redis Hash：`presence:admin` → `{ "5": "2", "8": "1" }`（user_id → 连接数）

- 所有写操作通过 Lua 脚本保证原子性
- Hash 设有 24h TTL，`set_online` 时刷新，防止 worker 崩溃后 stale 数据永久残留
- 启动时 `clear_all()` 清空所有 presence key

### 禁止事项

- ❌ 禁止在 namespace `on_connect` 外发起未认证的 emit
- ❌ 禁止 `async with session` 外访问 ORM 属性（在 session 内提取到局部变量）
- ❌ 禁止手动创建 `io()` 实例，必须通过 `useSocketIO` composable
- ❌ 禁止在 Celery Worker 中 `import get_sio()`（使用 `sio_bridge` 的 `*_sync` 函数）
- ❌ 禁止跨 namespace 直接 emit（通过 `get_sio().emit(namespace="/admin")` 方式）

### 检查清单

- [ ] Namespace 连接认证使用 `raise_on_expired=True` 区分 token 过期和无效
- [ ] DB 属性在 `async with session` 内提取到局部变量
- [ ] 广播使用 `skip_sid=sid` 排除发起者
- [ ] Celery 中用 `sio_bridge` 同步函数，不用 `get_sio()`
- [ ] 前端 handler 通过 `socketIOStore.registerHandler` 注册（非直接 `socket.on`）
- [ ] 登出时调用 `socketIOStore.disconnect()`（自动清理 handlers）
- [ ] 新增事件类型需在 `notification_seeds.py` 添加模板

完整指南 → `.windsurf/workflows/websocket-guide.md`

---

## 二十七、通知系统规范

### 27.1 架构概览

所有业务通知统一走 `NotificationService.send()`，通过渠道驱动层分发到多个渠道。

```
业务代码 → notify(db, template_code, recipients, data)
              │
              ├─ 查模板 → channels: ["ws", "inbox", "email"]
              ├─ 查用户偏好 → {channel_ws: true, channel_email: false}
              │
              └─ CHANNEL_REGISTRY 遍历
                   ├─ InboxChannel  → DB 写入
                   ├─ WSChannel     → Socket.IO emit
                   ├─ EmailChannel  → notification 队列 → send_notification_email
                   └─ WebhookChannel → (预留)
```

### 27.2 调用方式

**异步上下文**（Controller / Service）：
```python
from app.services.common.notification_service import notify

await notify(db, "ai.batch_complete", [("tenant_admin", user_id)], {"total": 500})
```

**同步上下文**（Celery 任务）：
```python
from app.services.common.notification_service import notify_sync

notify_sync("system.task_failure", [("admin", 1)], {"error": str(exc)})
```

**带富文本邮件**：
```python
await notify(db, "system.password_reset", [("tenant_admin", uid)],
    data={"user_name": "张三"},
    email_html=html_body, email_subject="密码重置")
```

### 27.3 模板编码规范

格式：`{category}.{event_name}`

| 分类 | 前缀 | 示例 |
|------|------|------|
| system | `system.` | `system.password_reset`, `system.maintenance` |
| ai | `ai.` | `ai.batch_complete`, `ai.quota_warning` |
| task | `task.` | `task.completed`, `task.failed` |
| biz | `biz.` | `biz.tenant_created`, `biz.plan_changed` |
| audit | `audit.` | `audit.suspicious_login` |

新增模板需在 `sio/notification_seeds.py` 的 `SEED_TEMPLATES` 中添加。

### 27.4 渠道 channels 配置

| 场景 | channels | 说明 |
|------|----------|------|
| 仅实时 | `["ws"]` | AI 对话完成等即时信息 |
| 实时+收件箱 | `["ws", "inbox"]` | 大多数业务通知（默认） |
| 收件箱+邮件 | `["inbox", "email"]` | 重要通知（任务失败、SSL 到期） |
| 仅邮件 | `["email"]` | 密码重置 |
| 全渠道 | `["ws", "inbox", "email"]` | 紧急安全通知 |

### 27.5 渠道启用优先级

```
能否发送 = notification_enabled (总开关)
          AND template.channels 包含该渠道
          AND user_preference 允许该渠道
          AND channel.is_enabled() (渠道自身开关)
```

### 27.6 扩展新渠道

1. 实现 `NotificationChannel` 子类（`channels/` 目录）
2. 在 `channels/__init__.py` 的 `_register_builtin_channels` 中注册
3. 更新需要该渠道的模板 channels 列表
4. `NotificationPreference` 自动支持 `channel_{code}` 偏好

### 27.7 队列规范

- 通知相关邮件走 `notification` 队列（`tasks/notification.py`）
- 手动/测试邮件走 `default` 队列（`tasks/email.py`）
- Worker 启动需监听 notification 队列：`celery -A app.celery_app worker -Q default,notification,...`

### 27.8 禁止事项

- ❌ 业务代码直接 `from app.tasks.email import send_email_task` 发邮件
- ❌ 通知逻辑中硬编码渠道（必须通过模板 channels 配置）
- ❌ 跳过 NotificationService 直接操作 Notification 表
- ✅ 手动发送邮件接口（`/admin/system/email-logs` 发送功能）保留直接调 `send_email_task`

---

## 二十八、参考文件

完整规范详见 references 目录：

- `references/platform-infrastructure.md` — 平台基础设施（多租户/认证/异常/日志/SSE/启动/存储/配置/组件）
- `references/backend-crud.md` — 后端 CRUD 7步完整代码 + 响应/异常/权限/枚举/日志
- `references/frontend-crud.md` — 前端 CRUD 4步完整代码 + 权限/搜索/i18n/图标/请求/命名
- `references/frontend-spec.md` — 前端开发手册完整版（含拖拽排序、列表 UI 设计、CSS 动画等）
- `references/backend-spec.md` — 后端开发指南完整版（含存储、日志、枚举、Service 钩子等）
- `references/async-tasks.md` — 异步任务与定时任务开发规范（Celery/Redis/队列/定时任务）
- `references/devgenius-workflow.md` — DevGenius MCP 工作流详解（工具速查、流程图、文档管理）
- `references/ai-module.md` — AI 模块开发规范（引擎/网关/工具/RAG/数据智能/事件/安全）
