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
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from app.ai.tools.executors.base import BaseToolExecutor
from app.ai.tools.executors.builtin import fetch_support, search_support, time_ops
from app.ai.tools.types import ToolDefinition, ToolResult
from app.ai.web_search.orchestrator import run_web_search as orchestrated_run_web_search
from app.ai.web_search.types import (
    STATUS_NO_RESULTS as WS_STATUS_NO_RESULTS,
)
from app.ai.web_search.types import (
    STATUS_SUCCESS as WS_STATUS_SUCCESS,
)
from app.ai.web_search.types import (
    WebSearchExecution as OrchestratedWebSearchExecution,
)
from app.core.config import settings
from app.core.i18n import _
from app.core.logging import LogManager
from app.core.response import build_public_error_text

if TYPE_CHECKING:
    from app.ai.tools.types import ExecutionContext

logger = LogManager.get_logger("ai.tool.builtin")

# Built-in function type / 内置函数类型
BuiltinFunc = Callable[..., Coroutine[Any, Any, str]]


def _build_search_summary_payload(
    execution: OrchestratedWebSearchExecution,
) -> dict[str, Any]:
    return search_support.build_search_summary_payload(execution)


def _build_fetch_summary(output: str, *, max_length: int = 220) -> str | None:
    return fetch_support._build_fetch_summary(output, max_length=max_length)


def _extract_fetch_summary_payload(
    *,
    requested_url: str,
    output: str | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    return fetch_support._extract_fetch_summary_payload(
        requested_url=requested_url,
        output=output,
        error=error,
    )


def _normalize_text(text: str) -> str:
    """Collapse whitespace and trim text. / 折叠空白并裁剪文本。"""
    return " ".join((text or "").split())


def _looks_historical_query(query: str) -> bool:
    normalized = _normalize_text(query).lower()
    if not normalized:
        return False
    if any(
        term in normalized for term in ("年代", "朝代", "古代", "战时", "世纪", "历史")
    ):
        return True

    tokens = normalized.split()
    for idx, token in enumerate(tokens):
        if token in {
            "history",
            "historical",
            "era",
            "ancient",
            "medieval",
            "wartime",
            "dynasty",
        }:
            return True
        if token.endswith("s") and token[:-1].isdigit() and len(token[:-1]) >= 3:
            return True
        if token.isdigit() and idx + 1 < len(tokens) and tokens[idx + 1] == "century":
            return True
    return False


def _wants_current_results(query: str) -> bool:
    normalized = _normalize_text(query).lower()
    if not normalized:
        return False
    return any(
        term in normalized
        for term in (
            "最新",
            "今年",
            "当前",
            "现在",
            "近期",
            "今天",
            "今日",
            "latest",
            "recent",
            "current",
            "today",
            "now",
            "this year",
        )
    )


def _replace_recent_years(query: str, current_year: int) -> str:
    chars = list(query)
    result: list[str] = []
    idx = 0
    length = len(chars)
    while idx < length:
        if (
            idx + 4 <= length
            and "".join(chars[idx : idx + 4]).isdigit()
            and (idx == 0 or not chars[idx - 1].isalnum())
            and (idx + 4 == length or not chars[idx + 4].isalnum())
        ):
            year_text = "".join(chars[idx : idx + 4])
            year_value = int(year_text)
            if year_value != current_year and 2000 <= year_value <= current_year + 1:
                result.append(str(current_year))
                idx += 4
                continue
        result.append(chars[idx])
        idx += 1
    return "".join(result)


def _correct_query_year(query: str) -> str:
    """Replace stale calendar years in web_search queries unless the query is clearly historical."""
    if not query:
        return query
    if _looks_historical_query(query):
        return query
    if not _wants_current_results(query):
        return query
    try:
        current_year = datetime.now(settings.tz).year
    except Exception:
        current_year = datetime.now(timezone.utc).year
    return _replace_recent_years(query, current_year)


async def _run_web_search(
    query: str,
    max_results: int,
    *,
    context: "ExecutionContext | None" = None,
) -> OrchestratedWebSearchExecution:
    return await orchestrated_run_web_search(
        query,
        max_results,
        context=context,
    )


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
            if func_name == "web_search":
                query = str(arguments.get("query") or "")
                max_results = int(arguments.get("max_results") or 5)
                execution = await _run_web_search(
                    query,
                    max_results,
                    context=context,
                )
                duration_ms = int((time.perf_counter() - start) * 1000)
                is_failure = execution.meta.status not in {
                    WS_STATUS_SUCCESS,
                    WS_STATUS_NO_RESULTS,
                }
                return ToolResult(
                    tool_call_id=tool_call_id,
                    name=func_name,
                    success=not is_failure,
                    output="" if is_failure else execution.output,
                    error=execution.output if is_failure else "",
                    summary=(
                        f"{execution.meta.provider or execution.meta.selected_backend or 'search'}: {len(execution.items)} result(s)"
                        if execution.meta.status
                        in {WS_STATUS_SUCCESS, WS_STATUS_NO_RESULTS}
                        else execution.meta.failure_reason
                    ),
                    summary_payload=_build_search_summary_payload(execution),
                    duration_ms=duration_ms,
                )

            if func_name == "fetch_url":
                url = str(arguments.get("url") or "")
                max_length = int(arguments.get("max_length") or 5000)
                ok, payload = await BuiltinToolExecutor._fetch_url_result(
                    url, max_length
                )
                duration_ms = int((time.perf_counter() - start) * 1000)
                if not ok:
                    summary_payload = _extract_fetch_summary_payload(
                        requested_url=url,
                        error=payload,
                    )
                    return ToolResult(
                        tool_call_id=tool_call_id,
                        name=func_name,
                        success=False,
                        error=payload,
                        summary="fetch_url failed",
                        summary_payload=summary_payload,
                        error_type=str(summary_payload.get("error_type") or ""),
                        duration_ms=duration_ms,
                    )
                summary = _build_fetch_summary(payload)
                summary_payload = _extract_fetch_summary_payload(
                    requested_url=url,
                    output=payload,
                )
                return ToolResult(
                    tool_call_id=tool_call_id,
                    name=func_name,
                    success=True,
                    output=payload,
                    summary=summary,
                    summary_payload=summary_payload,
                    duration_ms=duration_ms,
                )

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
        self.register_function("web_search", self._web_search)
        self.register_function("fetch_url", self._fetch_url)

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

    @staticmethod
    async def _web_search(query: str = "", max_results: int = 5) -> str:
        """
        Web search: automatically choose a search source and return web results. / 联网搜索：自动选择搜索源并返回网页结果。

        Returns a list of search results (title + snippet + link).
        返回搜索结果列表（标题 + 摘要 + 链接）。
        """
        if not query:
            return "Error: query parameter is required"

        max_results = min(max(1, max_results), 10)
        return (await _run_web_search(query, max_results)).output

    @staticmethod
    async def _fetch_url_result(
        url: str = "", max_length: int = 5000
    ) -> tuple[bool, str]:
        """
        Fetch URL; returns (success, text).
        On failure, text is the error detail for ToolResult.error (no \"Error:\" prefix).
        """
        return await fetch_support.fetch_url_result(
            url=url,
            max_length=max_length,
        )

    @staticmethod
    async def _fetch_url(url: str = "", max_length: int = 5000) -> str:
        """
        Fetch web content (legacy string API for tests). / 抓取网页内容。
        """
        ok, text = await BuiltinToolExecutor._fetch_url_result(url, max_length)
        if ok:
            return text
        return f"Error: {text}"


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
