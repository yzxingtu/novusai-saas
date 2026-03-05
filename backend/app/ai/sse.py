"""
SSE 流式响应封装

提供 Server-Sent Events (SSE) 格式的流式响应支持
"""

import json
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any

from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.types import ChatChunk
from app.core.i18n import _
from app.core.logging import LogManager

logger = LogManager.get_logger("ai.sse")


class SSEChunkEncoder:
    """
    SSE 块编码器

    将数据块编码为 SSE 格式：data: {json}\n\n
    """

    @staticmethod
    def encode(data: dict[str, Any] | str) -> str:
        """
        编码数据块为 SSE 格式

        Args:
            data: 数据（字典或字符串）

        Returns:
            SSE 格式的字符串
        """
        if isinstance(data, str):
            # 特殊标记（如 [DONE]）
            return f"data: {data}\n\n"

        # 普通 JSON 数据
        json_str = json.dumps(data, ensure_ascii=False)
        return f"data: {json_str}\n\n"

    @staticmethod
    def done() -> str:
        """
        生成结束标记

        Returns:
            SSE 结束标记
        """
        return "data: [DONE]\n\n"


class SSEStreamingResponse:
    """
    SSE 流式响应封装

    将 AsyncIterator[ChatChunk] 转换为 SSE 格式的流式响应
    支持 Token 计数和完成回调
    """

    def __init__(
        self,
        chunk_iterator: AsyncIterator[ChatChunk],
        db: AsyncSession,
        on_complete: Callable[[int, int, int], Awaitable[None]] | None = None,
    ):
        """
        初始化 SSE 流式响应

        Args:
            chunk_iterator: ChatChunk 异步迭代器
            db: 数据库会话
            on_complete: 完成回调函数，参数为 (input_tokens, output_tokens, total_tokens)
        """
        self.chunk_iterator = chunk_iterator
        self.db = db
        self.on_complete = on_complete

        # Token 计数累加器
        self.input_tokens = 0
        self.output_tokens = 0
        self.total_tokens = 0

    async def _generate(self) -> AsyncIterator[str]:
        """
        生成 SSE 流式响应

        仅在流式传输成功完成时触发 on_complete 回调记录使用量。
        发生异常或客户端断开时不记录，避免错误计量。

        Yields:
            SSE 格式的字符串
        """
        stream_success = False

        try:
            async for chunk in self.chunk_iterator:
                # 累加 Token 计数
                if chunk.input_tokens is not None:
                    self.input_tokens = chunk.input_tokens
                if chunk.output_tokens is not None:
                    self.output_tokens = chunk.output_tokens
                if chunk.total_tokens is not None:
                    self.total_tokens = chunk.total_tokens

                # 转换为字典格式
                chunk_dict = {
                    "delta": chunk.delta,
                    "role": chunk.role,
                    "finish_reason": chunk.finish_reason,
                    "input_tokens": chunk.input_tokens,
                    "output_tokens": chunk.output_tokens,
                    "total_tokens": chunk.total_tokens,
                    "tool_calls": chunk.tool_calls,
                    "metadata": chunk.metadata,
                }

                # 移除 None 值以减少数据传输
                chunk_dict = {k: v for k, v in chunk_dict.items() if v is not None}

                # 编码为 SSE 格式并 yield（finish_reason chunk 的 content 也正常发送）
                yield SSEChunkEncoder.encode(chunk_dict)

                # finish_reason chunk 已发送给客户端，发结束标记后退出
                if chunk.finish_reason is not None:
                    yield SSEChunkEncoder.done()
                    stream_success = True
                    break
            else:
                # 迭代器正常结束但无 finish_reason（部分供应商直接结束迭代）
                yield SSEChunkEncoder.done()
                stream_success = True

        except GeneratorExit:
            # 客户端提前断开连接 — 不记录使用量
            logger.warning(_("ai.log.sse_client_disconnected"))
            raise

        except Exception as e:
            # 流式响应发生错误 — 不记录使用量（token 计数可能不完整）
            logger.error("SSE stream error: %s", str(e))
            error_chunk = {
                "error": True,
                "message": str(e),
            }
            yield SSEChunkEncoder.encode(error_chunk)
            yield SSEChunkEncoder.done()

        finally:
            # 仅在流式传输成功完成时触发回调记录使用量
            if stream_success and self.on_complete:
                try:
                    await self.on_complete(
                        self.input_tokens,
                        self.output_tokens,
                        self.total_tokens,
                    )
                except Exception as e:
                    logger.error("SSE callback error: %s", str(e))

    def response(self) -> StreamingResponse:
        """
        创建 FastAPI StreamingResponse

        Returns:
            FastAPI StreamingResponse 对象
        """
        return StreamingResponse(
            self._generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",  # 禁用 Nginx 缓冲
            },
        )


__all__ = [
    "SSEChunkEncoder",
    "SSEStreamingResponse",
]
