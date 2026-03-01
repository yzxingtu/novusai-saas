"""
对话执行引擎

支持多轮对话，维护会话上下文，处理 tool calling 循环
支持 SSE 流式输出
"""

from __future__ import annotations

import re
import time
from typing import TYPE_CHECKING, Any, AsyncIterator, Awaitable, Callable

from fastapi.responses import StreamingResponse

from app.ai.adapters import AdapterRegistry
from app.ai.types import ChatChunk, ChatMessage, messages_to_dicts
from app.core.logging import LogManager
from app.models.ai.agent import Agent
from app.enums.ai import RequestTypeEnum
from app.services.ai.metering_service import CostCalculator, TokenCounter

from .base import BaseEngine
from .stream_handler import StreamExecutionHandler
from .types import ExecutionRequest, ExecutionResult

if TYPE_CHECKING:
    from app.ai.skills.resolver import SkillResolveResult

logger = LogManager.get_logger("ai.engine.conversation")



# DeepSeek 模型内部 function call 标记（｜DSML｜parameter, ｜DSML｜invoke 等）
_MODEL_FC_TOKEN_RE = re.compile(r'</?｜[A-Za-z]+｜[^>]*>')
# 完整 DSML function_calls 块（含嵌套内容）
_MODEL_FC_BLOCK_RE = re.compile(
    r'<｜DSML｜function_calls>.*?</｜DSML｜function_calls>',
    re.DOTALL,
)


def _strip_model_fc_tokens(text: str) -> str:
    """过滤模型泄漏的内部 function call 标记（DeepSeek ｜DSML｜ 等）"""
    if '｜' not in text:
        return text
    # 先移除完整块，再清理残留标签
    text = _MODEL_FC_BLOCK_RE.sub('', text)
    return _MODEL_FC_TOKEN_RE.sub('', text)


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

    async def execute(
        self,
        agent: Agent,
        request: ExecutionRequest,
        skill_result: SkillResolveResult | None = None,
    ) -> ExecutionResult:
        """执行对话模式"""
        start = time.perf_counter()

        try:
            # 1. 共享前置逻辑（Skill 解析 + 消息构建 + RAG + 工具优化）
            prep = await self._prepare_execution(agent, request, skill_result)
            messages = prep.messages
            tools = prep.tools
            rag_sources = prep.rag_sources

            # 2. 调用 LLM
            response = await self._call_llm(
                agent=agent,
                messages=messages,
                tools=tools or None,
                tenant_id=request.tenant_id,
                user_id=request.user_id,
                route_result=prep.route_result,
            )

            total_tokens = response.total_tokens or 0

            # 4. 工具调用循环（传入 route_result 保持模型一致）
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

            # 5. 追加最终 assistant 消息
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
            # 附加 RAG 引用来源
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
    # SSE 流式执行
    # ========================================

    async def stream_execute(
        self,
        agent: Agent,
        request: ExecutionRequest,
        on_complete: Callable[[ExecutionResult], Awaitable[None]] | None = None,
        skill_result: SkillResolveResult | None = None,
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

        # 共享前置逻辑（Skill 解析 + 消息构建 + RAG + 工具优化）
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
    # 内部方法：流式 LLM 调用
    # ========================================

    async def _stream_llm_chunks(
        self,
        agent: Agent,
        messages: list[ChatMessage],
        tenant_id: int | None = None,
        route_result: Any | None = None,
    ) -> AsyncIterator[ChatChunk]:
        """
        通过 adapter 获取流式 ChatChunk（含限流/配额/计量保护）

        使用 adapter 实现真实流式推送，但在流前后执行 gateway 级别的
        限流检查、配额检查和用量计量，确保与非流式路径一致的安全保障。

        Args:
            agent: 智能体
            messages: 消息列表
            tenant_id: 租户 ID（用于获取 API Key）
            route_result: ModelRouter 路由结果（影响 provider/model 选择）

        Yields:
            ChatChunk
        """
        # 路由覆写优先
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

        # 非视觉模型：移除图片附件，避免 API 报错
        if is_vision is False:
            for msg in messages:
                if msg.attachments:
                    msg.attachments = [
                        a for a in msg.attachments if a.get("type") != "image"
                    ]
                    if not msg.attachments:
                        msg.attachments = None

        # 为了兼容现有限流/配额逻辑，保留 model_obj 引用
        model_obj = agent.model

        # 通过 gateway 获取 provider 和 API Key
        provider, api_key = await self.gateway.get_provider_and_key(
            provider_code, tenant_id,
        )
        ai_model = model_obj

        # 限流 + 配额检查（复用 gateway 统一方法）
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

        total_tokens = 0
        input_tokens = 0
        output_tokens = 0
        async for chunk in adapter.stream_chat(
            messages=messages,
            model=model_code,
            temperature=agent.temperature,
            max_tokens=agent.max_tokens,
            top_p=agent.top_p or 1.0,
        ):
            if chunk.total_tokens is not None:
                total_tokens = chunk.total_tokens
            if chunk.input_tokens is not None:
                input_tokens = chunk.input_tokens
            if chunk.output_tokens is not None:
                output_tokens = chunk.output_tokens
            yield chunk

        # 流结束后：调整 TPM 和配额（复用 gateway 统一方法）
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
