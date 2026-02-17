"""
内置工具执行器

提供安全的内置函数（datetime、math 等），不涉及外部调用
"""

import ast
import json
import operator
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
        """格式化 JSON 字符串"""
        try:
            parsed = json.loads(data)
            return json.dumps(parsed, indent=2, ensure_ascii=False)
        except json.JSONDecodeError as exc:
            return f"Error: Invalid JSON - {exc}"


# ========================================
# 安全数学表达式解析器
# ========================================

# 允许的二元运算符
_SAFE_BINOPS: dict[type, Callable[..., object]] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}

# 允许的一元运算符
_SAFE_UNARYOPS: dict[type, Callable[..., object]] = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}


def _safe_eval_node(node: ast.AST) -> int | float:
    """递归求值 AST 节点，仅允许安全的数学操作"""
    if isinstance(node, ast.Expression):
        return _safe_eval_node(node.body)

    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
        return node.value

    if isinstance(node, ast.BinOp):
        op_func = _SAFE_BINOPS.get(type(node.op))
        if op_func is None:
            raise ValueError(f"Unsupported operator: {type(node.op).__name__}")
        left = _safe_eval_node(node.left)
        right = _safe_eval_node(node.right)
        # 防止天文数字指数 (如 10**10000)
        if isinstance(node.op, ast.Pow) and isinstance(right, (int, float)) and abs(right) > 1000:
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
    """安全地求值数学表达式

    使用 ast.parse 将表达式解析为 AST，然后递归求值。
    仅允许数字常量和基本算术运算符，禁止任何函数调用、
    属性访问、变量引用或其他代码执行。

    Raises:
        ValueError: 表达式包含不安全的操作
        SyntaxError: 表达式语法错误
        ZeroDivisionError: 除零错误
    """
    tree = ast.parse(expression.strip(), mode="eval")
    return _safe_eval_node(tree)


__all__ = ["BuiltinToolExecutor"]
