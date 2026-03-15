"""
Tool Execution Module / 工具执行模块

Provides a complete framework for tool definition, registration, and secure sandbox execution.
提供工具定义、注册、安全沙箱执行的完整框架。
"""

from app.ai.tools.executors.base import BaseToolExecutor
from app.ai.tools.executors.builtin_executor import BuiltinToolExecutor
from app.ai.tools.executors.toolkit_executor import ToolkitExecutor
from app.ai.tools.sandbox import SandboxConfig, ToolSandbox
from app.ai.tools.types import ToolDefinition, ToolParameter, ToolResult

__all__ = [
    # Types / 类型
    "ToolParameter",
    "ToolDefinition",
    "ToolResult",
    # Sandbox / 沙箱
    "ToolSandbox",
    "SandboxConfig",
    # Executors / 执行器
    "BaseToolExecutor",
    "BuiltinToolExecutor",
    "ToolkitExecutor",
]
