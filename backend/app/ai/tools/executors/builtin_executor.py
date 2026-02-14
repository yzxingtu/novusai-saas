"""
内置工具执行器

提供安全的内置函数（datetime、math 等），不涉及外部调用
"""

import json
import math
import time
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Callable, Coroutine

from app.ai.tools.executors.base import BaseToolExecutor
from app.ai.tools.types import ToolDefinition, ToolResult
from app.core.i18n import _
from app.core.logging import LogManager

if TYPE_CHECKING:
    from app.ai.tools.types import ExecutionContext

logger = LogManager.get_logger("ai.tool.builtin")

# 内置函数类型
BuiltinFunc = Callable[..., Coroutine[Any, Any, str]]


class BuiltinToolExecutor(BaseToolExecutor):
    """
    内置函数工具执行器

    维护一个安全函数注册表，所有函数在进程内执行。
    禁止任何 IO 操作和危险调用。
    """

    def __init__(self) -> None:
        self._functions: dict[str, BuiltinFunc] = {}
        self._register_defaults()

    def register_function(self, name: str, func: BuiltinFunc) -> None:
        """注册一个内置函数"""
        self._functions[name] = func

    async def execute(
        self,
        definition: ToolDefinition,
        tool_call_id: str,
        arguments: dict[str, Any],
        context: "ExecutionContext | None" = None,
    ) -> ToolResult:
        """执行内置函数"""
        start = time.perf_counter()
        func_name = definition.name

        func = self._functions.get(func_name)
        if not func:
            return ToolResult(
                tool_call_id=tool_call_id,
                name=func_name,
                success=False,
                error=_("tool.builtin.not_found", name=func_name),
            )

        try:
            output = await func(**arguments)
            duration_ms = int((time.perf_counter() - start) * 1000)

            return ToolResult(
                tool_call_id=tool_call_id,
                name=func_name,
                success=True,
                output=output,
                duration_ms=duration_ms,
            )

        except Exception as exc:
            duration_ms = int((time.perf_counter() - start) * 1000)
            logger.error(
                "Builtin tool error: %s: %s",
                func_name,
                str(exc),
                exc_info=True,
            )
            return ToolResult(
                tool_call_id=tool_call_id,
                name=func_name,
                success=False,
                error=str(exc),
                duration_ms=duration_ms,
            )

    async def validate(
        self,
        definition: ToolDefinition,
        arguments: dict[str, Any],
    ) -> bool:
        """校验内置函数参数"""
        func_name = definition.name
        if func_name not in self._functions:
            return False

        # 检查必填参数
        for param in definition.parameters:
            if param.required and param.name not in arguments:
                return False

        return True

    # ========================================
    # 默认内置函数
    # ========================================

    def _register_defaults(self) -> None:
        """注册默认内置函数"""
        self.register_function("get_current_time", self._get_current_time)
        self.register_function("calculate", self._calculate)
        self.register_function("format_json", self._format_json)

    @staticmethod
    async def _get_current_time(
        timezone_name: str = "UTC",
        format: str = "%Y-%m-%d %H:%M:%S",
    ) -> str:
        """获取当前时间"""
        import zoneinfo

        try:
            tz = zoneinfo.ZoneInfo(timezone_name)
        except (KeyError, Exception):
            tz = timezone.utc

        now = datetime.now(tz)
        return now.strftime(format)

    @staticmethod
    async def _calculate(expression: str = "") -> str:
        """
        安全的数学计算

        仅允许数学运算和常量，禁止任何函数调用或导入
        """
        if not expression:
            return _("tool.builtin.empty_expression")

        # 仅允许安全字符
        allowed_chars = set("0123456789+-*/.() eE")
        if not all(c in allowed_chars for c in expression.replace(" ", "")):
            return _("tool.builtin.unsafe_characters")

        try:
            result = eval(expression, {"__builtins__": {}}, {"math": math})  # noqa: S307
            return str(result)
        except Exception as exc:
            return f"Error: {exc}"

    @staticmethod
    async def _format_json(data: str = "") -> str:
        """格式化 JSON 字符串"""
        try:
            parsed = json.loads(data)
            return json.dumps(parsed, indent=2, ensure_ascii=False)
        except json.JSONDecodeError as exc:
            return f"Error: Invalid JSON - {exc}"


__all__ = ["BuiltinToolExecutor"]
