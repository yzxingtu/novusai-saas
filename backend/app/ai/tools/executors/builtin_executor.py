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
from app.ai.tools.types import ToolDefinition, ToolResult
from app.core.i18n import _
from app.core.logging import LogManager

if TYPE_CHECKING:
    from app.ai.tools.types import ExecutionContext

logger = LogManager.get_logger("ai.tool.builtin")

# Built-in function type / 内置函数类型
BuiltinFunc = Callable[..., Coroutine[Any, Any, str]]


# SSRF protection: block access to intranet/cloud metadata hostnames
# SSRF 防护：阻止访问内网/云元数据的主机名
_SSRF_BLOCKED_HOSTS = frozenset({
    "localhost", "127.0.0.1", "0.0.0.0", "::1",
    "169.254.169.254", "metadata.google.internal",
    "metadata.google", "100.100.100.200",
})
# Private IP range prefixes (quick check, not exact CIDR)
# 内网 IP 段前缀（快速检查，非精确 CIDR）
_SSRF_PRIVATE_PREFIXES = ("10.", "172.16.", "172.17.", "172.18.", "172.19.",
                          "172.20.", "172.21.", "172.22.", "172.23.",
                          "172.24.", "172.25.", "172.26.", "172.27.",
                          "172.28.", "172.29.", "172.30.", "172.31.",
                          "192.168.", "fd", "fc")


def _is_ssrf_blocked(url: str) -> str | None:
    """Check if URL points to intranet/cloud metadata, return error message or None. / 检查 URL 是否指向内网/云元数据，返回错误消息或 None。"""
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower()
        if not host:
            return "Invalid URL: no hostname"
        if host in _SSRF_BLOCKED_HOSTS:
            return f"Blocked: requests to {host} are not allowed"
        if host.startswith(_SSRF_PRIVATE_PREFIXES):
            return f"Blocked: requests to private network ({host}) are not allowed"
        # Block non-HTTP(S) protocols / 阻止非 HTTP(S) 协议
        if parsed.scheme not in ("http", "https"):
            return f"Blocked: only http/https URLs are allowed, got {parsed.scheme}"
    except Exception:
        return "Invalid URL"
    return None


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
                error=str(exc),
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
        timezone_name: str = "UTC",
        format: str = "%Y-%m-%d %H:%M:%S",
    ) -> str:
        """Get current time / 获取当前时间"""
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
        Web search: search web content via DuckDuckGo HTML API. / 联网搜索：通过 DuckDuckGo HTML API 搜索网页内容。

        Returns a list of search results (title + snippet + link).
        返回搜索结果列表（标题 + 摘要 + 链接）。
        """
        if not query:
            return "Error: query parameter is required"

        import re
        from html import unescape

        import httpx

        max_results = min(max(1, max_results), 10)
        url = "https://html.duckduckgo.com/html/"
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        }

        try:
            async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                resp = await client.post(url, data={"q": query}, headers=headers)
                resp.raise_for_status()
                html = resp.text

            # Parse results from DuckDuckGo HTML response
            results: list[dict[str, str]] = []

            # Extract result blocks
            snippet_re = re.compile(
                r'<a[^>]+class="result__a"[^>]*href="([^"]*)"[^>]*>(.*?)</a>'
                r'.*?<a[^>]+class="result__snippet"[^>]*>(.*?)</a>',
                re.DOTALL,
            )
            for match in snippet_re.finditer(html):
                if len(results) >= max_results:
                    break
                href = unescape(match.group(1))
                title = re.sub(r"<[^>]+>", "", unescape(match.group(2))).strip()
                snippet = re.sub(r"<[^>]+>", "", unescape(match.group(3))).strip()
                if title and href:
                    results.append({"title": title, "url": href, "snippet": snippet})

            if not results:
                return f"No results found for: {query}"

            lines = [f"Search results for: {query}\n"]
            for i, r in enumerate(results, 1):
                lines.append(f"{i}. {r['title']}")
                lines.append(f"   URL: {r['url']}")
                if r["snippet"]:
                    lines.append(f"   {r['snippet']}")
                lines.append("")
            return "\n".join(lines)

        except httpx.TimeoutException:
            return f"Error: Search timed out for query: {query}"
        except Exception as exc:
            logger.warning("web_search failed: {}", exc)
            return f"Error: Search failed - {exc}"

    @staticmethod
    async def _fetch_url(url: str = "", max_length: int = 5000) -> str:
        """
        Fetch web content: retrieve text content from a specified URL. / 抓取网页内容：获取指定 URL 的文本内容。

        Automatically extracts body text, removing HTML tags and scripts.
        自动提取正文文本，去除 HTML 标签和脚本。
        """
        if not url:
            return "Error: url parameter is required"

        # SSRF protection: block intranet/cloud metadata access / SSRF 防护：阻止内网/云元数据访问
        ssrf_err = _is_ssrf_blocked(url)
        if ssrf_err:
            return f"Error: {ssrf_err}"

        import re

        import httpx

        max_length = min(max(500, max_length), 20000)

        try:
            async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                resp = await client.get(url, headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36"
                    ),
                })
                resp.raise_for_status()
                html = resp.text

            # Remove script/style/noscript tags
            html = re.sub(r"<(script|style|noscript)[^>]*>.*?</\1>", "", html, flags=re.DOTALL | re.IGNORECASE)
            # Remove HTML tags
            text = re.sub(r"<[^>]+>", " ", html)
            # Collapse whitespace
            text = re.sub(r"\s+", " ", text).strip()

            if len(text) > max_length:
                text = text[:max_length] + "... [truncated]"

            return f"Content from {url}:\n\n{text}" if text else f"No readable content found at {url}"

        except httpx.TimeoutException:
            return f"Error: Request timed out for URL: {url}"
        except Exception as exc:
            logger.warning("fetch_url failed for {}: {}", url, exc)
            return f"Error: Failed to fetch URL - {exc}"


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

    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
        return node.value

    if isinstance(node, ast.BinOp):
        op_func = _SAFE_BINOPS.get(type(node.op))
        if op_func is None:
            raise ValueError(f"Unsupported operator: {type(node.op).__name__}")
        left = _safe_eval_node(node.left)
        right = _safe_eval_node(node.right)
        # Prevent astronomical exponents (e.g. 10**10000) / 防止天文数字指数 (如 10**10000)
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
