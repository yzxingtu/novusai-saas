"""
访问控制中间件

实施"默认拒绝"安全策略：
- 所有 API 端点默认需要认证和权限声明
- 必须显式使用 @public、@auth_only 或 @action_* 装饰器标记访问级别
- 未标记的端点将返回 403 错误

这确保开发者不会因遗漏装饰器而导致 API 被无权限访问。
"""

from starlette.types import ASGIApp, Receive, Scope, Send
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Match

from app.core.i18n import _
from app.rbac.decorators import (
    ACCESS_PUBLIC,
    ACCESS_AUTH_ONLY,
    ACCESS_PERMISSION,
)


# 豁免路径前缀（这些路径不受访问控制限制）
# 主要用于 FastAPI 内置路由和静态文件
EXEMPT_PATH_PREFIXES = (
    "/docs",
    "/redoc",
    "/openapi.json",
    "/health",
    "/plugin-assets",
    "/",  # 根路径健康检查
)


class AccessControlMiddleware:
    """
    访问控制中间件
    
    安全策略：
    1. 检查路由端点是否有 _access_level 标记
    2. 未标记的端点默认拒绝访问（403）
    3. 标记为 @public 的端点无需认证
    4. 标记为 @auth_only 的端点只需认证
    5. 标记为 @action_* 的端点需要认证和权限检查
    
    注意：此中间件在 PermissionMiddleware 之后执行
    """
    
    def __init__(self, app: ASGIApp) -> None:
        self.app = app
        self._app_instance = None
    
    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        # 获取请求路径
        path = scope.get("path", "")
        
        # 豁免路径直接放行
        if self._is_exempt_path(path):
            await self.app(scope, receive, send)
            return
        
        # 获取 FastAPI 应用实例（用于路由匹配）
        app_instance = self._get_app_instance()
        if app_instance is None:
            await self.app(scope, receive, send)
            return
        
        # 尝试匹配路由
        endpoint = self._find_endpoint(app_instance, scope)
        
        if endpoint is None:
            # 未找到路由，让 FastAPI 处理 404
            await self.app(scope, receive, send)
            return
        
        # 检查端点的访问级别标记
        access_level = getattr(endpoint, "_access_level", None)
        
        if access_level is None:
            # 未标记访问级别 -> 默认拒绝
            response = JSONResponse(
                status_code=403,
                content={
                    "code": 4030,
                    "message": _("rbac.endpoint_not_declared"),
                    "data": None,
                },
            )
            await response(scope, receive, send)
            return
        
        # 已标记访问级别，继续处理
        # PUBLIC: 无需认证，直接放行
        # AUTH_ONLY: 认证由 FastAPI 依赖处理
        # PERMISSION: 认证和权限由 FastAPI 依赖和装饰器处理
        await self.app(scope, receive, send)
    
    def _is_exempt_path(self, path: str) -> bool:
        """检查路径是否在豁免列表中"""
        # 精确匹配根路径
        if path == "/":
            return True
        # 前缀匹配
        for prefix in EXEMPT_PATH_PREFIXES:
            if prefix != "/" and path.startswith(prefix):
                return True
        return False
    
    def _get_app_instance(self):
        """获取 FastAPI 应用实例"""
        if self._app_instance is not None:
            return self._app_instance
        
        # 遍历中间件栈找到 FastAPI 应用
        app = self.app
        while hasattr(app, "app"):
            app = app.app
            if hasattr(app, "routes"):
                self._app_instance = app
                return app
        
        return None
    
    def _find_endpoint(self, app, scope: Scope):
        """查找匹配的端点函数"""
        # 遍历所有路由尝试匹配
        for route in app.routes:
            match, child_scope = route.matches(scope)
            if match == Match.FULL:
                # 获取端点函数
                endpoint = getattr(route, "endpoint", None)
                return endpoint
        
        return None
