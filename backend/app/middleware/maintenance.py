"""
Maintenance Mode Middleware / 维护模式中间件

Intercepts non-admin requests with 503 when maintenance mode is enabled.
当平台开启维护模式时，拦截非管理员请求返回 503。
Admin endpoints (/admin/*) are unaffected / 管理员端不受影响。

Config / 配置项：
- maintenance_mode: bool — Maintenance mode toggle / 维护模式开关
- maintenance_message: str — Maintenance message / 维护提示信息
"""

from starlette.types import ASGIApp, Receive, Scope, Send

from app.core.i18n import _
from app.core.logging import get_logger
from app.core.response import error

logger = get_logger(__name__)
_DEFAULT_MAINTENANCE_MESSAGE_KEY = "system.maintenance.default_message"

# Exempt paths: still accessible during maintenance / 豁免路径：维护模式下仍可访问
_EXEMPT_PREFIXES = (
    "/admin",  # Admin panel / 管理端
    "/api/public",  # Public API / 公开 API
    "/docs",  # API docs / API 文档
    "/redoc",
    "/openapi.json",
    "/health",  # Health check / 健康检查
    "/ready",  # Readiness (DB) / 就绪探针
    "/metrics",  # Prometheus metrics / Prometheus 指标
    "/sio",  # Socket.IO (admin connections) / Socket.IO（管理员连接）
    "/files",  # Static files / 静态文件
)


class MaintenanceMiddleware:
    """
    Maintenance Mode Middleware.
    维护模式中间件。

    Reads platform config maintenance_mode, when enabled / 读取平台配置 maintenance_mode，开启时：
    - /admin/* and /api/public/* pass through / 正常放行
    - Other requests return 503 + maintenance_message / 其他请求返回 503
    - Uses Redis cache to reduce DB queries / 使用 Redis 缓存减少 DB 查询
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path: str = scope.get("path", "")

        # Exempt paths pass through / 豁免路径直接放行
        for prefix in _EXEMPT_PREFIXES:
            if path == prefix or path.startswith(prefix + "/"):
                await self.app(scope, receive, send)
                return

        # Check maintenance mode / 检查维护模式
        if await self._is_maintenance_mode():
            message = await self._get_maintenance_message()
            response = error(
                message=message,
                code=5030,
                data={"maintenance": True},
                status_code=503,
            )
            await response(scope, receive, send)
            return

        await self.app(scope, receive, send)

    @staticmethod
    async def _is_maintenance_mode() -> bool:
        """Read maintenance mode toggle from Redis cache or DB / 从 Redis 缓存或 DB 读取维护模式开关"""
        try:
            from app.core.redis import get_redis_client

            redis = get_redis_client()
            cached = await redis.get("maintenance:mode")
            if cached is not None:
                return cached == "1"
        except Exception as exc:
            logger.debug("maintenance Redis read failed: {}", exc)

        # Redis miss → read from DB / 从 DB 读取
        try:
            from app.configs.service import ConfigService
            from app.core.database import async_session_factory

            async with async_session_factory() as db:
                service = ConfigService(db)
                value = await service.get_platform_config("maintenance_mode")

            result = bool(value) if value is not None else False

            # Write to cache (60s TTL, maintenance mode change takes effect within 1 min) / 写入缓存
            try:
                redis = get_redis_client()
                await redis.set("maintenance:mode", "1" if result else "0", ex=60)
            except Exception as exc:
                logger.debug("maintenance Redis cache write (mode) failed: {}", exc)

            return result
        except Exception as exc:
            logger.debug("maintenance mode read from DB failed: {}", exc)
            return False

    @staticmethod
    async def _get_maintenance_message() -> str:
        """Get maintenance message / 获取维护提示信息"""
        try:
            from app.core.redis import get_redis_client

            redis = get_redis_client()
            cached = await redis.get("maintenance:message")
            if cached:
                return cached
        except Exception as exc:
            logger.debug("maintenance Redis read (message) failed: {}", exc)

        try:
            from app.configs.service import ConfigService
            from app.core.database import async_session_factory

            async with async_session_factory() as db:
                service = ConfigService(db)
                message = await service.get_platform_config("maintenance_message")

            result = str(message) if message else _(_DEFAULT_MAINTENANCE_MESSAGE_KEY)

            try:
                redis = get_redis_client()
                await redis.set("maintenance:message", result, ex=60)
            except Exception as exc:
                logger.debug("maintenance Redis cache write (message) failed: {}", exc)

            return result
        except Exception as exc:
            logger.debug("maintenance message read from DB failed: {}", exc)
            return _(_DEFAULT_MAINTENANCE_MESSAGE_KEY)


__all__ = ["MaintenanceMiddleware"]
