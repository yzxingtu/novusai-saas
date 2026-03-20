"""
Image Generation Engine / 图像生成引擎

Handles Agent requests with model.type=image, calls image generation API
via AIGateway.generate_image(), and pushes results as SSE events.
处理 model.type=image 的 Agent 请求，通过 AIGateway.generate_image()
调用生图 API，并以 SSE 事件推送结果。
"""

from __future__ import annotations

import time
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import TYPE_CHECKING

from fastapi.responses import StreamingResponse

from app.ai.engine.types import ExecutionRequest, ExecutionResult
from app.ai.sse import SSEChunkEncoder
from app.core.logging import LogManager

if TYPE_CHECKING:
    from app.ai.gateway import AIGateway
    from app.models.ai.agent import Agent

logger = LogManager.get_logger("ai.engine.image_generation")


class ImageGenerationEngine:
    """
    Image Generation Engine / 图像生成引擎

    Sends user prompt to image generation model, pushes image_result events via SSE.
    将用户 prompt 发送到生图模型，通过 SSE 推送 image_result 事件。

    SSE event types / SSE 事件类型：
    - thinking: Generating image / 正在生成图片
    - image_result: Image result (with url, revised_prompt) / 图片生成结果
    - done: Completion / 完成
    - [DONE]: SSE end marker / SSE 结束标记
    """

    def __init__(self, gateway: AIGateway):
        self.gateway = gateway

    async def stream_execute(
        self,
        agent: Agent,
        request: ExecutionRequest,
        on_complete: Callable[[ExecutionResult], Awaitable[dict | None]] | None = None,
        image_params: dict | None = None,
    ) -> StreamingResponse:
        """
        SSE streaming image generation.
        SSE 流式执行图像生成。

        Args:
            agent: Agent (bound model.type=image) / 智能体（绑定的 model.type=image）
            request: Execution request (last user message as prompt) / 执行请求
            on_complete: Completion callback / 完成回调
            image_params: Image generation parameters (size/quality/style/n) / 图像生成参数

        Returns:
            StreamingResponse (SSE)
        """
        start = time.perf_counter()

        async def generate() -> AsyncIterator[str]:
            output = ""
            try:
                # Extract prompt (last user message) / 提取 prompt（最后一条 user 消息）
                prompt = ""
                for msg in reversed(request.messages):
                    if msg.role == "user":
                        prompt = msg.content or ""
                        break

                if not prompt:
                    yield SSEChunkEncoder.encode({
                        "error": True,
                        "message": "No prompt provided",
                    })
                    yield SSEChunkEncoder.done()
                    return

                # Notify frontend that generation is in progress / 通知前端正在生成
                yield SSEChunkEncoder.encode({"event": "thinking"})

                # Get model info / 获取模型信息
                model_obj = agent.model
                provider_code = (
                    model_obj.provider.code
                    if model_obj and model_obj.provider
                    else ""
                )
                model_code = model_obj.code if model_obj else ""

                # Call AIGateway for image generation / 调用 AIGateway 生图
                params = image_params or {}
                response = await self.gateway.generate_image(
                    provider_code=provider_code,
                    prompt=prompt,
                    model=model_code,
                    size=params.get("size", "1024x1024"),
                    quality=params.get("quality", "standard"),
                    style=params.get("style", "vivid"),
                    n=params.get("n", 1),
                    tenant_id=request.tenant_id,
                    user_id=request.user_id,
                    agent_id=agent.id,
                    conversation_id=request.conversation_id,
                )

                # Push each image result / 推送每张图片的结果
                for img in response.images:
                    yield SSEChunkEncoder.encode({
                        "event": "image_result",
                        "url": img.url,
                        "is_base64": img.is_base64,
                        "revised_prompt": img.revised_prompt,
                    })

                # Generate text description as output / 生成文本描述作为 output
                output = prompt
                if response.revised_prompt:
                    output = response.revised_prompt

                # Push message content (display text in frontend) / 推送消息内容（让前端显示文字）
                display_text = f"![generated image]({response.images[0].url})" if response.images else ""
                if display_text:
                    yield SSEChunkEncoder.encode({
                        "event": "message",
                        "delta": display_text,
                    })

                # Callback (before done event) / 回调（在 done 事件之前）
                duration_ms = int((time.perf_counter() - start) * 1000)
                extra_done_data: dict = {}
                if on_complete:
                    runtime_info = dict(getattr(response, "metadata", {}) or {}).get(
                        "runtime_model_info", {}
                    )
                    result = ExecutionResult(
                        success=True,
                        output=output,
                        messages=[
                            {"role": "user", "content": prompt},
                            {"role": "assistant", "content": display_text},
                        ],
                        total_tokens=0,
                        duration_ms=duration_ms,
                        conversation_id=request.conversation_id,
                        runtime_model_id=runtime_info.get("model_id"),
                        runtime_model_name=runtime_info.get("model_name"),
                        runtime_provider_id=runtime_info.get("provider_id"),
                        runtime_provider_name=runtime_info.get("provider_name"),
                    )
                    try:
                        cb_result = await on_complete(result)
                        if isinstance(cb_result, dict):
                            extra_done_data = cb_result
                    except Exception as cb_exc:
                        logger.error("on_complete callback error: {}", str(cb_exc))

                # Completion event / 完成事件
                yield SSEChunkEncoder.encode({
                    "event": "done",
                    "conversation_id": request.conversation_id,
                    "total_tokens": 0,
                    "duration_ms": duration_ms,
                    **extra_done_data,
                })
                yield SSEChunkEncoder.done()

            except Exception as exc:
                logger.error(
                    "Image generation failed: agent={} error={}",
                    agent.id, str(exc), exc_info=True,
                )
                try:
                    yield SSEChunkEncoder.encode({
                        "error": True,
                        "message": str(exc),
                    })
                    yield SSEChunkEncoder.done()
                except Exception:
                    pass

                if on_complete:
                    duration_ms = int((time.perf_counter() - start) * 1000)
                    await on_complete(ExecutionResult(
                        success=False,
                        error=str(exc),
                        duration_ms=duration_ms,
                        conversation_id=request.conversation_id,
                    ))

        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )


__all__ = ["ImageGenerationEngine"]
