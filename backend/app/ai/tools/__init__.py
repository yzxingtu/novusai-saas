"""
工具执行模块

提供工具定义、注册、安全沙箱执行的完整框架
"""

from app.ai.tools.types import ToolParameter, ToolDefinition, ToolResult
from app.ai.tools.registry import ToolRegistry, get_tool_registry
from app.ai.tools.sandbox import ToolSandbox, SandboxConfig
from app.ai.tools.executors.base import BaseToolExecutor
from app.ai.tools.executors.builtin_executor import BuiltinToolExecutor
from app.ai.tools.executors.toolkit_executor import ToolkitExecutor

__all__ = [
    # 类型
    "ToolParameter",
    "ToolDefinition",
    "ToolResult",
    # 注册表
    "ToolRegistry",
    "get_tool_registry",
    # 沙箱
    "ToolSandbox",
    "SandboxConfig",
    # 执行器
    "BaseToolExecutor",
    "BuiltinToolExecutor",
    "ToolkitExecutor",
]
