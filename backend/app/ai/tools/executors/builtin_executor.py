"""
Builtin Tool Executor / 内置工具执行器

Provides safe built-in functions (datetime, math, etc.) without external calls.
提供安全的内置函数（datetime、math 等），不涉及外部调用。
"""

import ast
import json
import operator
import re
import time
from collections.abc import Callable, Coroutine
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any
from urllib.parse import parse_qs, unquote, urlparse

from app.ai.tools.executors.base import BaseToolExecutor
from app.ai.tools.types import ToolDefinition, ToolResult
from app.core.i18n import _
from app.core.logging import LogManager
from app.core.response import build_public_error_text

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

_DEFAULT_WEB_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "text/plain;q=0.8,*/*;q=0.7"
    ),
    "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
}
_MAIN_CONTENT_SELECTORS = (
    "main",
    "article",
    "[role='main']",
    "#main",
    "#content",
    "#main-content",
    ".main-content",
    ".article-content",
    ".entry-content",
    ".post-content",
    ".markdown-body",
    ".docMainContainer",
    ".docs-body",
)
_TEXT_BLOCK_TAGS = ("h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "blockquote", "pre", "td", "th")
_NOISE_TAGS = (
    "script",
    "style",
    "noscript",
    "template",
    "svg",
    "canvas",
    "iframe",
    "form",
    "button",
    "input",
    "select",
    "textarea",
    "nav",
    "footer",
    "header",
    "aside",
)
_NOISE_HINTS = (
    "breadcrumb",
    "cookie",
    "footer",
    "header",
    "menu",
    "nav",
    "navbar",
    "pagination",
    "share",
    "sidebar",
    "social",
    "subscribe",
    "table-of-contents",
    "toc",
    "toolbar",
)


def _build_builtin_follow_up_message(func_name: str, output: str) -> str | None:
    """Provide tool-specific guidance to help the LLM stop repeating web tools. / 为内置联网工具提供收敛提示。"""
    if not output:
        return None

    if func_name == "web_search":
        if output.startswith("Error:"):
            return (
                f"{output}\n\n"
                "The web search already failed for this exact query. "
                "Do not call web_search again with the same query unless the user changes it. "
                "Either answer from the evidence already in the conversation or try a different research strategy."
            )
        return (
            f"{output}\n\n"
            "You have already completed the web search for this query. "
            "Do not call web_search again unless the user changes the query. "
            "Answer directly from these results, or call fetch_url for specific URLs if deeper detail is needed. "
            "If the user asked for multiple articles, multiple sources, or cross-verification, inspect enough distinct results to support a multi-source summary before the final answer."
        )

    if func_name == "fetch_url":
        if output.startswith("Error:"):
            return (
                f"{output}\n\n"
                "Fetching this URL already failed with the same arguments. "
                "Do not call fetch_url again for the same URL unless the user explicitly asks to retry. "
                "Either answer from earlier evidence or choose a different URL."
            )
        return (
            f"{output}\n\n"
            "You have already fetched this URL. "
            "Do not call fetch_url again for the same URL unless the user explicitly asks to refresh it or inspect another page. "
            "Use the fetched content above to answer directly. "
            "If the user asked for multiple sources or cross-verification and you still have fewer than two distinct relevant pages, fetch another distinct relevant URL before the final summary."
        )

    return None


def _normalize_text(text: str) -> str:
    """Collapse whitespace and trim text. / 折叠空白并裁剪文本。"""
    import re

    return re.sub(r"\s+", " ", text or "").strip()


def _truncate_text(text: str, max_length: int) -> tuple[str, bool]:
    """Truncate text at a readable boundary. / 在较自然的边界截断文本。"""
    if len(text) <= max_length:
        return text, False

    cut = text[:max_length].rstrip()
    breakpoints = [
        cut.rfind("\n\n"),
        cut.rfind(". "),
        cut.rfind("。"),
        cut.rfind("! "),
        cut.rfind("? "),
        cut.rfind("; "),
    ]
    last_break = max(breakpoints)
    if last_break >= max_length // 2:
        cut = cut[: last_break + 1].rstrip()
    return f"{cut}... [truncated]", True


def _decode_duckduckgo_result_url(url: str) -> str:
    """Decode DuckDuckGo redirect links when present. / 解码 DuckDuckGo 跳转链接。"""
    if not url:
        return ""

    if url.startswith("//"):
        url = f"https:{url}"
    elif url.startswith("/"):
        url = f"https://duckduckgo.com{url}"

    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    encoded = params.get("uddg")
    if encoded and (
        parsed.netloc.endswith("duckduckgo.com")
        or parsed.path.startswith("/l/")
    ):
        return unquote(encoded[0])
    return url


def _extract_duckduckgo_results(html: str, max_results: int) -> list[dict[str, str]]:
    """Parse DuckDuckGo HTML result page. / 解析 DuckDuckGo HTML 搜索结果页。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "lxml")
    results: list[dict[str, str]] = []
    seen_urls: set[str] = set()

    for link in soup.select("a.result__a"):
        href = _decode_duckduckgo_result_url(link.get("href", "").strip())
        title = _normalize_text(link.get_text(" ", strip=True))
        if not href or not title or href in seen_urls:
            continue

        container = link.find_parent(
            lambda tag: tag.name in {"article", "div", "td", "tr"}
            and any(cls.startswith("result") for cls in tag.get("class", []))
        )
        snippet = ""
        if container:
            snippet_node = container.select_one(".result__snippet")
            if snippet_node is None:
                snippet_node = container.find(
                    lambda tag: tag.name in {"a", "div", "span"}
                    and any(
                        cls.startswith("result__snippet")
                        for cls in tag.get("class", [])
                    )
                )
            if snippet_node is not None:
                snippet = _normalize_text(snippet_node.get_text(" ", strip=True))

        results.append({"title": title, "url": href, "snippet": snippet})
        seen_urls.add(href)
        if len(results) >= max_results:
            break

    return results


def _format_search_results(query: str, results: list[dict[str, str]]) -> str:
    """Format search results for tool output. / 格式化搜索结果输出。"""
    lines = [f"Search results for: {query}\n"]
    for i, item in enumerate(results, 1):
        lines.append(f"{i}. {item['title']}")
        lines.append(f"   URL: {item['url']}")
        if item["snippet"]:
            lines.append(f"   {item['snippet']}")
        lines.append("")
    return "\n".join(lines)


async def _search_with_duckduckgo(query: str, max_results: int) -> tuple[list[dict[str, str]], str | None]:
    import httpx

    try:
        timeout = httpx.Timeout(20.0, connect=10.0)
        async with httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=True,
            headers=_DEFAULT_WEB_HEADERS,
        ) as client:
            resp = await client.post(
                "https://html.duckduckgo.com/html/",
                data={"q": query},
            )

        if resp.status_code >= 400:
            return [], f"HTTP {resp.status_code}"
        return _extract_duckduckgo_results(resp.text, max_results), None
    except httpx.TimeoutException:
        return [], "timeout"
    except Exception as exc:
        logger.warning("DuckDuckGo search failed: {}", exc)
        return [], str(exc)


def _remove_noise_nodes(soup: Any) -> None:
    """Drop common non-content nodes. / 删除常见非正文节点。"""
    for tag in soup(_NOISE_TAGS):
        tag.decompose()

    for node in soup.find_all(True):
        if not isinstance(getattr(node, "attrs", None), dict):
            continue

        if node.has_attr("hidden") or node.get("aria-hidden") == "true":
            node.decompose()
            continue

        style = (node.get("style") or "").lower()
        if "display:none" in style or "visibility:hidden" in style:
            node.decompose()
            continue

        if node.name not in {"div", "section", "ul", "ol"}:
            continue

        hints = " ".join([
            node.get("id", ""),
            " ".join(node.get("class", [])),
        ]).lower()
        if hints and any(noise in hints for noise in _NOISE_HINTS):
            node.decompose()


def _score_content_node(node: Any) -> int:
    """Rough heuristic for selecting the main content container. / 粗略评分主内容容器。"""
    paragraph_texts = [
        _normalize_text(item.get_text(" ", strip=True))
        for item in node.find_all(["p", "li"], limit=80)
    ]
    paragraph_chars = sum(len(text) for text in paragraph_texts if text)
    heading_count = len(node.find_all(["h1", "h2", "h3"], limit=16))
    link_chars = sum(
        len(_normalize_text(link.get_text(" ", strip=True)))
        for link in node.find_all("a", limit=120)
    )
    total_text = len(_normalize_text(node.get_text(" ", strip=True)))
    return paragraph_chars + (heading_count * 40) + min(total_text, 1600) - (link_chars // 3)


def _pick_main_content_node(soup: Any) -> Any:
    """Pick the most likely main-content node. / 选择最可能的正文节点。"""
    body = soup.find("body") or soup

    for selector in _MAIN_CONTENT_SELECTORS:
        node = body.select_one(selector)
        if node is not None and _score_content_node(node) >= 200:
            return node

    best_node = body
    best_score = _score_content_node(body)
    for node in body.find_all(["article", "main", "section", "div"], limit=240):
        score = _score_content_node(node)
        if score > best_score:
            best_node = node
            best_score = score

    return best_node


def _collect_text_blocks(node: Any, *, max_blocks: int = 120) -> list[str]:
    """Extract readable text blocks from an HTML node. / 从 HTML 节点提取可读文本块。"""
    blocks: list[str] = []
    seen: set[str] = set()

    for element in node.find_all(_TEXT_BLOCK_TAGS):
        text = _normalize_text(element.get_text(" ", strip=True))
        if not text or len(text) < 3 or text in seen:
            continue

        # Skip menus or one-word chrome fragments that still slip through.
        if element.name in {"li", "td", "th"} and len(text) < 8:
            continue

        blocks.append(text)
        seen.add(text)
        if len(blocks) >= max_blocks:
            break

    if not blocks:
        fallback = _normalize_text(node.get_text("\n", strip=True))
        if fallback:
            blocks.append(fallback)

    return blocks


def _extract_meta_description(soup: Any) -> str:
    """Read meta description / 提取 meta description。"""
    for attrs in (
        {"name": "description"},
        {"property": "og:description"},
        {"name": "twitter:description"},
    ):
        tag = soup.find("meta", attrs=attrs)
        content = _normalize_text(tag.get("content", "")) if tag else ""
        if content:
            return content
    return ""


def _extract_readable_page(html: str) -> dict[str, Any]:
    """Extract title, headings and main body from HTML. / 从 HTML 提取标题、要点标题与正文。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "lxml")
    _remove_noise_nodes(soup)

    title = ""
    if soup.title and soup.title.string:
        title = _normalize_text(soup.title.string)

    description = _extract_meta_description(soup)
    content_node = _pick_main_content_node(soup)
    headings: list[str] = []
    if content_node is not None:
        for heading in content_node.find_all(["h1", "h2", "h3"], limit=8):
            text = _normalize_text(heading.get_text(" ", strip=True))
            if text and text not in headings:
                headings.append(text)

    blocks = _collect_text_blocks(content_node)
    if title and blocks and blocks[0].lower() == title.lower():
        blocks = blocks[1:]
    body = "\n".join(blocks).strip()

    return {
        "title": title,
        "description": description,
        "headings": headings,
        "body": body,
    }


def _format_html_fetch_output(
    *,
    requested_url: str,
    final_url: str,
    page: dict[str, Any],
    max_length: int,
) -> str:
    """Format extracted page content for tool output. / 格式化页面提取结果。"""
    lines = [f"Content from {final_url}"]
    if final_url != requested_url:
        lines.append(f"Redirected from: {requested_url}")
    if page.get("title"):
        lines.append(f"Title: {page['title']}")
    if page.get("description"):
        lines.append(f"Description: {page['description']}")
    if page.get("headings"):
        lines.append(f"Key sections: {', '.join(page['headings'][:6])}")

    prefix = "\n".join(lines).strip()
    body = page.get("body", "") or ""
    if not body:
        return (
            f"{prefix}\n\nNo readable main content found. "
            "The page may require JavaScript or block automated reading."
        )

    remaining = max(max_length - len(prefix) - 2, 200)
    excerpt, _ = _truncate_text(body, remaining)
    return f"{prefix}\n\n{excerpt}"


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
                llm_follow_up_message=_build_builtin_follow_up_message(
                    func_name,
                    output,
                ),
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
        Web search: automatically choose a search source and return web results. / 联网搜索：自动选择搜索源并返回网页结果。

        Returns a list of search results (title + snippet + link).
        返回搜索结果列表（标题 + 摘要 + 链接）。
        """
        if not query:
            return "Error: query parameter is required"

        max_results = min(max(1, max_results), 10)
        providers = [("duckduckgo", _search_with_duckduckgo)]

        errors: list[str] = []
        for provider_name, provider in providers:
            results, error = await provider(query, max_results)
            if results:
                logger.info(
                    "web_search provider selected: provider={} query={}",
                    provider_name,
                    query[:120],
                )
                return _format_search_results(query, results)
            if error:
                errors.append(f"{provider_name}:{error}")

        if errors:
            logger.warning(
                "web_search all providers failed: query={} errors={}",
                query[:120],
                errors,
            )
            if all(err.endswith("timeout") or ":timeout" in err for err in errors):
                return f"Error: Search timed out for query: {query}"
            return f"No results found for: {query}"

        return f"No results found for: {query}"

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

        import httpx

        max_length = min(max(500, max_length), 20000)

        try:
            timeout = httpx.Timeout(20.0, connect=10.0)
            async with httpx.AsyncClient(
                timeout=timeout,
                follow_redirects=True,
                headers=_DEFAULT_WEB_HEADERS,
            ) as client:
                resp = await client.get(url)

            final_url = str(resp.url)
            content_type = (resp.headers.get("content-type") or "").lower()
            raw_text = resp.text or ""

            if resp.status_code >= 400:
                page = _extract_readable_page(raw_text) if raw_text else {}
                title = page.get("title") if page else ""
                message = f"Error: HTTP {resp.status_code} while fetching {final_url}"
                if title:
                    message += f" (title: {title})"
                return message

            if "html" in content_type or "<html" in raw_text[:1000].lower():
                page = _extract_readable_page(raw_text)
                return _format_html_fetch_output(
                    requested_url=url,
                    final_url=final_url,
                    page=page,
                    max_length=max_length,
                )

            text, _ = _truncate_text(_normalize_text(raw_text), max_length)
            return (
                f"Content from {final_url}:\n\n{text}"
                if text
                else f"No readable content found at {final_url}"
            )

        except httpx.TimeoutException:
            return f"Error: Request timed out for URL: {url}"
        except httpx.HTTPError as exc:
            logger.warning("fetch_url request error for {}: {}", url, exc)
            return f"Error: Failed to fetch URL - {exc}"
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
