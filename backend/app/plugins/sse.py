"""
Plugin SSE streaming response utility. / 插件 SSE 流式响应工具。

Provides reusable StreamingResponse generator templates for plugin API handlers
to reuse directly, avoiding each plugin re-implementing SSE encapsulation.
/ 提供可复用的 StreamingResponse 生成器模板，供插件 API handler 直接复用。
"""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import AsyncGenerator
from typing import Any

from fastapi.responses import StreamingResponse

from app.core.logging import get_logger

logger = get_logger(__name__)

# Heartbeat interval (seconds) — prevent reverse proxy timeout disconnect
# / 心跳间隔
_HEARTBEAT_INTERVAL = 15.0

# SSE heartbeat comment (not treated as event by client EventSource)
# / SSE 心跳注释
_HEARTBEAT_LINE = ":heartbeat\n\n"


def plugin_sse_response(
    generator: AsyncGenerator[str, None],
    *,
    heartbeat: bool = True,
    plugin_name: str = "",
) -> StreamingResponse:
    """
    Wrap plugin text delta generator as standard SSE StreamingResponse.
    / 将插件文本增量生成器包装为标准 SSE StreamingResponse。

    SSE protocol:
    - Each text chunk → ``data: {"event":"message","delta":"..."}\n\n``
    - Stream end → ``data: {"event":"done"}\n\n`` + ``data: [DONE]\n\n``
    - Exception → ``data: {"error":true,"message":"..."}\n\n`` + ``data: [DONE]\n\n``
    - Heartbeat → ``:heartbeat\n\n`` (every 15s, prevent Nginx/ALB timeout)
    / SSE 协议说明

    Usage example (plugin API handler) / 用法示例::

        async def my_stream_handler(request, db, ctx):
            async def gen():
                async for delta in ctx.call_ai_feature_stream("ai_writer", messages):
                    yield delta
            return plugin_sse_response(gen(), plugin_name="my-plugin")

    Args:
        generator: Async generator, yields plain text delta strings / 异步生成器，产生纯文本增量字符串
        heartbeat: Whether to enable heartbeat (default True) / 是否启用心跳（默认 True）
        plugin_name: Plugin name (for logging only) / 插件名称（仅用于日志）

    Returns:
        FastAPI StreamingResponse (text/event-stream)
    """

    async def _sse_wrapper() -> AsyncGenerator[str, None]:
        chunk_count = 0
        start = time.perf_counter()

        try:
            if heartbeat:
                # Use anext + wait_for to implement heartbeat:
                # if generator produces nothing within _HEARTBEAT_INTERVAL, send heartbeat keepalive
                # / 使用 anext + wait_for 实现心跳保活
                gen_iter = generator.__aiter__()
                while True:
                    try:
                        delta = await asyncio.wait_for(
                            gen_iter.__anext__(),
                            timeout=_HEARTBEAT_INTERVAL,
                        )
                        if delta:
                            chunk_count += 1
                            yield _encode({"event": "message", "delta": delta})
                    except asyncio.TimeoutError:
                        yield _HEARTBEAT_LINE
                    except StopAsyncIteration:
                        break
            else:
                async for delta in generator:
                    if delta:
                        chunk_count += 1
                        yield _encode({"event": "message", "delta": delta})

            # Normal end / 正常结束
            yield _encode({"event": "done"})
            yield _done()

        except Exception as exc:
            logger.error(
                "Plugin SSE error (plugin=%s): %s",
                plugin_name, exc,
                exc_info=True,
            )
            try:
                yield _encode({"error": True, "message": str(exc)})
                yield _done()
            except Exception:
                pass  # Connection already closed / 连接已断开

        finally:
            latency_ms = int((time.perf_counter() - start) * 1000)
            if chunk_count > 0 or latency_ms > 100:
                logger.info(
                    "plugin_sse: plugin=%s chunks=%d latency_ms=%d heartbeat=%s",
                    plugin_name, chunk_count, latency_ms, heartbeat,
                )

    return StreamingResponse(
        _sse_wrapper(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


def _encode(data: dict[str, Any]) -> str:
    """Encode as SSE data line / 编码为 SSE data 行"""
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


def _done() -> str:
    """SSE end marker / SSE 结束标记"""
    return "data: [DONE]\n\n"


__all__ = ["plugin_sse_response"]
