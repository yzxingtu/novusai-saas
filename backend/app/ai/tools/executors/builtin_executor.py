"""
Builtin Tool Executor / 内置工具执行器

Provides safe built-in functions (datetime, math, etc.) without external calls.
提供安全的内置函数（datetime、math 等），不涉及外部调用。
"""

import ast
import json
import operator
import time
from collections.abc import Callable, Coroutine
from typing import TYPE_CHECKING, Any

from app.ai.tools.executors.base import BaseToolExecutor
from app.ai.tools.executors.builtin import time_ops
from app.ai.tools.types import ToolDefinition, ToolResult
from app.core.config import settings
from app.core.i18n import _
from app.core.logging import LogManager
from app.core.response import build_public_error_text

if TYPE_CHECKING:
    from app.ai.tools.types import ExecutionContext

logger = LogManager.get_logger("ai.tool.builtin")

# Built-in function type / 内置函数类型
BuiltinFunc = Callable[..., Coroutine[Any, Any, str]]


class BuiltinToolExecutor(BaseToolExecutor):
    """
    Built-in function tool executor. / 内置函数工具执行器。

    Maintains a safe function registry; all functions execute in-process.
    Any IO operations and dangerous calls are forbidden.
    维护一个安全函数注册表，所有函数在进程内执行。
    禁止任何 IO 操作和危险调用。
    """

    def __init__(self) -> None:
        self._functions: dict[str, BuiltinFunc] = {}
        self._register_defaults()

    def register_function(self, name: str, func: BuiltinFunc) -> None:
        """Register a built-in function / 注册一个内置函数"""
        self._functions[name] = func

    async def execute(
        self,
        definition: ToolDefinition,
        tool_call_id: str,
        arguments: dict[str, Any],
        context: "ExecutionContext | None" = None,
    ) -> ToolResult:
        """Execute a built-in function / 执行内置函数"""
        _ = context
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
                "Builtin tool error: {}: {}",
                func_name,
                str(exc),
                exc_info=True,
            )
            return ToolResult(
                tool_call_id=tool_call_id,
                name=func_name,
                success=False,
                error=build_public_error_text(
                    message="Builtin tool execution failed",
                    exc=exc,
                ),
                duration_ms=duration_ms,
            )

    async def validate(
        self,
        definition: ToolDefinition,
        arguments: dict[str, Any],
    ) -> bool:
        """Validate built-in function arguments / 校验内置函数参数"""
        func_name = definition.name
        if func_name not in self._functions:
            return False

        # Check required parameters / 检查必填参数
        for param in definition.parameters:
            if param.required and param.name not in arguments:
                return False

        return True

    # ========================================
    # Default built-in functions / 默认内置函数
    # ========================================

    def _register_defaults(self) -> None:
        """Register default built-in functions / 注册默认内置函数"""
        self.register_function("get_current_time", self._get_current_time)
        self.register_function("calculate", self._calculate)
        self.register_function("format_json", self._format_json)

    @staticmethod
    async def _get_current_time(
        timezone_name: str = settings.TIMEZONE,
        format: str = "%Y-%m-%d %H:%M:%S",
    ) -> str:
        """Get current time / 获取当前时间"""
        return time_ops.get_current_time(
            timezone_name=timezone_name,
            format=format,
        )

    @staticmethod
    async def _calculate(expression: str = "") -> str:
        """
        Safe mathematical calculation. / 安全的数学计算。

        Uses an AST parser, only allowing numeric constants and basic arithmetic operators.
        Function calls, attribute access, imports, or any other code execution are forbidden.
        使用 AST 解析器，仅允许数字常量和基本算术运算符。
        禁止函数调用、属性访问、导入或任何其他代码执行。
        """
        if not expression:
            return _("tool.builtin.empty_expression")

        try:
            result = _safe_eval_math(expression)
            return str(result)
        except (ValueError, SyntaxError, TypeError, ZeroDivisionError) as exc:
            return _("tool.builtin.calc_error").format(error=str(exc))

    @staticmethod
    async def _format_json(data: str = "") -> str:
        """Format JSON string / 格式化 JSON 字符串"""
        try:
            parsed = json.loads(data)
            return json.dumps(parsed, indent=2, ensure_ascii=False)
        except json.JSONDecodeError as exc:
            return f"Error: Invalid JSON - {exc}"


# ========================================
# Safe Math Expression Parser / 安全数学表达式解析器
# ========================================

# Allowed binary operators / 允许的二元运算符
_SAFE_BINOPS: dict[type, Callable[..., object]] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}

# Allowed unary operators / 允许的一元运算符
_SAFE_UNARYOPS: dict[type, Callable[..., object]] = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}


def _safe_eval_node(node: ast.AST) -> int | float:
    """递归求值 AST 节点，仅允许安全的数学操作 / Recursively evaluate AST node, only allowing safe math operations."""
    if isinstance(node, ast.Expression):
        return _safe_eval_node(node.body)

    if (
        isinstance(node, ast.Constant)
        and isinstance(node.value, (int, float))
        and not isinstance(node.value, bool)
    ):
        return node.value

    if isinstance(node, ast.BinOp):
        op_func = _SAFE_BINOPS.get(type(node.op))
        if op_func is None:
            raise ValueError(f"Unsupported operator: {type(node.op).__name__}")
        left = _safe_eval_node(node.left)
        right = _safe_eval_node(node.right)
        # Prevent astronomical exponents (e.g. 10**10000) / 防止天文数字指数 (如 10**10000)
        if (
            isinstance(node.op, ast.Pow)
            and isinstance(right, (int, float))
            and abs(right) > 1000
        ):
            raise ValueError("Exponent too large (max 1000)")
        return op_func(left, right)

    if isinstance(node, ast.UnaryOp):
        op_func = _SAFE_UNARYOPS.get(type(node.op))
        if op_func is None:
            raise ValueError(f"Unsupported unary operator: {type(node.op).__name__}")
        return op_func(_safe_eval_node(node.operand))

    raise ValueError(
        f"Unsupported expression type: {type(node).__name__}. "
        "Only numbers and arithmetic operators (+, -, *, /, //, %, **) are allowed."
    )


def _safe_eval_math(expression: str) -> int | float:
    """Safely evaluate a math expression.
    安全地求值数学表达式。

    Uses ast.parse to parse the expression into an AST, then recursively evaluates it.
    Only numeric constants and basic arithmetic operators are allowed; any function calls,
    attribute access, variable references, or other code execution are forbidden.
    使用 ast.parse 将表达式解析为 AST，然后递归求值。
    仅允许数字常量和基本算术运算符，禁止任何函数调用、
    属性访问、变量引用或其他代码执行。

    Raises:
        ValueError: Expression contains unsafe operations / 表达式包含不安全的操作
        SyntaxError: Expression syntax error / 表达式语法错误
        ZeroDivisionError: Division by zero / 除零错误
    """
    tree = ast.parse(expression.strip(), mode="eval")
    return _safe_eval_node(tree)


__all__ = ["BuiltinToolExecutor"]
