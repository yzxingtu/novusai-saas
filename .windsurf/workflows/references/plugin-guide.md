# 插件开发指南

## 一、插件体系概述

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

---

## 二、插件生命周期

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

---

## 三、插件目录结构

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

---

## 四、插件作用域（Scope）

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

---

## 五、manifest.json 示例

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

---

## 六、权限声明

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

---

## 七、各扩展点开发示例

### 7.1 AdapterPlugin（AI 适配器）

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

### 7.2 SkillPlugin（技能扩展）

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

### 7.3 StoragePlugin（存储驱动）

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

### 7.4 ApiPlugin（API 端点）

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

### 7.5 HookPlugin（事件钩子）

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

---

## 八、敏感配置加密

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

---

## 九、开发标准流程

```
1. 在 backend/app/plugins/ 下创建插件目录
2. 编写 plugin.py 继承 BasePlugin + 所需扩展点
3. 编写 manifest.json
4. 实现扩展点必要方法
5. 添加 i18n（locales/ 目录）
6. 测试：启动后在管理端 /admin/system/plugins 安装并启用
7. 前端页面（可选）：放入 frontend/ 目录，manifest 声明路由
```

---

## 十、检查清单

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

---

## 十一、关键文件索引

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
