"""
Access Control Middleware / 访问控制中间件

Implements "deny by default" security policy / 实施"默认拒绝"安全策略：
- All API endpoints require auth and permission declaration by default / 所有端点默认需要认证和权限声明
- Must explicitly use @public, @auth_only or @action_* decorators / 必须显式标记访问级别
- Unmarked endpoints return 403 / 未标记的端点返回 403

Ensures developers don't accidentally expose APIs without permissions.
确保开发者不会因遗漏装饰器而导致 API 被无权限访问。
"""

from starlette.routing import Match
from starlette.types import ASGIApp, Receive, Scope, Send

from app.core.i18n import _
from app.core.response import error

# Exempt path prefixes (not subject to access control) / 豁免路径前缀
# Mainly for FastAPI built-in routes and static files / 主要用于内置路由和静态文件
EXEMPT_PATH_PREFIXES = (
    "/docs",
    "/redoc",
    "/openapi.json",
    "/health",
    "/ready",
    "/plugin-public-assets",
    "/plugin-assets",
    "/plugin-icons",
    "/",  # Root path health check / 根路径健康检查
)


class AccessControlMiddleware:
    """
    Access Control Middleware.
    访问控制中间件。

    Security policy / 安全策略：
    1. Check if route endpoint has _access_level mark / 检查路由端点是否有 _access_level 标记
    2. Unmarked endpoints denied by default (403) / 未标记的端点默认拒绝
    3. @public endpoints need no auth / 无需认证
    4. @auth_only endpoints need auth only / 只需认证
    5. @action_* endpoints need auth + permission check / 需要认证和权限检查

    Note: runs after PermissionMiddleware / 注意：在 PermissionMiddleware 之后执行
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app
        self._app_instance = None

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Get request path / 获取请求路径
        path = scope.get("path", "")

        # Exempt paths pass through / 豁免路径直接放行
        if self._is_exempt_path(path):
            await self.app(scope, receive, send)
            return

        # Get FastAPI app instance (for route matching) / 获取 FastAPI 应用实例
        app_instance = self._get_app_instance()
        if app_instance is None:
            await self.app(scope, receive, send)
            return

        # Try to match route / 尝试匹配路由
        endpoint = self._find_endpoint(app_instance, scope)

        if endpoint is None:
            # Route not found, let FastAPI handle 404 / 未找到路由
            await self.app(scope, receive, send)
            return

        # Check endpoint access level mark / 检查端点的访问级别标记
        access_level = getattr(endpoint, "_access_level", None)

        if access_level is None:
            # No access level mark -> deny by default / 未标记 -> 默认拒绝
            response = error(
                message=_("rbac.endpoint_not_declared"),
                code=4030,
                status_code=403,
            )
            await response(scope, receive, send)
            return

        # Access level marked, continue processing / 已标记访问级别，继续处理
        # PUBLIC: no auth needed / 无需认证
        # AUTH_ONLY: auth handled by FastAPI deps / 认证由 FastAPI 依赖处理
        # PERMISSION: auth + permission handled by deps & decorators / 认证和权限由依赖和装饰器处理
        await self.app(scope, receive, send)

    def _is_exempt_path(self, path: str) -> bool:
        """Check if path is in exempt list / 检查路径是否在豁免列表中"""
        # Exact match root path / 精确匹配根路径
        if path == "/":
            return True
        # Prefix match / 前缀匹配
        for prefix in EXEMPT_PATH_PREFIXES:
            if prefix != "/" and path.startswith(prefix):
                return True
        return False

    def _get_app_instance(self):
        """Get FastAPI app instance / 获取 FastAPI 应用实例"""
        if self._app_instance is not None:
            return self._app_instance

        # Traverse middleware stack to find FastAPI app / 遍历中间件栈找到 FastAPI 应用
        app = self.app
        while hasattr(app, "app"):
            app = app.app
            if hasattr(app, "routes"):
                self._app_instance = app
                return app

        return None

    def _find_endpoint(self, app, scope: Scope):
        """Find matching endpoint function / 查找匹配的端点函数"""
        # Iterate all routes to find match / 遍历所有路由尝试匹配
        for route in app.routes:
            match, child_scope = route.matches(scope)
            if match == Match.FULL:
                # Get endpoint function / 获取端点函数
                endpoint = getattr(route, "endpoint", None)
                return endpoint

        return None
