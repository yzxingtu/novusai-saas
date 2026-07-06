"""
Internal API Executor / 内部 API 执行器

Executes the internal-ops meta-tools (list / describe / invoke). Invocations
are performed as HTTP self-calls against this application carrying a
short-lived AI proxy token, so RBAC, tenant isolation, request validation and
audit logging are all enforced by the existing middleware stack.
执行内部操作元工具（list / describe / invoke）。invoke 通过携带短时效 AI 代理
token 的 HTTP 自调用完成，RBAC、租户隔离、参数校验与审计日志全部复用现有
中间件栈强制执行。
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

import httpx

from app.ai.internal_ops.catalog import (
    USER_ROLE_TO_SCOPE,
    InternalOperation,
    get_operation,
    has_permission,
    search_operations,
)
from app.ai.internal_ops.proxy_token import issue_ai_proxy_token
from app.ai.internal_ops.tools import (
    TOOL_DESCRIBE_OPERATION,
    TOOL_INVOKE_OPERATION,
    TOOL_LIST_OPERATIONS,
)
from app.ai.tools.executors.base import BaseToolExecutor
from app.ai.tools.types import ExecutionContext, ToolDefinition, ToolResult
from app.core.config import settings
from app.core.logging import LogManager

logger = LogManager.get_logger("ai.tool.internal_api")

# Pending write confirmations live this long in Redis / 待确认写操作的 Redis TTL（秒）
_PENDING_CONFIRMATION_TTL_SECONDS = 600
_PENDING_KEY_PREFIX = "ai:internal_ops:pending"

# Cap for non-JSON response bodies relayed to the LLM / 非 JSON 响应体转发上限
_MAX_TEXT_BODY_CHARS = 2000

_PATH_PLACEHOLDER_RE = re.compile(r"\{(\w+)\}")


def _json_output(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, default=str)


def _arguments_digest(
    operation_id: str,
    path_params: dict[str, Any],
    query_params: dict[str, Any],
    body: dict[str, Any] | None,
) -> str:
    canonical = json.dumps(
        [operation_id, path_params, query_params, body],
        ensure_ascii=False,
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:32]


class InternalApiExecutor(BaseToolExecutor):
    """
    Internal API meta-tool executor / 内部 API 元工具执行器

    Security model / 安全模型:
    - The proxy token subject is the conversation user, so the self-call goes
      through PermissionMiddleware and RBAC exactly like a manual request.
      代理 token 主体是对话用户本人，自调用与手工请求一样经过权限中间件与 RBAC。
    - Write operations require a server-armed confirmation: the preview call
      records a Redis entry, and execution only proceeds when the confirmed
      replay matches that entry. An LLM passing confirmed=true on its own
      cannot bypass the preview.
      写操作需要服务端布防的确认：预览时写入 Redis 记录，仅当确认重放命中该
      记录才执行。LLM 自行伪造 confirmed=true 无法绕过预览。
    """

    async def validate(
        self,
        definition: ToolDefinition,
        arguments: dict[str, Any],
    ) -> bool:
        # JSON Schema validation already runs in ToolSandbox / 沙箱已做 Schema 校验
        return True

    async def execute(
        self,
        definition: ToolDefinition,
        tool_call_id: str,
        arguments: dict[str, Any],
        context: ExecutionContext | None = None,
    ) -> ToolResult:
        name = definition.name
        if context is None or not context.user_id:
            return ToolResult.error_result(
                tool_call_id,
                "Internal operations require an authenticated conversation user.",
                name=name,
            )

        scope = USER_ROLE_TO_SCOPE.get(str(context.user_role or "").strip())
        if not scope:
            return ToolResult.error_result(
                tool_call_id,
                f"Unsupported user role for internal operations: {context.user_role}",
                name=name,
            )

        try:
            if name == TOOL_LIST_OPERATIONS:
                return self._list_operations(tool_call_id, arguments, context, scope)
            if name == TOOL_DESCRIBE_OPERATION:
                return self._describe_operation(
                    tool_call_id, arguments, context, scope
                )
            if name == TOOL_INVOKE_OPERATION:
                return await self._invoke_operation(
                    tool_call_id, arguments, context, scope
                )
        except Exception as exc:  # noqa: BLE001
            logger.error("Internal ops tool {} failed: {}", name, exc, exc_info=True)
            return ToolResult.error_result(
                tool_call_id,
                f"Internal operation tool failed: {exc}",
                name=name,
            )

        return ToolResult.error_result(
            tool_call_id,
            f"Unknown internal ops tool: {name}",
            name=name,
        )

    # ------------------------------------------------------------------
    # list / describe
    # ------------------------------------------------------------------

    def _list_operations(
        self,
        tool_call_id: str,
        arguments: dict[str, Any],
        context: ExecutionContext,
        scope: str,
    ) -> ToolResult:
        page, total = search_operations(
            scope=scope,
            user_permissions=set(context.permissions or set()),
            keyword=str(arguments.get("keyword") or ""),
            module=str(arguments.get("module") or ""),
            method=str(arguments.get("method") or ""),
            offset=int(arguments.get("offset") or 0),
        )
        payload: dict[str, Any] = {
            "total": total,
            "returned": len(page),
            "operations": [op.to_brief() for op in page],
        }
        if total == 0:
            payload["empty_result"] = True
            payload["should_stop_searching"] = True
            payload["recommended_next_action"] = (
                "Stop calling list_internal_operations after one retry; "
                "tell the user no matching operation is available in the "
                "current permission scope."
            )
            payload["possible_reasons"] = [
                "permission_scope_has_no_matching_operation",
                "feature_not_enabled",
                "endpoint_not_registered",
            ]
            payload["hint"] = (
                "No operations matched in the current permission scope. "
                "Retry at most once with a broader keyword, then stop "
                "searching and explain that no matching operation is "
                "available."
            )
        elif total > len(page):
            payload["hint"] = (
                "More results available; refine the keyword or pass a larger "
                "offset to page through."
            )
        return ToolResult(
            tool_call_id=tool_call_id,
            name=TOOL_LIST_OPERATIONS,
            success=True,
            output=_json_output(payload),
            summary=f"{total} operations matched",
        )

    def _describe_operation(
        self,
        tool_call_id: str,
        arguments: dict[str, Any],
        context: ExecutionContext,
        scope: str,
    ) -> ToolResult:
        operation_id = str(arguments.get("operation_id") or "").strip()
        op = get_operation(operation_id)
        error = self._check_operation_access(op, operation_id, context, scope)
        if error:
            return ToolResult.error_result(
                tool_call_id, error, name=TOOL_DESCRIBE_OPERATION
            )
        assert op is not None
        return ToolResult(
            tool_call_id=tool_call_id,
            name=TOOL_DESCRIBE_OPERATION,
            success=True,
            output=_json_output(op.to_detail()),
            summary=f"{op.method} {op.path}",
        )

    # ------------------------------------------------------------------
    # invoke
    # ------------------------------------------------------------------

    async def _invoke_operation(
        self,
        tool_call_id: str,
        arguments: dict[str, Any],
        context: ExecutionContext,
        scope: str,
    ) -> ToolResult:
        operation_id = str(arguments.get("operation_id") or "").strip()
        op = get_operation(operation_id)
        error = self._check_operation_access(op, operation_id, context, scope)
        if error:
            return ToolResult.error_result(
                tool_call_id, error, name=TOOL_INVOKE_OPERATION
            )
        assert op is not None

        path_params = dict(arguments.get("path_params") or {})
        query_params = dict(arguments.get("query_params") or {})
        body = arguments.get("body")
        if body is not None and not isinstance(body, dict):
            return ToolResult.error_result(
                tool_call_id,
                "Argument 'body' must be a JSON object.",
                name=TOOL_INVOKE_OPERATION,
            )

        # Fill path placeholders / 填充路径占位符
        placeholders = _PATH_PLACEHOLDER_RE.findall(op.path)
        missing = [p for p in placeholders if p not in path_params]
        if missing:
            return ToolResult.error_result(
                tool_call_id,
                f"Missing path params: {missing}. "
                "Call describe_internal_operation for the parameter spec.",
                name=TOOL_INVOKE_OPERATION,
            )
        resolved_path = op.path
        for p in placeholders:
            resolved_path = resolved_path.replace(
                "{" + p + "}", str(path_params[p])
            )

        # Write operations require a server-armed confirmation
        # 写操作需要服务端布防的确认
        if op.is_write:
            digest = _arguments_digest(operation_id, path_params, query_params, body)
            confirmed = arguments.get("confirmed") is True
            gate = await self._write_confirmation_gate(
                context=context,
                op=op,
                digest=digest,
                confirmed=confirmed,
                preview={
                    "operation_id": operation_id,
                    "path_params": path_params,
                    "query_params": query_params,
                    "body": body,
                },
            )
            if gate is not None:
                return ToolResult(
                    tool_call_id=tool_call_id,
                    name=TOOL_INVOKE_OPERATION,
                    success=True,
                    output=gate,
                    summary=f"Awaiting confirmation: {op.method} {resolved_path}",
                )

        return await self._perform_http_call(
            tool_call_id=tool_call_id,
            context=context,
            op=op,
            resolved_path=resolved_path,
            query_params=query_params,
            body=body,
        )

    def _check_operation_access(
        self,
        op: InternalOperation | None,
        operation_id: str,
        context: ExecutionContext,
        scope: str,
    ) -> str | None:
        """Shared lookup + scope + permission pre-check / 查找与权限预检"""
        if op is None:
            return (
                f"Operation '{operation_id}' not found. Use "
                "list_internal_operations to discover valid operation ids."
            )
        if op.scope != scope:
            return (
                f"Operation '{operation_id}' belongs to the '{op.scope}' console "
                f"and is not available for the current '{scope}' user."
            )
        if not has_permission(set(context.permissions or set()), op.permission_code):
            return (
                f"The current user lacks permission '{op.permission_code}' "
                "required by this operation."
            )
        return None

    async def _write_confirmation_gate(
        self,
        *,
        context: ExecutionContext,
        op: InternalOperation,
        digest: str,
        confirmed: bool,
        preview: dict[str, Any],
    ) -> str | None:
        """
        Returns a confirmation-preview output, or None when execution may
        proceed. 返回确认预览输出；返回 None 表示放行执行。
        """
        from app.core.redis import get_redis_client

        key = (
            f"{_PENDING_KEY_PREFIX}:{context.conversation_id or 0}"
            f":{context.agent_id}:{context.user_id}:{digest}"
        )
        try:
            client = get_redis_client()
            if confirmed and await client.exists(key):
                await client.delete(key)
                return None
            await client.setex(key, _PENDING_CONFIRMATION_TTL_SECONDS, "1")
        except Exception as exc:  # noqa: BLE001
            # Fail closed: never run unverified writes without the Redis gate
            # 故障关闭：Redis 不可用时绝不执行未经验证的写操作
            logger.error("Write confirmation gate unavailable: {}", exc)
            return _json_output(
                {
                    "error": (
                        "Write confirmation service is unavailable; "
                        "the operation was NOT executed. Try again later."
                    ),
                }
            )

        # Build user-readable approval presentation / 构建用户可读确认展示
        from app.ai.internal_ops.approval_presentation import (
            build_approval_presentation,
        )

        presentation = await build_approval_presentation(
            db=context.db,
            operation_id=op.operation_id,
            method=op.method,
            path=op.path,
            permission_code=op.permission_code,
            summary=op.summary,
            action=op.action,
            body=preview.get("body"),
            path_params=preview.get("path_params"),
            query_params=preview.get("query_params"),
        )

        return _json_output(
            {
                "requires_confirmation": True,
                "action": f"{op.method} {op.path}",
                "operation_id": op.operation_id,
                "summary": op.summary,
                "permission": op.permission_code,
                "preview": preview,
                "approval_presentation": presentation.to_dict(),
                "message": (
                    "This is a write operation and it was NOT executed yet. "
                    "Present the preview to the user and wait. If the user "
                    "explicitly approves in a later message, call "
                    "invoke_internal_operation again with the exact same "
                    "arguments plus confirmed=true. If the user rejects, do "
                    "not retry."
                ),
            }
        )

    async def _perform_http_call(
        self,
        *,
        tool_call_id: str,
        context: ExecutionContext,
        op: InternalOperation,
        resolved_path: str,
        query_params: dict[str, Any],
        body: dict[str, Any] | None,
    ) -> ToolResult:
        token = issue_ai_proxy_token(
            user_id=int(context.user_id or 0),
            user_role=str(context.user_role),
            tenant_id=context.tenant_id,
            agent_id=context.agent_id,
            conversation_id=context.conversation_id,
        )
        headers = {
            "Authorization": f"Bearer {token}",
            "User-Agent": (
                f"NovusAI-Copilot/1.0 (agent={context.agent_id}; "
                f"conversation={context.conversation_id or 0})"
            ),
        }

        timeout = 30.0
        if context.tool_timeout_seconds:
            timeout = max(min(float(context.tool_timeout_seconds) - 1.0, 55.0), 5.0)

        async with httpx.AsyncClient(
            base_url=settings.APP_INTERNAL_BASE_URL,
            timeout=timeout,
            follow_redirects=False,
        ) as client:
            try:
                response = await client.request(
                    op.method,
                    resolved_path,
                    params=query_params or None,
                    json=body if op.method in ("POST", "PUT", "PATCH") else None,
                    headers=headers,
                )
            except httpx.HTTPError as exc:
                return ToolResult.error_result(
                    tool_call_id,
                    f"Internal API call failed: {exc}",
                    name=TOOL_INVOKE_OPERATION,
                )

        try:
            response_body: Any = response.json()
        except ValueError:
            text = response.text or ""
            response_body = text[:_MAX_TEXT_BODY_CHARS]

        payload = {
            "status_code": response.status_code,
            "ok": 200 <= response.status_code < 300,
            "operation_id": op.operation_id,
            "body": response_body,
        }
        return ToolResult(
            tool_call_id=tool_call_id,
            name=TOOL_INVOKE_OPERATION,
            success=True,
            output=_json_output(payload),
            summary=f"{op.method} {resolved_path} → {response.status_code}",
        )


__all__ = ["InternalApiExecutor"]
