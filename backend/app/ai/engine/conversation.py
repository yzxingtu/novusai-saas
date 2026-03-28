"""
Conversation Execution Engine / 对话执行引擎

Supports multi-turn conversation, maintains session context, handles tool calling loop.
Supports SSE streaming output.
支持多轮对话，维护会话上下文，处理 tool calling 循环。
支持 SSE 流式输出。
"""

from __future__ import annotations

import re
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from fastapi.responses import StreamingResponse

from app.ai.adapters import AdapterRegistry
from app.ai.tools.types import ToolDefinition, to_openai_tools
from app.ai.types import ChatChunk, ChatMessage, messages_to_dicts
from app.ai.usage_mode import resolve_chat_usage
from app.ai.usage_recorder import UsageRecorder
from app.configs.service import PLATFORM_TENANT_ID
from app.core.i18n import _
from app.core.logging import LogManager
from app.core.runtime_identity import get_runtime_identity_tag
from app.core.response import build_public_error_text
from app.enums.ai import CallStatusEnum, RequestTypeEnum
from app.exceptions import BusinessException, NotFoundException
from app.models.ai.agent import Agent
from app.services.ai.usage_metrics import CostCalculator, TokenCounter

from .base import BaseEngine, log_user_type_for_call_log
from .stream_handler import StreamExecutionHandler
from .types import ExecutionRequest, ExecutionResult, ToolUsePolicy

if TYPE_CHECKING:
    from app.ai.skills.resolver import SkillResolveResult

logger = LogManager.get_logger("ai.engine.conversation")


@dataclass
class _StreamRuntimeContext:
    provider: Any
    api_key: Any
    ai_model: Any
    model_code: str
    is_vision: bool
    is_audio: bool
    is_video: bool
    estimated_input: int
    metering_context: Any
    should_meter_usage: bool
    should_record_call_log: bool
    runtime_info: dict[str, Any]



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
            retry_overhead_tokens = 0

            # 2. Call LLM / 调用 LLM
            response = await self._call_llm(
                agent=agent,
                messages=messages,
                tools=tools or None,
                all_tool_names=[tool.name for tool in prep.all_tools],
                tool_use_policy=prep.tool_use_policy,
                tenant_id=request.tenant_id,
                user_id=request.user_id,
                conversation_id=request.conversation_id,
                billing_context=request.billing_context,
                route_result=prep.route_result,
                log_user_type=log_user_type_for_call_log(request.user_role),
            )
            should_retry, retry_policy, breach_preview = self._should_retry_tool_contract_breach(
                response=response,
                current_policy=prep.tool_use_policy,
                tools=tools or [],
                input_variables=request.input_variables,
            )
            del breach_preview
            if (
                should_retry
                and retry_policy is not None
                and not prep.tool_use_policy.retry_on_contract_breach
                and prep.tool_use_policy.mode != "required"
            ):
                self._log_tool_contract_diagnostics(
                    agent=agent,
                    messages=messages,
                    response=response,
                    tools=tools or [],
                    policy=retry_policy,
                    conversation_id=request.conversation_id,
                    breach_type="initial_capability_denial_or_no_tool_use",
                    retry_result="no_retry",
                    continuation=prep.continuation_context,
                )
            elif should_retry and retry_policy is not None:
                retry_overhead_tokens += response.total_tokens or 0
                self._log_tool_contract_diagnostics(
                    agent=agent,
                    messages=messages,
                    response=response,
                    tools=tools or [],
                    policy=retry_policy,
                    conversation_id=request.conversation_id,
                    breach_type="initial_capability_denial_or_no_tool_use",
                    retry_result="retrying",
                    continuation=prep.continuation_context,
                )
                retry_tools = self._filter_tools_for_policy(
                    prep.all_tools or tools or [],
                    retry_policy,
                )
                retry_response = await self._call_llm(
                    agent=agent,
                    messages=messages,
                    tools=retry_tools or None,
                    all_tool_names=[tool.name for tool in prep.all_tools],
                    tool_use_policy=retry_policy,
                    breach_retry_result="retry_follow_up",
                    tenant_id=request.tenant_id,
                    user_id=request.user_id,
                    conversation_id=request.conversation_id,
                    billing_context=request.billing_context,
                    route_result=prep.route_result,
                    log_user_type=log_user_type_for_call_log(request.user_role),
                )
                retry_fixed = bool(retry_response.tool_calls)
                self._log_tool_contract_diagnostics(
                    agent=agent,
                    messages=messages,
                    response=retry_response,
                    tools=retry_tools or [],
                    policy=retry_policy,
                    conversation_id=request.conversation_id,
                    breach_type="initial_capability_denial_or_no_tool_use",
                    retry_result="succeeded" if retry_fixed else "failed",
                    continuation=prep.continuation_context,
                )
                response = retry_response
                if retry_fixed:
                    tools = retry_tools

            total_tokens = retry_overhead_tokens + (response.total_tokens or 0)

            # 4. Tool call loop (pass route_result + tool_consent_modes for unified consent semantic) / 工具调用循环（传入 route_result + tool_consent_modes 统一授权语义）
            tool_results = []
            if response.tool_calls and tools:
                response, tool_results, loop_tokens = await self._handle_tool_calls(
                    agent=agent,
                    messages=messages,
                    response=response,
                    tools=tools,
                    all_tools=prep.all_tools,
                    request=request,
                    route_result=prep.route_result,
                    tool_consent_modes=prep.tool_consent_modes,
                    continuation_context=prep.continuation_context,
                )
                total_tokens = retry_overhead_tokens + loop_tokens
                if response is not None:
                    self._log_web_research_contract_diagnostics(
                        agent=agent,
                        messages=messages,
                        response=response,
                        tools=tools or [],
                        continuation=prep.continuation_context,
                        conversation_id=request.conversation_id,
                    )

            # 5. Append final assistant message / 追加最终 assistant 消息
            skip_final_assistant = bool(
                getattr(response, "metadata", None)
                and response.metadata.get("skip_final_assistant")
            )
            output = response.message.content or ""
            cleaned_output, action_buttons = StreamExecutionHandler._extract_action_buttons(
                output,
            )
            if action_buttons:
                output = cleaned_output
            if not skip_final_assistant:
                messages.append(
                    ChatMessage(
                        role="assistant",
                        content=output,
                        metadata=(
                            {"action_buttons": action_buttons}
                            if action_buttons
                            else None
                        ),
                    )
                )

            duration_ms = int((time.perf_counter() - start) * 1000)
            runtime_info = dict(getattr(response, "metadata", {}) or {}).get(
                "runtime_model_info", {}
            )

            result = ExecutionResult(
                success=True,
                output=output,
                messages=self._messages_to_dicts(messages),
                tool_results=tool_results,
                total_tokens=total_tokens,
                duration_ms=duration_ms,
                conversation_id=request.conversation_id,
                runtime_model_id=runtime_info.get("model_id"),
                runtime_model_name=runtime_info.get("model_name"),
                runtime_provider_id=runtime_info.get("provider_id"),
                runtime_provider_name=runtime_info.get("provider_name"),
                rag_sources=rag_sources,
            )

            return result

        except (BusinessException, NotFoundException):
            raise

        except Exception as exc:
            duration_ms = int((time.perf_counter() - start) * 1000)
            logger.error(
                "Conversation execution failed: agent={} error={}",
                agent.id,
                str(exc),
                exc_info=True,
            )
            return ExecutionResult(
                success=False,
                error=build_public_error_text(
                    message=_("common.server_error"),
                    exc=exc,
                ),
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
        prep.stream_runtime = await self._prepare_stream_runtime(
            agent=agent,
            messages=prep.messages,
            tenant_id=request.tenant_id,
            route_result=prep.route_result,
        )

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
        conversation_id: int | None = None,
        route_result: Any | None = None,
        tools: list[ToolDefinition] | None = None,
        user_id: int | None = None,
        log_user_type: str | None = None,
        billing_context: dict[str, Any] | None = None,
        runtime_context: _StreamRuntimeContext | None = None,
        all_tool_names: list[str] | None = None,
        tool_use_policy: ToolUsePolicy | None = None,
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
            tenant_id: Tenant ID (for API Key retrieval) / 企业 ID
            route_result: ModelRouter route result (affects provider/model selection) / ModelRouter 路由结果
            tools: Tool definition list (for Function Calling) / 工具定义列表
            user_id: Caller user id for ai_call_logs / 调用人 ID
            log_user_type: Explicit call_log user_type / 调用日志用户类型

        Yields:
            ChatChunk
        """
        stream_start = time.perf_counter()

        if runtime_context is None:
            runtime_context = await self._prepare_stream_runtime(
                agent=agent,
                messages=messages,
                tenant_id=tenant_id,
                route_result=route_result,
            )

        provider = runtime_context.provider
        api_key = runtime_context.api_key
        ai_model = runtime_context.ai_model
        model_code = runtime_context.model_code
        is_vision = runtime_context.is_vision
        is_audio = runtime_context.is_audio
        is_video = runtime_context.is_video
        estimated_input = runtime_context.estimated_input
        metering_context = runtime_context.metering_context
        should_meter_usage = runtime_context.should_meter_usage
        should_record_call_log = runtime_context.should_record_call_log

        adapter = AdapterRegistry.create_adapter(
            provider_type=provider.type,
            api_key=api_key.decrypt_key(),
            base_url=provider.base_url,
            provider_config=provider.config,
            internal_db=self.db,
            internal_tenant_id=tenant_id,
        )
        openai_tools = to_openai_tools(tools) if tools else None
        effective_policy = tool_use_policy or ToolUsePolicy()
        effective_tool_choice = (
            effective_policy.mode
            if openai_tools and effective_policy.mode in {"auto", "required"}
            else None
        )
        request_log_data = {
            "_stream": True,
            "messages": messages_to_dicts(messages),
            "temperature": agent.temperature,
            "max_tokens": agent.max_tokens,
            "top_p": agent.top_p or 1.0,
            "tools": openai_tools,
            "tool_choice": effective_tool_choice,
            "selected_tool_names": [tool.name for tool in (tools or [])],
            "all_tool_names": all_tool_names or [tool.name for tool in (tools or [])],
            "tool_use_policy": {
                "family": effective_policy.family,
                "mode": effective_policy.mode,
                "allowed_tool_names": effective_policy.allowed_tool_names,
            },
        }
        if effective_policy.reason.startswith(("capability_denial:", "required_retry:")):
            request_log_data["breach_retry_result"] = "retry_follow_up"
        if openai_tools and any(
            isinstance(tool, dict)
            and (tool.get("function", {}) or {}).get("name") in {"web_search", "fetch_url"}
            for tool in openai_tools
        ) and not effective_tool_choice:
            logger.warning(
                "Tool policy not loaded: status=policy_not_loaded runtime={} conversation_id={} agent_id={} tool_names={}",
                get_runtime_identity_tag(),
                conversation_id,
                getattr(agent, "id", None),
                [
                    (tool.get("function", {}) or {}).get("name")
                    for tool in openai_tools
                    if isinstance(tool, dict)
                ],
            )

        supports_streaming = getattr(ai_model, "supports_streaming", True) if ai_model else True
        routed_model_id = (
            int(getattr(route_result, "model_id", 0) or 0)
            if route_result is not None and getattr(route_result, "is_overridden", False)
            else None
        )
        route_reason = (
            route_result.reason
            if route_result is not None and getattr(route_result, "is_overridden", False)
            else None
        )

        total_tokens = 0
        input_tokens = 0
        output_tokens = 0
        usage_mode = "actual"
        streamed_output = ""
        runtime_info = runtime_context.runtime_info

        try:
            if not supports_streaming:
                logger.info(
                    "Model {} does not support streaming, falling back to sync chat",
                    model_code,
                )
                response = await adapter.chat(
                    messages=messages,
                    model=model_code,
                    temperature=agent.temperature,
                    max_tokens=agent.max_tokens,
                    top_p=agent.top_p or 1.0,
                    tools=openai_tools,
                    tool_choice=effective_tool_choice,
                    supports_vision=bool(is_vision),
                    supports_audio=bool(is_audio),
                    supports_video=bool(is_video),
                )
                total_tokens = response.total_tokens or 0
                input_tokens = response.input_tokens or 0
                output_tokens = response.output_tokens or 0
                streamed_output = response.message.content or ""
                yield ChatChunk(
                    delta=response.message.content or "",
                    role=response.message.role,
                    finish_reason="stop",
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    total_tokens=total_tokens,
                    tool_calls=response.tool_calls,
                    metadata={"runtime_model_info": runtime_info},
                )
            else:
                async for chunk in adapter.stream_chat(
                    messages=messages,
                    model=model_code,
                    temperature=agent.temperature,
                    max_tokens=agent.max_tokens,
                    top_p=agent.top_p or 1.0,
                    tools=openai_tools,
                    tool_choice=effective_tool_choice,
                    supports_vision=bool(is_vision),
                    supports_audio=bool(is_audio),
                    supports_video=bool(is_video),
                ):
                    if chunk.total_tokens is not None:
                        total_tokens = chunk.total_tokens
                    if chunk.input_tokens is not None:
                        input_tokens = chunk.input_tokens
                    if chunk.output_tokens is not None:
                        output_tokens = chunk.output_tokens
                    if chunk.delta:
                        streamed_output += chunk.delta
                    chunk.metadata = dict(chunk.metadata or {})
                    if chunk.metadata.get("usage_mode"):
                        usage_mode = str(chunk.metadata["usage_mode"])
                    chunk.metadata.setdefault("runtime_model_info", runtime_info)
                    yield chunk
        except Exception as exc:
            logger.error(
                "Engine stream upstream failed: provider={} model={} conversation={} error={}",
                provider.code,
                model_code,
                conversation_id,
                str(exc),
                exc_info=True,
            )
            if should_record_call_log and ai_model:
                try:
                    await self.gateway.usage_recorder.log_call_failure(
                        error=exc,
                        start_time=stream_start,
                        provider=provider,
                        model=model_code,
                        model_id=ai_model.id,
                        messages=messages,
                        temperature=agent.temperature,
                        max_tokens=agent.max_tokens,
                        top_p=agent.top_p or 1.0,
                    tools=openai_tools,
                    tool_choice=effective_tool_choice,
                    all_tool_names=all_tool_names or [tool.name for tool in (tools or [])],
                    tool_use_policy_family=effective_policy.family,
                        tool_use_policy_mode=effective_policy.mode,
                        allowed_tool_names=effective_policy.allowed_tool_names,
                        breach_retry_result=request_log_data.get("breach_retry_result"),
                        request_type=RequestTypeEnum.CHAT.value,
                        tenant_id=tenant_id,
                        user_id=user_id,
                        user_type=log_user_type,
                        agent_id=getattr(agent, "id", None),
                        conversation_id=conversation_id,
                        billing_context=self.gateway._merge_model_provider_snapshots(
                            billing_context,
                            provider=provider,
                            ai_model=ai_model,
                        ),
                        routed_model_id=routed_model_id,
                        route_reason=route_reason,
                    )
                except Exception as log_exc:
                    logger.error(
                        "Engine stream failure audit log failed: provider={} model={} conversation={} error={}",
                        provider.code,
                        model_code,
                        conversation_id,
                        str(log_exc),
                    )
            raise

        # 流结束后：与 gateway.chat 一致 — 先租户计量再 Key；日志 best-effort
        # 整个尾部用 try/except 保护，避免计量/flush 异常阻塞生成器导致前端永远收不到 done
        latency_ms = int((time.perf_counter() - stream_start) * 1000)
        try:
            resolved_log_type = UsageRecorder._resolve_call_user_type(tenant_id, log_user_type)
            resolved_usage = resolve_chat_usage(
                messages=messages,
                output_text=streamed_output,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
                estimated_input=estimated_input,
            )
            input_tokens = resolved_usage.input_tokens
            output_tokens = resolved_usage.output_tokens
            total_tokens = resolved_usage.total_tokens
            usage_mode = resolved_usage.usage_mode

            cost = (
                CostCalculator.calculate_cost(ai_model, input_tokens, output_tokens)
                if ai_model
                else 0.0
            )

            if should_meter_usage and ai_model and estimated_input > 0:
                assert tenant_id is not None
                await self.gateway.usage_recorder.record_usage_and_adjust(
                    tenant_id=tenant_id,
                    model_id=ai_model.id,
                    request_type=RequestTypeEnum.CHAT.value,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    total_tokens=total_tokens,
                    cost=cost,
                    estimated_input=estimated_input,
                    latency_ms=latency_ms,
                    user_id=user_id,
                    metering_context=metering_context,
                )

            api_key.increment_usage()
            await self.db.flush()

            if should_record_call_log and ai_model:
                try:
                    assert tenant_id is not None
                    await self.gateway.usage_recorder.call_log_service.log_call_async(
                        tenant_id=tenant_id,
                        model_id=ai_model.id,
                        provider_id=provider.id,
                        request_type=RequestTypeEnum.CHAT.value,
                        request_data={
                            **request_log_data,
                        },
                        response_data={
                            "input_tokens": input_tokens,
                            "output_tokens": output_tokens,
                            "total_tokens": total_tokens,
                            "model": model_code,
                            "usage_mode": usage_mode,
                        },
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        total_tokens=total_tokens,
                        cost=cost,
                        latency_ms=latency_ms,
                        status=CallStatusEnum.SUCCESS.value,
                        user_id=user_id,
                        user_type=resolved_log_type,
                        agent_id=getattr(agent, "id", None),
                        conversation_id=conversation_id,
                        billing_context=self.gateway._merge_model_provider_snapshots(
                            billing_context,
                            provider=provider,
                            ai_model=ai_model,
                        ),
                        routed_model_id=routed_model_id,
                        route_reason=route_reason,
                    )
                except Exception as log_exc:
                    logger.error("Engine stream call log failed: {}", str(log_exc))
        except Exception as tail_exc:
            logger.error(
                "Stream tail metering/flush failed (stream still completes): model={} error={}",
                model_code,
                str(tail_exc),
            )

    async def _prepare_stream_runtime(
        self,
        *,
        agent: Agent,
        messages: list[ChatMessage],
        tenant_id: int | None,
        route_result: Any | None = None,
    ) -> _StreamRuntimeContext:
        """Prepare first-round stream runtime and perform quota/rate preflight.

        为首轮流式请求准备运行时上下文，并在返回 StreamingResponse 之前完成限速/配额预检。
        """
        if route_result is not None and getattr(route_result, "is_overridden", False):
            provider_code: str = route_result.provider_code or ""
            model_code: str = route_result.model_code or ""
            routed_mid = int(getattr(route_result, "model_id", 0) or 0)
            route_model_obj = None
            if routed_mid:
                from app.repositories.ai.model_repository import AIModelRepository

                route_model_obj = await AIModelRepository(self.db).get_active_with_provider(
                    routed_mid,
                )
            if route_model_obj is not None:
                ai_model = route_model_obj
                is_vision = bool(route_model_obj.supports_vision)
                is_audio = bool(getattr(route_model_obj, "supports_audio", False))
                is_video = bool(getattr(route_model_obj, "supports_video", False))
            else:
                ai_model = agent.model
                reason_str: str = route_result.reason or ""
                is_vision = "vision" in reason_str
                is_audio = "audio" in reason_str
                is_video = "video" in reason_str
        else:
            mobj = agent.model
            ai_model = mobj
            provider_code = mobj.provider.code if mobj and mobj.provider else ""
            model_code = mobj.code if mobj else ""
            is_vision = mobj.supports_vision if mobj else False
            is_audio = getattr(mobj, "supports_audio", False) if mobj else False
            is_video = getattr(mobj, "supports_video", False) if mobj else False

        for msg in messages:
            if msg.attachments:
                kept = [
                    a
                    for a in msg.attachments
                    if not (
                        (a.get("type") == "image" and not is_vision)
                        or (a.get("type") == "audio" and not is_audio)
                        or (a.get("type") == "video" and not is_video)
                    )
                ]
                msg.attachments = kept if kept else None

        provider, api_key = await self.gateway.get_provider_and_key(
            provider_code, tenant_id,
        )

        estimated_input = 0
        metering_context = None
        should_meter_usage = tenant_id is not None and tenant_id > PLATFORM_TENANT_ID
        should_record_call_log = tenant_id is not None
        if should_record_call_log and ai_model:
            estimated_input = TokenCounter.count_messages_tokens(
                messages_to_dicts(messages)
            )
        if should_meter_usage and ai_model:
            metering_context = await self.gateway.usage_recorder.check_rate_and_quota(
                tenant_id, ai_model.id, ai_model, estimated_input,
            )

        return _StreamRuntimeContext(
            provider=provider,
            api_key=api_key,
            ai_model=ai_model,
            model_code=model_code,
            is_vision=is_vision,
            is_audio=is_audio,
            is_video=is_video,
            estimated_input=estimated_input,
            metering_context=metering_context,
            should_meter_usage=should_meter_usage,
            should_record_call_log=should_record_call_log,
            runtime_info={
                "provider_id": provider.id,
                "provider_name": (
                    getattr(provider, "name", None)
                    or getattr(provider, "code", None)
                    or f"Provider #{provider.id}"
                ),
                "model_id": ai_model.id if ai_model else None,
                "model_name": (
                    (getattr(ai_model, "name", None) or model_code)
                    if ai_model
                    else None
                ),
                "model_code": model_code,
            },
        )


__all__ = ["ConversationEngine"]
