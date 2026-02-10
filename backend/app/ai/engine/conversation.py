"""
对话执行引擎

支持多轮对话，维护会话上下文，处理 tool calling 循环
支持 SSE 流式输出
"""

import time
from typing import Any, AsyncIterator, Awaitable, Callable

from fastapi.responses import StreamingResponse

from app.ai.adapters import AdapterRegistry
from app.ai.sse import SSEChunkEncoder
from app.ai.tools.registry import ToolRegistry
from app.ai.types import ChatChunk, ChatMessage
from app.core.logging import LogManager
from app.models.ai.agent import Agent

from .base import BaseEngine
from .types import ExecutionRequest, ExecutionResult

logger = LogManager.get_logger("ai.engine.conversation")


class ConversationEngine(BaseEngine):
    """
    对话执行引擎

    处理多轮对话场景：
    1. 构建 system 消息 + 历史消息 + 新用户消息
    2. 调用 LLM
    3. 如果返回 tool_calls，进入工具调用循环
    4. 返回最终 assistant 回复

    支持两种输出模式：
    - execute(): 非流式，一次性返回完整结果
    - stream_execute(): SSE 流式，逐 token 推送
    """

    async def execute(self, agent: Agent, request: ExecutionRequest) -> ExecutionResult:
        """执行对话模式"""
        start = time.perf_counter()

        try:
            # 1. 构建消息列表
            messages: list[ChatMessage] = []

            # system 消息（注入 input_variables 到占位符）
            system_msg = self._build_system_message(agent, request.input_variables)
            messages.append(system_msg)

            # 历史消息（来自 request.messages）
            if request.messages:
                messages.extend(request.messages)

            # 2. 解析工具（按租户隔离）
            tools = self._resolve_tools(agent, tenant_id=request.tenant_id)

            # 3. 调用 LLM
            response = await self._call_llm(
                agent=agent,
                messages=messages,
                tools=tools or None,
                tenant_id=request.tenant_id,
                user_id=request.user_id,
            )

            total_tokens = response.total_tokens or 0

            # 4. 工具调用循环
            tool_results = []
            if response.tool_calls and tools:
                response, tool_results, total_tokens = await self._handle_tool_calls(
                    agent=agent,
                    messages=messages,
                    response=response,
                    tools=tools,
                    request=request,
                )

            # 5. 追加最终 assistant 消息
            output = response.message.content or ""
            messages.append(ChatMessage(role="assistant", content=output))

            duration_ms = int((time.perf_counter() - start) * 1000)

            return ExecutionResult(
                success=True,
                output=output,
                messages=self._messages_to_dicts(messages),
                tool_results=tool_results,
                total_tokens=total_tokens,
                duration_ms=duration_ms,
                conversation_id=request.conversation_id,
            )

        except Exception as exc:
            duration_ms = int((time.perf_counter() - start) * 1000)
            logger.error(
                "Conversation execution failed: agent=%d error=%s",
                agent.id,
                str(exc),
                exc_info=True,
            )
            return ExecutionResult(
                success=False,
                error=str(exc),
                duration_ms=duration_ms,
                conversation_id=request.conversation_id,
            )

    # ========================================
    # SSE 流式执行
    # ========================================

    async def stream_execute(
        self,
        agent: Agent,
        request: ExecutionRequest,
        on_complete: Callable[[ExecutionResult], Awaitable[None]] | None = None,
    ) -> StreamingResponse:
        """
        SSE 流式执行对话

        事件类型：
        - message: 内容增量 {"event": "message", "delta": "..."}
        - tool_call: 工具调用 {"event": "tool_call", "name": "...", "success": bool}
        - done: 完成 {"event": "done", "conversation_id": N, "total_tokens": N}
        - [DONE]: SSE 结束标记

        执行策略：
        - 无工具时：通过 adapter 真实流式推送 token
        - 有工具时：非流式处理工具调用，发送工具事件后推送最终内容

        Args:
            agent: 智能体模型实例
            request: 执行请求
            on_complete: 流式完成后的回调（用于持久化消息等）

        Returns:
            StreamingResponse (SSE)
        """
        start = time.perf_counter()

        # 构建消息列表
        messages: list[ChatMessage] = []
        system_msg = self._build_system_message(agent, request.input_variables)
        messages.append(system_msg)

        if request.messages:
            messages.extend(request.messages)

        tools = self._resolve_tools(agent, tenant_id=request.tenant_id)

        async def _sse_generator() -> AsyncIterator[str]:
            """SSE 事件生成器"""
            total_tokens = 0
            all_tool_results: list[Any] = []
            output = ""

            try:
                if tools:
                    # ---- 有工具：非流式处理工具调用 ----
                    response = await self._call_llm(
                        agent=agent,
                        messages=messages,
                        tools=tools,
                        tenant_id=request.tenant_id,
                        user_id=request.user_id,
                    )
                    total_tokens += response.total_tokens or 0

                    if response.tool_calls:
                        response, all_tool_results, total_tokens = (
                            await self._handle_tool_calls(
                                agent=agent,
                                messages=messages,
                                response=response,
                                tools=tools,
                                request=request,
                            )
                        )

                        # 发送工具调用事件
                        for tr in all_tool_results:
                            yield SSEChunkEncoder.encode({
                                "event": "tool_call",
                                "name": tr.name,
                                "success": tr.success,
                            })

                    # 发送最终内容
                    output = response.message.content or ""
                    messages.append(ChatMessage(role="assistant", content=output))

                    yield SSEChunkEncoder.encode({
                        "event": "message",
                        "delta": output,
                    })

                else:
                    # ---- 无工具：真实流式推送 ----
                    async for chunk in self._stream_llm_chunks(
                        agent=agent,
                        messages=messages,
                        tenant_id=request.tenant_id,
                    ):
                        if chunk.delta:
                            output += chunk.delta
                            yield SSEChunkEncoder.encode({
                                "event": "message",
                                "delta": chunk.delta,
                            })

                        # 累计 token（最后一个 chunk 包含完整统计）
                        if chunk.total_tokens is not None:
                            total_tokens = chunk.total_tokens

                        if chunk.finish_reason is not None:
                            break

                    messages.append(ChatMessage(role="assistant", content=output))

                # ---- 发送完成事件 ----
                duration_ms = int((time.perf_counter() - start) * 1000)

                yield SSEChunkEncoder.encode({
                    "event": "done",
                    "conversation_id": request.conversation_id,
                    "total_tokens": total_tokens,
                    "duration_ms": duration_ms,
                })
                yield SSEChunkEncoder.done()

                # 构建结果并调用回调
                result = ExecutionResult(
                    success=True,
                    output=output,
                    messages=self._messages_to_dicts(messages),
                    tool_results=all_tool_results,
                    total_tokens=total_tokens,
                    duration_ms=duration_ms,
                    conversation_id=request.conversation_id,
                )

                if on_complete:
                    await on_complete(result)

            except Exception as exc:
                logger.error(
                    "Stream execution failed: agent=%d error=%s",
                    agent.id,
                    str(exc),
                    exc_info=True,
                )
                yield SSEChunkEncoder.encode({
                    "error": True,
                    "message": str(exc),
                })
                yield SSEChunkEncoder.done()

                # 异常路径也触发回调，确保上层可执行状态清理/持久化
                if on_complete:
                    duration_ms = int((time.perf_counter() - start) * 1000)
                    failed_result = ExecutionResult(
                        success=False,
                        error=str(exc),
                        duration_ms=duration_ms,
                        conversation_id=request.conversation_id,
                    )
                    try:
                        await on_complete(failed_result)
                    except Exception as cb_exc:
                        logger.error(
                            "on_complete callback error: %s",
                            str(cb_exc),
                        )

        return StreamingResponse(
            _sse_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    # ========================================
    # 内部方法：流式 LLM 调用
    # ========================================

    async def _stream_llm_chunks(
        self,
        agent: Agent,
        messages: list[ChatMessage],
        tenant_id: int | None = None,
    ) -> AsyncIterator[ChatChunk]:
        """
        直接通过 adapter 获取流式 ChatChunk

        绕过 gateway 的 SSE 封装，用于引擎内部流式推送。
        非流式的工具调用轮次仍通过 gateway.chat() 走完整链路。

        Args:
            agent: 智能体
            messages: 消息列表
            tenant_id: 租户 ID（用于获取 API Key）

        Yields:
            ChatChunk
        """
        model_obj = agent.model
        provider_code = (
            model_obj.provider.code if model_obj and model_obj.provider else ""
        )
        model_code = model_obj.code if model_obj else ""

        # 通过 gateway 获取 provider 和 API Key
        provider, api_key = await self.gateway.get_provider_and_key(
            provider_code, tenant_id,
        )

        adapter = AdapterRegistry.create_adapter(
            provider_type=provider.type,
            api_key=api_key.decrypt_key(),
            base_url=provider.base_url,
        )

        async for chunk in adapter.stream_chat(
            messages=messages,
            model=model_code,
            temperature=agent.temperature,
            max_tokens=agent.max_tokens,
            top_p=agent.top_p or 1.0,
        ):
            yield chunk


__all__ = ["ConversationEngine"]
