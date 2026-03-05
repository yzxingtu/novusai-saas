"""
HTTP/Webhook 工具执行器

执行声明式 HTTP 请求，支持模板变量替换、多种认证方式、JSONPath 响应提取。
"""

from __future__ import annotations

import json
import re
import time
from typing import TYPE_CHECKING, Any

from app.ai.tools.executors.base import BaseToolExecutor
from app.ai.tools.types import ToolDefinition, ToolResult
from app.core.logging import LogManager

if TYPE_CHECKING:
    from app.ai.tools.types import ExecutionContext

logger = LogManager.get_logger("ai.tool.http")

# 安全限制
_MAX_RESPONSE_SIZE = 50_000  # 50KB
_BLOCKED_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0", "169.254.169.254", "metadata.google.internal"}
# 内网 IP 段前缀（SSRF 防护）
_PRIVATE_IP_PREFIXES = ("10.", "172.16.", "172.17.", "172.18.", "172.19.",
                        "172.20.", "172.21.", "172.22.", "172.23.",
                        "172.24.", "172.25.", "172.26.", "172.27.",
                        "172.28.", "172.29.", "172.30.", "172.31.",
                        "192.168.", "fd", "fc")
# 额外阻止的主机名
_EXTRA_BLOCKED_HOSTS = {"::1", "metadata.google", "100.100.100.200"}


def _substitute_template(template: str, variables: dict[str, Any]) -> str:
    """替换 {{variable}} 占位符"""
    def replacer(match: re.Match) -> str:
        key = match.group(1)
        return str(variables.get(key, match.group(0)))
    return re.sub(r"\{\{(\w+)\}\}", replacer, template)


def _extract_json_path(data: Any, path: str) -> Any:
    """简易 JSONPath 提取（支持 $.a.b.c 格式）"""
    if not path or not path.startswith("$"):
        return data
    parts = path.lstrip("$.").split(".")
    current = data
    for part in parts:
        if not part:
            continue
        if isinstance(current, dict):
            current = current.get(part)
        elif isinstance(current, list):
            try:
                current = current[int(part)]
            except (ValueError, IndexError):
                return None
        else:
            return None
    return current


class HttpToolExecutor(BaseToolExecutor):
    """
    HTTP/Webhook 工具执行器

    从 ToolDefinition.config 中读取：
    - _http_url: 请求 URL（支持 {{var}} 模板）
    - _http_method: HTTP 方法
    - _http_headers: 请求头 dict
    - _http_body_template: 请求体模板
    - _http_query_params: 查询参数 dict
    - _http_auth_type: 认证类型 (none/bearer/api_key/basic)
    - _http_auth_config: 认证配置
    - _http_response_path: JSONPath 响应提取路径
    """

    async def execute(
        self,
        definition: ToolDefinition,
        tool_call_id: str,
        arguments: dict[str, Any],
        context: ExecutionContext | None = None,
    ) -> ToolResult:
        """执行 HTTP 请求"""
        _ = context
        start = time.perf_counter()
        cfg = definition.config or {}

        url = _substitute_template(cfg.get("_http_url", ""), arguments)
        method = cfg.get("_http_method", "GET")
        headers = dict(cfg.get("_http_headers", {}))
        body_template = cfg.get("_http_body_template", "")
        query_params = dict(cfg.get("_http_query_params", {}))
        auth_type = cfg.get("_http_auth_type", "none")
        auth_config = cfg.get("_http_auth_config", {})
        response_path = cfg.get("_http_response_path", "")

        # SSRF 防护：阻止内网/云元数据请求
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            host = (parsed.hostname or "").lower()
            if host in _BLOCKED_HOSTS or host in _EXTRA_BLOCKED_HOSTS:
                return ToolResult(
                    tool_call_id=tool_call_id,
                    name=definition.name,
                    success=False,
                    error=f"Blocked: requests to {host} are not allowed",
                )
            if host.startswith(_PRIVATE_IP_PREFIXES):
                return ToolResult(
                    tool_call_id=tool_call_id,
                    name=definition.name,
                    success=False,
                    error=f"Blocked: requests to private network ({host}) are not allowed",
                )
        except Exception:
            pass

        # 替换查询参数中的模板变量
        for k, v in query_params.items():
            if isinstance(v, str):
                query_params[k] = _substitute_template(v, arguments)

        # 替换请求头中的模板变量
        for k, v in headers.items():
            if isinstance(v, str):
                headers[k] = _substitute_template(v, arguments)

        # 构建请求体
        body: str | None = None
        if body_template:
            body = _substitute_template(body_template, arguments)
        elif method in ("POST", "PUT", "PATCH") and "input" in arguments:
            body = str(arguments["input"])

        # 应用认证
        self._apply_auth(headers, auth_type, auth_config)

        try:
            import httpx

            timeout = definition.timeout or 30
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
                resp = await client.request(
                    method=method,
                    url=url,
                    headers=headers,
                    params=query_params if query_params else None,
                    content=body.encode("utf-8") if body else None,
                )

            duration_ms = int((time.perf_counter() - start) * 1000)

            # 截取响应
            resp_text = resp.text[:_MAX_RESPONSE_SIZE]

            # 尝试 JSONPath 提取
            if response_path:
                try:
                    resp_json = resp.json()
                    extracted = _extract_json_path(resp_json, response_path)
                    if extracted is not None:
                        resp_text = json.dumps(extracted, ensure_ascii=False, default=str)
                except Exception:
                    pass

            if resp.status_code >= 400:
                return ToolResult(
                    tool_call_id=tool_call_id,
                    name=definition.name,
                    success=False,
                    error=f"HTTP {resp.status_code}: {resp_text[:500]}",
                    duration_ms=duration_ms,
                )

            return ToolResult(
                tool_call_id=tool_call_id,
                name=definition.name,
                success=True,
                output=resp_text,
                duration_ms=duration_ms,
            )

        except Exception as exc:
            duration_ms = int((time.perf_counter() - start) * 1000)
            logger.error("HTTP tool error: %s %s: %s", method, url, str(exc))
            return ToolResult(
                tool_call_id=tool_call_id,
                name=definition.name,
                success=False,
                error=f"HTTP request failed: {str(exc)}",
                duration_ms=duration_ms,
            )

    async def validate(
        self,
        definition: ToolDefinition,
        arguments: dict[str, Any],
    ) -> bool:
        """校验 HTTP 工具参数"""
        _ = arguments
        cfg = definition.config or {}
        url = cfg.get("_http_url", "")
        return bool(url)

    @staticmethod
    def _apply_auth(
        headers: dict[str, str],
        auth_type: str,
        auth_config: dict[str, Any],
    ) -> None:
        """应用认证到请求头"""
        if auth_type == "bearer":
            token = auth_config.get("token", "")
            if token:
                headers["Authorization"] = f"Bearer {token}"
        elif auth_type == "api_key":
            key_name = auth_config.get("key_name", "X-API-Key")
            key_value = auth_config.get("key_value", "")
            if key_value:
                headers[key_name] = key_value
        elif auth_type == "basic":
            import base64
            username = auth_config.get("username", "")
            password = auth_config.get("password", "")
            if username:
                credentials = base64.b64encode(
                    f"{username}:{password}".encode()
                ).decode()
                headers["Authorization"] = f"Basic {credentials}"


__all__ = ["HttpToolExecutor"]
