"""
动态 CORS 中间件 / Dynamic CORS middleware.

为 HTTP 请求统一追加动态 Origin 头，
并对预检请求直接短路响应。
Adds dynamic Origin headers for HTTP responses and short-circuits preflight
requests with shared policy checks.
"""

from __future__ import annotations

from starlette.datastructures import Headers, MutableHeaders
from starlette.responses import Response
from starlette.types import ASGIApp, Receive, Scope, Send

from app.core.cors import get_cors_headers_for_origin, is_origin_allowed


class DynamicCORSMiddleware:
    """动态 CORS 中间件 / Dynamic CORS middleware."""

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = Headers(scope=scope)
        origin = headers.get("origin")
        requested_headers = headers.get("access-control-request-headers")
        is_preflight = (
            scope.get("method") == "OPTIONS"
            and headers.get("access-control-request-method") is not None
        )

        if is_preflight:
            if origin and await is_origin_allowed(origin):
                response = Response(status_code=204)
                response.headers.update(
                    await get_cors_headers_for_origin(
                        origin,
                        allow_headers=requested_headers,
                        preflight=True,
                    )
                )
            else:
                response = Response(status_code=400)
            await response(scope, receive, send)
            return

        cors_headers = await get_cors_headers_for_origin(origin)

        async def send_wrapper(message):
            if message["type"] == "http.response.start" and cors_headers:
                mutable_headers = MutableHeaders(scope=message)
                for key, value in cors_headers.items():
                    mutable_headers[key] = value
            await send(message)

        await self.app(scope, receive, send_wrapper)


__all__ = ["DynamicCORSMiddleware"]
