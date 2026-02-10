"""
HTTP 工具执行器

通过 httpx 执行 HTTP API 调用，支持域名过滤、header 注入和响应截断
"""

import json
import time
from typing import Any

import httpx

from app.ai.tools.executors.base import BaseToolExecutor
from app.ai.tools.security import SSRFBlockedError, UrlValidator
from app.ai.tools.types import ToolDefinition, ToolResult
from app.core.i18n import _
from app.core.logging import LogManager

logger = LogManager.get_logger("ai.tool.http")

# 默认限制
DEFAULT_TIMEOUT = 30
DEFAULT_MAX_RESPONSE_SIZE = 10000  # 字符


class HttpToolExecutor(BaseToolExecutor):
    """
    HTTP API 工具执行器

    支持:
    - GET / POST 请求
    - 自定义 headers 注入
    - 域名白/黑名单过滤
    - 响应体大小截断
    """

    def __init__(
        self,
        allowed_domains: list[str] | None = None,
        blocked_domains: list[str] | None = None,
        max_response_size: int = DEFAULT_MAX_RESPONSE_SIZE,
        timeout: int = DEFAULT_TIMEOUT,
    ):
        """
        Args:
            allowed_domains: 允许访问的域名列表（为空则不限制）
            blocked_domains: 禁止访问的域名列表
            max_response_size: 最大响应体字符数
            timeout: 请求超时秒数
        """
        self.allowed_domains = allowed_domains or []
        self.blocked_domains = blocked_domains or []
        self.max_response_size = max_response_size
        self.timeout = timeout

    async def execute(
        self,
        definition: ToolDefinition,
        tool_call_id: str,
        arguments: dict[str, Any],
    ) -> ToolResult:
        """
        执行 HTTP 请求

        config 格式:
            url: 请求 URL（可含 {param} 占位符）
            method: GET / POST（默认 GET）
            headers: 额外请求头 dict
            body_field: POST 时放入 body 的参数名列表
        """
        start = time.perf_counter()
        config = definition.config

        # 构建 URL
        url_template: str = config.get("url", "")
        if not url_template:
            return ToolResult(
                tool_call_id=tool_call_id,
                name=definition.name,
                success=False,
                error=_("tool.error.http_missing_url"),
            )

        # 占位符替换
        try:
            url = url_template.format(**arguments)
        except (KeyError, IndexError):
            url = url_template

        # SSRF 安全检查（DNS 解析 + 内网 IP 检测 + 域名过滤）
        try:
            await UrlValidator.validate(
                url,
                allowed_domains=self.allowed_domains or None,
                blocked_domains=self.blocked_domains or None,
            )
        except SSRFBlockedError as ssrf_err:
            return ToolResult(
                tool_call_id=tool_call_id,
                name=definition.name,
                success=False,
                error=str(ssrf_err),
            )

        method: str = config.get("method", "GET").upper()
        headers: dict[str, str] = config.get("headers", {})
        body_fields: list[str] = config.get("body_fields", [])

        # 构建请求参数
        request_kwargs: dict[str, Any] = {
            "url": url,
            "headers": headers,
            "timeout": self.timeout,
        }

        if method == "POST":
            body = {k: arguments[k] for k in body_fields if k in arguments}
            request_kwargs["json"] = body
        else:
            # GET: 将参数作为 query string
            query_params = {
                k: v for k, v in arguments.items()
                if k not in ("url",)
            }
            request_kwargs["params"] = query_params

        try:
            async with httpx.AsyncClient(follow_redirects=False) as client:
                response = await client.request(method, **request_kwargs)

            duration_ms = int((time.perf_counter() - start) * 1000)

            # 截断响应体
            body_text = response.text
            if len(body_text) > self.max_response_size:
                body_text = body_text[: self.max_response_size] + "\n...[truncated]"

            # 非 2xx 视为业务失败但不抛异常
            if response.status_code >= 400:
                return ToolResult(
                    tool_call_id=tool_call_id,
                    name=definition.name,
                    success=False,
                    error=f"HTTP {response.status_code}: {body_text}",
                    duration_ms=duration_ms,
                )

            return ToolResult(
                tool_call_id=tool_call_id,
                name=definition.name,
                success=True,
                output=body_text,
                duration_ms=duration_ms,
            )

        except httpx.TimeoutException:
            duration_ms = int((time.perf_counter() - start) * 1000)
            logger.warning(
                "HTTP tool timeout: %s %s after %dms",
                method,
                url,
                duration_ms,
            )
            return ToolResult(
                tool_call_id=tool_call_id,
                name=definition.name,
                success=False,
                error=_("tool.error.http_timeout"),
                duration_ms=duration_ms,
            )

        except Exception as exc:
            duration_ms = int((time.perf_counter() - start) * 1000)
            logger.error(
                "HTTP tool error: %s %s: %s",
                method,
                url,
                str(exc),
                exc_info=True,
            )
            return ToolResult(
                tool_call_id=tool_call_id,
                name=definition.name,
                success=False,
                error=str(exc),
                duration_ms=duration_ms,
            )

    async def validate(
        self,
        definition: ToolDefinition,
        arguments: dict[str, Any],
    ) -> bool:
        """校验 HTTP 工具参数"""
        config = definition.config
        if not config.get("url"):
            return False

        # 检查必填参数
        for param in definition.parameters:
            if param.required and param.name not in arguments:
                return False

        return True


__all__ = ["HttpToolExecutor"]
