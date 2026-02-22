# NovusAI 插件开发指南

## 概述

NovusAI 插件系统允许开发者通过 **7 种扩展点** 扩展平台能力：

| 扩展点 | 基类 | 用途 | 路由挂载 |
|--------|------|------|----------|
| **AdapterPlugin** | `AdapterPlugin` | AI 模型适配器（OpenAI、Anthropic 等） | - |
| **ToolPlugin** | `ToolPlugin` | 注册自定义工具类型供 Agent 调用 | - |
| **HookPlugin** | `HookPlugin` | 订阅系统事件（EventBus） | - |
| **ApiPlugin** | `ApiPlugin` | 挂载自定义 REST API 路由 | `/plugins/{name}/` |
| **SkillPlugin** | `SkillPlugin` | 注册技能类型，自动创建技能包 | - |
| **StoragePlugin** | `StoragePlugin` | 注册自定义存储驱动 | - |
| **复合插件** | 多继承 | 同时实现多个扩展点 | 按类型组合 |

所有插件继承自 `BasePlugin`，遵循统一的生命周期。

---

## 目录结构

完整的插件目录结构（以 `rich-editor` 为例）：

```
backend/app/plugins/rich_editor/
├── __init__.py                 # 包初始化
├── plugin.py                   # 插件入口（必须）
├── manifest.json               # 插件元数据（必须）
│
├── api/                        # API 端点（ApiPlugin）
│   ├── __init__.py
│   └── documents.py
│
├── models/                     # 数据模型（SQLAlchemy）
│   ├── __init__.py
│   ├── document.py
│   └── document_version.py
│
├── repositories/               # 数据访问层
│   ├── __init__.py
│   └── document_repository.py
│
├── services/                   # 业务逻辑层
│   ├── __init__.py
│   └── document_service.py
│
├── tools/                      # AI 工具执行器（SkillPlugin）
│   ├── __init__.py
│   └── executor.py
│
├── prompts/                    # 系统提示词
│   └── system_prompt.md
│
├── migrations/                 # 数据库迁移（SQL）
│   ├── 001_create_documents_table.sql
│   ├── 001_create_documents_table.down.sql
│   ├── 002_create_versions_table.sql
│   └── 002_create_versions_table.down.sql
│
├── locales/                    # 多语言翻译
│   ├── zh-CN.json
│   └── en-US.json
│
├── frontend/                   # 前端模板（可选）
│   ├── api-documents.ts
│   ├── types.ts
│   └── locales/
│       ├── zh-CN.json
│       └── en-US.json
│
└── requirements.txt            # Python 依赖（可选）
```

> **命名约定**：
> - 插件名用连字符：`rich-editor`
> - 目录名用下划线：`rich_editor`
> - `name` property 返回连字符格式

---

## 快速开始

### 1. 脚手架创建

```bash
cd backend
python scripts/novusai_plugin.py init my-plugin --type tool --author "开发者"
```

### 2. 实现插件逻辑

编辑 `plugin.py`，实现对应扩展点的抽象方法。

### 3. 开发期间安装

开发时插件代码直接放在 `backend/app/plugins/` 目录下，通过管理后台上传 `.nap` 包或通过入口点安装：

```
POST /admin/plugins/install
{ "entry_point": "app.plugins.my_plugin.plugin.MyPlugin" }
```

或上传 `.nap` 包：
```
POST /admin/plugins/upload  (multipart/form-data, file=xxx.nap)
```

> 如果目录已存在但数据库无安装记录（开发模式），系统会跳过文件拷贝直接注册插件。

### 4. 启用插件

安装后插件状态为 `installed`，需要在管理后台手动**启用**。启用时会：
- 调用 `on_enable()` 钩子
- 注册扩展点（路由、技能、适配器等）
- SkillPlugin 自动创建技能包和技能记录

---

## 插件生命周期

```
安装 ──► on_install()    ──► DB 记录创建（status: installed）
                                    │
启用 ──► on_enable()     ──► 扩展点注册 + SkillPlugin 装配（status: enabled）
                                    │
                              [插件运行中]
                                    │
禁用 ──► on_disable()    ──► 扩展点注销（status: disabled）
                                    │
卸载 ──► on_uninstall()  ──► 迁移回滚 + DB 记录删除

升级 ──► on_upgrade(from_version) ──► DB 更新新版本
```

### 生命周期钩子

```python
async def on_install(self, ctx: PluginContext) -> None:
    """安装时调用一次。
    用途：初始化默认数据。
    注意：数据库迁移由 PluginManager 统一执行，不要在此处手动调用。
    注意：此时 SkillPackage 尚未创建，不要在此处绑定技能包。"""

async def on_enable(self, ctx: PluginContext) -> None:
    """每次启用时调用（在扩展点注册和 SkillPlugin 装配之前）。
    用途：注册事件处理器、初始化资源。
    注意：此时 SkillPackage 尚未创建。"""

async def on_after_enable(self, ctx: PluginContext) -> None:
    """启用后回调（在 SkillPluginProvisioner.provision 之后执行）。
    用途：创建 Agent、绑定技能包、注册功能分配。
    此时 SkillPackage 已由 SkillPluginProvisioner 创建，可以安全绑定。
    该钩子失败不会阻断启用流程（non-blocking）。"""

async def on_disable(self, ctx: PluginContext) -> None:
    """每次禁用时调用。
    用途：清理资源、注销处理器。"""

async def on_uninstall(self, ctx: PluginContext) -> None:
    """永久卸载时调用。
    用途：清理 Agent、删除自定义数据。
    注意：数据库迁移回滚由 PluginManager 统一执行。"""

async def on_upgrade(self, ctx: PluginContext, from_version: str) -> None:
    """版本升级时调用。
    用途：数据迁移、配置格式转换。"""
```

### 启用阶段执行顺序

```
enable_platform()
  ├── on_enable()                    ← 插件自定义逻辑
  ├── extension_registry.register()  ← 注册路由/技能类型/适配器
  ├── SkillPluginProvisioner.provision()  ← 创建 SkillPackage + Skill
  ├── on_after_enable()              ← 🔑 此时 SkillPackage 已存在
  ├── savepoint.commit()
  └── status → enabled
```

> **重要**：如果需要在启用时创建 Agent 并绑定 SkillPackage，
> 必须放在 `on_after_enable()` 中，而不是 `on_install()` 或 `on_enable()` 中。

### PluginContext

```python
ctx.db           # AsyncSession — 数据库会话
ctx.logger       # Logger — 带插件名的日志实例
ctx.config       # dict — 插件配置
ctx.plugin_name  # str — 插件标识名
```

> **重要**：`on_install` 中的异常如果不 catch，会导致安装失败并回滚。
> 非关键操作（如创建 Agent）建议用 try-catch 包裹，失败时记录警告但不阻断安装。

---

## 插件元数据

### 必须实现的 Property

```python
@property
def name(self) -> str:
    """插件唯一标识，小写+连字符（如 'my-plugin'）"""

@property
def display_name(self) -> str:
    """显示名称，支持 i18n key（如 _('plugin.my.display_name')）"""

@property
def version(self) -> str:
    """语义化版本号（如 '1.0.0'）"""
```

### 可选 Property

```python
@property
def description(self) -> str: ...          # 插件描述（支持 i18n）
def author(self) -> str: ...               # 作者
def icon(self) -> str: ...                 # 图标（见下方图标章节）
def scope(self) -> str: ...                # 作用域：all_tenants / platform_only / global
def config_schema(self) -> dict | None: ...  # 配置表单 JSON Schema
def default_config(self) -> dict: ...      # 默认配置值
def required_permissions(self) -> list[str]: ...  # 权限声明
def dependencies(self) -> dict[str, str]: ...     # 依赖插件
def conflicts(self) -> list[str]: ...      # 冲突插件
def platform_version(self) -> str | None: ...     # 最低平台版本
```

---

## 扩展点详解

### SkillPlugin（技能插件）

注册自定义技能类型，自动创建技能包和技能记录，供 Agent 绑定调用。

```python
from app.plugins.extensions.skill_plugin import SkillPlugin
from app.ai.tools.types import ToolDefinition, ToolParameter

class MySkillPlugin(SkillPlugin):
    @property
    def name(self) -> str:
        return "my-skill"

    @property
    def display_name(self) -> str:
        return _("plugin.my_skill.display_name")

    @property
    def version(self) -> str:
        return "1.0.0"

    def get_skill_type(self) -> str:
        """技能类型标识（全局唯一）"""
        return "my_skill"

    def get_skill_display_name(self) -> str:
        """技能显示名称"""
        return _("plugin.my_skill.skill.display_name")

    def get_skill_icon(self) -> str:
        """技能图标"""
        return "lucide:zap"

    def get_skill_config_schema(self) -> dict:
        """技能配置 JSON Schema"""
        return {
            "type": "object",
            "properties": {
                "api_key": {"type": "string", "title": "API Key"},
            },
        }

    def resolve(self, skill_config: dict) -> list[ToolDefinition]:
        """将技能配置解析为 LLM 可调用的 ToolDefinition 列表"""
        return [
            ToolDefinition(
                name="my_tool",
                description=_("plugin.my_skill.tool.desc"),
                parameters=[
                    ToolParameter(
                        name="query",
                        type="string",
                        description="查询内容",
                        required=True,
                    ),
                ],
                config=skill_config,
                timeout=30,
            ),
        ]

    async def execute(self, tool_name: str, arguments: dict, context) -> str:
        """执行工具调用，返回结果给 LLM"""
        if tool_name == "my_tool":
            return f"查询结果: {arguments['query']}"
        return ""
```

**启用时自动装配**：
1. 创建 `SkillPackage` 记录（技能包）
2. 创建 `Skill` 记录（技能）
3. 注册到 ExtensionRegistry

### ApiPlugin（API 端点插件）

```python
from app.plugins.extensions.api_plugin import ApiPlugin

class MyApiPlugin(ApiPlugin):
    def get_router(self):
        from fastapi import APIRouter
        router = APIRouter()

        @router.get("/items")
        async def list_items():
            return {"items": []}

        return router

    def get_route_prefix(self) -> str:
        return ""  # 路由挂载到 /plugins/{name}/

    def get_auth_level(self) -> str:
        """认证级别：
        - 'public': 无需认证
        - 'auth_only': 需要平台管理员登录（默认）
        - 'admin_only': 需要超级管理员
        - 'tenant_auth': 需要租户管理员登录
        """
        return "tenant_auth"
```

### 复合插件（多扩展点）

同时实现多个扩展点，使用 Python 多继承：

```python
class MyCompositePlugin(ApiPlugin, SkillPlugin):
    """同时提供 API 端点和 AI 技能"""

    # ApiPlugin 方法
    def get_router(self): ...
    def get_route_prefix(self): ...
    def get_auth_level(self): ...

    # SkillPlugin 方法
    def get_skill_type(self): ...
    def resolve(self, config): ...
    async def execute(self, tool_name, args, ctx): ...
```

---

## 数据库迁移

### 迁移文件规范

放在 `{plugin_dir}/migrations/` 目录下，文件名格式：

```
NNN_description.sql          # 升级脚本
NNN_description.down.sql     # 降级脚本（可选，用于卸载回滚）
```

示例：
```
migrations/
├── 001_create_documents_table.sql
├── 001_create_documents_table.down.sql
├── 002_create_versions_table.sql
└── 002_create_versions_table.down.sql
```

### 升级脚本示例

```sql
-- 001_create_documents_table.sql
CREATE TABLE IF NOT EXISTS my_plugin_documents (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL,
    title VARCHAR(500) NOT NULL DEFAULT '',
    content TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'draft',
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    deleted_at TIMESTAMP WITHOUT TIME ZONE,
    delete_level VARCHAR(20),
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT (NOW() AT TIME ZONE 'utc'),
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT (NOW() AT TIME ZONE 'utc')
);

CREATE INDEX IF NOT EXISTS ix_my_doc_tenant ON my_plugin_documents (tenant_id);
```

### 降级脚本示例

```sql
-- 001_create_documents_table.down.sql
DROP TABLE IF EXISTS my_plugin_documents CASCADE;
```

### 执行机制

- **安装时**：`PluginManager.install()` 自动按编号顺序执行未执行的 `.sql` 文件
- **卸载时**：自动按编号倒序执行 `.down.sql` 文件
- **幂等性**：已执行的迁移记录在 `plugin_migrations` 表中，不会重复执行
- **注意**：`on_install` 钩子中**不要**手动调用 `run_migrations()`，由 Manager 统一执行

### 表命名约定

- 表名前缀使用插件缩写：如 `rich_editor_documents`、`my_plugin_items`
- 避免与平台核心表或其他插件表冲突
- 模型继承 `TenantModel`（租户级资源）或 `BaseModel`（全局资源）

---

## 多语言（i18n）

### 后端翻译文件

放在 `{plugin_dir}/locales/` 目录下：

```
locales/
├── zh-CN.json    # 中文
└── en-US.json    # 英文
```

> **文件名格式**：支持 `zh-CN.json`、`zh_CN.json`、`en-US.json`、`en.json` 等格式，
> 系统会自动匹配当前 locale。

### 翻译文件结构

```json
{
  "plugin": {
    "my_plugin": {
      "display_name": "我的插件",
      "description": "插件描述",
      "config": {
        "api_key": "API 密钥",
        "timeout": "超时时间（秒）"
      },
      "error": {
        "not_found": "资源不存在",
        "access_denied": "无权访问"
      },
      "message": {
        "created": "创建成功",
        "deleted": "删除成功"
      }
    }
  }
}
```

### 在代码中使用

```python
from app.core.i18n import _

# 在 property 中
@property
def display_name(self) -> str:
    return _("plugin.my_plugin.display_name")

# 在业务逻辑中
raise NotFoundException(
    message=_("plugin.my_plugin.error.not_found"),
)
```

### 翻译加载机制

- 系统启动时自动扫描 `app/plugins/*/locales/` 目录
- 插件翻译与平台核心翻译深度合并
- 安装/卸载插件后自动清除翻译缓存
- 无需手动注册翻译文件

### 前端翻译文件

如果插件有前端 UI，翻译文件放在：

```
frontend/apps/web-antd/src/locales/langs/zh-CN/tenant/myPlugin.json
frontend/apps/web-antd/src/locales/langs/en-US/tenant/myPlugin.json
```

使用方式：`$t('tenant.myPlugin.xxx')` 或 `_('tenant.myPlugin.xxx')`

---

## 插件配置

### 配置 Schema

通过 `config_schema` property 返回 JSON Schema，前端自动渲染配置表单：

```python
@property
def config_schema(self) -> dict:
    return {
        "type": "object",
        "properties": {
            "enabled": {
                "type": "boolean",
                "title": _("plugin.my.config.enabled"),
                "default": True,
            },
            "timeout": {
                "type": "integer",
                "title": _("plugin.my.config.timeout"),
                "default": 30,
                "minimum": 5,
                "maximum": 300,
            },
            "mode": {
                "type": "string",
                "title": _("plugin.my.config.mode"),
                "enum": ["fast", "balanced", "quality"],
                "default": "balanced",
            },
        },
    }
```

### 默认配置

```python
@property
def default_config(self) -> dict:
    return {
        "enabled": True,
        "timeout": 30,
        "mode": "balanced",
    }
```

### 配置合并

平台支持两级配置：
- **插件默认配置**：`default_config`
- **租户自定义配置**：租户管理员可覆盖部分字段

实际配置 = `deep_merge(default_config, tenant_config)`

---

## 插件图标

支持四种格式：

| 格式 | 示例 | 说明 |
|------|------|------|
| **Iconify** | `lucide:file-edit` | 推荐，无需额外文件 |
| **本地图片** | `/static/plugins/my-plugin/icon.png` | 放在 `frontend/apps/web-antd/public/static/` 下 |
| **远程 URL** | `https://example.com/icon.png` | 外部图片地址 |
| **Base64** | `data:image/png;base64,iVBOR...` | 内联图片 |

在 `manifest.json` 和 `icon` property 中设置：

```python
@property
def icon(self) -> str:
    return "lucide:file-edit"  # Iconify 图标名
```

---

## manifest.json 规范

```json
{
  "name": "my-plugin",
  "display_name": "My Plugin",
  "version": "1.0.0",
  "description": "插件描述",
  "author": "开发者",
  "plugin_type": "composite",
  "scope": "all_tenants",
  "entry_point": "plugin.MyPlugin",
  "icon": "lucide:plug",
  "is_system": false,
  "required_permissions": ["db:read", "db:write", "api:register"],
  "dependencies": {},
  "conflicts": [],
  "platform_version": ">=0.1.0"
}
```

### 必填字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `name` | string | 唯一标识，小写+连字符 |
| `version` | string | 语义化版本号 |
| `entry_point` | string | 入口类路径（相对于插件目录） |

### 可选字段

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `display_name` | string | `name` | 显示名称 |
| `description` | string | `""` | 描述 |
| `author` | string | `""` | 作者 |
| `plugin_type` | string | `"composite"` | `adapter` / `tool` / `hook` / `api` / `skill` / `composite` |
| `scope` | string | `"all_tenants"` | `all_tenants` / `platform_only` / `global` |
| `icon` | string | `""` | 图标 |
| `is_system` | boolean | `false` | 系统内置插件（不可卸载） |
| `required_permissions` | string[] | `[]` | 权限声明 |
| `dependencies` | object | `{}` | `{"other-plugin": ">=1.0.0"}` |
| `conflicts` | string[] | `[]` | 冲突插件列表 |
| `platform_version` | string | `null` | 最低平台版本 |
| `provides` | string[] | `[]` | 提供的扩展类型：`["skill", "api", "hook"]` |
| `skill_type` | string | `""` | SkillPlugin 的技能类型标识 |
| `agents` | object[] | `[]` | 声明的智能体列表（安装向导展示+模型选择） |
| `models` | string[] | `[]` | 插件使用的数据库模型名称（安装向导展示） |
| `migrations` | string[] | `[]` | 迁移脚本编号列表 |

---

## .nap 打包格式

`.nap` 文件是标准 ZIP 压缩包，包含插件源码：

```
my-plugin-1.0.0.nap (ZIP)
├── manifest.json        # 必须
├── plugin.py            # 必须（入口点）
├── __init__.py
├── requirements.txt     # Python 依赖
├── locales/             # 翻译文件
│   ├── zh-CN.json
│   └── en-US.json
├── migrations/          # 数据库迁移
│   ├── 001_xxx.sql
│   └── 001_xxx.down.sql
└── ...                  # 其他源码文件
```

### CLI 命令

```bash
# 创建插件骨架
python scripts/novusai_plugin.py init <name> --type <type> --author <author>

# 打包为 .nap
python scripts/novusai_plugin.py pack <directory> [--output <path>]

# 校验 .nap 包
python scripts/novusai_plugin.py validate <file.nap>
```

---

## 安装方式对比

| 方式 | 适用场景 | install_source |
|------|----------|----------------|
| **入口点安装** | 开发调试 | `entry_point` |
| **上传 .nap 安装** | 生产部署、交付 | `local` |
| **应用商店安装** | 从 Marketplace 下载 | `marketplace` |

> 开发期间推荐直接在 `app/plugins/` 下写代码，然后通过上传 `.nap` 安装注册到数据库。
> 如果目录已存在但数据库无记录，系统会跳过文件拷贝直接注册。

---

## Agent 集成（SkillPlugin 专属）

### manifest.json 声明 agents

如果插件会创建智能体，**必须在 manifest.json 中声明 `agents` 字段**。
安装向导据此展示插件结构，并在含智能体时要求用户选择 AI 模型。

```json
{
  "agents": [
    {
      "name": "my-plugin-agent",
      "description": "插件专属 AI 助手的功能描述",
      "recommended_model": "支持 function calling 的 Chat 模型（如 GPT-4o、Claude 3.5 Sonnet）"
    }
  ]
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `name` | string | Agent 唯一名称（对应 `Agent.name`） |
| `description` | string | Agent 用途说明（显示在安装预览中） |
| `recommended_model` | string | 推荐的模型类型说明（显示在安装预览中） |

### 自动创建 Agent

SkillPlugin 应在 `on_after_enable` 中创建专属 Agent（此时 SkillPackage 已创建）：

```python
async def on_after_enable(self, ctx: PluginContext) -> None:
    """在 SkillPluginProvisioner.provision 之后执行"""
    await self._provision_agent(ctx)

async def _provision_agent(self, ctx):
    from app.models.ai.agent import Agent
    from app.models.system.agent_assignment import SystemAgentAssignment

    db = ctx.db

    # 幂等检查
    # ...

    # ✅ 优先使用用户在安装/启用时选择的模型（ctx.model_id）
    # 回退到平台默认模型
    selected_model_id = ctx.model_id
    if not selected_model_id:
        selected_model_id = await self._get_default_model_id(db)
    if not selected_model_id:
        logger.warning("No active AI model found, agent creation deferred")
        return

    # 创建 Agent
    agent = Agent(
        name="my-plugin-agent",
        system_prompt="你是一个 xxx 助手...",
        model_id=selected_model_id,
        is_system=True,
        status="published",
    )
    db.add(agent)
    await db.flush()

    # 注册功能分配（resolve 机制）
    assignment = SystemAgentAssignment(
        feature_code="my_plugin",
        feature_name=_("plugin.my.feature_name"),
        agent_id=agent.id,
        is_active=True,
    )
    db.add(assignment)
```

### Resolve 机制

前端通过 resolve API 获取绑定的 Agent：

```
GET /tenant/ai/agent-assignments/resolve/{feature_code}
→ { agent_id, agent_name, is_active, is_override }
```

租户可在「功能分配」中覆盖 Agent → 下次打开插件自动使用新 Agent。

### 智能体模型选择（重要）

插件创建 Agent 时需要指定 `model_id`（NOT NULL 约束）。但**插件开发者无法预知部署环境中有哪些可用模型**。

**最优解：使用 `ctx.model_id`**（用户在安装/启用时选择的模型）：

```python
# ✅ 最佳做法：优先用户选择，回退平台默认
selected_model_id = ctx.model_id  # 安装向导中用户选择的模型
if not selected_model_id:
    selected_model_id = await self._get_default_model_id(db)
```

**安装流程**：

1. 用户上传 `.nap` 包 → 安装向导解析 manifest
2. 向导检测到 `agents` 声明 → 显示模型选择下拉
3. 用户选择模型 → 点击「确认安装」
4. `model_id` 通过 `PluginContext.model_id` 传递给 `on_after_enable()`
5. 插件用此 `model_id` 创建 Agent

> **允许但不推荐**：在 `plugin.py` 中硬编码 `model_id` 或 `model_code`。
> 这会导致在没有该特定模型的环境中安装失败。

**在 README.md 中说明推荐模型**：
```markdown
## 推荐模型

本插件的 AI 功能推荐使用以下模型：
- **最佳效果**：GPT-4o / Claude 3.5 Sonnet（支持复杂续写、代码理解）
- **性价比**：GPT-4o-mini / DeepSeek-Chat（日常编辑场景）
- **要求**：必须支持 function calling

安装时安装向导会提示选择模型。安装后也可在「智能体管理」中修改模型配置。
```

**安装后可在管理后台手动调整**：
- 「智能体管理」→ 找到插件创建的 Agent → 修改模型
- 「功能分配」→ 租户可覆盖绑定不同的 Agent

> **注意**：如果安装时未选择模型且平台没有配置任何 AI 模型，Agent 创建会被跳过。
> 管理员需先在「模型管理」中添加模型，然后禁用再启用插件来触发 Agent 创建。

---

## 插件文档（README）

### 编写 README

在插件根目录放置 `README.md` 文件，管理员可在插件详情中点击「查看文档」阅读：

```
my_plugin/
├── README.md          ← 插件使用文档
├── plugin.py
└── ...
```

推荐包含以下章节：
- **功能特性**：列出插件提供的核心功能
- **配置项**：每个配置字段的说明和默认值
- **使用方式**：安装启用后的操作步骤
- **API 端点**：如果是 ApiPlugin，列出所有端点
- **技术栈**：使用的主要技术

### API 端点

管理后台通过以下 API 读取插件文档：

```
GET /admin/plugins/{plugin_id}/readme
→ { "plugin_name": "my-plugin", "has_readme": true, "content": "..." }
```

---

## 技能类型 i18n（SkillPlugin 专属）

如果插件注册了新的 `skill_type`，需要在前端 i18n 中添加对应的类型名和描述：

### 添加位置

```
frontend/apps/web-antd/src/locales/langs/zh-CN/admin/ai.json
frontend/apps/web-antd/src/locales/langs/en-US/admin/ai.json
```

### 需要添加的 key

```json
{
  "skill": {
    "type_options": {
      "my_skill": "我的技能"          // ← 下拉选项显示名
    },
    "typeDesc": {
      "my_skill": "技能描述文本..."    // ← 技能详情页说明
    }
  }
}
```

> 如果不添加这些 key，前端会显示原始 key 字符串（如 `admin.ai.skill.typeDesc.my_skill`）。

---

## 开发最佳实践

### 命名规范

- 插件名：小写+连字符（`my-awesome-plugin`）
- 目录名：小写+下划线（`my_awesome_plugin`）
- 表名前缀：插件缩写+下划线（`map_items`、`red_documents`）

### 安全

- **禁止硬编码密钥**，通过 `config_schema` 的 `format: "password"` 字段让用户配置
- API 端点使用 `get_auth_level()` 指定认证级别
- 租户级资源使用 `TenantModel` + `TenantRepository` 自动隔离

### 错误处理

- `on_install` / `on_enable` 中的非关键操作用 try-catch 包裹
- 使用平台统一异常：`NotFoundException`、`BusinessException`、`ValidationException`
- 使用 i18n key 作为错误消息，不要硬编码中文

### 国际化

- 所有用户可见的字符串必须使用 `_()`
- 禁止硬编码中文字符串
- 翻译文件 key 结构：`plugin.{plugin_name}.{category}.{key}`

### 性能

- 数据库查询使用索引，在迁移 SQL 中创建索引
- 避免 N+1 查询，使用 joinedload 或批量查询
- 大文件操作使用异步 IO

### 版本管理

- 严格遵循语义化版本（semver）
- 破坏性变更升 major，新功能升 minor，修复升 patch
- 迁移文件编号只增不减

---

## 完整示例

参考项目中的 `rich-editor` 插件（`backend/app/plugins/rich_editor/`）：

- **复合插件**：同时实现 `ApiPlugin`（文档 CRUD）+ `SkillPlugin`（8 个 AI 工具）
- **数据库迁移**：5 张表的创建和回滚 SQL
- **多语言**：zh-CN + en-US 完整翻译
- **Agent 集成**：自动创建 Agent + 注册功能分配
- **前端模板**：API 客户端 + 类型定义 + 组件模板
