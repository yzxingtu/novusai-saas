"""
SSE (Server-Sent Events) 核心封装

提供统一的 SSE 流式响应基类，用于所有需要流式响应的场景。
支持标准事件格式、错误处理、连接保活等功能。
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
    SSE 事件类型

    定义标准的事件类型常量
    """

    MESSAGE = "message"  # 普通数据消息
    ERROR = "error"      # 错误消息
    DONE = "done"        # 完成标记
    KEEPALIVE = "keepalive"  # 保活消息（注释行）


class SSEFormatter:
    """
    SSE 格式化器

    将数据格式化为标准的 SSE 格式：
    - event: 事件类型
    - data: JSON 数据
    - id: 事件 ID（可选）

    示例：
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
        格式化 SSE 事件

        Args:
            event: 事件类型（message/error/done）
            data: 事件数据（字典或字符串）
            event_id: 事件 ID（可选）

        Returns:
            格式化后的 SSE 字符串
        """
        lines = []

        # 添加 event 行
        if event:
            lines.append(f"event: {event}")

        # 添加 data 行
        if isinstance(data, str):
            # 字符串直接使用
            lines.append(f"data: {data}")
        elif isinstance(data, dict):
            # 字典转 JSON
            json_str = json.dumps(data, ensure_ascii=False)
            lines.append(f"data: {json_str}")
        else:
            # 其他类型转字符串
            lines.append(f"data: {str(data)}")

        # 添加 id 行（可选）
        if event_id:
            lines.append(f"id: {event_id}")

        # 添加空行表示事件结束
        lines.append("")

        return "\n".join(lines) + "\n"

    @staticmethod
    def format_message(data: dict, event_id: str | None = None) -> str:
        """
        格式化消息事件

        Args:
            data: 消息数据
            event_id: 事件 ID

        Returns:
            SSE 格式字符串
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
        格式化错误事件

        Args:
            code: 错误码
            message: 错误消息
            event_id: 事件 ID

        Returns:
            SSE 格式字符串
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
        格式化完成标记

        Returns:
            SSE 格式字符串
        """
        return SSEFormatter.format_event(
            event=SSEEvent.DONE,
            data="[DONE]",
        )

    @staticmethod
    def format_keepalive() -> str:
        """
        格式化保活消息（注释行）

        注释行格式：: keepalive

        Returns:
            SSE 格式字符串
        """
        return ": keepalive\n\n"


async def _keepalive_sender(
    interval_seconds: int = 15,
) -> AsyncIterator[str]:
    """
    保活消息发送器

    定期发送注释行以保持连接活跃

    Args:
        interval_seconds: 发送间隔（秒）

    Yields:
        保活消息字符串
    """
    try:
        while True:
            await asyncio.sleep(interval_seconds)
            yield SSEFormatter.format_keepalive()
    except asyncio.CancelledError:
        # 任务被取消，正常退出
        pass


async def _wrap_generator_with_keepalive(
    generator: AsyncIterator[str],
    keepalive_interval: int = 15,
) -> AsyncIterator[str]:
    """
    包装生成器，添加保活功能

    Args:
        generator: 原始生成器
        keepalive_interval: 保活间隔（秒）

    Yields:
        SSE 事件字符串
    """
    keepalive_task = None

    try:
        # 启动保活任务
        keepalive_task = asyncio.create_task(
            _keepalive_sender(keepalive_interval).__anext__()
        )

        async for item in generator:
            # 从生成器产出数据
            yield item

            # 检查保活任务是否已完成
            if keepalive_task.done():
                try:
                    # 产出保活消息
                    keepalive_msg = keepalive_task.result()
                    yield keepalive_msg

                    # 重新启动下一个保活任务
                    keepalive_task = asyncio.create_task(
                        _keepalive_sender(keepalive_interval).__anext__()
                    )
                except Exception as e:
                    logger.error("Keepalive task failed", error=str(e))

    except GeneratorExit:
        # 客户端断开连接
        logger.info("Client disconnected")
        raise

    except Exception as e:
        # 发生错误，发送错误事件
        logger.error("Generator error", error=str(e))
        yield SSEFormatter.format_error(
            code="STREAM_ERROR",
            message=str(e),
        )
        yield SSEFormatter.format_done()
        raise

    finally:
        # 清理保活任务
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
    创建 SSE 流式响应

    工厂方法，封装 SSE 响应创建逻辑。

    Args:
        generator: 异步生成器，产出字符串或字典
        keepalive_interval: 保活间隔（秒），默认 15 秒
        media_type: MIME 类型，默认 text/event-stream
        headers: 额外的响应头

    Returns:
        FastAPI StreamingResponse 对象
    """
    async def sse_generator() -> AsyncIterator[str]:
        """内部生成器，处理不同类型的数据"""
        async for item in generator:
            if isinstance(item, str):
                # 已经是 SSE 格式字符串，直接 yield
                yield item
            elif isinstance(item, dict):
                # 字典格式化为 SSE 事件
                event_id = str(uuid.uuid4())
                yield SSEFormatter.format_message(item, event_id)
            else:
                # 其他类型转字符串
                yield str(item)

    # 包装保活功能
    wrapped_generator = _wrap_generator_with_keepalive(
        sse_generator(),
        keepalive_interval,
    )

    # 默认响应头
    default_headers = {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",  # 禁用 Nginx 缓冲
    }

    # 合并自定义响应头
    if headers:
        default_headers.update(headers)

    # 创建 StreamingResponse
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
