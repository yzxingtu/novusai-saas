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
    verify_token_with_scope,
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

# HTTP 方法到操作类型的映射
METHOD_ACTION_MAP = {
    "GET": "query",
    "POST": "create",
    "PUT": "update",
    "PATCH": "update",
    "DELETE": "delete",
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


def extract_module_from_path(path: str) -> str | None:
    """
    从路径提取业务模块
    
    Args:
        path: 请求路径，如 /admin/admins/1
    
    Returns:
        模块名，如 admin_user
    """
    # 路径到模块的映射
    path_module_map = {
        "/admin/auth": "auth",
        "/admin/permissions": "permission",
        "/admin/roles": "role",
        "/admin/admins": "admin_user",
        "/admin/tenants": "tenant",
        "/admin/tenant-domains": "domain",
        "/admin/configs": "config",
        "/admin/plans": "plan",
        "/admin/operation-logs": "log",
        "/admin/system-logs": "log",
        "/tenant/auth": "auth",
        "/tenant/permissions": "permission",
        "/tenant/roles": "role",
        "/tenant/admins": "tenant_admin",
        "/tenant/users": "tenant_user",
        "/tenant/configs": "config",
        "/tenant/operation-logs": "log",
        "/api/v1/auth": "auth",
    }
    
    for prefix, module in path_module_map.items():
        if path.startswith(prefix):
            return module
    
    return "other"


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
        }
        
        if not auth_header.startswith("Bearer "):
            return user_info
        
        token = auth_header[7:]
        
        # 尝试验证为平台管理员
        user_id, extra = verify_token_with_scope(
            token, TOKEN_SCOPE_ADMIN, TOKEN_TYPE_ACCESS
        )
        if user_id:
            user_info["user_type"] = UserTypeEnum.ADMIN.value
            user_info["user_id"] = int(user_id)
            return user_info
        
        # 尝试验证为租户管理员
        user_id, extra = verify_token_with_scope(
            token, TOKEN_SCOPE_TENANT_ADMIN, TOKEN_TYPE_ACCESS
        )
        if user_id:
            user_info["user_type"] = UserTypeEnum.TENANT_ADMIN.value
            user_info["user_id"] = int(user_id)
            if extra and "tenant_id" in extra:
                user_info["tenant_id"] = extra["tenant_id"]
            return user_info
        
        # 尝试验证为租户用户
        user_id, extra = verify_token_with_scope(
            token, TOKEN_SCOPE_TENANT_USER, TOKEN_TYPE_ACCESS
        )
        if user_id:
            user_info["user_type"] = UserTypeEnum.TENANT_USER.value
            user_info["user_id"] = int(user_id)
            if extra and "tenant_id" in extra:
                user_info["tenant_id"] = extra["tenant_id"]
            return user_info
        
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
        
        # 获取用户名
        username = user_info.get("username")
        
        # 如果有 user_id，优先从 scope state 获取（由 PermissionMiddleware 注入）
        if not username and user_info.get("user_id"):
            if "state" in scope:
                state = scope["state"]
                user = getattr(state, "user", None)
                if user and hasattr(user, "username"):
                    username = user.username
        
        # 提取模块和操作类型
        path = request_info.get("path", "")
        method = request_info.get("method", "")
        module = extract_module_from_path(path)
        action = METHOD_ACTION_MAP.get(method, "other")
        
        # 特殊操作类型判断
        if "/auth/login" in path:
            action = "login"
        elif "/auth/logout" in path:
            action = "logout"
        elif "/export" in path:
            action = "export"
        elif "/import" in path:
            action = "import"
        
        # 构建资源标识
        resource = f"{module}:{action}" if module else None
        
        # 异步写入
        create_log_async(
            tenant_id=user_info.get("tenant_id"),
            user_type=user_info.get("user_type", UserTypeEnum.ANONYMOUS.value),
            user_id=user_info.get("user_id"),
            username=username,
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
