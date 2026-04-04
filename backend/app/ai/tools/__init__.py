"""
Tool execution package with lazy exports to avoid import cycles.
工具执行包，使用延迟导出避免导入环。
"""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.ai.tools.executors.base import BaseToolExecutor
    from app.ai.tools.executors.builtin_executor import BuiltinToolExecutor
    from app.ai.tools.executors.toolkit_executor import ToolkitExecutor
    from app.ai.tools.sandbox import SandboxConfig, ToolSandbox
    from app.ai.tools.types import ToolDefinition, ToolParameter, ToolResult

_EXPORTS: dict[str, tuple[str, str]] = {
    "ToolParameter": ("app.ai.tools.types", "ToolParameter"),
    "ToolDefinition": ("app.ai.tools.types", "ToolDefinition"),
    "ToolResult": ("app.ai.tools.types", "ToolResult"),
    "ToolSandbox": ("app.ai.tools.sandbox", "ToolSandbox"),
    "SandboxConfig": ("app.ai.tools.sandbox", "SandboxConfig"),
    "BaseToolExecutor": ("app.ai.tools.executors.base", "BaseToolExecutor"),
    "BuiltinToolExecutor": (
        "app.ai.tools.executors.builtin_executor",
        "BuiltinToolExecutor",
    ),
    "ToolkitExecutor": ("app.ai.tools.executors.toolkit_executor", "ToolkitExecutor"),
}

__all__ = list(_EXPORTS)


def __getattr__(name: str) -> Any:
    target = _EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attribute = target
    value = getattr(import_module(module_name), attribute)
    globals()[name] = value
    return value
