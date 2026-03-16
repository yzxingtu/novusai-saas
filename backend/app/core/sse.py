"""
SSE (Server-Sent Events) 核心封装 / SSE Core Wrapper

提供统一的 SSE 流式响应基类，用于所有需要流式响应的场景。
Provides unified SSE streaming response base class for all streaming scenarios.
支持标准事件格式、错误处理、连接保活等功能。
Supports standard event format, error handling, connection keep-alive, etc.
"""

import asyncio
import contextlib
import json
import uuid
from collections.abc import AsyncIterator
from typing import Any

from fastapi.responses import StreamingResponse

from app.core.logging import LogManager

logger = LogManager.get_logger("app")


class SSEEvent:
    """
    SSE 事件类型 / SSE Event Types

    定义标准的事件类型常量 / Defines standard event type constants
    """

    MESSAGE = "message"  # 普通数据消息 / Normal data message
    ERROR = "error"      # 错误消息 / Error message
    DONE = "done"        # 完成标记 / Completion marker
    KEEPALIVE = "keepalive"  # 保活消息（注释行） / Keep-alive (comment line)


class SSEFormatter:
    """
    SSE 格式化器 / SSE Formatter

    将数据格式化为标准的 SSE 格式：
    Formats data into standard SSE format:
    - event: 事件类型 / Event type
    - data: JSON 数据 / JSON data
    - id: 事件 ID（可选） / Event ID (optional)

    示例 / Example:
    ```
    event: message
    data: {"text": "hello"}
    id: uuid-123

    ```
    """

    @staticmethod
    def format_event(
        event: str,
        data: Any,
        event_id: str | None = None,
    ) -> str:
        """
        格式化 SSE 事件 / Format SSE event

        Args:
            event: 事件类型（message/error/done） / Event type
            data: 事件数据（字典或字符串） / Event data (dict or string)
            event_id: 事件 ID（可选） / Event ID (optional)

        Returns:
            格式化后的 SSE 字符串 / Formatted SSE string
        """
        lines = []

        # 添加 event 行 / Add event line
        if event:
            lines.append(f"event: {event}")

        # 添加 data 行 / Add data line
        if isinstance(data, str):
            # 字符串直接使用 / Use string directly
            lines.append(f"data: {data}")
        elif isinstance(data, dict):
            # 字典转 JSON / Convert dict to JSON
            json_str = json.dumps(data, ensure_ascii=False)
            lines.append(f"data: {json_str}")
        else:
            # 其他类型转字符串 / Convert other types to string
            lines.append(f"data: {str(data)}")

        # 添加 id 行（可选） / Add id line (optional)
        if event_id:
            lines.append(f"id: {event_id}")

        # 添加空行表示事件结束 / Add empty line to mark event end
        lines.append("")

        return "\n".join(lines) + "\n"

    @staticmethod
    def format_message(data: dict, event_id: str | None = None) -> str:
        """
        格式化消息事件 / Format message event

        Args:
            data: 消息数据 / Message data
            event_id: 事件 ID / Event ID

        Returns:
            SSE 格式字符串 / SSE formatted string
        """
        return SSEFormatter.format_event(
            event=SSEEvent.MESSAGE,
            data=data,
            event_id=event_id,
        )

    @staticmethod
    def format_error(
        code: str,
        message: str,
        event_id: str | None = None,
    ) -> str:
        """
        格式化错误事件 / Format error event

        Args:
            code: 错误码 / Error code
            message: 错误消息 / Error message
            event_id: 事件 ID / Event ID

        Returns:
            SSE 格式字符串 / SSE formatted string
        """
        error_data = {
            "error": True,
            "code": code,
            "message": message,
        }
        return SSEFormatter.format_event(
            event=SSEEvent.ERROR,
            data=error_data,
            event_id=event_id,
        )

    @staticmethod
    def format_done() -> str:
        """
        格式化完成标记 / Format completion marker

        Returns:
            SSE 格式字符串 / SSE formatted string
        """
        return SSEFormatter.format_event(
            event=SSEEvent.DONE,
            data="[DONE]",
        )

    @staticmethod
    def format_keepalive() -> str:
        """
        格式化保活消息（注释行） / Format keep-alive message (comment line)

        注释行格式 / Comment line format: : keepalive

        Returns:
            SSE 格式字符串 / SSE formatted string
        """
        return ": keepalive\n\n"


async def _keepalive_sender(
    interval_seconds: int = 15,
) -> AsyncIterator[str]:
    """
    保活消息发送器 / Keep-alive message sender

    定期发送注释行以保持连接活跃 / Periodically sends comment lines to keep connection alive

    Args:
        interval_seconds: 发送间隔（秒） / Send interval (seconds)

    Yields:
        保活消息字符串 / Keep-alive message string
    """
    try:
        while True:
            await asyncio.sleep(interval_seconds)
            yield SSEFormatter.format_keepalive()
    except asyncio.CancelledError:
        # 任务被取消，正常退出 / Task cancelled, exit normally
        pass


async def _wrap_generator_with_keepalive(
    generator: AsyncIterator[str],
    keepalive_interval: int = 15,
) -> AsyncIterator[str]:
    """
    包装生成器，添加保活功能 / Wrap generator with keep-alive functionality

    Args:
        generator: 原始生成器 / Original generator
        keepalive_interval: 保活间隔（秒） / Keep-alive interval (seconds)

    Yields:
        SSE 事件字符串 / SSE event string
    """
    keepalive_task = None

    try:
        # 启动保活任务 / Start keep-alive task
        keepalive_task = asyncio.create_task(
            _keepalive_sender(keepalive_interval).__anext__()
        )

        async for item in generator:
            # 从生成器产出数据 / Yield data from generator
            yield item

            # 检查保活任务是否已完成 / Check if keep-alive task completed
            if keepalive_task.done():
                try:
                    # 产出保活消息 / Yield keep-alive message
                    keepalive_msg = keepalive_task.result()
                    yield keepalive_msg

                    # 重新启动下一个保活任务 / Restart next keep-alive task
                    keepalive_task = asyncio.create_task(
                        _keepalive_sender(keepalive_interval).__anext__()
                    )
                except Exception as e:
                    logger.error("Keepalive task failed: {}", str(e))

    except GeneratorExit:
        # 客户端断开连接 / Client disconnected
        logger.info("Client disconnected")
        raise

    except Exception as e:
        # 发生错误，发送错误事件 / Error occurred, send error event
        logger.error("Generator error: {}", str(e))
        yield SSEFormatter.format_error(
            code="STREAM_ERROR",
            message=str(e),
        )
        yield SSEFormatter.format_done()
        raise

    finally:
        # 清理保活任务 / Cleanup keep-alive task
        if keepalive_task and not keepalive_task.done():
            keepalive_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await keepalive_task


def create_sse_response(
    generator: AsyncIterator[str | dict],
    *,
    keepalive_interval: int = 15,
    media_type: str = "text/event-stream",
    headers: dict[str, str] | None = None,
) -> StreamingResponse:
    """
    创建 SSE 流式响应 / Create SSE streaming response

    工厂方法，封装 SSE 响应创建逻辑。
    Factory method, encapsulates SSE response creation logic.

    Args:
        generator: 异步生成器，产出字符串或字典 / Async generator yielding strings or dicts
        keepalive_interval: 保活间隔（秒），默认 15 秒 / Keep-alive interval, default 15s
        media_type: MIME 类型，默认 text/event-stream / MIME type, default text/event-stream
        headers: 额外的响应头 / Extra response headers

    Returns:
        FastAPI StreamingResponse 对象 / FastAPI StreamingResponse object
    """
    async def sse_generator() -> AsyncIterator[str]:
        """内部生成器，处理不同类型的数据 / Internal generator, handles different data types"""
        async for item in generator:
            if isinstance(item, str):
                # 已经是 SSE 格式字符串，直接 yield / Already SSE format, yield directly
                yield item
            elif isinstance(item, dict):
                # 字典格式化为 SSE 事件 / Format dict as SSE event
                event_id = str(uuid.uuid4())
                yield SSEFormatter.format_message(item, event_id)
            else:
                # 其他类型转字符串 / Convert other types to string
                yield str(item)

    # 包装保活功能 / Wrap with keep-alive
    wrapped_generator = _wrap_generator_with_keepalive(
        sse_generator(),
        keepalive_interval,
    )

    # 默认响应头 / Default response headers
    default_headers = {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",  # 禁用 Nginx 缓冲 / Disable Nginx buffering
    }

    # 合并自定义响应头 / Merge custom response headers
    if headers:
        default_headers.update(headers)

    # 创建 StreamingResponse / Create StreamingResponse
    return StreamingResponse(
        wrapped_generator,
        media_type=media_type,
        headers=default_headers,
    )


__all__ = [
    "SSEEvent",
    "SSEFormatter",
    "create_sse_response",
]
