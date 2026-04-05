"""
Audit Log Middleware / 审计日志中间件

Intercepts all API requests and records operation logs to database.
拦截所有 API 请求，记录操作日志到数据库。
"""

import json
import re
import time
from typing import Any

from starlette.datastructures import Headers
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.security import (
    TOKEN_SCOPE_ADMIN,
    TOKEN_SCOPE_TENANT_ADMIN,
    TOKEN_SCOPE_TENANT_USER,
    TOKEN_TYPE_ACCESS,
    get_token_payload,
)
from app.enums.log import UserTypeEnum

# Path prefixes excluded from logging / 不记录日志的路径前缀
EXCLUDED_PATHS = [
    "/health",
    "/ready",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/favicon.ico",
]

# Path patterns excluded from logging / 不记录日志的路径正则
EXCLUDED_PATTERNS = [
    re.compile(r"^/static/"),
    re.compile(r"^/assets/"),
]

# Sensitive fields (need masking) / 敏感字段（需要脱敏）
SENSITIVE_FIELDS = {
    "password",
    "password_hash",
    "old_password",
    "new_password",
    "confirm_password",
    "token",
    "access_token",
    "refresh_token",
    "secret",
    "api_key",
    "secret_key",
}

# HTTP method to action type mapping (fallback only) / HTTP 方法到操作类型的映射
METHOD_ACTION_MAP = {
    "GET": "query",
    "POST": "create",
    "PUT": "update",
    "PATCH": "update",
    "DELETE": "delete",
}

# Special path action type mapping / 特殊路径的操作类型映射
SPECIAL_PATH_ACTIONS = {
    "/auth/login": "login",
    "/auth/logout": "logout",
    "/export": "export",
    "/import": "import",
}


def should_log_request(path: str, method: str) -> bool:
    """
    Check if this request should be logged / 判断是否应该记录该请求

    Args:
        path: Request path / 请求路径
        method: HTTP method / HTTP 方法

    Returns:
        Whether to log / 是否记录
    """
    # OPTIONS requests not logged / OPTIONS 请求不记录
    if method == "OPTIONS":
        return False

    # Excluded path prefixes / 排除的路径前缀
    for excluded in EXCLUDED_PATHS:
        if path.startswith(excluded):
            return False

    # Excluded path patterns / 排除的路径正则
    return all(not pattern.match(path) for pattern in EXCLUDED_PATTERNS)


def sanitize_body(body: dict | list | Any) -> dict | list | Any:
    """
    Sanitize sensitive fields in request body / 脱敏请求体中的敏感字段

    Args:
        body: Original request body / 原始请求体

    Returns:
        Sanitized request body / 脱敏后的请求体
    """
    if isinstance(body, dict):
        result = {}
        for key, value in body.items():
            if key.lower() in SENSITIVE_FIELDS:
                result[key] = "***"
            elif isinstance(value, (dict, list)):
                result[key] = sanitize_body(value)
            else:
                result[key] = value
        return result
    elif isinstance(body, list):
        return [sanitize_body(item) for item in body]
    return body


def extract_permission_from_route(
    scope: Scope,
) -> tuple[str | None, str | None, str | None]:
    """
    Extract permission info from FastAPI route / 从 FastAPI 路由提取权限信息

    Matches current request route to get resource and action from permission decorators.
    通过匹配当前请求的路由，获取权限装饰器定义的 resource 和 action。

    Args:
        scope: ASGI scope

    Returns:
        (module, action, resource) tuple / 元组
        - module: Business module / 业务模块 (e.g. organization, tenant)
        - action: Action type / 操作类型 (e.g. create, update)
        - resource: Full permission code / 完整权限码 (e.g. organization:create)
    """
    from starlette.routing import Match

    app = scope.get("app")
    if not app:
        return None, None, None

    # Iterate route matching / 遍历路由匹配
    for route in getattr(app, "routes", []):
        match, child_scope = route.matches(scope)
        if match == Match.FULL:
            endpoint = getattr(route, "endpoint", None)
            if endpoint:
                # Get info defined by permission decorators / 获取权限装饰器定义的信息
                permission_resource = getattr(endpoint, "_permission_resource", None)
                permission_action = getattr(endpoint, "_permission_action", None)

                if permission_resource and permission_action:
                    action = (
                        permission_action.get("action")
                        if isinstance(permission_action, dict)
                        else None
                    )
                    resource_code = (
                        f"{permission_resource}:{action}" if action else None
                    )
                    return permission_resource, action, resource_code

    return None, None, None


def get_special_action(path: str) -> str | None:
    """
    Check if path matches special action type / 检查路径是否匹配特殊操作类型

    Args:
        path: Request path / 请求路径

    Returns:
        Special action type or None / 特殊操作类型或 None
    """
    for pattern, action in SPECIAL_PATH_ACTIONS.items():
        if pattern in path:
            return action
    return None


def get_client_ip(scope: Scope) -> str | None:
    """
    Get client real IP / 获取客户端真实 IP

    Supports proxy X-Forwarded-For header / 支持代理服务器的 X-Forwarded-For 头
    """
    headers = Headers(scope=scope)

    # Prefer X-Forwarded-For / 优先从 X-Forwarded-For 获取
    x_forwarded_for = headers.get("x-forwarded-for")
    if x_forwarded_for:
        # First IP is client real IP / 取第一个 IP（客户端真实 IP）
        return x_forwarded_for.split(",")[0].strip()

    # From X-Real-IP / 从 X-Real-IP 获取
    x_real_ip = headers.get("x-real-ip")
    if x_real_ip:
        return x_real_ip

    # From ASGI scope / 从 ASGI scope 获取
    client = scope.get("client")
    if client:
        return client[0]

    return None


class AuditLogMiddleware:
    """
    Audit Log Middleware (ASGI implementation).
    审计日志中间件（ASGI 实现）。

    功能 / Features：
    1. 拦截所有 API 请求 / Intercept all API requests
    2. 记录请求/响应信息 / Record request/response info
    3. 从 Token 解析用户信息 / Parse user info from Token
    4. 请求体脱敏处理 / Sanitize request body
    5. 异步写入数据库（不阻塞请求） / Async write to DB (non-blocking)
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Ensure scope has state (for subsequent middleware) / 确保 scope 中有 state
        if "state" not in scope:
            from starlette.datastructures import State

            scope["state"] = State()

        # Get request info / 获取请求信息
        path = scope.get("path", "")
        method = scope.get("method", "")

        # Check if logging needed / 判断是否需要记录
        if not should_log_request(path, method):
            await self.app(scope, receive, send)
            return

        # Record start time / 记录开始时间
        start_time = time.time()

        # Collect request info / 收集请求信息
        request_info = await self._collect_request_info(scope, receive)

        # For collecting response info / 用于收集响应信息
        response_info: dict[str, Any] = {
            "status_code": None,
            "response_code": None,
            "response_message": None,
        }

        # Wrap receive to allow multiple body reads / 包装 receive 以允许多次读取请求体
        body_parts: list[bytes] = request_info.get("_body_parts", [])
        body_index = 0
        _http_request_done = [False]

        # Key distinction: _collect_request_info only calls original receive() for POST/PUT/PATCH. / 要点：仅 POST/PUT/PATCH 消费原始 receive
        # For GET/DELETE/HEAD etc., original receive() was never consumed,
        # still holds the real http.request message.
        #
        # Bug scenario (before fix):
        #   1. wrapped_receive 1st call → body_parts=[] → synthesize http.request(body=b"")
        #   2. SSE disconnect detection calls again → pass-through to original receive() → returns real http.request
        #   3. Starlette receives 2nd http.request → RuntimeError: Unexpected message received
        #
        # Fix: for methods where original receive was not consumed, pass-through the real message
        # instead of synthesizing empty body. This way Starlette only gets one http.request.
        _body_consumed_from_source = method in ("POST", "PUT", "PATCH")

        async def wrapped_receive() -> Message:
            nonlocal body_index
            if body_parts and body_index < len(body_parts):
                chunk = body_parts[body_index]
                body_index += 1
                more = body_index < len(body_parts)
                if not more:
                    _http_request_done[0] = True
                return {
                    "type": "http.request",
                    "body": chunk,
                    "more_body": more,
                }
            if not _http_request_done[0]:
                _http_request_done[0] = True
                if _body_consumed_from_source:
                    # POST/PUT/PATCH: body already consumed by _collect_request_info,
                    # synthesize empty body end message to prevent route handler from hanging.
                    # / 请求体已读完，合成空包尾防止挂起
                    return {"type": "http.request", "body": b"", "more_body": False}
                else:
                    # GET/DELETE etc.: original receive() was never called,
                    # pass-through returns real http.request to avoid duplicate messages.
                    # / GET 等未消费 receive，直通真实消息防重复
                    return await receive()
            # http.request 已交付完毕，pass-through 供断连检测（返回 http.disconnect 等）
            # http.request delivered, pass-through for disconnect detection (http.disconnect etc.)
            return await receive()

        # Wrap send to capture response info / 包装 send 以捕获响应信息
        response_body_parts: list[bytes] = []

        async def wrapped_send(message: Message) -> None:
            if message["type"] == "http.response.start":
                response_info["status_code"] = message.get("status")
            elif message["type"] == "http.response.body":
                # Try extracting business response code from body / 尝试从响应体提取业务响应码
                body = message.get("body", b"")
                if body:
                    response_body_parts.append(body)
                if not message.get("more_body", False) and response_body_parts:
                    try:
                        response_data = json.loads(b"".join(response_body_parts))
                        response_info["response_code"] = response_data.get("code")
                        response_info["response_message"] = response_data.get("message")
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        pass
            await send(message)

        # Execute request / 执行请求
        try:
            await self.app(scope, wrapped_receive, wrapped_send)
        finally:
            # Calculate duration / 计算耗时
            duration_ms = int((time.time() - start_time) * 1000)

            # Record log asynchronously / 异步记录日志
            await self._write_log(
                scope=scope,
                request_info=request_info,
                response_info=response_info,
                duration_ms=duration_ms,
            )

    async def _collect_request_info(
        self, scope: Scope, receive: Receive
    ) -> dict[str, Any]:
        """
        收集请求信息 / Collect request info

        Args:
            scope: ASGI scope
            receive: ASGI receive

        Returns:
            请求信息字典 / Request info dict
        """
        headers = Headers(scope=scope)

        # 基础信息 / Basic info
        info: dict[str, Any] = {
            "method": scope.get("method", ""),
            "path": scope.get("path", ""),
            "query_string": scope.get("query_string", b"").decode(
                "utf-8", errors="ignore"
            ),
            "ip": get_client_ip(scope),
            "user_agent": headers.get("user-agent"),
        }

        # 解析查询参数 / Parse query params
        if info["query_string"]:
            from urllib.parse import parse_qs

            info["query_params"] = parse_qs(info["query_string"])
        else:
            info["query_params"] = None

        # 收集请求体（仅对 POST/PUT/PATCH） / Collect request body (POST/PUT/PATCH only)
        body_parts: list[bytes] = []
        if info["method"] in ("POST", "PUT", "PATCH"):
            body = b""
            while True:
                message = await receive()
                chunk = message.get("body", b"")
                if chunk:
                    body += chunk
                    body_parts.append(chunk)
                if not message.get("more_body"):
                    break

            # 解析并脱敏请求体 / Parse and sanitize request body
            if body:
                try:
                    content_type = headers.get("content-type", "")
                    if "application/json" in content_type:
                        body_data = json.loads(body)
                        info["request_body"] = sanitize_body(body_data)
                    else:
                        # 非 JSON 请求体，仅记录大小 / Non-JSON body, record size only
                        info["request_body"] = {
                            "_size": len(body),
                            "_type": content_type,
                        }
                except (json.JSONDecodeError, UnicodeDecodeError):
                    info["request_body"] = {
                        "_size": len(body),
                        "_error": "parse_failed",
                    }

        info["_body_parts"] = body_parts
        return info

    async def _get_user_info(self, scope: Scope) -> dict[str, Any]:
        """
        从 scope 获取用户信息 / Get user info from scope

        优先从 PermissionMiddleware 注入的 state 获取，
        否则尝试从 Token 解析。
        Prefers state injected by PermissionMiddleware,
        otherwise parses from Token.
        """
        headers = Headers(scope=scope)
        auth_header = headers.get("authorization", "")

        user_info = {
            "tenant_id": None,
            "user_type": UserTypeEnum.ANONYMOUS.value,
            "user_id": None,
            "username": None,
            "nickname": None,
        }

        if not auth_header.startswith("Bearer "):
            return user_info

        token = auth_header[7:]

        # Get full token payload / 获取完整的 token payload
        payload = await get_token_payload(token, TOKEN_TYPE_ACCESS)
        if payload is None:
            return user_info

        token_scope = payload.get("scope")
        user_id = payload.get("sub")
        tenant_id = payload.get("tenant_id")
        impersonated_by = payload.get(
            "impersonated_by"
        )  # Impersonation flag / 一键登录标记

        if not user_id:
            return user_info

        # Admin impersonating tenant case / 平台管理员一键登录企业的情况：
        # token scope is tenant_admin, but has impersonated_by flag
        # Should be recorded as platform admin's operation / 记录为平台管理员的操作
        if impersonated_by is not None:
            user_info["user_type"] = UserTypeEnum.ADMIN.value
            user_info["user_id"] = int(
                impersonated_by
            )  # Use real platform admin ID / 使用真实的平台管理员 ID
            user_info["tenant_id"] = (
                None  # Platform logs not associated with tenant / 平台端日志不关联企业
            )
            return user_info

        # Determine user type by scope / 根据 scope 判断用户类型
        if token_scope == TOKEN_SCOPE_ADMIN:
            user_info["user_type"] = UserTypeEnum.ADMIN.value
            user_info["user_id"] = int(user_id)
        elif token_scope == TOKEN_SCOPE_TENANT_ADMIN:
            user_info["user_type"] = UserTypeEnum.TENANT_ADMIN.value
            user_info["user_id"] = int(user_id)
            user_info["tenant_id"] = tenant_id
        elif token_scope == TOKEN_SCOPE_TENANT_USER:
            user_info["user_type"] = UserTypeEnum.TENANT_USER.value
            user_info["user_id"] = int(user_id)
            user_info["tenant_id"] = tenant_id

        return user_info

    async def _write_log(
        self,
        scope: Scope,
        request_info: dict[str, Any],
        response_info: dict[str, Any],
        duration_ms: int,
    ) -> None:
        """
        Write log asynchronously / 异步写入日志

        Args:
            scope: ASGI scope
            request_info: Request info / 请求信息
            response_info: Response info / 响应信息
            duration_ms: Request duration / 请求耗时
        """
        from app.services.system.operation_log_service import create_log_async

        # Get user info / 获取用户信息
        user_info = await self._get_user_info(scope)

        # Get username and nickname / 获取用户名和昵称
        username = user_info.get("username")
        nickname = user_info.get("nickname")

        # Get trace_id from scope state (injected by TraceIdMiddleware)
        # 从 scope state 获取 trace_id（由 TraceIdMiddleware 注入）
        trace_id = ""
        if "state" in scope:
            state = scope["state"]
            trace_id = getattr(state, "trace_id", "") or ""

        # If user_id exists, prefer from scope state (injected by PermissionMiddleware) / 优先从 scope state 获取
        if user_info.get("user_id") and "state" in scope:
            state = scope["state"]
            user = getattr(state, "user", None)
            state_user_id = getattr(user, "id", None) if user else None
            state_tenant_id = getattr(user, "tenant_id", None) if user else None
            expected_tenant_id = user_info.get("tenant_id")
            same_actor = bool(
                user
                and state_user_id == user_info.get("user_id")
                and (
                    (
                        expected_tenant_id is None
                        and state_tenant_id in {None, 0}
                    )
                    or state_tenant_id == expected_tenant_id
                )
            )
            if same_actor:
                if not username and hasattr(user, "username"):
                    username = user.username
                if not nickname and hasattr(user, "nickname"):
                    nickname = user.nickname

        # Extract permission info from route (module, action, resource) / 从路由提取权限信息
        path = request_info.get("path", "")
        method = request_info.get("method", "")
        module, action, resource = extract_permission_from_route(scope)

        # Check special action types (e.g. login, logout) / 检查特殊操作类型
        special_action = get_special_action(path)
        if special_action:
            action = special_action
            # Rebuild resource for special actions / 特殊操作重新构建 resource
            if module:
                resource = f"{module}:{action}"

        # If action not found, use HTTP method mapping as fallback / 未获取到 action 时使用 HTTP 方法映射
        if not action:
            action = METHOD_ACTION_MAP.get(method, "other")

        # Async write / 异步写入
        create_log_async(
            trace_id=trace_id or None,
            tenant_id=user_info.get("tenant_id"),
            user_type=user_info.get("user_type", UserTypeEnum.ANONYMOUS.value),
            user_id=user_info.get("user_id"),
            username=username,
            nickname=nickname,
            module=module,
            action=action,
            resource=resource,
            method=method,
            path=path,
            query_params=request_info.get("query_params"),
            request_body=request_info.get("request_body"),
            status_code=response_info.get("status_code"),
            response_code=response_info.get("response_code"),
            response_message=response_info.get("response_message"),
            ip=request_info.get("ip"),
            user_agent=request_info.get("user_agent"),
            duration_ms=duration_ms,
        )


__all__ = ["AuditLogMiddleware"]
