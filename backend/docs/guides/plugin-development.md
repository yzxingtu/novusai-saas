# Plugin Development Guide

## 1. Architecture Overview

The NovusAI plugin system provides a modular architecture for extending platform capabilities without modifying core code.

```
app/plugins/
├── base.py              # BasePlugin abstract class
├── context.py           # PluginContext (injected capabilities)
├── manager.py           # PluginManager (lifecycle orchestrator)
├── packaging.py         # .nap package format tools
├── security.py          # Manifest validation, config encryption
├── dependencies.py      # Dependency & conflict resolution
├── migration_runner.py  # Database migration execution
├── dev_watcher.py       # Dev-mode hot reload
├── extensions/          # Extension point interfaces
│   ├── adapter_plugin.py
│   ├── api_plugin.py
│   ├── hook_plugin.py
│   ├── skill_plugin.py
│   └── tool_plugin.py
├── builtin/             # System plugins (is_system=True)
└── examples/            # Reference implementations
```

### Plugin Lifecycle

```
Install → Enable → (Running) → Disable → Uninstall
                      ↑
                   Upgrade
```

| State | Description |
|-------|-------------|
| `installed` | Plugin registered in DB, code loaded, not active |
| `enabled` | Extensions registered, routes mounted, events subscribed |
| `disabled` | Extensions unregistered, routes removed |
| `uninstalled` | DB record deleted, files cleaned up |

## 2. Extension Point Types

### 2.1 AdapterPlugin — AI Provider Adapters

Register custom AI model provider adapters (OpenAI-compatible, Anthropic, etc.).

```python
from app.plugins.extensions.adapter_plugin import AdapterPlugin
from app.ai.adapters.base import BaseAdapter

class MyAdapterPlugin(AdapterPlugin):
    @property
    def name(self) -> str:
        return "my-ai-provider"

    @property
    def display_name(self) -> str:
        return "My AI Provider"

    @property
    def version(self) -> str:
        return "1.0.0"

    def get_provider_info(self) -> dict:
        return {"name": "my-provider", "display_name": "My Provider"}

    def get_adapter_class(self) -> type[BaseAdapter]:
        from .adapter import MyAdapter
        return MyAdapter
```

### 2.2 ApiPlugin — Custom API Endpoints

Register custom FastAPI routes under `/plugins/{plugin-name}/`.

```python
from app.plugins.extensions.api_plugin import ApiPlugin

class WebhookPlugin(ApiPlugin):
    @property
    def name(self) -> str:
        return "my-webhook"

    # ... other properties ...

    def get_auth_level(self) -> str:
        """Auth level: "public", "auth_only" (default), "admin_only" """
        return "public"

    def get_router(self):
        from fastapi import APIRouter
        router = APIRouter()

        @router.post("/receive")
        async def receive(payload: dict):
            return {"status": "ok"}

        @router.get("/status")
        async def status():
            return {"healthy": True}

        return router
```

### 2.3 HookPlugin — Event Subscribers

Subscribe to system events (agent creation, conversation completion, etc.).

```python
from app.plugins.extensions.hook_plugin import HookPlugin, EventHandler

class AuditPlugin(HookPlugin):
    @property
    def name(self) -> str:
        return "audit-logger"

    # ... other properties ...

    def get_event_handlers(self):
        from app.ai.events.types import ConversationCompleted, ToolCallFailed
        return [
            (ConversationCompleted, self._on_conversation_done, 100),
            (ToolCallFailed, self._on_tool_failed, 100),
        ]

    async def _on_conversation_done(self, event):
        # event.conversation_id, event.total_tokens, etc.
        pass

    async def _on_tool_failed(self, event):
        # event.tool_name, event.error, etc.
        pass
```

### 2.4 ToolPlugin — AI Tool Definitions

Register tools that AI agents can invoke.

```python
from app.plugins.extensions.tool_plugin import ToolPlugin

class WeatherPlugin(ToolPlugin):
    @property
    def name(self) -> str:
        return "weather-tool"

    # ... other properties ...

    def get_tool_definitions(self):
        from app.ai.tools.registry import ToolDefinition
        return [
            ToolDefinition(
                name="get_weather",
                description="Get current weather for a location",
                parameters={
                    "type": "object",
                    "properties": {
                        "city": {"type": "string", "description": "City name"}
                    },
                    "required": ["city"],
                },
                handler=self._get_weather,
            ),
        ]

    async def _get_weather(self, city: str) -> dict:
        return {"city": city, "temp": "22°C", "condition": "sunny"}
```

### 2.5 SkillPlugin — Configurable Skill Packages

Register skill types that can be bound to agents with custom configurations.

```python
from app.plugins.extensions.skill_plugin import SkillPlugin

class SlackSkillPlugin(SkillPlugin):
    @property
    def name(self) -> str:
        return "slack-notify"

    # ... other properties ...

    def get_skill_type(self) -> str:
        return "slack_notification"

    def get_skill_config_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "webhook_url": {"type": "string", "format": "uri"},
                "channel": {"type": "string"},
            },
            "required": ["webhook_url"],
        }

    def resolve(self, skill_config: dict) -> list:
        # Return ToolDefinition list based on config
        return [...]

    async def execute(self, tool_name: str, arguments: dict, context) -> dict:
        # Execute the tool
        return {"status": "sent"}
```

## 3. Manifest Reference

Every plugin requires a `manifest.json`:

```json
{
  "name": "my-plugin",
  "display_name": "My Plugin",
  "version": "1.0.0",
  "description": "What this plugin does",
  "author": "Your Name",
  "plugin_type": "composite",
  "entry_point": "plugin.MyPlugin",
  "icon": "lucide:plug",
  "homepage": "https://github.com/...",
  "config_schema": null,
  "default_config": {},
  "required_permissions": [],
  "dependencies": {},
  "conflicts": [],
  "provides": [],
  "platform_version": null,
  "frontend": {
    "endpoint": "admin",
    "menus": [],
    "routes": [],
    "locales": {}
  }
}
```

### Field Reference

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | Yes | Unique identifier (lowercase, hyphens, `^[a-z][a-z0-9-]*[a-z0-9]$`) |
| `display_name` | string | Yes | Human-readable name |
| `version` | string | Yes | Semver (e.g., `1.0.0`, `2.1.0-beta.1`) |
| `entry_point` | string | Yes | Dotted Python path (e.g., `plugin.MyPlugin`) |
| `description` | string | No | Plugin description |
| `author` | string | No | Author name |
| `plugin_type` | string | No | `adapter`, `tool`, `hook`, `api`, `skill`, `composite` |
| `icon` | string | No | Icon identifier (e.g., `lucide:plug`) |
| `homepage` | string | No | Project URL |
| `config_schema` | object | No | JSON Schema for plugin configuration |
| `default_config` | object | No | Default configuration values |
| `required_permissions` | array | No | Required capabilities (see Permissions) |
| `dependencies` | object | No | Plugin dependencies (`{"name": ">=1.0.0"}`) |
| `conflicts` | array | No | Conflicting plugin names |
| `provides` | array | No | Capabilities provided (`["skill"]`, `["hook"]`, etc.) |
| `platform_version` | string | No | Platform version constraint (e.g., `>=2.0.0`) |
| `frontend` | object | No | Frontend page/menu registration (see Frontend section) |

### Permissions

| Permission | Description |
|------------|-------------|
| `db:read` | Read database access |
| `db:write` | Write database access |
| `http:outbound` | Make external HTTP requests |
| `tool:register` | Register AI tools |
| `event:subscribe` | Subscribe to system events |
| `event:publish` | Publish system events |
| `api:register` | Register custom API routes |
| `skill:register` | Register skill types |
| `config:read` | Read platform configuration |
| `config:write` | Write platform configuration |
| `storage:read` | Read file storage |
| `storage:write` | Write file storage |

## 4. Lifecycle Hooks

Override these methods in your plugin class:

```python
async def on_install(self, ctx: PluginContext) -> None:
    """Called once during installation. Set up initial state."""

async def on_uninstall(self, ctx: PluginContext) -> None:
    """Called before uninstallation. Clean up resources."""

async def on_enable(self, ctx: PluginContext) -> None:
    """Called when plugin is enabled. Start services."""

async def on_disable(self, ctx: PluginContext) -> None:
    """Called when plugin is disabled. Stop services."""

async def on_upgrade(self, ctx: PluginContext, old_version: str) -> None:
    """Called during upgrade. Migrate data if needed."""
```

The `PluginContext` provides:
- `ctx.logger` — Plugin-specific logger
- `ctx.db` — Database session (if `db:read`/`db:write` declared)
- `ctx.event_bus` — Event bus (if `event:subscribe`/`event:publish` declared)
- `ctx.tool_registry` — Tool registry (if `tool:register` declared)

## 5. Database Migrations

Place SQL migration files in your plugin directory:

```
my-plugin/
├── manifest.json
├── plugin.py
└── migrations/
    ├── 001_create_table.sql
    ├── 001_create_table.down.sql
    ├── 002_add_column.sql
    └── 002_add_column.down.sql
```

- Forward migrations: `NNN_description.sql`
- Rollback migrations: `NNN_description.down.sql`
- Executed automatically during install, rolled back during uninstall

## 6. Frontend Integration

### Page Registration

Declare frontend routes and menus in `manifest.json`:

```json
{
  "frontend": {
    "endpoint": "admin",
    "menus": [
      {
        "code": "PluginMyFeature",
        "name": "My Feature",
        "path": "/my-feature",
        "component": "/plugins/my-plugin/index",
        "icon": "lucide:star",
        "sort_order": 100
      }
    ]
  }
}
```

Place Vue components at `frontend/apps/web-antd/src/views/plugins/{plugin-name}/`.

### i18n

Place translation files in your plugin directory:

```
my-plugin/
├── locales/
│   ├── zh-CN.json
│   └── en-US.json
```

Or inline in manifest:

```json
{
  "frontend": {
    "locales": {
      "zh-CN": {"plugin": {"my-plugin": {"title": "我的插件"}}},
      "en-US": {"plugin": {"my-plugin": {"title": "My Plugin"}}}
    }
  }
}
```

## 7. Packaging & Distribution

### Create a Plugin

```bash
# Scaffold a new plugin
python -c "from app.plugins.packaging import scaffold_plugin; scaffold_plugin('./plugins', 'my-plugin', 'hook')"
```

### Pack as .nap

```python
from app.plugins.packaging import pack_plugin
nap_path = pack_plugin("./plugins/my-plugin")
# Creates my-plugin-1.0.0.nap
```

### Install via API

```bash
# Upload .nap file
curl -X POST /admin/plugins/upload \
  -F "file=@my-plugin-1.0.0.nap"

# Enable
curl -X POST /admin/plugins/{id}/enable
```

## 8. Security

- **Sensitive config fields** marked with `"format": "password"` in `config_schema` are automatically encrypted at rest
- **Permissions** are enforced — undeclared capabilities are not injected into `PluginContext`
- **API routes** default to `auth_only` (requires authenticated admin). Override `get_auth_level()` for public or admin-only
- **Zip slip** attacks are prevented during package extraction
- **Plugin names** are validated against path traversal patterns

## 9. Development Mode

In `DEBUG=True` mode, the dev watcher monitors plugin files for changes:

```python
# In app startup
from app.plugins.dev_watcher import start_plugin_watcher
await start_plugin_watcher(app)
```

Changes to `.py` files in the plugins directory trigger automatic module cache clearing. The plugin reloads on next access.

## 10. Common Pitfalls

1. **Missing abstract methods** — Each extension point has required methods. Check the base class.
2. **Skill type conflicts** — Two plugins cannot register the same `skill_type`. You'll get a `ConflictException`.
3. **System plugins** — Plugins with `is_system=True` cannot be uninstalled or disabled.
4. **Concurrent operations** — The `PluginManager` uses an async lock for write operations (install/uninstall/enable/disable/upgrade).
5. **Config encryption** — Don't read raw DB values for password fields. Use `decrypt_sensitive_config()`.
