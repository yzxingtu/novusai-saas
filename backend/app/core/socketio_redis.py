"""
Socket.IO Redis connection options / Socket.IO Redis 连接参数。

These settings are intentionally scoped to Socket.IO managers. The regular
Redis client keeps its request-oriented timeout behavior.
"""

SOCKETIO_REDIS_CONNECT_TIMEOUT_SECONDS = 5


def get_socketio_redis_listener_options() -> dict[str, object]:
    """Options for the API-side long-running Pub/Sub listener."""
    return {
        "socket_connect_timeout": SOCKETIO_REDIS_CONNECT_TIMEOUT_SECONDS,
        "socket_timeout": None,
        "socket_keepalive": True,
    }


def get_socketio_redis_publisher_options() -> dict[str, object]:
    """Options for write-only Pub/Sub publishers such as Celery workers."""
    return {
        "socket_connect_timeout": SOCKETIO_REDIS_CONNECT_TIMEOUT_SECONDS,
        "socket_keepalive": True,
    }
