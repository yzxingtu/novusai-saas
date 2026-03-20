# 插件系统开发规范（代码验证版）

> 本文档基于 `backend/app/plugins/` 实际代码审计编写，所有路径、类名、方法签名均与代码一致。
> 最后审计时间：2026-02-27

## 一、目录结构

### 1.1 框架代码（平台侧）

```
backend/app/plugins/
├── __init__.py
├── base.py              # PluginBase 抽象基类（5 个生命周期钩子）
├── manifest.py          # plugin.yaml Pydantic Schema（610 行，30+ Schema，含强校验）
├── loader.py            # PluginLoader（发现/清单/主类/README/i18n）
├── lifecycle.py         # PluginLifecycle（install/enable/disable/uninstall）
├── context.py           # PluginContext 沙箱 + PluginDbProxy
├── context_factory.py   # 版本化 Context 创建
├── registry.py          # ExtensionRegistry 单例（11 种扩展类型）
├── _extension_registrar.py # 扩展点批量注册（fail-close 策略）
├── exceptions.py        # 8 个异常类
├── package_security.py  # ZIP 包安全校验与安全解压
├── asset_resolver.py    # 插件前端静态资源路径解析（安全策略）
├── api_dispatcher.py    # 插件 API 统一分发器（自动注入 PluginContext）
├── webhook_dispatcher.py # Webhook 分发器
├── sse.py               # plugin_sse_response（SSE 流式封装 + 心跳）
├── sio_auth.py          # 插件 Socket.IO 鉴权代理
├── event_bus.py         # 跨插件事件总线（PluginEventBus）
├── security_scan.py     # AST 安全扫描
├── health.py            # 健康监控（错误追踪 + 自动降级）
├── startup.py           # 启动：自动发现（discover_and_register）+ 恢复（restore_enabled_plugins）
├── progress.py          # 进度推送器（PluginProgressEmitter，INSTALL/ENABLE/UNINSTALL_STEPS）
├── scope.py             # 作用域可见性判定
├── version_manager.py   # 版本管理（升级/回滚/备份）
├── preview.py           # 安装预览（manifest 分析 + 冲突检测）
├── marketplace.py       # 市场客户端（GitHub/Gitee 双源）
├── update_checker.py    # 更新检查（24h 缓存）
├── crypto.py            # 配置加密/解密
├── license.py           # License 工具（含 fail-close 验证策略）
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
│   ├── package.json         # npm 依赖声明（dev 模式用）
│   ├── vite.config.ts       # UMD 构建配置（prod 构建用）
│   ├── src/                 # 源码（dev 模式实时转译）
│   │   ├── index.ts         # 入口：export 组件 + setup()
│   │   └── *.vue            # Vue 组件
│   └── dist/                # UMD 构建产物（prod 模式）
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
scope: global_shared               # 插件资源作用域：ResourceScopeEnum 五类之一（见下方）

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
      type: toolkit                # 必须使用标准 SkillTypeEnum 值（toolkit/builtin 等）
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
  #    method: 仅允许 GET/POST/PUT/PATCH/DELETE（自动转大写）
  #    auth:   仅允许 required/none（自动转小写）
  #    path:   禁止前导斜杠，路径参数名必须合法标识符（如 {doc_id}，禁止 {1bad}）
  api:
    admin_routes:
      - method: GET
        path: "stats"                # 正确：无前导斜杠
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
  #    method: 仅允许 GET/POST/PUT/DELETE（自动转大写）
  #    path:   必须以 / 开头（自动规范化），支持路径参数
  #    auth.type: 仅允许 none/hmac/token/signature
  webhooks:
    - path: "/callback"             # 必须有前导斜杠
      handler: "webhooks.github.handle_github"
      method: POST
      auth:
        type: hmac                  # none | hmac | token | signature
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
        path: "/tenant/plugins/my-plugin"
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
      entry: ""                    # 企业端入口 JS
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

# ── 企业级配置 Schema ──
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

### 顶层 `scope`（`plugins` 表 · 资源作用域）

与 **`ResourceScopeEnum`** 一致（五类），**不是** RBAC 的 `PermissionScope`，也不是插件 YAML 里菜单/权限扩展里的「端侧」字段：

| 值 | 含义（摘要） |
|---|------|
| `global_shared` | 管理端 + 全部企业 |
| `admin_only` | 仅管理端功能侧消费 |
| `all_tenants` | 仅企业端全部企业 |
| `admin_and_selected_tenants` | 管理端 + RTA 指定企业 |
| `selected_tenants` | 仅 RTA 指定企业 |

指定企业列表统一走 **`resource_tenant_assignments`**（`resource_type='plugin'`）。

### `extensions.*` 里的 `scope`（端侧挂载，已归一化）

`manifest.py` 将 YAML 中的旧串映射为 **`admin` / `tenant` / `user` / `both`**（权限扩展可为四值）。**禁止**把此处字段当成 `ResourceScopeEnum`。

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

**自动发现（启动时，discover_and_register）**：
1. 扫描 `backend/plugins/` 目录，发现含 `plugin.yaml` 的子目录
2. 磁盘有 + DB 无 → 自动注册为 `installed`（disabled），执行安全扫描 + Alembic 迁移 + AI features + on_install
3. 磁盘有 + DB 有 → 同步 manifest 到 DB
4. DB 有 + 磁盘无 → 标记为 error（文件缺失）

**安装（ZIP 上传，10 步）**：
1. 复制源文件到 `backend/plugins/{name}/`
2. 解析 `plugin.yaml` → `PluginManifest`
3. 校验兼容性 + 安全扫描
4. 记录声明的依赖（**不安装 pip/npm**，延迟到 enable 阶段）
5. `alembic upgrade plugin_{name}@head`
6. 注册 AI features → `SystemAgentAssignment`（agent_id=NULL，需管理员手动绑定）
7. 合并 i18n 翻译
8. 实例化 PluginBase 子类 → 调用 `on_install(ctx)`
9. 写入 `plugins` 表（status=installed）
10. 创建 `PluginVersion` 记录

**启用（带进度推送 ENABLE_STEPS）**：
1. 检查依赖插件是否已启用 + 版本约束
2. `pip install` Python 依赖（fatal，失败阻止启用）→ emitter pip running/success
3. `pnpm add` npm 依赖（non-fatal，仅 dev 模式）→ emitter npm running/success
4. 通过 `ExtensionRegistry` 注册所有扩展点 → emitter extensions
5. 创建/更新 SkillPackage + Skill DB 记录
6. 调用 `on_enable(ctx)` → emitter on_enable
7. 更新 status=enabled → emitter done

**禁用（不卸载依赖）**：
1. 检查其他插件是否依赖此插件
2. 检查存储驱动是否正在使用
3. `ExtensionRegistry.unregister_all(plugin_name)` 反注册所有扩展
4. 停用 SkillPackage + Skill 记录（is_active=False）
5. 调用 `on_disable(ctx)`
6. 更新 status=disabled（**不卸载 pip/npm 依赖**，重新启用时无需等待）

**卸载（14 步，带进度推送 UNINSTALL_STEPS）**：
1. 检查依赖（其他插件依赖此插件则阻止）
2. 禁用（如果启用中）
3. 调用 `on_uninstall(ctx)`
4. 反注册所有扩展点
5. 删除 SkillPackage + Skill 记录
6-8. 清理 AI features
9. `alembic downgrade plugin_{name}@base` + DROP 插件表 + 清理版本戳
10. 卸载独占 Python 依赖（三层安全检查：其他插件/项目/pip Required-by）
10.5. 卸载独占 npm 依赖（共享检查：其他插件 + 宿主 package.json）
11-13. 删除 PluginVersion / ResourceTenantAssignment / PluginLicense 记录
14. 删除 Plugin 记录 + 物理文件 `shutil.rmtree` + 卸载模块缓存

---

## 四、PluginContext API

来自 `context.py`（444 行），**每个方法调用前检查 capabilities**：

```python
# ── 配置 ──
await ctx.get_config()                      # 读取全局配置（自动解密 x-encrypted 字段）
await ctx.get_tenant_config(tenant_id)      # 读取企业级配置
await ctx.update_config(config)             # 更新全局配置（需 config:write）

# ── 数据库 ──
db = ctx.get_db()                           # 返回 PluginDbProxy（需 db:own_tables）
# PluginDbProxy 限制只能操作 px_{name}_* 表
# 支持方法: execute(), flush(), commit(), rollback(), add(), add_all(), delete(), refresh(), get(), text()
# 禁止: db.session（会抛 PluginSecurityError）

# ── 日志 ──
logger = ctx.get_logger()                   # 返回 Logger（名称: plugin.{name}）

# ── 存储 ──
storage = await ctx.get_storage()           # 需 storage:read 或 storage:write
# _NamespacedStorageProxy 限制路径在 plugins/{name}/
# 方法: put(), get(), delete(), exists(), get_url(), get_info()

# ── HTTP ──
result = await ctx.http_request("GET", url) # 需 http:outbound，自动 30s 超时
# 返回 {"status_code": int, "headers": dict, "body": str}

# ── AI（非流式）──
text = await ctx.call_ai_feature(           # 需 ai:call
    "ai_writer",                            # feature_code（不含 plugin.{name}. 前缀）
    [{"role": "user", "content": "..."}],   # messages
)
# 内部流程: 查找 SystemAgentAssignment → AgentChatService.chat()
# 未绑定 Agent 时抛 PluginError

# ── AI（流式）──
async for delta in ctx.call_ai_feature_stream(  # 需 ai:call
    "ai_writer",
    [{"role": "user", "content": "..."}],
):
    print(delta, end="")  # 仅 yield 纯文本增量，不含 SSE 包装
# 内部流程: AgentChatService.stream_chat() → 解析 SSE → yield message.delta
# 上游不支持流式时自动降级为 call_ai_feature 单 chunk 输出（日志标记 fallback=True）

# 在 API handler 中返回 SSE StreamingResponse:
from app.plugins.sse import plugin_sse_response
return plugin_sse_response(
    ctx.call_ai_feature_stream("ai_writer", messages),
    plugin_name=ctx.plugin_name,
)

ok = await ctx.is_ai_feature_configured("ai_writer")  # 自动拼接 plugin.{name}. 前缀

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

来自 `registry.py`（649 行），**单例模式**：

| # | 扩展类型 | 注册方法 | 桥接目标 |
|---|---------|---------|--------|
| 1 | adapter | `register_adapter()` | `AdapterRegistry.register()` |
| 2 | hook | `register_hook()` | `HookRegistry.register()` |
| 3 | storage | `register_storage_driver()` | `storage_manager.register_driver()` |
| 4 | skill | `register_skill()` | 内部字典 `_plugin_skill_resolvers` / `_plugin_executors` |
| 5 | event | `register_event()` | `PluginEventBus.subscribe()` |
| 6 | webhook | `register_webhook()` | 内部字典 `_plugin_webhooks` |
| 7 | task | `register_task()` | Celery Beat 动态调度 |
| 8 | notification | `register_notification()` | 内部字典 `_plugin_notifications` |
| 9 | permission | `register_permission()` | 内部字典 `_plugin_permissions` |
| 10 | socketio | `register_socketio()` | `AsyncServer.register_namespace()` |

**批量注册**：`_extension_registrar.register_all_extensions()` 统一加载并注册，加载失败的扩展记入 `get_failed_extensions()` 供生命周期层 fail-close 决策。

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
      type: toolkit                 # 必须使用标准 SkillTypeEnum 值
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
- 企业端：`/tenant/plugins/{plugin_name}/api/{path}`

**Handler 编写**：

```python
# backend/plugins/{name}/backend/api/handlers.py

async def get_stats(request, db, ctx):
    """Handler 签名：(request, db, ctx) — db 为 PluginDbProxy（非 AsyncSession）"""
    body = await request.json()  # POST 时读 body
    tenant_id = ctx.get_current_tenant_id()  # 从 RequestContext 获取
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

**注意**：API handler 参数按签名注入：
- `request`：Request
- `ctx`：PluginContext
- `db`：仅当插件具备 `db:own_tables` 能力且 handler 声明该参数时，才注入 `PluginDbProxy`
- 未具备 `db:own_tables` 但声明 `db` 参数时，dispatcher 返回 403

Webhook handler 签名是 `(plugin_name, path, method, headers, payload)`，与 API handler 完全不同。

---

## 九、安全加固（生产就绪）

### 9.1 ZIP 包安全（`package_security.py`）

所有插件 ZIP 上传（upload/preview/upgrade）和市场下载均经统一安全校验，**禁止使用原始 `zipfile.extractall()`**。

**可配置限制项**（`app.core.config.Settings`）：

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `PLUGIN_MAX_PACKAGE_SIZE` | 50 MB | 压缩包大小上限 |
| `PLUGIN_MAX_UNCOMPRESSED_SIZE` | 200 MB | 总解压大小上限 |
| `PLUGIN_MAX_ARCHIVE_FILES` | 2000 | 成员数上限 |
| `PLUGIN_MAX_ARCHIVE_SINGLE_FILE_SIZE` | 50 MB | 单文件大小上限 |
| `PLUGIN_MAX_COMPRESSION_RATIO` | 100x | 压缩比上限（防 zip bomb） |

**校验链路**：
1. 上传/下载时先校验压缩包大小
2. 解压前：成员数、单文件大小、总解压大小、压缩比、路径遍历（`../`）、符号链接
3. 解压中：逐块写入实时监控单文件/总大小
4. 违规抛 `PluginInstallError`（code=4236）

**市场下载**：流式写入 + 实时大小校验 + 下载完成后 `validate_plugin_zip_archive()` 二次校验。

### 9.2 Manifest 强校验

`manifest.py` 中的 Pydantic validators 在 `model_validate()` 阶段 fail-close：

| Schema | 字段 | 校验规则 |
|--------|------|----------|
| `ApiRouteSchema` | `method` | 仅 GET/POST/PUT/PATCH/DELETE（自动大写） |
| `ApiRouteSchema` | `auth` | 仅 required/none（自动小写） |
| `ApiRouteSchema` | `path` | 禁止前导斜杠，参数名须合法标识符（`{doc_id}` ✅，`{1bad}` ❌） |
| `WebhookExtensionSchema` | `method` | 仅 GET/POST/PUT/DELETE |
| `WebhookExtensionSchema` | `path` | 必须以 `/` 开头，参数名须合法标识符 |
| `WebhookAuthSchema` | `type` | 仅 none/hmac/token/signature |
| `SocketIONamespaceSchema` | `path` | 禁止路径参数，仅允许字母/数字/`_`/`-` |

**路径安全**：`_normalize_extension_path()` 统一拒绝空段、`.`、`..`、畸形参数（如 `{bad`）。

### 9.3 信任边界与 fail-close

| 机制 | 说明 |
|------|------|
| **PluginContext 信任边界** | 生产模式从 DB manifest 快照创建 Context；DEBUG 模式允许磁盘 manifest 热重载 |
| **扩展注册 fail-close** | 关键扩展加载失败时，lifecycle 将插件状态设为 ERROR 并回滚注册 |
| **License 验证 fail-close** | 生产模式下无公钥时拒绝验证（返回 False）；DEBUG 模式降级为长度校验 |
| **Webhook 错误脱敏** | 生产模式 handler 异常只返回 "Internal server error"，不暴露堆栈 |
| **版本管理分布式锁** | upgrade/rollback 持有 Redis 分布式锁 + 操作后清理 sys.modules 缓存 |

### 9.4 静态资源安全（`asset_resolver.py`）

`/plugin-assets/{name}/{path}` 端点的安全策略：
- 仅服务 `frontend/dist/` 子目录下的文件（禁止访问 `plugin.yaml`/`backend/` 等）
- 插件名必须是合法 kebab-case（拒绝 `../` 等遍历）
- 可配置 `PLUGIN_ASSETS_ENABLED_ONLY=True`（默认）仅对已启用插件提供资源

---

## 十、异常体系

来自 `exceptions.py`（68 行）：

| 异常类 | 基类 | 错误码 | 用途 |
|--------|------|--------|------|
| `PluginError` | `BusinessException` | 4230 | 通用错误 |
| `PluginNotFoundError` | `NotFoundException` | 4041 | 插件不存在 |
| `PluginManifestError` | `ValidationException` | 4231 | 清单解析/强校验失败 |
| `PluginDependencyError` | `PluginError` | 4232 | 依赖安装失败 |
| `PluginSecurityError` | `PluginError` | 4233 | 安全违规（沙箱/表名） |
| `PluginLicenseError` | `PluginError` | 4234 | License 无效 |
| `PluginConflictError` | `PluginError` | 4235 | 扩展冲突 |
| `PluginInstallError` | `PluginError` | 4236 | 安装失败（含 ZIP 安全违规） |

---

## 十一、枚举（来自 enums/plugin.py）

| 枚举 | 值 |
|------|---|
| `PluginStatusEnum` | installed / enabled / disabled / error |
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
├── package.json             # npm_dependencies: list[str] = Field(default_factory=list)
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

### 11.6 Dev 模式 vs 生产模式（前端加载）

插件前端在 Dev 模式和生产模式下的加载方式完全不同：

| 维度 | Dev 模式（Vite dev server） | 生产模式（构建产物） |
|------|---------------------------|-------------------|
| **JS 加载** | ESM `import()` 动态导入，Vite 实时转译源码 | `<script>` 标签注入 UMD 包 |
| **源码位置** | `plugins/{name}/frontend/src/index.ts` | `plugins/{name}/frontend/dist/index.js` |
| **热更新** | 修改插件 `.vue`/`.ts` 后刷新浏览器即可 | 需重新 `npx vite build` 生成 UMD |
| **依赖解析** | Vite 从插件 `node_modules` 解析专有依赖 | 所有依赖打包进 UMD bundle |
| **共享依赖** | `@novus/plugin-shared` → 宿主 `plugin-shared.ts`（ESM） | `@novus/plugin-shared` → `window.NovusPluginShared`（UMD external） |
| **npm 安装** | 后端 `_install_npm_deps()` 通过 `pnpm add --filter=@vben/web-antd` 安装 | 跳过（UMD 已包含所有依赖） |
| **CSS** | 按 manifest `styles` 声明注入 `<link>` | 同左 |

#### Vite 插件 `novus-plugins-loader`（`vite-plugin-novus-plugins.ts`）

**Dev 模式行为**：
1. `config()` — 设置 `server.fs.strict = false`（允许 Vite 访问 `backend/plugins/` 目录），收集插件 `package.json` 依赖加入 `optimizeDeps.include`
2. `resolveId()` — 拦截裸模块导入：
   - `@novus/plugin-shared` → 解析到宿主 `src/utils/plugin-shared.ts`
   - 插件 `package.json` 中声明的依赖 → 从插件自身 `node_modules` 解析（`createRequire()`）
   - 其他依赖（`vue`/`ant-design-vue` 等） → Vite 默认解析（使用宿主版本）
3. `configureServer()` — 中间件拦截 `/plugin-assets/{name}/index.js` 请求 → 通过 `server.transformRequest()` 实时转译 `src/index.ts` 源码返回 ESM；同时 `server.watcher.add()` 监听插件源码目录变动

**Build 模式行为**：
1. `writeBundle()` — 将每个插件的 `frontend/dist/` 复制到构建输出目录 `plugin-assets/{name}/`

#### plugin-loader.ts 加载分支

```typescript
if (import.meta.env.DEV) {
  // Dev: ESM import() → Vite 转译 src/index.ts
  const devUrl = `/plugin-assets/${pluginName}/index.js?t=${Date.now()}`;
  mod = await import(devUrl);
} else {
  // Prod: <script> 注入 → 读取 window.NovusPlugin_{name_underscored}
  mod = await loadViaScript(pluginName);
}
```

#### 后端 npm 依赖安装（`lifecycle.py: _install_npm_deps`）

仅在 `settings.DEBUG = True` 时执行：
1. 检查 `apps/web-antd/node_modules` 和 `frontend/node_modules` 是否已存在声明的包
2. 安全校验：拒绝 `--` 开头的包名和含 shell 元字符的包名
3. 解析包名（去版本号）：`@scope/name@^1.0` → `@scope/name`
4. 仅安装缺失的包：`pnpm add <missing> --filter=@vben/web-antd`
5. 工作目录：`frontend/`（`backend/` 的兄弟目录）
6. 生产模式直接跳过（日志记录 "production mode uses UMD bundles"）

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

## 十四、插件开发检查清单

### 必须

- [ ] `plugin.yaml` 通过 `PluginManifest.model_validate()` 校验
- [ ] `name` 是小写 kebab-case（`^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$`）
- [ ] `scope` 是合法枚举值
- [ ] API route `method` 仅 GET/POST/PUT/PATCH/DELETE，`auth` 仅 required/none
- [ ] API route `path` 无前导斜杠，路径参数名是合法标识符（如 `{doc_id}`）
- [ ] Webhook `path` 以 `/` 开头，`auth.type` 仅 none/hmac/token/signature
- [ ] Socket.IO `path` 无路径参数，仅含字母/数字/`_`/`-`
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
- [ ] 禁止使用原始 `zipfile.extractall()`——必须用 `package_security.extract_plugin_zip_safely()`
- [ ] 禁止在 API/Webhook 路径中使用 `..` 或数字开头的参数名（manifest 校验会拒绝）
