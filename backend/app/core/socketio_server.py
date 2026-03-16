"""
Socket.IO 服务器单例 / Socket.IO Server Singleton

提供全局 AsyncServer 实例，使用 AsyncRedisManager 支持多 Worker 部署。
Provides global AsyncServer instance, using AsyncRedisManager for multi-worker deployment.
通过 ASGI 模式与 FastAPI 集成。
Integrated with FastAPI via ASGI mode.
"""

import socketio

from app.core.config import settings
from app.core.logging import LogManager

logger = LogManager.get_logger("app")

# ========================================
# Redis Manager（多 Worker 消息同步 / Multi-worker message sync）
# ========================================

_redis_manager = socketio.AsyncRedisManager(
    settings.REDIS_URL,
    write_only=False,
)

# ========================================
# AsyncServer 实例
# ========================================

# Allow all origins for multi-tenant SaaS (subdomain + custom domains are dynamic)
# 多租户 SaaS 允许所有 Origin（子域名 + 自定义域名是动态的）
sio = socketio.AsyncServer(
    async_mode="asgi",
    client_manager=_redis_manager,
    cors_allowed_origins="*",
    ping_interval=25,
    ping_timeout=20,
    logger=False,
    engineio_logger=False,
)

logger.info("Socket.IO AsyncServer created with Redis manager")


def get_sio() -> socketio.AsyncServer:
    """获取全局 Socket.IO 服务器实例 / Get global Socket.IO server instance"""
    return sio


async def apply_ws_config() -> None:
    """
    从平台配置读取 WS 参数并应用到 AsyncServer
    Read WS params from platform config and apply to AsyncServer.

    在 lifespan startup（DB + Redis 初始化之后）调用。
    Called during lifespan startup (after DB + Redis initialization).
    修改 engine.io 的 ping_interval / ping_timeout 属性，
    对新建连接生效（已有连接保持旧值）。
    Modifies engine.io ping_interval/ping_timeout; takes effect for new connections only.
    """
    try:
        from app.sio.ws_config import get_ws_configs

        cfg = await get_ws_configs(
            "ws_enabled", "ws_ping_interval", "ws_ping_timeout",
        )

        ping_interval = cfg.get("ws_ping_interval", 25)
        ping_timeout = cfg.get("ws_ping_timeout", 20)

        # 更新 engine.io 属性（对新连接生效） / Update engine.io attributes (effective for new connections)
        if hasattr(sio, "eio"):
            sio.eio.ping_interval = int(ping_interval)
            sio.eio.ping_timeout = int(ping_timeout)

        ws_enabled = cfg.get("ws_enabled", True)
        logger.info(
            "Socket.IO config applied: enabled={} ping_interval={} ping_timeout={}",
            ws_enabled, ping_interval, ping_timeout,
        )
    except Exception as e:
        logger.warning("Failed to apply WS config: {}", e)
