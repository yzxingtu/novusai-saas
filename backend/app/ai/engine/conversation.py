"""
Conversation Execution Engine
对话执行引擎

Supports multi-turn conversation, maintains session context, handles tool calling loop.
Supports SSE streaming output.
支持多轮对话，维护会话上下文，处理 tool calling 循环。
支持 SSE 流式输出。
"""

from __future__ import annotations

import re
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import TYPE_CHECKING, Any

from fastapi.responses import StreamingResponse

from app.ai.adapters import AdapterRegistry
from app.ai.tools.types import ToolDefinition, to_openai_tools
from app.ai.types import ChatChunk, ChatMessage, messages_to_dicts
from app.core.logging import LogManager
from app.enums.ai import RequestTypeEnum
from app.models.ai.agent import Agent
from app.services.ai.metering_service import CostCalculator, TokenCounter

from .base import BaseEngine
from .stream_handler import StreamExecutionHandler
from .types import ExecutionRequest, ExecutionResult

if TYPE_CHECKING:
    from app.ai.skills.resolver import SkillResolveResult

logger = LogManager.get_logger("ai.engine.conversation")



# DeepSeek model internal function call markers (｜DSML｜parameter, ｜DSML｜invoke etc.) / DeepSeek 模型内部 function call 标记
_MODEL_FC_TOKEN_RE = re.compile(r'</?｜[A-Za-z]+｜[^>]*>')
# Complete DSML function_calls block (with nested content) / 完整 DSML function_calls 块（含嵌套内容）
_MODEL_FC_BLOCK_RE = re.compile(
    r'<｜DSML｜function_calls>.*?</｜DSML｜function_calls>',
    re.DOTALL,
)


def _strip_model_fc_tokens(text: str) -> str:
    """Filter leaked internal function call markers from model output (DeepSeek ｜DSML｜ etc.) / 过滤模型泄漏的内部 function call 标记"""
    if '｜' not in text:
        return text
    # Remove complete blocks first, then clean up residual tags / 先移除完整块，再清理残留标签
    text = _MODEL_FC_BLOCK_RE.sub('', text)
    return _MODEL_FC_TOKEN_RE.sub('', text)


class ConversationEngine(BaseEngine):
    """
    Conversation Execution Engine / 对话执行引擎

    Handles multi-turn conversation scenarios:
    处理多轮对话场景：
    1. Build system message + history messages + new user message / 构建 system 消息 + 历史消息 + 新用户消息
    2. Call LLM / 调用 LLM
    3. If tool_calls returned, enter tool call loop / 如果返回 tool_calls，进入工具调用循环
    4. Return final assistant reply / 返回最终 assistant 回复

    Supports two output modes / 支持两种输出模式：
    - execute(): Non-streaming, returns complete result at once / 非流式，一次性返回完整结果
    - stream_execute(): SSE streaming, pushes token by token / SSE 流式，逐 token 推送
    """

    async def execute(
        self,
        agent: Agent,
        request: ExecutionRequest,
        skill_result: SkillResolveResult | None = None,
    ) -> ExecutionResult:
        """Execute conversation mode / 执行对话模式"""
        start = time.perf_counter()

        try:
            # 1. Shared pre-logic (Skill resolve + message building + RAG + tool optimization) / 共享前置逻辑
            prep = await self._prepare_execution(agent, request, skill_result)
            messages = prep.messages
            tools = prep.tools
            rag_sources = prep.rag_sources

            # 2. Call LLM / 调用 LLM
            response = await self._call_llm(
                agent=agent,
                messages=messages,
                tools=tools or None,
                tenant_id=request.tenant_id,
                user_id=request.user_id,
                route_result=prep.route_result,
            )

            total_tokens = response.total_tokens or 0

            # 4. Tool call loop (pass route_result to maintain model consistency) / 工具调用循环（传入 route_result 保持模型一致）
            tool_results = []
            if response.tool_calls and tools:
                response, tool_results, total_tokens = await self._handle_tool_calls(
                    agent=agent,
                    messages=messages,
                    response=response,
                    tools=tools,
                    request=request,
                    route_result=prep.route_result,
                )

            # 5. Append final assistant message / 追加最终 assistant 消息
            output = response.message.content or ""
            messages.append(ChatMessage(role="assistant", content=output))

            duration_ms = int((time.perf_counter() - start) * 1000)

            result = ExecutionResult(
                success=True,
                output=output,
                messages=self._messages_to_dicts(messages),
                tool_results=tool_results,
                total_tokens=total_tokens,
                duration_ms=duration_ms,
                conversation_id=request.conversation_id,
            )
            # Attach RAG reference sources / 附加 RAG 引用来源
            if rag_sources:
                result.rag_sources = rag_sources  # type: ignore[attr-defined]

            return result

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
    # SSE Streaming Execution / SSE 流式执行
    # ========================================

    async def stream_execute(
        self,
        agent: Agent,
        request: ExecutionRequest,
        on_complete: Callable[[ExecutionResult], Awaitable[None]] | None = None,
        skill_result: SkillResolveResult | None = None,
    ) -> StreamingResponse:
        """
        SSE streaming conversation execution.
        SSE 流式执行对话。

        Event types / 事件类型：
        - message: Content delta / 内容增量
        - tool_call: Tool call result / 工具调用
        - done: Completion / 完成
        - [DONE]: SSE end marker / SSE 结束标记

        Execution strategy / 执行策略：
        - Without tools: Real streaming via adapter / 无工具时通过 adapter 真实流式推送 token
        - With tools: Each round uses real stream_chat, executes tools after detecting tool_calls
          有工具时每轮走真实 stream_chat，检测到 tool_calls 后执行工具并进入下一轮

        Args:
            agent: Agent model instance / 智能体模型实例
            request: Execution request / 执行请求
            on_complete: Callback after stream completion (for message persistence etc.) / 流式完成后的回调

        Returns:
            StreamingResponse (SSE)
        """
        start = time.perf_counter()

        # Shared pre-logic (Skill resolve + message building + RAG + tool optimization) / 共享前置逻辑
        prep = await self._prepare_execution(agent, request, skill_result)

        handler = StreamExecutionHandler(
            engine=self,
            agent=agent,
            request=request,
            prep=prep,
            start_time=start,
            on_complete=on_complete,
        )

        return StreamingResponse(
            handler.generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    # ========================================
    # Internal: Streaming LLM Call / 内部方法：流式 LLM 调用
    # ========================================

    async def _stream_llm_chunks(
        self,
        agent: Agent,
        messages: list[ChatMessage],
        tenant_id: int | None = None,
        route_result: Any | None = None,
        tools: list[ToolDefinition] | None = None,
    ) -> AsyncIterator[ChatChunk]:
        """
        Get streaming ChatChunk via adapter (with rate limiting/quota/metering protection).
        通过 adapter 获取流式 ChatChunk（含限流/配额/计量保护）。

        Uses adapter for real streaming, but executes gateway-level rate limiting,
        quota checking, and usage metering before/after stream, ensuring same
        security guarantees as non-streaming path.
        使用 adapter 实现真实流式推送，但在流前后执行 gateway 级别的限流/配额/计量检查。

        Args:
            agent: Agent / 智能体
            messages: Message list / 消息列表
            tenant_id: Tenant ID (for API Key retrieval) / 租户 ID
            route_result: ModelRouter route result (affects provider/model selection) / ModelRouter 路由结果
            tools: Tool definition list (for Function Calling) / 工具定义列表

        Yields:
            ChatChunk
        """
        # Route override takes priority / 路由覆写优先
        if route_result is not None and getattr(route_result, "is_overridden", False):
            provider_code: str = route_result.provider_code or ""
            model_code: str = route_result.model_code or ""
            is_vision: bool = "vision" in (route_result.reason or "")
        else:
            model_obj = agent.model
            provider_code = (
                model_obj.provider.code if model_obj and model_obj.provider else ""
            )
            model_code = model_obj.code if model_obj else ""
            is_vision = model_obj.supports_vision if model_obj else False

        # Non-vision model: remove image attachments to avoid API errors / 非视觉模型：移除图片附件，避免 API 报错
        if is_vision is False:
            for msg in messages:
                if msg.attachments:
                    msg.attachments = [
                        a for a in msg.attachments if a.get("type") != "image"
                    ]
                    if not msg.attachments:
                        msg.attachments = None

        # Keep model_obj reference for backward compatibility with rate limiting/quota logic / 为了兼容现有限流/配额逻辑，保留 model_obj 引用
        model_obj = agent.model

        # Get provider and API Key via gateway / 通过 gateway 获取 provider 和 API Key
        provider, api_key = await self.gateway.get_provider_and_key(
            provider_code, tenant_id,
        )
        ai_model = model_obj

        # Rate limiting + quota check (reuse gateway unified method) / 限流 + 配额检查（复用 gateway 统一方法）
        estimated_input = 0
        if tenant_id and ai_model:
            estimated_input = TokenCounter.count_messages_tokens(
                messages_to_dicts(messages)
            )
            await self.gateway.usage_recorder.check_rate_and_quota(
                tenant_id, ai_model.id, ai_model, estimated_input,
            )

        adapter = AdapterRegistry.create_adapter(
            provider_type=provider.type,
            api_key=api_key.decrypt_key(),
            base_url=provider.base_url,
        )
        openai_tools = to_openai_tools(tools) if tools else None

        total_tokens = 0
        input_tokens = 0
        output_tokens = 0
        async for chunk in adapter.stream_chat(
            messages=messages,
            model=model_code,
            temperature=agent.temperature,
            max_tokens=agent.max_tokens,
            top_p=agent.top_p or 1.0,
            tools=openai_tools,
        ):
            if chunk.total_tokens is not None:
                total_tokens = chunk.total_tokens
            if chunk.input_tokens is not None:
                input_tokens = chunk.input_tokens
            if chunk.output_tokens is not None:
                output_tokens = chunk.output_tokens
            yield chunk

        # After stream ends: adjust TPM and quota (reuse gateway unified method) / 流结束后：调整 TPM 和配额（复用 gateway 统一方法）
        if tenant_id and ai_model and estimated_input > 0:
            cost = CostCalculator.calculate_cost(ai_model, input_tokens, output_tokens)
            await self.gateway.usage_recorder.record_usage_and_adjust(
                tenant_id=tenant_id,
                model_id=ai_model.id,
                request_type=RequestTypeEnum.CHAT.value,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
                cost=cost,
                estimated_input=estimated_input,
                latency_ms=0,
            )


__all__ = ["ConversationEngine"]
