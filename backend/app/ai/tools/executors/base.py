"""
Abstract Base Class for Tool Executors / 工具执行器抽象基类

All tool executors must inherit from this class and implement the execute and validate methods.
所有工具执行器必须继承此类，实现 execute 和 validate 方法。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

from app.ai.tools.types import ToolDefinition, ToolResult

if TYPE_CHECKING:
    from app.ai.tools.types import ExecutionContext


class BaseToolExecutor(ABC):
    """
    Abstract base class for tool executors. / 工具执行器抽象基类。

    Each ToolTypeEnum corresponds to a concrete executor implementation.
    每种 ToolTypeEnum 对应一个具体的执行器实现。
    """

    @abstractmethod
    async def execute(
        self,
        definition: ToolDefinition,
        tool_call_id: str,
        arguments: dict[str, Any],
        context: ExecutionContext | None = None,
    ) -> ToolResult:
        """
        Execute a tool call.
        执行工具调用。

        Args:
            definition: Tool definition / 工具定义
            tool_call_id: tool_call_id returned by LLM / LLM 返回的 tool_call_id
            arguments: Arguments passed by LLM / LLM 传入的参数
            context: Execution context (optional) / 执行上下文（可选）

        Returns:
            ToolResult execution result / ToolResult 执行结果
        """

    @abstractmethod
    async def validate(
        self,
        definition: ToolDefinition,
        arguments: dict[str, Any],
    ) -> bool:
        """
        Validate argument legality.
        校验参数合法性。

        Args:
            definition: Tool definition / 工具定义
            arguments: Arguments passed by LLM / LLM 传入的参数

        Returns:
            True if arguments are valid / True 表示参数合法
        """


__all__ = ["BaseToolExecutor"]
