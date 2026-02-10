"""
工具执行器抽象基类

所有工具执行器必须继承此类，实现 execute 和 validate 方法
"""

from abc import ABC, abstractmethod
from typing import Any

from app.ai.tools.types import ToolDefinition, ToolResult


class BaseToolExecutor(ABC):
    """
    工具执行器抽象基类

    每种 ToolTypeEnum 对应一个具体的执行器实现
    """

    @abstractmethod
    async def execute(
        self,
        definition: ToolDefinition,
        tool_call_id: str,
        arguments: dict[str, Any],
    ) -> ToolResult:
        """
        执行工具调用

        Args:
            definition: 工具定义
            tool_call_id: LLM 返回的 tool_call_id
            arguments: LLM 传入的参数

        Returns:
            ToolResult 执行结果
        """

    @abstractmethod
    async def validate(
        self,
        definition: ToolDefinition,
        arguments: dict[str, Any],
    ) -> bool:
        """
        校验参数合法性

        Args:
            definition: 工具定义
            arguments: LLM 传入的参数

        Returns:
            True 表示参数合法
        """


__all__ = ["BaseToolExecutor"]
