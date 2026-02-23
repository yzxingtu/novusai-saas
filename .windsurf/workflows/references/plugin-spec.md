# 插件系统开发规范（代码验证版）

> 本文档基于 `backend/app/plugins/` 实际代码审计编写，所有路径、类名、方法签名均与代码一致。
> 最后审计时间：2026-02-23

## 一、目录结构

### 1.1 框架代码（平台侧）

```
backend/app/plugins/
├── __init__.py
├── base.py              # PluginBase 抽象基类（5 个生命周期钩子）
├── manifest.py          # plugin.yaml Pydantic Schema（434 行，30+ Schema）
├── loader.py            # PluginLoader（发现/清单/主类/README/i18n）
├── lifecycle.py         # PluginLifecycle（install/enable/disable/uninstall）
├── context.py           # PluginContext 沙箱 + PluginDbProxy
├── context_factory.py   # 版本化 Context 创建
├── registry.py          # ExtensionRegistry 单例（9 种扩展类型）
├── exceptions.py        # 7 个异常类
├── api_dispatcher.py    # 插件 API 统一分发器
├── webhook_dispatcher.py # Webhook 分发器
├── security_scan.py     # AST 安全扫描
├── health.py            # 健康监控（错误追踪 + 自动降级）
├── startup.py           # 启动恢复（restore_enabled_plugins）
├── scope.py             # 作用域可见性判定
├── version_manager.py   # 版本管理（升级/回滚/备份）
├── preview.py           # 安装预览（manifest 分析 + 冲突检测）
├── marketplace.py       # 市场客户端（GitHub/Gitee 双源）
├── update_checker.py    # 更新检查（24h 缓存）
├── crypto.py            # 配置加密/解密
├── license.py           # License 工具
├── backup.py            # 插件备份
└── telemetry.py         # 遥测
```

### 1.2 已安装插件（插件侧）

```
backend/plugins/{plugin-name}/
├── plugin.yaml              # 清单文件（必须）
├── README.md                # 说明文档（推荐）
├── README.zh-CN.md          # 中文说明（可选）
├── backend/
│   ├── __init__.py          # 空文件（必须）
│   ├── main.py              # 入口：PluginBase 子类（必须）
│   ├── skills/              # 技能解析器（按需）
│   │   └── {type}_resolver.py
│   ├── executors/           # 工具执行器（按需）
│   │   └── {type}_executor.py
│   ├── api/                 # 自定义 API handler（按需）
│   └── migrations/
│       └── versions/        # Alembic 迁移文件（按需）
├── frontend/
│   └── dist/                # 前端 UMD 包（按需）
└── locales/
    ├── zh-CN.json           # 中文翻译
    └── en.json              # 英文翻译
```

**关键路径约定**（来自 `loader.py`）：
- 清单文件：`backend/plugins/{name}/plugin.yaml`
- 主入口：`backend/plugins/{name}/backend/main.py`
- 已安装插件根目录：`PLUGINS_DIR = Path(__file__).parent.parent.parent / "plugins"`（即 `backend/plugins/`）

---

## 二、plugin.yaml 完整规范

基于 `manifest.py` 中的 `PluginManifest` Pydantic Schema：

```yaml
# ── 必填字段 ──
name: my-plugin                    # 小写 kebab-case，正则: ^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$
version: "1.0.0"                   # semver 字符串
display_name:                      # I18nText（dict[str, str]）
  zh-CN: "我的插件"
  en: "My Plugin"
scope: all_tenants                 # PluginScopeEnum 值（见下方）

# ── 基本信息（可选）──
description:
  zh-CN: "插件描述"
  en: "Plugin description"
author: "NovusAI"
icon: "lucide:puzzle"              # Iconify 图标名 或图片 URL
icon_color: "#4f46e5"
banner: ""
homepage: "https://example.com"
repository_url: "https://github.com/..."
license: "MIT"
tags: ["editor", "ai"]

# ── 开发者（可选）──
developer:
  name: "开发者"
  email: "dev@example.com"
  url: "https://..."

# ── 能力声明（必须如实声明需要的能力）──
capabilities:
  - db:own_tables                  # 操作 px_{name}_* 表
  - http:outbound                  # 外部 HTTP 请求
  - storage:read                   # 读取存储
  - storage:write                  # 写入存储
  - ai:call                        # 调用 AI 功能
  - config:write                   # 写入配置
  - notifications:send             # 发送通知

# ── 扩展点声明 ──
extensions:
  # 1. 技能（AI Agent 工具）
  skills:
    - name: weather-query
      type: weather_query          # 技能类型标识（全局唯一）
      display_name: { zh-CN: "天气查询", en: "Weather Query" }
      description: { zh-CN: "...", en: "..." }
      entry_point: "skills.weather_resolver"  # 相对于 backend/ 的模块路径

  # 2. AI 适配器
  adapters:
    - provider_code: my_provider
      display_name: { zh-CN: "...", en: "..." }
      entry_point: "adapters.my_adapter.MyAdapter"
      supported_models: ["model-a", "model-b"]

  # 3. 存储驱动
  storage_drivers:
    - code: s3_compatible
      display_name: { zh-CN: "...", en: "..." }
      entry_point: "drivers.s3_driver.S3Driver"

  # 4. API 路由
  api:
    admin_routes:
      - method: GET
        path: "stats"
        handler: "api.handlers.get_stats"
        summary: "获取统计数据"
        auth: required
    tenant_routes: []
    public_routes: []

  # 5. 钩子（同步拦截）
  hooks:
    - point: "before_agent_chat"
      handler: "hooks.chat_filter.filter_input"
      priority: 50                 # 数字越小优先级越高
      description: "过滤聊天输入"

  # 6. 定时任务
  tasks:
    - name: daily-sync
      handler: "tasks.sync.run_sync"
      schedule_type: cron           # interval | cron
      cron_expression: "0 2 * * *"
      interval_seconds: null
      queue: default
      description: "每日同步"

  # 7. 通知模板
  notifications:
    - code: "plugin.my-plugin.doc_shared"
      title: { zh-CN: "文档已分享", en: "Document Shared" }
      channels: ["ws", "inbox"]
      category: biz

  # 8. 权限声明
  permissions:
    - code: "my-plugin:manage"
      name: { zh-CN: "管理我的插件", en: "Manage My Plugin" }
      scope: tenant
      actions: ["read", "create", "update", "delete"]

  # 9. Webhook 端点
  webhooks:
    - path: "/callback"
      handler: "webhooks.github.handle_github"
      method: POST
      auth:
        type: hmac                  # hmac | token | signature
        secret_config_key: "webhook_secret"
        header_name: "X-Hub-Signature-256"
      description: "GitHub webhook"

  # 10. EventBus 订阅
  events:
    - event: "AgentChatCompleted"   # 事件类名（来自 app.ai.events.types）
      handler: "events.on_chat.handle"

  # 11. 前端扩展
  frontend:
    menus:
      - name: my-page
        path: "/tenant/my-plugin"
        icon: "lucide:puzzle"
        parent: null
        sort_order: 100
        scope: tenant
        component: "pages/index"
    header_widgets: []
    floating_panels: []
    standalone_pages: []
    dashboard_widgets:
      - name: my-widget
        component: "widgets/MyWidget"
        title: { zh-CN: "我的组件", en: "My Widget" }
        grid: { w: 6, h: 4 }
        scope: tenant
    settings_tabs: []
    admin:
      entry: ""                    # 管理端入口 JS
      styles: []
    tenant:
      entry: ""                    # 租户端入口 JS
      styles: []

# ── AI 需求 ──
ai_requirements:
  features:
    - feature_code: "ai_writer"
      display_name: { zh-CN: "AI 写作", en: "AI Writer" }
      description: { zh-CN: "...", en: "..." }
      default_prompt: "You are a writing assistant..."
  required_model_types: ["chat"]
  min_context_window: null

# ── 配置 Schema（JSON Schema 格式）──
config_schema:
  type: object
  properties:
    api_key:
      type: string
      title: "API Key"
      x-encrypted: true            # 标记为加密字段
    max_retries:
      type: integer
      default: 3

# ── 租户级配置 Schema ──
tenant_config_schema: null

# ── 依赖 ──
dependencies:
  python: ["httpx>=0.24"]          # pip install 的包
  plugins: ["novusdoc"]            # 依赖的其他插件
  system: []                       # 系统依赖

# ── 定价 ──
pricing:
  type: free                       # free | paid
  price: null
  currency: CNY
  trial:
    enabled: false
    days: 14

# ── Feature Flags ──
features:
  - code: "advanced_export"
    name: { zh-CN: "高级导出", en: "Advanced Export" }
    default: true
    description: { zh-CN: "...", en: "..." }

# ── 兼容性矩阵 ──
compatibility:
  platform_version: ">=1.0.0"
  conflicts:
    - plugin: "old-editor"
      reason: { zh-CN: "功能冲突", en: "Feature conflict" }
  requires:
    - plugin: "novusdoc"
      version: ">=1.0.0"

# ── 资源 ──
resources:
  readme: { zh-CN: "README.zh-CN.md", en: "README.md" }
  changelog: "CHANGELOG.md"
  screenshots: ["screenshot1.png"]
  documentation_url: ""

# ── 版本化 ──
api_version: "1"
```

### scope 枚举值（来自 `enums/plugin.py` PluginScopeEnum）

| 值 | 含义 |
|---|------|
| `admin_only` | 仅平台管理员可见 |
| `all_tenants` | 所有租户可用 |
| `assigned_tenants` | 仅分配的租户可用 |
| `admin_and_all` | 管理员 + 所有租户 |
| `admin_and_assigned` | 管理员 + 分配的租户 |

---

## 三、PluginBase 生命周期钩子

来自 `base.py`（42 行）：

```python
from app.plugins.base import PluginBase

class MyPlugin(PluginBase):
    """所有钩子可选，默认空实现"""

    async def on_install(self, ctx: PluginContext) -> None:
        """安装后调用（仅首次安装）— 初始化种子数据"""

    async def on_enable(self, ctx: PluginContext) -> None:
        """启用时调用 — 启动后台任务等"""

    async def on_disable(self, ctx: PluginContext) -> None:
        """禁用时调用 — 清理后台任务等"""

    async def on_uninstall(self, ctx: PluginContext) -> None:
        """卸载前调用 — 清理自定义数据"""

    async def on_upgrade(self, ctx: PluginContext, old_version: str) -> None:
        """版本升级后调用 — 数据迁移"""
```

**lifecycle.py 调用顺序**：

**安装（10 步）**：
1. 复制源文件到 `backend/plugins/{name}/`
2. 解析 `plugin.yaml` → `PluginManifest`
3. 校验兼容性
4. `pip install` Python 依赖 → 记录到 `Plugin.installed_packages`
5. `alembic upgrade plugin_{name}@head`
6. 注册 AI features → `SystemAgentAssignment`（agent_id=NULL，需管理员手动绑定）
7. 合并 i18n 翻译
8. 实例化 PluginBase 子类 → 调用 `on_install(ctx)`
9. 写入 `plugins` 表（status=installed）
10. 创建 `PluginVersion` 记录

**启用**：
1. 通过 `ExtensionRegistry` 注册所有扩展点（skills/adapters/storage/hooks/events/webhooks/tasks/notifications/permissions）
2. 调用 `on_enable(ctx)`
3. 更新 status=enabled

**禁用**：
1. `ExtensionRegistry.unregister_all(plugin_name)` 反注册所有扩展
2. 调用 `on_disable(ctx)`
3. 更新 status=disabled

**卸载（14 步）**：
1. 检查依赖（TODO: Phase 3 完善）
2. 禁用（如果启用中）
3. 调用 `on_uninstall(ctx)`
4. 反注册所有扩展点
5-8. 清理 AI features / i18n / 通知 / 权限
9. `alembic downgrade plugin_{name}@base`（仅 confirm_data_delete=true 时）
10. 卸载独占 Python 依赖（引用计数）
11-13. 删除 PluginVersion / PluginTenantAssignment / PluginLicense 记录
14. 删除 Plugin 记录 + 物理文件 `shutil.rmtree`

---

## 四、PluginContext API

来自 `context.py`（444 行），**每个方法调用前检查 capabilities**：

```python
# ── 配置 ──
await ctx.get_config()                      # 读取全局配置（自动解密 x-encrypted 字段）
await ctx.get_tenant_config(tenant_id)      # 读取租户级配置
await ctx.update_config(config)             # 更新全局配置（需 config:write）

# ── 数据库 ──
db = ctx.get_db()                           # 返回 PluginDbProxy（需 db:own_tables）
# PluginDbProxy 限制只能操作 px_{name}_* 表
# 方法: execute(), flush(), commit(), rollback(), add()

# ── 日志 ──
logger = ctx.get_logger()                   # 返回 Logger（名称: plugin.{name}）

# ── 存储 ──
storage = await ctx.get_storage()           # 需 storage:read 或 storage:write
# _NamespacedStorageProxy 限制路径在 plugins/{name}/
# 方法: put(), get(), delete(), exists(), url()

# ── HTTP ──
result = await ctx.http_request("GET", url) # 需 http:outbound，自动 30s 超时
# 返回 {"status_code": int, "headers": dict, "body": str}

# ── AI ──
text = await ctx.call_ai_feature(           # 需 ai:call
    "ai_writer",                            # feature_code（不含 plugin.{name}. 前缀）
    [{"role": "user", "content": "..."}],   # messages
)
# 内部流程: 查找 SystemAgentAssignment → AgentChatService.simple_chat()
# 未绑定 Agent 时抛 PluginError

ok = await ctx.is_ai_feature_configured("plugin.my-plugin.ai_writer")  # 注意: 此方法不自动拼前缀，需传完整 feature_code

# ── 通知 ──
await ctx.send_notification(                # 需 notifications:send
    tenant_id=1,
    user_ids=[1, 2],
    template_code="plugin.my-plugin.doc_shared",
    variables={"doc_name": "文档A"},
)

# ── 事件 ──
ctx.emit_event("document_saved", {"doc_id": 123})
# 触发 plugin.{name}.document_saved 钩子点（当前仅日志，Phase 0 完善 EventBus）

# ── 系统 ──
version = ctx.get_platform_version()        # 读取 settings.APP_VERSION
enabled = await ctx.is_feature_enabled("advanced_export")  # 检查 Feature Flag
```

### PluginDbProxy 安全机制

```python
class PluginDbProxy:
    """表名前缀: px_{name.replace('-', '_')}_"""

    # 拦截 execute() 检查 SQL 中的表名
    # 拦截 add() 检查 __tablename__
    # 允许的表: px_{name}_* 和 alembic_version / information_schema
    # 违规 → PluginSecurityError(code=4233)
```

---

## 五、扩展点注册（ExtensionRegistry）

来自 `registry.py`（419 行），**单例模式**：

| # | 扩展类型 | 注册方法 | 桥接目标 |
|---|---------|---------|---------|
| 1 | adapter | `register_adapter()` | `AdapterRegistry.register()` |
| 2 | hook | `register_hook()` | `HookRegistry.register()` |
| 3 | storage | `register_storage_driver()` | `storage_manager.register_driver()` |
| 4 | skill | `register_skill()` | 内部字典 `_plugin_skill_resolvers` / `_plugin_executors` |
| 5 | event | `register_event()` | `EventBus.subscribe()` |
| 6 | webhook | `register_webhook()` | 内部字典 `_plugin_webhooks` |
| 7 | task | `register_task()` | 预留（Phase 2 Celery Beat） |
| 8 | notification | `register_notification()` | 预留（Phase 2 DB 写入） |
| 9 | permission | `register_permission()` | 预留（Phase 2 DB 写入） |

**反注册**：`unregister_all(plugin_name)` 遍历追踪列表逐个反注册。

**冲突检测**：`get_conflicts(manifest)` 检查 adapter/skill/storage 是否与已注册扩展冲突。

---

## 六、Alembic 迁移

### 表名前缀

所有插件表必须以 `px_{plugin_name_underscored}_` 为前缀：

```python
# plugin_name = "novusdoc" → 表前缀 = "px_novusdoc_"
# plugin_name = "my-plugin" → 表前缀 = "px_my_plugin_"
```

来自 `context.py` 第 33 行：
```python
self._table_prefix = f"px_{plugin_name.replace('-', '_')}_"
```

### 迁移文件约定

```python
# backend/plugins/{name}/backend/migrations/versions/001_init.py

"""create initial tables

Revision ID: 001
Revises:
Create Date: 2026-01-01

branch_labels = ('plugin_{name_underscored}',)
"""
from alembic import op
import sqlalchemy as sa

revision = '001'
down_revision = None
branch_labels = ('plugin_novusdoc',)  # 必须声明 branch_labels

def upgrade():
    op.create_table(
        'px_novusdoc_documents',  # 前缀必须匹配
        sa.Column('id', sa.BigInteger(), primary_key=True),
        sa.Column('title', sa.String(500), nullable=False),
        # ...
    )

def downgrade():
    op.drop_table('px_novusdoc_documents')
```

**lifecycle.py 调用方式**：
- 安装：`alembic upgrade plugin_{name_underscored}@head`
- 卸载：`alembic downgrade plugin_{name_underscored}@base`（仅 confirm_data_delete=true）
- 工作目录：`PLUGINS_DIR.parent`（即 `backend/`）

---

## 七、Skill 扩展（完整示例）

以 `example-weather` 为参照：

### 7.1 plugin.yaml 声明

```yaml
extensions:
  skills:
    - name: weather-query
      type: weather_query           # 技能类型标识（全局唯一）
      entry_point: "skills.weather_resolver"  # 必须包含 resolve() 函数
```

### 7.2 Resolver（skills/{type}_resolver.py）

```python
# backend/plugins/{name}/backend/skills/weather_resolver.py
from app.ai.tools.types import ToolDefinition, ToolParameter

def resolve(skill, config: dict) -> list[ToolDefinition]:
    """
    将 Skill 模型实例解析为 ToolDefinition 列表。

    Args:
        skill: Skill 模型实例
        config: 合并后的配置

    Returns:
        ToolDefinition 列表
    """
    return [
        ToolDefinition(
            name="get_weather",
            description="查询城市天气",
            tool_type="weather_query",
            parameters=[
                ToolParameter(
                    name="city", type="string",
                    description="城市名称", required=True,
                ),
            ],
            config=config,
            enabled=True,
            timeout=config.get("timeout", 10),
        ),
    ]
```

### 7.3 Executor（executors/{type}_executor.py）

```python
# backend/plugins/{name}/backend/executors/weather_query_executor.py
from app.ai.tools.executors.base import BaseToolExecutor
from app.ai.tools.types import ToolDefinition, ToolResult

class WeatherExecutor(BaseToolExecutor):
    """工具执行器 — 类名不限，但必须继承 BaseToolExecutor"""

    async def validate(self, definition: ToolDefinition, arguments: dict) -> bool:
        return bool(arguments.get("city"))

    async def execute(
        self, definition: ToolDefinition, tool_call_id: str,
        arguments: dict, context=None,
    ) -> ToolResult:
        city = arguments.get("city", "")
        # ... 业务逻辑 ...
        return ToolResult(
            tool_call_id=tool_call_id,
            name="get_weather",
            success=True,
            output=f"Weather for {city}: 22°C, Sunny",
            duration_ms=50,
        )
```

**加载约定**（来自 `lifecycle.py` 第 701-740 行）：
- Executor 文件名：`{skill_type}_executor.py`（type 中 `-` 替换为 `_`）
- 路径：`backend/plugins/{name}/backend/executors/{skill_type}_executor.py`
- 自动扫描文件中 `BaseToolExecutor` 的子类

---

## 八、API 路由分发

来自 `api_dispatcher.py`（162 行）：

**路径约定**：
- 管理端：`/admin/plugins/{plugin_name}/api/{path}`
- 租户端：`/tenant/plugins/{plugin_name}/api/{path}`

**Handler 编写**：

```python
# backend/plugins/{name}/backend/api/handlers.py

async def get_stats(request, db):
    """Handler 接收 request 和 db 两个参数"""
    body = await request.json()  # POST 时读 body
    # ... 业务逻辑 ...
    return {"total": 42}  # 返回 dict 自动包装为 success(data=...)
```

**Handler 加载路径**（manifest 声明）：
- `handler: "api.handlers.get_stats"` → 物理文件 `backend/plugins/{name}/backend/api/handlers.py` 中的 `get_stats`

**状态检查**：请求时自动检查 Plugin.status == "enabled"，禁用/未安装返回 404。

### Webhook Handler 签名（与 API Handler 不同）

Webhook 走 `webhook_dispatcher.py`，路由 `/webhooks/plugins/{plugin_name}/{path:path}`（不走认证中间件）：

```python
# backend/plugins/{name}/backend/webhooks/github.py

async def handle_github(plugin_name, path, method, headers, payload):
    """Webhook handler 签名：5 个具名参数"""
    signature = headers.get("X-Hub-Signature-256", "")
    event_type = headers.get("X-GitHub-Event", "")
    # ... 业务逻辑 ...
    return {"ok": True}
```

**注意**：API handler 签名是 `(request, db)`，Webhook handler 签名是 `(plugin_name, path, method, headers, payload)`，二者完全不同。

---

## 九、异常体系

来自 `exceptions.py`（68 行）：

| 异常类 | 基类 | 错误码 | 用途 |
|--------|------|--------|------|
| `PluginError` | `BusinessException` | 4230 | 通用错误 |
| `PluginNotFoundError` | `NotFoundException` | 4041 | 插件不存在 |
| `PluginManifestError` | `ValidationException` | 4231 | 清单解析失败 |
| `PluginDependencyError` | `PluginError` | 4232 | 依赖安装失败 |
| `PluginSecurityError` | `PluginError` | 4233 | 安全违规 |
| `PluginLicenseError` | `PluginError` | 4234 | License 无效 |
| `PluginConflictError` | `PluginError` | 4235 | 扩展冲突 |
| `PluginInstallError` | `PluginError` | 4236 | 安装失败 |

---

## 十、枚举（来自 enums/plugin.py）

| 枚举 | 值 |
|------|---|
| `PluginStatusEnum` | installed / enabled / disabled / error |
| `PluginScopeEnum` | admin_only / all_tenants / assigned_tenants / admin_and_all / admin_and_assigned |
| `PluginTierEnum` | official / verified / community |
| `PluginInstallSourceEnum` | local / marketplace / git |
| `PluginPricingTypeEnum` | free / paid |
| `PluginLicenseTypeEnum` | trial / perpetual |
| `PluginVersionStatusEnum` | active / archived |

---

## 十一、前端集成

### 核心原则

**插件前端代码严禁写入主系统。** 所有插件 Vue 组件、样式、i18n 翻译必须在 `plugins/{name}/frontend/` 内，通过 Vite 构建为 UMD 包，由宿主动态加载。

### 11.1 UMD 动态加载架构

**加载流程**：
1. 宿主 `bootstrap.ts` 调用 `exposePluginShared()` → 挂载 `window.Vue` / `window.AntDesignVue` / `window.NovusPluginShared`
2. `usePluginFrontendInit` composable 获取已启用插件列表（`GET /admin/plugins?filter[status][eq]=enabled`）
3. 对每个有 `extensions.frontend` 声明的插件，`plugin-loader.ts` 通过 `<script>` 加载 `/plugin-assets/{name}/index.js` + CSS
4. UMD 包注册到 `window.NovusPlugin_{name_underscored}`，自动调用 `setup()` 注册 i18n
5. 组件通过 `pluginSlotsStore.registerSlot()` 注册到对应插槽（`markRaw` 包裹）
6. 布局组件 `basic.vue` 的 `#header-right-89` 等插槽动态渲染

**宿主共享依赖映射**：

| 插件中的 import | Vite external | 映射到 window |
|---|---|---|
| `from 'vue'` | `vue` | `window.Vue` |
| `from 'vue-router'` | `vue-router` | `window.VueRouter` |
| `from 'ant-design-vue'` | `ant-design-vue` | `window.AntDesignVue` |
| `from '@novus/plugin-shared'` | `@novus/plugin-shared` | `window.NovusPluginShared` |

`NovusPluginShared` 提供：`requestClient` / `$t` / `IconifyIcon` / `registerLocale` / `usePluginSlotsStore`

### 11.2 插件前端构建

```
plugins/{name}/frontend/
├── package.json             # devDependencies: vite + @vitejs/plugin-vue
├── vite.config.ts           # UMD 构建配置（external + globals）
├── src/
│   ├── index.ts             # 入口：export 组件 + setup() 注册 i18n
│   ├── locales.ts           # 内联 i18n 消息（zhCN / enUS）
│   ├── types.ts             # NovusPluginSharedAPI 类型声明
│   └── *.vue                # 组件文件
└── dist/                    # 构建产物（包含在插件 zip 中）
    ├── index.js             # UMD bundle
    └── {name}.css           # 提取的样式
```

**构建命令**：
```bash
npm install
npx vite build    # → dist/index.js + dist/{name}.css
```

**vite.config.ts 模板**：
```typescript
import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';
import { resolve } from 'node:path';

export default defineConfig({
  plugins: [vue()],
  build: {
    outDir: 'dist',
    lib: {
      entry: resolve(__dirname, 'src/index.ts'),
      name: 'NovusPlugin_{name_underscored}',
      formats: ['umd'],
      fileName: () => 'index.js',
    },
    rollupOptions: {
      external: ['vue', 'vue-router', 'ant-design-vue', '@novus/plugin-shared'],
      output: {
        globals: {
          vue: 'Vue',
          'vue-router': 'VueRouter',
          'ant-design-vue': 'AntDesignVue',
          '@novus/plugin-shared': 'NovusPluginShared',
        },
      },
    },
    cssCodeSplit: false,
  },
});
```

**index.ts 入口模板**：
```typescript
import MyWidget from './MyWidget.vue';
import { zhCN, enUS } from './locales';

export function setup(): void {
  const shared = (window as unknown as Record<string, unknown>)
    .NovusPluginShared as { registerLocale?: Function };
  if (shared?.registerLocale) {
    shared.registerLocale('zh-CN', 'plugin.{name}', zhCN);
    shared.registerLocale('zh', 'plugin.{name}', zhCN);
    shared.registerLocale('en-US', 'plugin.{name}', enUS);
    shared.registerLocale('en', 'plugin.{name}', enUS);
  }
}

export { MyWidget };
```

### 11.3 插件槽位（plugin-slots.ts）

5 种插槽类型：`headerWidgets` / `floatingPanels` / `dashboardWidgets` / `settingsTabs` / `sidebarMenus`

插件通过 `plugin.yaml` 的 `extensions.frontend.header_widgets` 等声明前端插槽，`usePluginFrontendInit` 自动读取 manifest 并从 UMD 包中取出对应组件注册。

### 11.4 宿主关键文件索引

| 文件 | 职责 |
|------|------|
| `frontend/.../utils/plugin-shared.ts` | 暴露 `window.Vue` / `NovusPluginShared` 共享依赖 |
| `frontend/.../utils/plugin-loader.ts` | UMD `<script>` 加载 + CSS + 自动调用 `setup()` |
| `frontend/.../composables/use-plugin-frontend-init.ts` | 获取已启用插件 → 加载 UMD → 注册到 slots store |
| `frontend/.../stores/plugin-slots.ts` | Pinia 插槽 Store（5 种类型） |
| `frontend/.../layouts/basic.vue` | `#header-right-89` 渲染 `headerWidgets` |
| `frontend/.../bootstrap.ts` | 调用 `exposePluginShared()` |
| `backend/app/main.py` | `/plugin-assets/{name}/` 静态服务路由 |
| `backend/app/middleware/access_control.py` | `/plugin-assets` 在豁免路径列表中 |
| `frontend/.../vite.config.mts` | 开发代理: `/plugin-assets` → `http://127.0.0.1:8000` |

### 11.5 API 调用

```typescript
// 管理端 plugin API: frontend/apps/web-antd/src/api/admin/plugin.ts
import { getPluginListApi, enablePluginApi } from '#/api/admin/plugin';
// 市场 API: frontend/apps/web-antd/src/api/admin/plugin-marketplace.ts
import { getMarketplaceListApi } from '#/api/admin/plugin-marketplace';
```

---

## 十二、命名规范汇总

| 项目 | 格式 | 示例 |
|------|------|------|
| 插件名 | 小写 kebab-case | `novusdoc`, `crm-module` |
| DB 表前缀 | `px_{name_underscored}_` | `px_novusdoc_documents` |
| Alembic 分支 | `plugin_{name_underscored}` | `plugin_novusdoc` |
| i18n Key 前缀 | `plugin.{name}.` | `plugin.novusdoc.title` |
| API 路径 | `/admin/plugins/{name}/api/` | `/admin/plugins/novusdoc/api/docs` |
| Webhook 路径 | `/webhooks/plugins/{name}/` | `/webhooks/plugins/novusdoc/callback` |
| AI feature_code | `plugin.{name}.{code}` | `plugin.novusdoc.ai_writer` |
| 通知模板 | `plugin.{name}.{event}` | `plugin.novusdoc.doc_shared` |
| Logger 名称 | `plugin.{name}` | `plugin.novusdoc` |
| 存储命名空间 | `plugins/{name}/` | `plugins/novusdoc/images/1.png` |
| 前端全局变量 | `NovusPlugin_{name_underscored}` | `NovusPlugin_novusdoc` |
| 前端资源 | `/plugin-assets/{name}/` | `/plugin-assets/novusdoc/index.js` |

---

## 十三、插件开发检查清单

### 必须

- [ ] `plugin.yaml` 通过 `PluginManifest.model_validate()` 校验
- [ ] `name` 是小写 kebab-case（`^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$`）
- [ ] `scope` 是合法枚举值
- [ ] `backend/main.py` 包含 `PluginBase` 子类
- [ ] `backend/__init__.py` 存在（空文件即可）
- [ ] 所有 DB 表以 `px_{name_underscored}_` 为前缀
- [ ] Alembic 迁移声明 `branch_labels = ('plugin_{name_underscored}',)`
- [ ] `capabilities` 如实声明所有需要的能力
- [ ] i18n 翻译文件（`locales/zh-CN.json` + `locales/en.json`）

### 推荐

- [ ] README.md 或 README.zh-CN.md
- [ ] Skill Resolver 的 `resolve()` 返回正确的 `ToolDefinition`
- [ ] Executor 继承 `BaseToolExecutor`，实现 `validate()` + `execute()`
- [ ] Executor 文件名匹配 `{skill_type}_executor.py`
- [ ] 安全扫描无警告（`security_scan.py` 检查 eval/exec/subprocess 等危险调用）
- [ ] on_install 中初始化种子数据（非 Alembic 迁移）
- [ ] config_schema 中敏感字段标记 `x-encrypted: true`

### 禁止

- [ ] 禁止在主系统代码中写入插件组件/逻辑/国际化——插件所有代码必须在 `backend/plugins/{name}/`
- [ ] 禁止硬编码插件组件映射——不允许在宿主 `import` / `import.meta.glob` 插件组件
- [ ] 禁止在主系统 `locales/` 中放插件翻译——插件 i18n 通过 `setup()` 动态 `registerLocale()`
- [ ] 禁止在主系统 `components/` 中放插件组件——插件 Vue 组件通过 UMD 动态加载
- [ ] 禁止操作非 `px_{name}_*` 前缀的表（PluginDbProxy 会拦截）
- [ ] 禁止不声明能力就调用受限 API（PluginSecurityError）
- [ ] 禁止 `eval()` / `exec()` / `subprocess` 等危险调用（安全扫描警告）
- [ ] 禁止在插件代码中直接 import 其他插件的内部模块
- [ ] 禁止硬编码中文字符串（使用 i18n `locales/*.json`）
- [ ] 禁止插件 SFC 中使用宿主路径别名（如 `#/locales`、`@vben/icons`）——必须用 external（`vue`/`ant-design-vue`/`@novus/plugin-shared`）
