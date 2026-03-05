"""
维护模式中间件

当平台开启维护模式时，拦截非管理员请求返回 503。
管理员端（/admin/*）不受影响，确保管理员可以正常操作。

配置项：
- maintenance_mode: bool — 维护模式开关
- maintenance_message: str — 维护提示信息
"""

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

# 豁免路径：维护模式下仍可访问
_EXEMPT_PREFIXES = (
    "/admin",          # 管理端（管理员需要正常操作）
    "/api/public",     # 公开 API（获取维护状态等）
    "/docs",           # API 文档
    "/redoc",
    "/openapi.json",
    "/health",         # 健康检查
    "/sio",            # Socket.IO（管理员连接）
    "/files",          # 静态文件
)


class MaintenanceMiddleware:
    """
    维护模式中间件

    读取平台配置 maintenance_mode，开启时：
    - /admin/* 和 /api/public/* 正常放行
    - 其他请求返回 503 + maintenance_message
    - 使用 Redis 缓存减少 DB 查询
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path: str = scope.get("path", "")

        # 豁免路径直接放行
        for prefix in _EXEMPT_PREFIXES:
            if path == prefix or path.startswith(prefix + "/"):
                await self.app(scope, receive, send)
                return

        # 检查维护模式
        if await self._is_maintenance_mode():
            message = await self._get_maintenance_message()
            response = JSONResponse(
                status_code=503,
                content={
                    "code": 5030,
                    "message": message,
                    "data": {"maintenance": True},
                },
            )
            await response(scope, receive, send)
            return

        await self.app(scope, receive, send)

    @staticmethod
    async def _is_maintenance_mode() -> bool:
        """从 Redis 缓存或 DB 读取维护模式开关"""
        try:
            from app.core.redis import get_redis_client
            redis = get_redis_client()
            cached = await redis.get("maintenance:mode")
            if cached is not None:
                return cached == "1"
        except Exception:
            pass

        # Redis miss → 从 DB 读取
        try:
            from app.configs.service import ConfigService
            from app.core.database import async_session_factory

            async with async_session_factory() as db:
                service = ConfigService(db)
                value = await service.get_platform_value("maintenance_mode")

            result = bool(value) if value is not None else False

            # 写入缓存（60 秒 TTL，维护模式变更最多 1 分钟生效）
            try:
                redis = get_redis_client()
                await redis.set("maintenance:mode", "1" if result else "0", ex=60)
            except Exception:
                pass

            return result
        except Exception:
            return False

    @staticmethod
    async def _get_maintenance_message() -> str:
        """获取维护提示信息"""
        try:
            from app.core.redis import get_redis_client
            redis = get_redis_client()
            cached = await redis.get("maintenance:message")
            if cached:
                return cached
        except Exception:
            pass

        try:
            from app.configs.service import ConfigService
            from app.core.database import async_session_factory

            async with async_session_factory() as db:
                service = ConfigService(db)
                message = await service.get_platform_value("maintenance_message")

            result = str(message) if message else "System is under maintenance. Please try again later."

            try:
                redis = get_redis_client()
                await redis.set("maintenance:message", result, ex=60)
            except Exception:
                pass

            return result
        except Exception:
            return "System is under maintenance. Please try again later."


__all__ = ["MaintenanceMiddleware"]
