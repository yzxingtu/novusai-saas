# builtin/ — System Plugins

This directory contains **system-level plugins** (`is_system=True`) that ship with the platform.

System plugins:
- **Cannot be uninstalled** or disabled by users
- Are loaded automatically during platform startup
- Provide core platform capabilities (e.g., AI provider adapters)

## Current Plugins

| Plugin | Type | Description |
|--------|------|-------------|
| `anthropic/` | AdapterPlugin | Anthropic Claude API adapter |

> **Note**: The OpenAI Compatible Adapter has been integrated into the core system (`main.py` → `AdapterRegistry.register`) and is no longer a plugin.

## Adding a New System Plugin

1. Create a plugin module (single `.py` file or directory with `plugin.py` + `manifest.json`)
2. Set `is_system = True` in the plugin class
3. Register in the database with `is_system=True` during platform initialization

## Non-System Plugins

For example/reference plugins, see `../examples/`.
For user-installable plugins, use the upload/install API.
