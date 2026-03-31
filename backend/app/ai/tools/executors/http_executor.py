"""
HTTP/Webhook Tool Executor. / HTTP/Webhook 工具执行器。

Executes declarative HTTP requests with template variable substitution, multiple auth methods, and JSONPath response extraction.
执行声明式 HTTP 请求，支持模板变量替换、多种认证方式、JSONPath 响应提取。
"""

from __future__ import annotations

import json
import re
import time
from typing import TYPE_CHECKING, Any

from app.ai.tools.executors.base import BaseToolExecutor
from app.ai.tools.security import SSRFBlockedError, UrlValidator
from app.ai.tools.types import ToolDefinition, ToolResult
from app.core.logging import LogManager
from app.core.response import build_public_error_text
from app.enums.agent import ActionLevelEnum, ActionStatusEnum, ActionTypeEnum
from app.middleware.trace import trace_id_var
from app.services.ai.action_log_service import write_ai_action_log

if TYPE_CHECKING:
    from app.ai.tools.types import ExecutionContext

logger = LogManager.get_logger("ai.tool.http")

# Security limits / 安全限制
_MAX_RESPONSE_SIZE = 50_000  # 50KB  # 补充说明 / note


def _substitute_template(template: str, variables: dict[str, Any]) -> str:
    """Substitute {{variable}} placeholders / 替换 {{variable}} 占位符"""
    def replacer(match: re.Match) -> str:
        key = match.group(1)
        return str(variables.get(key, match.group(0)))
    return re.sub(r"\{\{(\w+)\}\}", replacer, template)


def _extract_json_path(data: Any, path: str) -> Any:
    """Simple JSONPath extraction (supports $.a.b.c format). / 简易 JSONPath 提取（支持 $.a.b.c 格式）。"""
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
    HTTP/Webhook tool executor.
    HTTP/Webhook 工具执行器。

    Reads from ToolDefinition.config:
    从 ToolDefinition.config 中读取：
    - _http_url: Request URL (supports {{var}} templates) / 请求 URL（支持 {{var}} 模板）
    - _http_method: HTTP method / HTTP 方法
    - _http_headers: Request headers dict / 请求头 dict
    - _http_body_template: Request body template / 请求体模板
    - _http_query_params: Query parameters dict / 查询参数 dict
    - _http_auth_type: Auth type (none/bearer/api_key/basic) / 认证类型
    - _http_auth_config: Auth configuration / 认证配置
    - _http_response_path: JSONPath response extraction path / JSONPath 响应提取路径
    """

    async def execute(
        self,
        definition: ToolDefinition,
        tool_call_id: str,
        arguments: dict[str, Any],
        context: ExecutionContext | None = None,
    ) -> ToolResult:
        """Execute HTTP request / 执行 HTTP 请求"""
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

        # SSRF protection: reuse shared UrlValidator (redirect/DNS/内网/metadata 统一策略)
        try:
            await UrlValidator.validate(url)
        except SSRFBlockedError as e:
            return ToolResult(
                tool_call_id=tool_call_id,
                name=definition.name,
                success=False,
                error=build_public_error_text(message=str(e)),
            )

        # Substitute template variables in query params / 替换查询参数中的模板变量
        for k, v in query_params.items():
            if isinstance(v, str):
                query_params[k] = _substitute_template(v, arguments)

        # Substitute template variables in headers / 替换请求头中的模板变量
        for k, v in headers.items():
            if isinstance(v, str):
                headers[k] = _substitute_template(v, arguments)

        # Build request body / 构建请求体
        body: str | None = None
        if body_template:
            body = _substitute_template(body_template, arguments)
        elif method in ("POST", "PUT", "PATCH") and "input" in arguments:
            body = str(arguments["input"])

        # Apply authentication / 应用认证
        self._apply_auth(headers, auth_type, auth_config)

        try:
            import httpx

            timeout = definition.timeout or 30
            # Redirects are disabled here so every outbound target must pass the / 上文为英文说明 / English above
            # shared UrlValidator check explicitly instead of silently hopping
            # to another host after the first validated URL.
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
                resp = await client.request(
                    method=method,
                    url=url,
                    headers=headers,
                    params=query_params if query_params else None,
                    content=body.encode("utf-8") if body else None,
                )

            duration_ms = int((time.perf_counter() - start) * 1000)

            # Truncate response / 截取响应
            resp_text = resp.text[:_MAX_RESPONSE_SIZE]

            # Attempt JSONPath extraction / 尝试 JSONPath 提取
            if response_path:
                try:
                    resp_json = resp.json()
                    extracted = _extract_json_path(resp_json, response_path)
                    if extracted is not None:
                        resp_text = json.dumps(extracted, ensure_ascii=False, default=str)
                except Exception as json_exc:
                    logger.debug("HTTP tool JSONPath extract failed: {}", json_exc)

            if 300 <= resp.status_code < 400:
                location = resp.headers.get("location", "")
                return ToolResult(
                    tool_call_id=tool_call_id,
                    name=definition.name,
                    success=False,
                    error=build_public_error_text(
                        message="HTTP redirect blocked",
                        detail=location or "no location header",
                    ),
                    duration_ms=duration_ms,
                )

            if resp.status_code >= 400:
                result = ToolResult(
                    tool_call_id=tool_call_id,
                    name=definition.name,
                    success=False,
                    error=build_public_error_text(
                        message=f"HTTP {resp.status_code} from upstream service",
                    ),
                    duration_ms=duration_ms,
                )
                await self._audit_http_action(
                    definition=definition,
                    context=context,
                    tool_call_id=tool_call_id,
                    arguments=arguments,
                    url=url,
                    method=method,
                    query_params=query_params,
                    status=ActionStatusEnum.FAILED.value,
                    duration_ms=duration_ms,
                    response_summary={
                        "status_code": resp.status_code,
                        "response_path": response_path or None,
                    },
                    error_message=result.error,
                )
                return result

            result = ToolResult(
                tool_call_id=tool_call_id,
                name=definition.name,
                success=True,
                output=resp_text,
                duration_ms=duration_ms,
            )
            await self._audit_http_action(
                definition=definition,
                context=context,
                tool_call_id=tool_call_id,
                arguments=arguments,
                url=url,
                method=method,
                query_params=query_params,
                status=ActionStatusEnum.SUCCESS.value,
                duration_ms=duration_ms,
                response_summary={
                    "status_code": resp.status_code,
                    "response_path": response_path or None,
                },
                error_message=None,
            )
            return result

        except Exception as exc:
            duration_ms = int((time.perf_counter() - start) * 1000)
            logger.error("HTTP tool error: {} {}: {}", method, url, str(exc))
            result = ToolResult(
                tool_call_id=tool_call_id,
                name=definition.name,
                success=False,
                error=build_public_error_text(
                    message="HTTP request failed",
                    exc=exc,
                ),
                duration_ms=duration_ms,
            )
            await self._audit_http_action(
                definition=definition,
                context=context,
                tool_call_id=tool_call_id,
                arguments=arguments,
                url=url,
                method=method,
                query_params=query_params,
                status=ActionStatusEnum.FAILED.value,
                duration_ms=duration_ms,
                response_summary=None,
                error_message=result.error,
            )
            return result

    async def validate(
        self,
        definition: ToolDefinition,
        arguments: dict[str, Any],
    ) -> bool:
        """Validate HTTP tool parameters / 校验 HTTP 工具参数"""
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
        """Apply authentication to request headers / 应用认证到请求头"""
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

    async def _audit_http_action(
        self,
        *,
        definition: ToolDefinition,
        context: ExecutionContext | None,
        tool_call_id: str,
        arguments: dict[str, Any],
        url: str,
        method: str,
        query_params: dict[str, Any],
        status: str,
        duration_ms: int,
        response_summary: dict[str, Any] | None,
        error_message: str | None,
    ) -> None:
        if not context or not context.db:
            return
        try:
            await write_ai_action_log(
                context.db,
                tenant_id=context.tenant_id,
                agent_id=context.agent_id,
                operator_id=context.user_id,
                operator_type=context.user_role,
                conversation_id=context.conversation_id,
                tool_call_id=tool_call_id,
                skill_id=context.skill_id,
                action_name=f"http_{method.lower()}",
                action_type=ActionTypeEnum.ACTION.value,
                action_level=ActionLevelEnum.DANGEROUS.value,
                request_data={
                    "tool_name": definition.name,
                    "trace_id": trace_id_var.get() or None,
                    "url": url,
                    "method": method,
                    "arguments": arguments,
                    "query_params": query_params,
                },
                response_data=response_summary,
                status=status,
                error_message=error_message,
                duration_ms=duration_ms,
            )
        except Exception as exc:
            logger.warning("Failed to write HTTP tool audit log: {}", str(exc))


__all__ = ["HttpToolExecutor"]
