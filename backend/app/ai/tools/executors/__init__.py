"""
Concrete tool executors with lazy exports.
具体工具执行器使用延迟导出，避免包级导入环。
"""

from __future__ import annotations

from importlib import import_module
from typing import Any

_EXPORTS: dict[str, tuple[str, str]] = {
    "BaseToolExecutor": ("app.ai.tools.executors.base", "BaseToolExecutor"),
    "BuiltinToolExecutor": (
        "app.ai.tools.executors.builtin_executor",
        "BuiltinToolExecutor",
    ),
    "ToolkitExecutor": ("app.ai.tools.executors.toolkit_executor", "ToolkitExecutor"),
}

__all__ = [
    "BaseToolExecutor",
    "BuiltinToolExecutor",
    "ToolkitExecutor",
]


def __getattr__(name: str) -> Any:
    target = _EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attribute = target
    value = getattr(import_module(module_name), attribute)
    globals()[name] = value
    return value
