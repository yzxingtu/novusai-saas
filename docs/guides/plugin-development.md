# NovusAI Plugin Development Guide

## Overview

NovusAI's plugin system allows developers to extend platform capabilities through four extension points:

| Extension Point | Base Class | Purpose |
|----------------|------------|---------|
| **AdapterPlugin** | `AdapterPlugin` | Add AI model provider adapters (OpenAI, Anthropic, etc.) |
| **ToolPlugin** | `ToolPlugin` | Register custom tool types for AI agents |
| **HookPlugin** | `HookPlugin` | Subscribe to system events via EventBus |
| **ApiPlugin** | `ApiPlugin` | Mount custom REST API routes |

All plugins inherit from `BasePlugin` and follow a consistent lifecycle.

---

## Quick Start

### 1. Scaffold a New Plugin

```bash
cd backend
python scripts/novusai_plugin.py init my-weather-tool --type tool --author "Your Name"
```

This creates:

```
my-weather-tool/
├── manifest.json      # Plugin metadata
├── plugin.py          # Entry point
├── __init__.py
├── README.md
└── CHANGELOG.md
```

### 2. Implement Your Plugin

Edit `plugin.py` — see [Extension Point API Reference](#extension-point-api-reference) for your specific type.

### 3. Pack & Install

```bash
# Pack into .nap file
python scripts/novusai_plugin.py pack my-weather-tool/

# Validate the package
python scripts/novusai_plugin.py validate my-weather-tool-0.1.0.nap

# Install via admin panel: upload the .nap file
# Or install via entry_point for development:
#   POST /admin/plugins/install { "entry_point": "my_weather_tool.plugin.MyWeatherToolPlugin" }
```

---

## Plugin Lifecycle

```
install ──► on_install() ──► DB record created (status: installed)
                                    │
enable  ──► on_enable()  ──► Extensions registered (status: enabled)
                                    │
                              [Plugin is active]
                                    │
disable ──► on_disable() ──► Extensions unregistered (status: disabled)
                                    │
uninstall ► on_uninstall() ► DB record deleted

upgrade ──► on_upgrade(from_version) ──► DB updated with new version
```

### Lifecycle Hooks

```python
async def on_install(self, ctx: PluginContext) -> None:
    """Called once when plugin is first installed.
    Use for: creating DB tables, initializing default data."""

async def on_enable(self, ctx: PluginContext) -> None:
    """Called each time plugin is enabled.
    Use for: registering event handlers, setting up resources."""

async def on_disable(self, ctx: PluginContext) -> None:
    """Called each time plugin is disabled.
    Use for: cleanup, unregistering handlers."""

async def on_uninstall(self, ctx: PluginContext) -> None:
    """Called when plugin is permanently removed.
    Use for: dropping DB tables, deleting files."""

async def on_upgrade(self, ctx: PluginContext, from_version: str) -> None:
    """Called when upgrading from an older version.
    Use for: data migrations between versions."""
```

### PluginContext

Every lifecycle hook receives a `PluginContext` with:

- `ctx.db` — AsyncSession for database access
- `ctx.logger` — Scoped logger instance
- `ctx.config` — Plugin configuration dict
- `ctx.plugin_name` — Plugin identifier

---

## Plugin Metadata (Properties)

Every plugin must implement these abstract properties:

```python
@property
def name(self) -> str:
    """Unique identifier (e.g. 'my-weather-tool'). Lowercase, hyphens allowed."""

@property
def display_name(self) -> str:
    """Human-readable name shown in UI."""

@property
def version(self) -> str:
    """Semantic version (e.g. '1.2.3')."""
```

Optional properties:

```python
@property
def description(self) -> str: ...          # Plugin description
def author(self) -> str: ...               # Author name
def homepage(self) -> str: ...             # URL
def icon(self) -> str: ...                 # Lucide icon name or URL
def config_schema(self) -> dict | None: ...  # JSON Schema for config form
def default_config(self) -> dict: ...      # Default configuration
def required_permissions(self) -> list[str]: ...  # Permission declarations
def dependencies(self) -> dict[str, str]: ...     # {"other-plugin": ">=1.0.0"}
def conflicts(self) -> list[str]: ...      # Mutually exclusive plugins
def platform_version(self) -> str | None: ...     # Min platform version
```

---

## Extension Point API Reference

### AdapterPlugin

Add a new AI model provider adapter.

```python
from app.plugins.extensions.adapter_plugin import AdapterPlugin
from app.ai.adapters.base import BaseAdapter

class MyAdapterPlugin(AdapterPlugin):
    @property
    def name(self) -> str:
        return "my-provider"

    @property
    def display_name(self) -> str:
        return "My Provider"

    @property
    def version(self) -> str:
        return "1.0.0"

    def get_adapter_class(self) -> type[BaseAdapter]:
        """Return the adapter class to register."""
        from .my_adapter import MyAdapter
        return MyAdapter

    def get_provider_info(self) -> dict[str, Any]:
        """Provider metadata for UI display."""
        return {
            "name": "my_provider",
            "display_name": "My Provider",
            "icon": "lucide:cloud",
            "base_url": "https://api.myprovider.com/v1",
            "supports": {
                "chat": True,
                "streaming": True,
                "function_calling": False,
                "vision": False,
                "embedding": False,
            },
        }

    def get_supported_features(self) -> list[str]:
        """List of supported feature flags."""
        return ["chat", "streaming"]
```

**Registration**: On enable, `AdapterRegistry.register()` is called automatically. On disable, `AdapterRegistry.unregister()` is called.

---

### ToolPlugin

Register custom tool types that AI agents can use.

```python
from app.plugins.extensions.tool_plugin import ToolPlugin, ToolDefinition

class MyToolPlugin(ToolPlugin):
    @property
    def name(self) -> str:
        return "weather-tool"

    @property
    def display_name(self) -> str:
        return "Weather Tool"

    @property
    def version(self) -> str:
        return "1.0.0"

    def get_tool_type(self) -> str:
        """Unique tool type identifier."""
        return "weather"

    def get_tool_definitions(self) -> list[ToolDefinition]:
        """Return tool definitions for LLM function calling."""
        return [
            ToolDefinition(
                name="get_weather",
                description="Get current weather for a location",
                parameters={
                    "type": "object",
                    "properties": {
                        "location": {
                            "type": "string",
                            "description": "City name",
                        },
                    },
                    "required": ["location"],
                },
            ),
        ]

    async def execute(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        ctx: Any,
    ) -> Any:
        """Execute the tool with given arguments."""
        if tool_name == "get_weather":
            location = arguments["location"]
            # Your implementation here
            return {"temperature": 22, "condition": "sunny"}

    def get_config_schema(self) -> dict[str, Any] | None:
        """Optional JSON Schema for tool configuration."""
        return {
            "type": "object",
            "properties": {
                "api_key": {
                    "type": "string",
                    "title": "API Key",
                    "format": "password",
                },
            },
            "required": ["api_key"],
        }
```

**Registration**: Tool types are tracked in `PluginManager._plugin_tools`. Use `get_all_tool_types()` to get both built-in and plugin tool types.

---

### HookPlugin

Subscribe to system events via the EventBus.

```python
from app.plugins.extensions.hook_plugin import HookPlugin
from app.ai.events.types import ExecutionCompleted, ExecutionFailed

class MyHookPlugin(HookPlugin):
    @property
    def name(self) -> str:
        return "my-analytics"

    @property
    def display_name(self) -> str:
        return "Analytics Hook"

    @property
    def version(self) -> str:
        return "1.0.0"

    def get_event_handlers(self) -> list[tuple]:
        """Return (event_type, handler, priority) tuples.
        Lower priority = earlier execution."""
        return [
            (ExecutionCompleted, self._on_completed, 10),
            (ExecutionFailed, self._on_failed, 10),
        ]

    async def _on_completed(self, event: ExecutionCompleted) -> None:
        """Handle successful execution."""
        # Log analytics, send notifications, etc.
        pass

    async def _on_failed(self, event: ExecutionFailed) -> None:
        """Handle failed execution."""
        pass
```

**Available Events** (from `app.ai.events.types`):
- `ExecutionStarted`, `ExecutionCompleted`, `ExecutionFailed`
- `MessageAdded`
- `ToolCallStarted`, `ToolCallCompleted`
- `QuotaExceeded`, `QuotaWarning`

**Error Isolation**: Handler exceptions are caught by EventBus and logged — they never affect the main flow or other handlers.

---

### ApiPlugin

Mount custom REST API routes dynamically.

```python
from fastapi import APIRouter
from app.plugins.extensions.api_plugin import ApiPlugin

class MyApiPlugin(ApiPlugin):
    @property
    def name(self) -> str:
        return "my-webhooks"

    @property
    def display_name(self) -> str:
        return "Webhook API"

    @property
    def version(self) -> str:
        return "1.0.0"

    def get_router(self) -> APIRouter:
        """Return a FastAPI router with your endpoints."""
        router = APIRouter()

        @router.get("/status")
        async def get_status():
            return {"status": "ok"}

        @router.post("/webhook")
        async def handle_webhook(data: dict):
            # Process webhook
            return {"received": True}

        return router

    def get_route_prefix(self) -> str:
        """Optional sub-prefix (appended to /plugins/{name}/)."""
        return ""

    def get_route_tags(self) -> list[str]:
        """OpenAPI tags for documentation."""
        return ["Webhooks"]
```

**Route Mounting**: Routes are mounted at `/plugins/{plugin_name}/` automatically. They inherit platform authentication middleware (tenant isolation, RBAC).

**Route Lifecycle**: Routes are added on enable via `app.include_router()` and removed on disable.

---

## manifest.json Specification

```json
{
  "name": "my-plugin",
  "display_name": "My Plugin",
  "version": "1.0.0",
  "description": "A brief description",
  "author": "Author Name",
  "plugin_type": "tool",
  "entry_point": "plugin.MyPluginPlugin",
  "icon": "lucide:plug",
  "homepage": "https://github.com/...",
  "config_schema": {
    "type": "object",
    "properties": {
      "api_key": { "type": "string", "title": "API Key", "format": "password" }
    },
    "required": ["api_key"]
  },
  "default_config": {},
  "required_permissions": ["http:outbound"],
  "dependencies": { "other-plugin": ">=1.0.0" },
  "conflicts": ["incompatible-plugin"],
  "platform_version": ">=2.0.0"
}
```

### Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Unique ID. Lowercase, hyphens, starts with letter. |
| `display_name` | string | Human-readable name. |
| `version` | string | Semantic version (`MAJOR.MINOR.PATCH`). |
| `entry_point` | string | Dotted Python path to plugin class. |

### Optional Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `description` | string | `""` | Brief description. |
| `author` | string | `""` | Author name. |
| `plugin_type` | string | `"composite"` | One of: `adapter`, `tool`, `hook`, `api`, `composite`. |
| `icon` | string | `""` | Lucide icon name or URL. |
| `homepage` | string | `""` | Project homepage URL. |
| `config_schema` | object\|null | `null` | JSON Schema for configuration form. |
| `default_config` | object | `{}` | Default configuration values. |
| `required_permissions` | string[] | `[]` | Permission declarations. |
| `dependencies` | object | `{}` | `{"plugin-name": ">=version"}` |
| `conflicts` | string[] | `[]` | Mutually exclusive plugin names. |
| `platform_version` | string\|null | `null` | Minimum platform version requirement. |

---

## .nap Package Format

A `.nap` file is a standard ZIP archive containing the plugin source:

```
my-plugin-1.0.0.nap (ZIP)
├── manifest.json        # Required
├── plugin.py            # Required (entry point)
├── __init__.py          # Recommended
├── README.md            # Optional
├── CHANGELOG.md         # Optional
├── requirements.txt     # Optional (Python dependencies)
└── src/                 # Optional (additional source files)
```

### CLI Commands

```bash
# Scaffold a new plugin
python scripts/novusai_plugin.py init <name> --type <type> --author <author>

# Pack plugin directory into .nap
python scripts/novusai_plugin.py pack <directory> [--output <path>]

# Validate a .nap package
python scripts/novusai_plugin.py validate <file.nap>
```

---

## Configuration Schema

Use standard JSON Schema to define plugin configuration. The frontend renders it as a dynamic form via `SchemaForm` component.

Supported field types:

| JSON Schema | Rendered As |
|-------------|-------------|
| `"type": "string"` | Text Input |
| `"type": "number"` / `"integer"` | Number Input |
| `"type": "boolean"` | Switch |
| `"enum": [...]` | Select Dropdown |
| `"type": "array", "items": {"enum": [...]}` | Multi-Select |
| `"format": "password"` | Password Input |
| `"format": "textarea"` | Textarea |

Supported validations: `required`, `pattern`, `minLength`, `maxLength`, `minimum`, `maximum`, `default`, `description`.

---

## Best Practices

1. **Naming**: Use lowercase with hyphens (`my-awesome-plugin`).
2. **Versioning**: Follow semver strictly. Bump major for breaking changes.
3. **Error Handling**: Never let exceptions escape lifecycle hooks. Log and handle gracefully.
4. **Permissions**: Declare all required permissions in `required_permissions`.
5. **Configuration**: Provide sensible `default_config` values.
6. **Documentation**: Include a comprehensive `README.md` in your plugin.
7. **Testing**: Test your plugin independently before packaging.
8. **System Plugins**: Only mark as `is_system=True` for core platform plugins that should not be disabled.
