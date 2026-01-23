"""
审计日志中间件

拦截所有 API 请求，记录操作日志到数据库
"""

import json
import time
import re
from typing import Any

from starlette.types import ASGIApp, Receive, Scope, Send, Message
from starlette.requests import Request
from starlette.datastructures import Headers

from app.core.config import settings
from app.core.security import (
    get_token_payload,
    TOKEN_TYPE_ACCESS,
    TOKEN_SCOPE_ADMIN,
    TOKEN_SCOPE_TENANT_ADMIN,
    TOKEN_SCOPE_TENANT_USER,
)
from app.enums.log import UserTypeEnum


# 不记录日志的路径前缀
EXCLUDED_PATHS = [
    "/health",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/favicon.ico",
]

# 不记录日志的路径正则
EXCLUDED_PATTERNS = [
    re.compile(r"^/static/"),
    re.compile(r"^/assets/"),
]

# 敏感字段（需要脱敏）
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

# HTTP 方法到操作类型的映射（仅作为回退）
METHOD_ACTION_MAP = {
    "GET": "query",
    "POST": "create",
    "PUT": "update",
    "PATCH": "update",
    "DELETE": "delete",
}

# 特殊路径的操作类型映射
SPECIAL_PATH_ACTIONS = {
    "/auth/login": "login",
    "/auth/logout": "logout",
    "/export": "export",
    "/import": "import",
}


def should_log_request(path: str, method: str) -> bool:
    """
    判断是否应该记录该请求
    
    Args:
        path: 请求路径
        method: HTTP 方法
    
    Returns:
        是否记录
    """
    # OPTIONS 请求不记录
    if method == "OPTIONS":
        return False
    
    # 排除的路径前缀
    for excluded in EXCLUDED_PATHS:
        if path.startswith(excluded):
            return False
    
    # 排除的路径正则
    for pattern in EXCLUDED_PATTERNS:
        if pattern.match(path):
            return False
    
    return True


def sanitize_body(body: dict | list | Any) -> dict | list | Any:
    """
    脱敏请求体中的敏感字段
    
    Args:
        body: 原始请求体
    
    Returns:
        脱敏后的请求体
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


def extract_permission_from_route(scope: Scope) -> tuple[str | None, str | None, str | None]:
    """
    从 FastAPI 路由提取权限信息
    
    通过匹配当前请求的路由，获取权限装饰器定义的 resource 和 action
    
    Args:
        scope: ASGI scope
    
    Returns:
        (module, action, resource) 元组
        - module: 业务模块（如 organization, tenant）
        - action: 操作类型（如 create, update）
        - resource: 完整权限码（如 organization:create）
    """
    from starlette.routing import Match
    
    app = scope.get("app")
    if not app:
        return None, None, None
    
    # 遍历路由匹配
    for route in getattr(app, "routes", []):
        match, child_scope = route.matches(scope)
        if match == Match.FULL:
            endpoint = getattr(route, "endpoint", None)
            if endpoint:
                # 获取权限装饰器定义的信息
                permission_resource = getattr(endpoint, "_permission_resource", None)
                permission_action = getattr(endpoint, "_permission_action", None)
                
                if permission_resource and permission_action:
                    action = permission_action.get("action") if isinstance(permission_action, dict) else None
                    resource_code = f"{permission_resource}:{action}" if action else None
                    return permission_resource, action, resource_code
    
    return None, None, None


def get_special_action(path: str) -> str | None:
    """
    检查路径是否匹配特殊操作类型
    
    Args:
        path: 请求路径
    
    Returns:
        特殊操作类型或 None
    """
    for pattern, action in SPECIAL_PATH_ACTIONS.items():
        if pattern in path:
            return action
    return None


def get_client_ip(scope: Scope) -> str | None:
    """
    获取客户端真实 IP
    
    支持代理服务器的 X-Forwarded-For 头
    """
    headers = Headers(scope=scope)
    
    # 优先从 X-Forwarded-For 获取
    x_forwarded_for = headers.get("x-forwarded-for")
    if x_forwarded_for:
        # 取第一个 IP（客户端真实 IP）
        return x_forwarded_for.split(",")[0].strip()
    
    # 从 X-Real-IP 获取
    x_real_ip = headers.get("x-real-ip")
    if x_real_ip:
        return x_real_ip
    
    # 从 ASGI scope 获取
    client = scope.get("client")
    if client:
        return client[0]
    
    return None


class AuditLogMiddleware:
    """
    审计日志中间件（ASGI 实现）
    
    功能：
    1. 拦截所有 API 请求
    2. 记录请求/响应信息
    3. 从 Token 解析用户信息
    4. 请求体脱敏处理
    5. 异步写入数据库（不阻塞请求）
    """
    
    def __init__(self, app: ASGIApp) -> None:
        self.app = app
    
    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        # 确保 scope 中有 state（供后续中间件使用）
        if "state" not in scope:
            from starlette.datastructures import State
            scope["state"] = State()
        
        # 获取请求信息
        path = scope.get("path", "")
        method = scope.get("method", "")
        
        # 判断是否需要记录
        if not should_log_request(path, method):
            await self.app(scope, receive, send)
            return
        
        # 记录开始时间
        start_time = time.time()
        
        # 收集请求信息
        request_info = await self._collect_request_info(scope, receive)
        
        # 用于收集响应信息
        response_info: dict[str, Any] = {
            "status_code": None,
            "response_code": None,
            "response_message": None,
        }
        
        # 包装 receive 以允许多次读取请求体
        body_parts: list[bytes] = request_info.get("_body_parts", [])
        body_index = 0
        
        async def wrapped_receive() -> Message:
            nonlocal body_index
            if body_parts and body_index < len(body_parts):
                chunk = body_parts[body_index]
                body_index += 1
                return {
                    "type": "http.request",
                    "body": chunk,
                    "more_body": body_index < len(body_parts),
                }
            return await receive()
        
        # 包装 send 以捕获响应信息
        async def wrapped_send(message: Message) -> None:
            if message["type"] == "http.response.start":
                response_info["status_code"] = message.get("status")
            elif message["type"] == "http.response.body":
                # 尝试从响应体提取业务响应码
                body = message.get("body", b"")
                if body and response_info.get("status_code") == 200:
                    try:
                        response_data = json.loads(body)
                        response_info["response_code"] = response_data.get("code")
                        response_info["response_message"] = response_data.get("message")
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        pass
            await send(message)
        
        # 执行请求
        try:
            await self.app(scope, wrapped_receive, wrapped_send)
        finally:
            # 计算耗时
            duration_ms = int((time.time() - start_time) * 1000)
            
            # 异步记录日志
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
        收集请求信息
        
        Args:
            scope: ASGI scope
            receive: ASGI receive
        
        Returns:
            请求信息字典
        """
        headers = Headers(scope=scope)
        
        # 基础信息
        info: dict[str, Any] = {
            "method": scope.get("method", ""),
            "path": scope.get("path", ""),
            "query_string": scope.get("query_string", b"").decode("utf-8", errors="ignore"),
            "ip": get_client_ip(scope),
            "user_agent": headers.get("user-agent"),
        }
        
        # 解析查询参数
        if info["query_string"]:
            from urllib.parse import parse_qs
            info["query_params"] = parse_qs(info["query_string"])
        else:
            info["query_params"] = None
        
        # 收集请求体（仅对 POST/PUT/PATCH）
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
            
            # 解析并脱敏请求体
            if body:
                try:
                    content_type = headers.get("content-type", "")
                    if "application/json" in content_type:
                        body_data = json.loads(body)
                        info["request_body"] = sanitize_body(body_data)
                    else:
                        # 非 JSON 请求体，仅记录大小
                        info["request_body"] = {"_size": len(body), "_type": content_type}
                except (json.JSONDecodeError, UnicodeDecodeError):
                    info["request_body"] = {"_size": len(body), "_error": "parse_failed"}
        
        info["_body_parts"] = body_parts
        return info
    
    def _get_user_info(self, scope: Scope) -> dict[str, Any]:
        """
        从 scope 获取用户信息
        
        优先从 PermissionMiddleware 注入的 state 获取，
        否则尝试从 Token 解析
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
        
        # 获取完整的 token payload
        payload = get_token_payload(token, TOKEN_TYPE_ACCESS)
        if payload is None:
            return user_info
        
        token_scope = payload.get("scope")
        user_id = payload.get("sub")
        tenant_id = payload.get("tenant_id")
        impersonated_by = payload.get("impersonated_by")  # 一键登录标记
        
        if not user_id:
            return user_info
        
        # 平台管理员一键登录租户的情况：
        # token scope 是 tenant_admin，但有 impersonated_by 标记
        # 这种情况应该记录为平台管理员的操作
        if impersonated_by is not None:
            user_info["user_type"] = UserTypeEnum.ADMIN.value
            user_info["user_id"] = int(impersonated_by)  # 使用真实的平台管理员 ID
            user_info["tenant_id"] = None  # 平台端日志不关联租户
            return user_info
        
        # 根据 scope 判断用户类型
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
        异步写入日志
        
        Args:
            scope: ASGI scope
            request_info: 请求信息
            response_info: 响应信息
            duration_ms: 请求耗时
        """
        from app.services.system.operation_log_service import create_log_async
        
        # 获取用户信息
        user_info = self._get_user_info(scope)
        
        # 获取用户名和昵称
        username = user_info.get("username")
        nickname = user_info.get("nickname")
        
        # 如果有 user_id，优先从 scope state 获取（由 PermissionMiddleware 注入）
        if user_info.get("user_id") and "state" in scope:
            state = scope["state"]
            user = getattr(state, "user", None)
            if user:
                if not username and hasattr(user, "username"):
                    username = user.username
                if not nickname and hasattr(user, "nickname"):
                    nickname = user.nickname
        
        # 从路由提取权限信息（module, action, resource）
        path = request_info.get("path", "")
        method = request_info.get("method", "")
        module, action, resource = extract_permission_from_route(scope)
        
        # 检查特殊操作类型（如 login, logout）
        special_action = get_special_action(path)
        if special_action:
            action = special_action
            # 特殊操作重新构建 resource
            if module:
                resource = f"{module}:{action}"
        
        # 如果未获取到 action，使用 HTTP 方法映射作为回退
        if not action:
            action = METHOD_ACTION_MAP.get(method, "other")
        
        # 异步写入
        create_log_async(
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
