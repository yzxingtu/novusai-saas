"""
Conversation Execution Engine / 对话执行引擎

Supports multi-turn conversation, maintains session context, handles tool calling loop.
Supports SSE streaming output.
支持多轮对话，维护会话上下文，处理 tool calling 循环。
支持 SSE 流式输出。
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from typing import TYPE_CHECKING, Any

from app.ai.adapters import AdapterRegistry  # noqa: F401
from app.ai.runtime import ConversationQueryEngine  # noqa: F401
from app.ai.runtime.usage_metrics import CostCalculator  # noqa: F401

from .base import BaseEngine
from .conversation_entrypoints import _SyncIOAdapter  # noqa: F401
from .conversation_entrypoints import (
    execute_conversation as _execute_conversation,
)
from .conversation_entrypoints import (
    stream_execute_conversation as _stream_execute_conversation,
)
from .conversation_facade_support import (
    assistant_tool_round_count as _assistant_tool_round_count_impl,
)
from .conversation_facade_support import (
    build_runtime_accounting as _build_runtime_accounting,
)
from .conversation_facade_support import (
    build_runtime_preflight as _build_runtime_preflight,
)
from .conversation_facade_support import (
    call_llm as _call_llm_impl,
)
from .conversation_facade_support import (
    call_runtime_query_turn as _call_runtime_query_turn_impl,
)
from .conversation_facade_support import (
    finalize_completed_output as _finalize_completed_output_impl,
)
from .conversation_facade_support import (
    finalize_partial_output as _finalize_partial_output_impl,
)
from .conversation_facade_support import (
    normalize_tool_call_outcome as _normalize_tool_call_outcome_impl,
)
from .conversation_facade_support import (
    prepare_stream_runtime as _prepare_stream_runtime_impl,
)
from .conversation_facade_support import (
    register_tool_failures as _register_tool_failures_impl,
)
from .conversation_facade_support import (
    register_tool_round_delta as _register_tool_round_delta_impl,
)
from .conversation_facade_support import (
    stream_llm_chunks as _stream_llm_chunks_impl,
)
from .conversation_facade_support import (
    synthesize_tool_results_from_calls as _synthesize_tool_results_from_calls_impl,
)
from .conversation_runtime_preflight import (
    ConversationRuntimeContext,
)

if TYPE_CHECKING:
    from fastapi.responses import StreamingResponse

    from app.ai.skills.resolver import SkillResolveResult
    from app.ai.tools.types import ToolDefinition, ToolResult
    from app.ai.types import ChatChunk, ChatMessage, ChatResponse
    from app.models.ai.agent import Agent

    from .conversation_runtime_accounting import ConversationRuntimeAccounting
    from .conversation_runtime_preflight import ConversationRuntimePreflight
    from .execution_state_machine import ExecutionStateMachine
    from .types import ExecutionRequest, ExecutionResult, ToolUsePolicy

# Compatibility seam: replay tests and legacy callers still import the old
# private runtime-context name while the implementation has moved to the
# focused preflight helper module.
_StreamRuntimeContext = ConversationRuntimeContext


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

    @staticmethod
    def _assistant_tool_round_count(messages: list[ChatMessage]) -> int:
        return _assistant_tool_round_count_impl(messages)

    @staticmethod
    def _register_tool_round_delta(
        state: ExecutionStateMachine,
        *,
        before_count: int,
        messages: list[ChatMessage],
    ) -> None:
        _register_tool_round_delta_impl(
            state,
            before_count=before_count,
            messages=messages,
        )

    @staticmethod
    def _register_tool_failures(
        state: ExecutionStateMachine,
        tool_results: list[Any],
    ) -> None:
        _register_tool_failures_impl(state, tool_results)

    @staticmethod
    def _normalize_tool_call_outcome(
        outcome: tuple[Any, ...],
    ) -> tuple[ChatResponse | None, list[Any], int, int]:
        return _normalize_tool_call_outcome_impl(outcome)

    @staticmethod
    def _synthesize_tool_results_from_calls(
        tool_calls: list[dict[str, Any]] | None,
    ) -> list[ToolResult]:
        return _synthesize_tool_results_from_calls_impl(tool_calls)

    def _runtime_preflight(self) -> ConversationRuntimePreflight:
        return _build_runtime_preflight(self)

    def _runtime_accounting(self) -> ConversationRuntimeAccounting:
        return _build_runtime_accounting(
            self,
            cost_calculator=CostCalculator,
        )

    async def _finalize_partial_output(
        self,
        *,
        agent: Agent,
        request: ExecutionRequest,
        prep: Any,
        messages: list[ChatMessage],
        response: ChatResponse | None,
        state: ExecutionStateMachine,
        tool_results: list[ToolResult],
        reason: str,
        total_tokens: int,
        completion_tokens_used: int,
        selected_skill_names: list[str],
        context_sources: list[Any],
    ) -> tuple[str, int, int]:
        return await self.finalize_partial_output(
            agent=agent,
            request=request,
            prep=prep,
            messages=messages,
            response=response,
            state=state,
            tool_results=tool_results,
            reason=reason,
            total_tokens=total_tokens,
            completion_tokens_used=completion_tokens_used,
            selected_skill_names=selected_skill_names,
            context_sources=context_sources,
        )

    async def finalize_partial_output(
        self,
        *,
        agent: Agent,
        request: ExecutionRequest,
        prep: Any,
        messages: list[ChatMessage],
        response: ChatResponse | None,
        state: ExecutionStateMachine,
        tool_results: list[ToolResult],
        reason: str,
        total_tokens: int,
        completion_tokens_used: int,
        selected_skill_names: list[str],
        context_sources: list[Any],
    ) -> tuple[str, int, int]:
        return await _finalize_partial_output_impl(
            self,
            agent=agent,
            request=request,
            prep=prep,
            messages=messages,
            response=response,
            state=state,
            tool_results=tool_results,
            reason=reason,
            total_tokens=total_tokens,
            completion_tokens_used=completion_tokens_used,
            selected_skill_names=selected_skill_names,
            context_sources=context_sources,
        )

    async def _finalize_completed_output(
        self,
        *,
        agent: Agent,
        request: ExecutionRequest,
        prep: Any,
        messages: list[ChatMessage],
        response: ChatResponse | None,
        state: ExecutionStateMachine,
        tool_results: list[ToolResult],
        reason: str,
        total_tokens: int,
        completion_tokens_used: int,
        selected_skill_names: list[str],
        context_sources: list[Any],
    ) -> tuple[str, int, int]:
        return await self.finalize_completed_output(
            agent=agent,
            request=request,
            prep=prep,
            messages=messages,
            response=response,
            state=state,
            tool_results=tool_results,
            reason=reason,
            total_tokens=total_tokens,
            completion_tokens_used=completion_tokens_used,
            selected_skill_names=selected_skill_names,
            context_sources=context_sources,
        )

    async def finalize_completed_output(
        self,
        *,
        agent: Agent,
        request: ExecutionRequest,
        prep: Any,
        messages: list[ChatMessage],
        response: ChatResponse | None,
        state: ExecutionStateMachine,
        tool_results: list[ToolResult],
        reason: str,
        total_tokens: int,
        completion_tokens_used: int,
        selected_skill_names: list[str],
        context_sources: list[Any],
    ) -> tuple[str, int, int]:
        return await _finalize_completed_output_impl(
            self,
            agent=agent,
            request=request,
            prep=prep,
            messages=messages,
            response=response,
            state=state,
            tool_results=tool_results,
            reason=reason,
            total_tokens=total_tokens,
            completion_tokens_used=completion_tokens_used,
            selected_skill_names=selected_skill_names,
            context_sources=context_sources,
        )

    async def execute(
        self,
        agent: Agent,
        request: ExecutionRequest,
        skill_result: SkillResolveResult | None = None,
    ) -> ExecutionResult:
        """Execute conversation mode / 执行对话模式"""
        return await _execute_conversation(
            self,
            agent=agent,
            request=request,
            skill_result=skill_result,
        )

    async def _call_runtime_query_turn(
        self,
        *,
        agent: Agent,
        messages: list[ChatMessage],
        tools: list[ToolDefinition] | None,
        all_tool_names: list[str] | None,
        tool_use_policy: ToolUsePolicy | None,
        breach_retry_result: str | None,
        tenant_id: int | None,
        user_id: int | None,
        conversation_id: int | None,
        billing_context: dict[str, Any] | None,
        route_result: Any | None,
        log_user_type: str | None,
        selected_skill_names: list[str] | None,
        context_sources: list[Any] | None,
        execution_path: str | None,
        extra_kwargs: dict[str, Any] | None,
        skip_metering_preflight: bool,
    ) -> tuple[ChatResponse, ConversationQueryEngine]:
        return await _call_runtime_query_turn_impl(
            self,
            agent=agent,
            messages=messages,
            tools=tools,
            all_tool_names=all_tool_names,
            tool_use_policy=tool_use_policy,
            breach_retry_result=breach_retry_result,
            tenant_id=tenant_id,
            user_id=user_id,
            conversation_id=conversation_id,
            billing_context=billing_context,
            route_result=route_result,
            log_user_type=log_user_type,
            selected_skill_names=selected_skill_names,
            context_sources=context_sources,
            execution_path=execution_path,
            extra_kwargs=extra_kwargs,
            skip_metering_preflight=skip_metering_preflight,
            adapter_registry=AdapterRegistry,
            query_engine_cls=ConversationQueryEngine,
            accounting_builder=lambda runtime_engine: runtime_engine._runtime_accounting(),
        )

    async def _call_llm(
        self,
        agent: Agent,
        messages: list[ChatMessage],
        tools: list[ToolDefinition] | None = None,
        all_tool_names: list[str] | None = None,
        tool_use_policy: ToolUsePolicy | None = None,
        breach_retry_result: str | None = None,
        tenant_id: int | None = None,
        user_id: int | None = None,
        conversation_id: int | None = None,
        billing_context: dict[str, Any] | None = None,
        route_result: Any | None = None,
        log_user_type: str | None = None,
        selected_skill_names: list[str] | None = None,
        context_sources: list[Any] | None = None,
        execution_path: str | None = None,
        extra_kwargs: dict[str, Any] | None = None,
    ) -> ChatResponse:
        return await _call_llm_impl(
            self,
            agent=agent,
            messages=messages,
            tools=tools,
            all_tool_names=all_tool_names,
            tool_use_policy=tool_use_policy,
            breach_retry_result=breach_retry_result,
            tenant_id=tenant_id,
            user_id=user_id,
            conversation_id=conversation_id,
            billing_context=billing_context,
            route_result=route_result,
            log_user_type=log_user_type,
            selected_skill_names=selected_skill_names,
            context_sources=context_sources,
            execution_path=execution_path,
            extra_kwargs=extra_kwargs,
        )

    # ========================================
    # SSE Streaming Execution / SSE 流式执行
    # ========================================

    async def stream_execute(
        self,
        agent: Agent,
        request: ExecutionRequest,
        on_complete: Callable[
            [ExecutionResult],
            Awaitable[dict[str, Any] | None],
        ]
        | None = None,
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
        return await _stream_execute_conversation(
            self,
            agent=agent,
            request=request,
            on_complete=on_complete,
            skill_result=skill_result,
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
        execution_path: str | None = None,
        user_id: int | None = None,
        log_user_type: str | None = None,
        billing_context: dict[str, Any] | None = None,
        runtime_context: ConversationRuntimeContext | None = None,
        all_tool_names: list[str] | None = None,
        selected_skill_names: list[str] | None = None,
        context_sources: list[Any] | None = None,
        tool_use_policy: ToolUsePolicy | None = None,
        breach_retry_result: str | None = None,
        skip_metering_preflight: bool = False,
    ) -> AsyncIterator[ChatChunk]:
        async for chunk in _stream_llm_chunks_impl(
            self,
            agent=agent,
            messages=messages,
            tenant_id=tenant_id,
            conversation_id=conversation_id,
            route_result=route_result,
            tools=tools,
            execution_path=execution_path,
            user_id=user_id,
            log_user_type=log_user_type,
            billing_context=billing_context,
            runtime_context=runtime_context,
            all_tool_names=all_tool_names,
            selected_skill_names=selected_skill_names,
            context_sources=context_sources,
            tool_use_policy=tool_use_policy,
            breach_retry_result=breach_retry_result,
            skip_metering_preflight=skip_metering_preflight,
            adapter_registry=AdapterRegistry,
            query_engine_cls=ConversationQueryEngine,
            accounting_builder=lambda runtime_engine: runtime_engine._runtime_accounting(),
        ):
            yield chunk

    async def _prepare_stream_runtime(
        self,
        *,
        agent: Agent,
        messages: list[ChatMessage],
        tenant_id: int | None,
        route_result: Any | None = None,
        skip_metering_preflight: bool = False,
    ) -> ConversationRuntimeContext:
        return await _prepare_stream_runtime_impl(
            self,
            agent=agent,
            messages=messages,
            tenant_id=tenant_id,
            route_result=route_result,
            skip_metering_preflight=skip_metering_preflight,
        )


__all__ = ["ConversationEngine"]
