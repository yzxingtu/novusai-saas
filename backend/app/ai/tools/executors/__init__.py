"""
Concrete tool executors with lazy exports.
具体工具执行器使用延迟导出，避免包级导入环。
"""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.ai.tools.executors.base import BaseToolExecutor
    from app.ai.tools.executors.builtin_executor import BuiltinToolExecutor
    from app.ai.tools.executors.crud_executor import (
        CreateRecordExecutor,
        DeleteRecordExecutor,
        UpdateRecordExecutor,
    )
    from app.ai.tools.executors.text_to_sql_executor import TextToSQLExecutor
    from app.ai.tools.executors.toolkit_executor import ToolkitExecutor

_EXPORTS: dict[str, tuple[str, str]] = {
    "BaseToolExecutor": ("app.ai.tools.executors.base", "BaseToolExecutor"),
    "BuiltinToolExecutor": (
        "app.ai.tools.executors.builtin_executor",
        "BuiltinToolExecutor",
    ),
    "TextToSQLExecutor": (
        "app.ai.tools.executors.text_to_sql_executor",
        "TextToSQLExecutor",
    ),
    "ToolkitExecutor": ("app.ai.tools.executors.toolkit_executor", "ToolkitExecutor"),
    "CreateRecordExecutor": (
        "app.ai.tools.executors.crud_executor",
        "CreateRecordExecutor",
    ),
    "UpdateRecordExecutor": (
        "app.ai.tools.executors.crud_executor",
        "UpdateRecordExecutor",
    ),
    "DeleteRecordExecutor": (
        "app.ai.tools.executors.crud_executor",
        "DeleteRecordExecutor",
    ),
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
