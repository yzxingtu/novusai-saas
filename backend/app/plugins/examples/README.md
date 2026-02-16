# examples/ — Plugin Examples

This directory contains **example plugins** demonstrating different plugin types.

These are **not loaded automatically** — they serve as reference implementations for plugin developers.

## Available Examples

| Directory | Type | Description |
|-----------|------|-------------|
| `audit_hook/` | HookPlugin | Subscribes to system events and logs audit info |
| `webhook_api/` | ApiPlugin | Registers custom webhook receiver endpoints |
| `weather_tool/` | ToolPlugin | Example tool plugin (placeholder) |
| `slack_skill/` | SkillPlugin | Example skill plugin (placeholder) |

## Using an Example

1. Copy the example directory to the plugins install path
2. Register via the admin panel or API
3. Enable the plugin

Or pack it as a `.nap` file:
```bash
# From the example directory
python -m app.plugins.packaging pack_plugin ./audit_hook
```
