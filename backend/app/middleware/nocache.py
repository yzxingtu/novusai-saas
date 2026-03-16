"""
No-Cache API Middleware / API 禁止缓存中间件

Adds no-store to JSON responses without Cache-Control set,
preventing browser from caching GET causing stale data after save.
仅对未设置 Cache-Control 的 JSON 响应添加 no-store，
避免浏览器缓存 GET 导致保存后数据不更新。

Uses pure ASGI instead of BaseHTTPMiddleware to avoid CancelledError cascade on Ctrl+C shutdown.
使用纯 ASGI 实现，避免 Ctrl+C 关闭时 BaseHTTPMiddleware 导致的任务取消级联错误。
"""

from starlette.types import ASGIApp, Message, Receive, Scope, Send


class NoCacheAPIMiddleware:
    """
    No-Cache API Middleware (pure ASGI implementation).
    API 禁止缓存中间件（纯 ASGI 实现）
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def wrapped_send(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers_list = list(message.get("headers", []))
                has_cache_control = any(
                    h[0].lower() == b"cache-control" for h in headers_list
                )
                content_type = b""
                for h in headers_list:
                    if h[0].lower() == b"content-type":
                        content_type = h[1]
                        break
                if not has_cache_control and b"application/json" in content_type:
                    headers_list.append(
                        (b"cache-control", b"no-store, no-cache, must-revalidate")
                    )
                    headers_list.append((b"pragma", b"no-cache"))
                    message = {**message, "headers": headers_list}
            await send(message)

        await self.app(scope, receive, wrapped_send)
