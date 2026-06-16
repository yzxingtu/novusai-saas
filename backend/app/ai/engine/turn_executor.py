"""Unified turn execution loop for streaming and non-streaming flows."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

from app.ai.tools.types import ToolResult
from app.ai.types import ChatMessage, ChatResponse

from .execution_state_machine import ExecutionStateMachine
from .final_output_policy import (
    build_untrusted_final_output_fallback,
    is_trusted_assistant_final_output_source,
)
from .recovery_manager import RecoveryManager
from .turn_executor_tool_batch import (
    build_shortcircuit_fallback_response,
    execute_tool_batch,
    run_contract_retry_round,
    run_tool_batch_or_update_intents,
)
from .types import RecoveryDecision, ToolUsePolicy


@dataclass
class ModelRoundResult:
    """Result produced by one model call round."""

    response: Any | None
    total_tokens: int = 0
    completion_tokens_used: int = 0


@dataclass
class ToolBatchResult:
    """Result produced by handling one batch of tool calls."""

    response: Any | None
    tool_results: list[Any] = field(default_factory=list)
    total_tokens: int = 0
    completion_tokens_used: int = 0


@dataclass
class TurnExecutionResult:
    """Unified execution output for sync/stream adapters."""

    output: str
    total_tokens: int
    completion_tokens_used: int
    tool_results: list[Any]
    response: Any | None
    partial: bool
    paused_for_consent: bool
    completion_reason: str
    final_output_source: Literal[
        "assistant",
        "tool_evidence_completed",
        "recovery_evidence",
        "partial_output",
        "budget_fallback",
    ]
    action_buttons: list[dict[str, Any]] | None = None


class TurnIOAdapter(Protocol):
    """Transport/helper adapter; execution loop remains in TurnExecutor."""

    async def call_llm(
        self,
        *,
        messages: list[Any],
        tools: list[Any] | None,
        tool_use_policy: Any,
        **kwargs: Any,
    ) -> ModelRoundResult: ...

    async def handle_tool_calls(
        self,
        *,
        response: Any,
        tools: list[Any],
        messages: list[Any],
        **kwargs: Any,
    ) -> ToolBatchResult: ...

    async def finalize_partial_output(
        self,
        *,
        messages: list[ChatMessage],
        response: ChatResponse | None,
        state: ExecutionStateMachine,
        tool_results: list[ToolResult],
        reason: str,
        total_tokens: int,
        completion_tokens_used: int,
    ) -> tuple[str, int, int]: ...

    async def finalize_completed_output(
        self,
        *,
        messages: list[ChatMessage],
        response: ChatResponse | None,
        state: ExecutionStateMachine,
        tool_results: list[ToolResult],
        reason: str,
        total_tokens: int,
        completion_tokens_used: int,
    ) -> tuple[str, int, int]: ...

    def should_retry_tool_contract_breach(
        self,
        *,
        response: ChatResponse | None,
        current_policy: ToolUsePolicy,
        tools: list[Any],
        input_variables: dict[str, Any] | None,
    ) -> tuple[bool, ToolUsePolicy | None, str]: ...

    def analyze_post_tool_contract_breach(
        self,
        *,
        messages: list[ChatMessage],
        response: ChatResponse | None,
        current_policy: ToolUsePolicy,
        tools: list[Any],
        input_variables: dict[str, Any] | None,
    ) -> tuple[str | None, ToolUsePolicy | None, dict[str, Any]]: ...

    def restrict_tools_to_names(
        self,
        tools: list[Any],
        allowed_tool_names: list[str] | None,
    ) -> list[Any]: ...

    def log_tool_contract_diagnostics(
        self,
        *,
        agent: Any,
        messages: list[ChatMessage],
        response: ChatResponse | None,
        tools: list[Any],
        policy: ToolUsePolicy,
        conversation_id: int | None,
        breach_type: str,
        retry_result: str,
        continuation: Any,
    ) -> None: ...

    async def emit_chunk(self, text: str) -> None: ...


def active_intent(state: Any) -> Any | None:
    for intent in state.intent_plan:
        if intent.status in {"completed", "failed", "skipped"}:
            continue
        if intent.family == "none" or not intent.requires_tools:
            continue
        return intent
    return None


def assistant_tool_round_count(messages: list[ChatMessage]) -> int:
    return sum(
        1
        for message in messages
        if message.role == "assistant" and bool(message.tool_calls)
    )


def register_tool_round_delta(
    state: Any,
    *,
    before_count: int,
    messages: list[ChatMessage],
) -> None:
    delta = max(0, assistant_tool_round_count(messages) - before_count)
    for _round_idx in range(delta):
        state.register_tool_round()


def current_turn_start_index(messages: list[ChatMessage]) -> int:
    for index in range(len(messages) - 1, -1, -1):
        if messages[index].role == "user":
            return index
    return 0


def current_turn_messages(
    messages: list[ChatMessage],
    *,
    start_index: int,
) -> list[ChatMessage]:
    if start_index <= 0:
        return list(messages)
    return list(messages[start_index:])


def emit_round_started(
    state: ExecutionStateMachine,
    *,
    round_kind: str,
    policy: ToolUsePolicy | None,
    tools: list[Any] | None = None,
    intent: Any | None = None,
    reason: str | None = None,
) -> None:
    payload: dict[str, Any] = {
        "round_kind": round_kind,
        "tool_names": [tool.name for tool in (tools or [])],
        "allowed_tool_names": list(getattr(policy, "allowed_tool_names", []) or []),
        "tool_use_policy_family": getattr(policy, "family", None),
        "tool_use_policy_mode": getattr(policy, "mode", None),
        "tool_use_policy_reason": (
            reason or str(getattr(policy, "reason", "") or "").strip() or None
        ),
    }
    if intent is not None:
        payload["intent_id"] = getattr(intent, "intent_id", None)
        payload["intent_kind"] = getattr(intent, "kind", None)
        payload["intent_family"] = getattr(intent, "family", None)
    state.emit_event("turn.round_started", payload)


def response_has_visible_content(response: ChatResponse | None) -> bool:
    if response is None:
        return False
    return bool(str(response.message.content or "").strip())


def intent_retry_policy_reason(
    decision: RecoveryDecision,
    retry_intent: Any | None,
) -> str:
    decision_reason = str(decision.reason or "").strip()
    if retry_intent is None:
        return decision_reason

    return decision_reason


def post_tool_completion_state(
    *,
    state: ExecutionStateMachine,
    final_output_source: str,
    ran_post_tool_follow_up: bool,
) -> str:
    if final_output_source == "recovery_evidence":
        return "recovery_evidence"
    if final_output_source == "tool_evidence_completed":
        _ = state
        return "tool_evidence_completed"
    if final_output_source == "partial_output":
        return "partial_output"
    if final_output_source == "budget_fallback":
        return "budget_fallback"
    if ran_post_tool_follow_up:
        return "llm_follow_up"
    return "assistant"


def intent_missing_args(intent: Any | None) -> list[str]:
    metadata = dict(getattr(intent, "metadata", {}) or {}) if intent is not None else {}
    raw_missing_args = metadata.get("missing_args")
    if not isinstance(raw_missing_args, list):
        return []
    return [str(item).strip() for item in raw_missing_args if str(item).strip()]


def intent_requires_clarification(intent: Any | None) -> bool:
    return bool(
        intent is not None
        and getattr(intent, "allow_text_response", False)
        and intent_missing_args(intent)
    )


def cached_shortcircuit_intent(state: ExecutionStateMachine) -> Any | None:
    if active_intent(state) is not None:
        return None
    for intent in state.intent_plan:
        cached_result = str(getattr(intent, "cached_result", "") or "").strip()
        if bool(getattr(intent, "shortcircuit", False)) and cached_result:
            return intent
    return None


_SUCCESS_FINISH_REASONS = {"", "completed", "stop", "success"}
_TOOL_CONTINUATION_FINISH_REASONS = {"function_call", "tool_calls"}
_INTERRUPTED_FINISH_REASONS = {"canceled", "cancelled"}


def _normalize_finish_reason(value: Any) -> str:
    return str(value or "").strip().lower()


def _non_success_finish_completion_reason(response: ChatResponse | None) -> str:
    finish_reason = _normalize_finish_reason(
        getattr(response, "finish_reason", None)
    )
    if not finish_reason:
        metadata = (
            dict(getattr(response, "metadata", {}) or {})
            if response is not None
            else {}
        )
        finish_reason = _normalize_finish_reason(
            metadata.get("finish_reason") or metadata.get("completion_reason")
        )
    if (
        finish_reason in _SUCCESS_FINISH_REASONS
        or finish_reason in _TOOL_CONTINUATION_FINISH_REASONS
    ):
        return ""
    if finish_reason in _INTERRUPTED_FINISH_REASONS:
        return "interrupted"
    return finish_reason


async def finalize_turn_execution(
    *,
    state: ExecutionStateMachine,
    io: TurnIOAdapter,
    messages: list[ChatMessage],
    response: ChatResponse | None,
    decision: Any | None,
    tool_results: list[ToolResult],
    total_tokens: int,
    completion_tokens_used: int,
    ran_post_tool_follow_up: bool,
    emit_round_started_cb: Callable[..., None],
) -> tuple[
    str,
    bool,
    bool,
    str,
    Literal[
        "assistant",
        "tool_evidence_completed",
        "recovery_evidence",
        "partial_output",
        "budget_fallback",
    ],
    int,
    int,
    ChatResponse,
]:
    if response is None:
        response = ChatResponse(
            message=ChatMessage(role="assistant", content=""),
            total_tokens=0,
            output_tokens=0,
        )
    output = response.message.content
    paused_for_consent = bool(
        decision is not None and decision.action == "pause_for_consent"
    )
    partial = bool(decision is not None and decision.action == "return_partial")
    non_success_finish_reason = _non_success_finish_completion_reason(response)
    if not paused_for_consent and not partial and non_success_finish_reason:
        partial = True
    _ = emit_round_started_cb
    if decision is not None and decision.action in {
        "pause_for_consent",
        "return_partial",
    }:
        recovery_event = {
            "kind": (
                "partial_output"
                if decision.action == "return_partial"
                else "pause_for_consent"
            ),
            "action": decision.action,
            "target_intent_id": decision.target_intent_id,
            "reason": decision.reason,
        }
        state.recovery_events.append(recovery_event)
        decision.metadata = dict(decision.metadata or {})
        decision.metadata["source_recovery_event_seq"] = len(state.recovery_events)
        state.recovery_history.append(decision)
    completion_reason = "completed"
    final_output_source: Literal[
        "assistant",
        "tool_evidence_completed",
        "recovery_evidence",
        "partial_output",
        "budget_fallback",
    ] = "assistant"
    if paused_for_consent:
        state.transition("awaiting_consent")
        completion_reason = decision.reason or "pause_for_consent"
        RecoveryManager.ensure_latest_assistant_pending_consent(
            messages,
            RecoveryManager.pending_consent_payload_from_decision(decision),
        )
    elif partial:
        state.transition("partial_exit")
        completion_reason = (
            (decision.reason if decision is not None else "")
            or non_success_finish_reason
            or "return_partial"
        )
        output, total_tokens, completion_tokens_used = await io.finalize_partial_output(
            messages=messages,
            response=response,
            state=state,
            tool_results=tool_results,
            reason=completion_reason,
            total_tokens=total_tokens,
            completion_tokens_used=completion_tokens_used,
        )
        final_output_source = (
            "budget_fallback"
            if state.provider_failure_kind == "budget_exit"
            else "partial_output"
        )
    else:
        state.transition("completed")
        if not str(output or "").strip() and state.intent_plan:
            (
                output,
                total_tokens,
                completion_tokens_used,
            ) = await io.finalize_completed_output(
                messages=messages,
                response=response,
                state=state,
                tool_results=tool_results,
                reason=completion_reason,
                total_tokens=total_tokens,
                completion_tokens_used=completion_tokens_used,
            )
            if str(output or "").strip():
                final_output_source = "tool_evidence_completed"
                if state.preparation_diagnostics.get(
                    "deterministic_shortcircuit_tool_call"
                ):
                    final_output_source = "recovery_evidence"

    state.preparation_diagnostics["final_output_source"] = final_output_source
    state.preparation_diagnostics["post_tool_completion_state"] = (
        post_tool_completion_state(
            state=state,
            final_output_source=final_output_source,
            ran_post_tool_follow_up=ran_post_tool_follow_up,
        )
    )
    trusted_final_output = bool(str(output or "").strip()) and (
        is_trusted_assistant_final_output_source(final_output_source)
    )
    if (
        not partial
        and not paused_for_consent
        and not trusted_final_output
        and final_output_source in {"tool_evidence_completed", "budget_fallback"}
    ):
        fallback_output = build_untrusted_final_output_fallback()
        state.preparation_diagnostics["stripped_untrusted_final_output"] = True
        state.preparation_diagnostics["untrusted_final_output_fallback_applied"] = True
        output = fallback_output
        final_output_source = "platform_fallback"
        state.preparation_diagnostics["final_output_source"] = final_output_source
        if response is not None and getattr(response, "message", None) is not None:
            response.message.content = fallback_output

    return (
        str(output or ""),
        partial,
        paused_for_consent,
        completion_reason,
        final_output_source,
        total_tokens,
        completion_tokens_used,
        response,
    )


@dataclass
class _TurnRunLoop:
    """Keep turn-local mutable state inside one private owner during execution."""

    state: ExecutionStateMachine
    io: TurnIOAdapter
    prep: Any
    request: Any
    agent: Any
    messages: list[ChatMessage] = field(init=False)
    turn_start_index: int = field(init=False)
    tools: list[Any] = field(init=False)
    active_policy: ToolUsePolicy | None = field(init=False)
    active_tools: list[Any] = field(init=False)
    intent: Any | None = field(init=False)
    response: ChatResponse | None = field(init=False, default=None)
    tool_results: list[ToolResult] = field(init=False, default_factory=list)
    total_tokens: int = field(init=False, default=0)
    completion_tokens_used: int = field(init=False, default=0)
    decision: RecoveryDecision | None = field(init=False, default=None)
    ran_post_tool_follow_up: bool = field(init=False, default=False)

    def __post_init__(self) -> None:
        self.messages = self.prep.messages
        self.turn_start_index = current_turn_start_index(self.messages)
        self.tools = list(self.prep.tools or [])
        # ReAct: 使用全集工具，不再按 intent 限制工具选择
        # Intent 暂时保留用于确定性短路和诊断（待 #50-C 清理）
        self.active_tools = self.tools
        self.active_policy = self.prep.tool_use_policy
        # 保留 intent 用于确定性短路检查，但不用于工具选择
        self.intent = active_intent(self.state)

    @property
    def turn_messages(self) -> list[ChatMessage]:
        return current_turn_messages(
            self.messages,
            start_index=self.turn_start_index,
        )

    def emit_round(self, **kwargs: Any) -> None:
        emit_round_started(self.state, **kwargs)

    def emit_round_started(
        self,
        state: ExecutionStateMachine,
        **kwargs: Any,
    ) -> None:
        emit_round_started(state, **kwargs)

    def _apply_model_round(
        self,
        model_round: ModelRoundResult,
        *,
        replace_totals: bool,
    ) -> None:
        self.response = model_round.response
        total_tokens = int(model_round.total_tokens or 0)
        completion_tokens_used = int(model_round.completion_tokens_used or 0)
        if replace_totals:
            self.total_tokens = total_tokens
            self.completion_tokens_used = completion_tokens_used
        else:
            self.total_tokens += total_tokens
            self.completion_tokens_used += completion_tokens_used
        self.state.register_completion_tokens(self.completion_tokens_used)

    def _register_budget_exit_if_needed(self) -> None:
        budget_exit_reason = self.state.budget_exit_reason()
        if not budget_exit_reason:
            return
        self.state.register_provider_failure(
            kind="budget_exit",
            event={"kind": "budget_exit", "reason": budget_exit_reason},
        )

    def _decide_recovery(self) -> RecoveryDecision | None:
        return RecoveryManager.decide(
            self.state.intent_plan,
            budget=self.state.budget,
            provider_failure_kind=self.state.provider_failure_kind,
        )

    def _apply_cached_shortcircuit(self, intent: Any) -> None:
        cached_result = str(getattr(intent, "cached_result", "") or "").strip()
        intent.status = "completed"
        intent.metadata = dict(getattr(intent, "metadata", {}) or {})
        intent.metadata["cached_shortcircuit_completed"] = True
        self.state.preparation_diagnostics["cached_shortcircuit"] = True
        self.state.preparation_diagnostics["cached_shortcircuit_intent_kind"] = getattr(
            intent, "kind", None
        )
        self.response = ChatResponse(
            message=ChatMessage(role="assistant", content=cached_result),
            total_tokens=0,
            output_tokens=0,
            finish_reason="stop",
            metadata={
                "cached_shortcircuit": True,
                "cached_shortcircuit_intent_kind": getattr(intent, "kind", None),
            },
        )

    def _apply_deterministic_tool_shortcircuit(self) -> bool:
        synthetic_response = build_shortcircuit_fallback_response(
            intent=self.intent,
            response=None,
            tools=self.active_tools,
            total_tokens=0,
            completion_tokens_used=0,
        )
        if synthetic_response is None:
            return False

        synthetic_response.metadata = dict(synthetic_response.metadata or {})
        synthetic_response.metadata["deterministic_shortcircuit_tool_call"] = True
        self.state.preparation_diagnostics["deterministic_shortcircuit_tool_call"] = (
            True
        )
        self.state.preparation_diagnostics["deterministic_shortcircuit_intent_kind"] = (
            getattr(self.intent, "kind", None)
        )
        self.response = synthetic_response
        return True

    async def _run_missing_args_clarification(self, intent: Any) -> None:
        missing_args = intent_missing_args(intent)
        decision = RecoveryDecision(
            action="retry_intent",
            target_intent_id=getattr(intent, "intent_id", None),
            retry_family=getattr(intent, "family", None),
            completed_intent_ids=[
                item.intent_id
                for item in self.state.intent_plan
                if item.status == "completed"
            ],
            unfinished_intent_ids=[
                item.intent_id
                for item in self.state.intent_plan
                if item.status not in {"completed", "skipped"}
            ],
            reason="missing_args_clarification",
            metadata={"missing_args": missing_args},
        )
        self.state.register_retry(decision)
        self.messages.append(
            RecoveryManager.build_missing_args_clarification_message(
                decision=decision,
                intents=self.state.intent_plan,
                missing_args=missing_args,
            )
        )
        clarification_policy = ToolUsePolicy(
            family="none",
            mode="none",
            allowed_tool_names=[],
            retry_on_contract_breach=False,
            reason="missing_args_clarification",
        )
        self.emit_round(
            round_kind="intent_retry",
            policy=clarification_policy,
            tools=[],
            intent=intent,
            reason="missing_args_clarification",
        )
        clarification_round = await self.io.call_llm(
            messages=self.messages,
            tools=None,
            tool_use_policy=clarification_policy,
            breach_retry_result="intent_retry",
        )
        self._apply_model_round(clarification_round, replace_totals=False)
        intent.status = "completed"
        intent.metadata = dict(getattr(intent, "metadata", {}) or {})
        intent.metadata["clarification_requested"] = True

    async def run(self) -> TurnExecutionResult:
        # Phase 1: 短路检查（保留确定性短路）
        shortcircuit_applied = await self._try_shortcircuit()

        # Phase 2: ReAct 循环（如果是短路且有 tool_calls，则执行工具后结束）
        if shortcircuit_applied:
            # 确定性短路设置了 synthetic response，需要执行工具
            if getattr(self.response, "tool_calls", None):
                await self._execute_tool_batch_in_loop()
            return await self._finalize_result()

        await self._run_react_loop()

        # Phase 3: 结果整理
        return await self._finalize_result()

    async def _try_shortcircuit(self) -> bool:
        """尝试确定性短路，返回 True 表示已短路。

        保留的短路类型：
        - cached_shortcircuit: 缓存结果直接返回
        - deterministic_tool_shortcircuit: time_query / confirmation_replay / memory_*
        - missing_args_clarification: 缺失参数澄清
        """
        # 1. 缓存短路
        shortcircuit_intent = cached_shortcircuit_intent(self.state)
        if shortcircuit_intent is not None:
            self._apply_cached_shortcircuit(shortcircuit_intent)
            return True

        # 2. 确定性工具短路（time_query/confirmation_replay/memory_save/memory_recall）
        if self._apply_deterministic_tool_shortcircuit():
            return True

        # 3. 缺失参数澄清（暂时保留，待 #50-C 清理）
        if intent_requires_clarification(self.intent):
            await self._run_missing_args_clarification(self.intent)
            return True

        return False

    def _max_tool_rounds(self) -> int:
        """获取最大工具轮次数。"""
        if self.state.budget is None or self.state.budget.max_tool_rounds <= 0:
            return 6  # 默认值（TODO: 后续从智能体配置读取）
        return int(self.state.budget.max_tool_rounds)

    def _handle_budget_exit(self, reason: str) -> None:
        """处理预算耗尽情况。"""
        self.state.register_provider_failure(
            kind="budget_exit",
            event={"kind": "budget_exit", "reason": reason},
        )
        # 构建空响应
        self.response = ChatResponse(
            message=ChatMessage(role="assistant", content=""),
            total_tokens=0,
            output_tokens=0,
        )
        # 设置 decision 为 partial exit
        self.decision = RecoveryDecision(
            action="return_partial",
            reason=reason,
            provider_failure_kind="budget_exit",
        )

    async def _run_react_loop(self) -> None:
        """LLM 带全集工具循环调用，直到纯文本回复或预算耗尽。

        ReAct 循环流程：
        1. 检查预算
        2. 调用 LLM（带全集工具）
        3. 如果有 tool_calls：执行工具 → 结果回写 → 继续循环
        4. 如果无 tool_calls：检查 consent gate → 纯文本回复，循环结束
        """
        max_rounds = self._max_tool_rounds()

        # 初始预算检查
        initial_budget_exit = self.state.budget_exit_reason()
        if initial_budget_exit:
            self._handle_budget_exit(initial_budget_exit)
            return

        for round_idx in range(max_rounds):
            # 预算检查
            budget_exit = self.state.budget_exit_reason()
            if budget_exit:
                self._handle_budget_exit(budget_exit)
                return

            # 发出 round 事件
            self.emit_round(
                round_kind="react_round",
                policy=self.active_policy,
                tools=self.tools,  # 全集工具
                reason=f"react_round_{round_idx}",
            )

            # ReAct 第 2 轮起 tool_choice 改为 auto，允许 LLM 给出纯文本回复退出循环
            round_policy = (
                self.active_policy
                if round_idx == 0
                else ToolUsePolicy(
                    family=self.active_policy.family,
                    mode="auto",
                    allowed_tool_names=self.active_policy.allowed_tool_names,
                    retry_on_contract_breach=self.active_policy.retry_on_contract_breach,
                    reason=f"{self.active_policy.reason}:react_round_{round_idx}_auto",
                )
            )

            # LLM 调用（带全集工具）
            model_round = await self.io.call_llm(
                messages=self.messages,
                tools=self.tools or None,  # 不再按 intent 限制
                tool_use_policy=round_policy,
                react_round_index=round_idx,
            )
            self._apply_model_round(model_round, replace_totals=(round_idx == 0))

            # 无 tool_calls → 检查 consent gate 然后结束
            if not getattr(self.response, "tool_calls", None):
                # 在纯文本回复后检查 consent gate（可能从恢复场景来）
                await self._check_consent_gate()
                return

            # 确认门控检查（工具执行前检查）
            if await self._check_consent_gate():
                return  # 暂停等待用户确认

            # 执行工具批次
            await self._execute_tool_batch_in_loop()

            # 工具执行后再次检查确认门控
            if await self._check_consent_gate():
                return

            # 注册工具轮次
            self.state.register_tool_round()

        # 循环结束但仍有 tool_calls，说明预算耗尽
        budget_exit = self.state.budget_exit_reason() or "tool_round_budget_exceeded"
        self._handle_budget_exit(budget_exit)

    async def _execute_tool_batch_in_loop(self) -> None:
        """在 ReAct 循环内执行工具批次。"""
        (
            self.response,
            extra_tool_results,
            self.total_tokens,
            self.completion_tokens_used,
        ) = await execute_tool_batch(
            state=self.state,
            io=self.io,
            response=self.response,
            tools=self.tools,  # 全集
            all_tools=self.prep.all_tools or self.tools,
            messages=self.messages,
            turn_messages=self.turn_messages,
            tool_use_policy=self.active_policy,
            input_variables=self.request.input_variables,
            total_tokens=self.total_tokens,
            completion_tokens_used=self.completion_tokens_used,
        )
        self.tool_results.extend(extra_tool_results)

    async def _check_consent_gate(self) -> bool:
        """检查是否需要用户确认，返回 True 表示已暂停。

        当工具执行需要用户确认时（consent_mode="ask"），
        构建 pause_for_consent decision 并暂停执行。
        复用 RecoveryManager.decide 获取 decision。
        """
        decision = RecoveryManager.decide(
            self.state.intent_plan,
            budget=self.state.budget,
            provider_failure_kind=self.state.provider_failure_kind,
        )
        if decision is not None and decision.action == "pause_for_consent":
            self.decision = decision
            return True
        return False

    async def _run_initial_round(self) -> None:
        initial_budget_exit = self.state.budget_exit_reason()
        if initial_budget_exit:
            self.state.register_provider_failure(
                kind="budget_exit",
                event={"kind": "budget_exit", "reason": initial_budget_exit},
            )
            self.response = ChatResponse(
                message=ChatMessage(role="assistant", content=""),
                total_tokens=0,
                output_tokens=0,
            )
            return

        if intent_requires_clarification(self.intent):
            await self._run_missing_args_clarification(self.intent)
            return

        shortcircuit_intent = cached_shortcircuit_intent(self.state)
        if shortcircuit_intent is not None:
            self._apply_cached_shortcircuit(shortcircuit_intent)
            return

        if self._apply_deterministic_tool_shortcircuit():
            return

        model_round = await self.io.call_llm(
            messages=self.messages,
            tools=self.active_tools or None,
            tool_use_policy=self.active_policy,
        )
        self._apply_model_round(model_round, replace_totals=True)

    async def _run_tool_batch_or_update_intents(self) -> None:
        (
            self.response,
            self.tool_results,
            self.total_tokens,
            self.completion_tokens_used,
        ) = await run_tool_batch_or_update_intents(
            state=self.state,
            io=self.io,
            intent=self.intent,
            response=self.response,
            tools=self.active_tools,
            all_tools=self.prep.all_tools or self.tools,
            messages=self.messages,
            turn_messages=self.turn_messages,
            tool_use_policy=self.active_policy,
            input_variables=self.request.input_variables,
            total_tokens=self.total_tokens,
            completion_tokens_used=self.completion_tokens_used,
        )

    async def _run_contract_retry_round(self) -> None:
        (
            self.response,
            self.tool_results,
            self.total_tokens,
            self.completion_tokens_used,
            self.active_policy,
            self.active_tools,
        ) = await run_contract_retry_round(
            state=self.state,
            io=self.io,
            agent=self.agent,
            request=self.request,
            prep=self.prep,
            messages=self.messages,
            turn_messages=self.turn_messages,
            response=self.response,
            active_policy=self.active_policy,
            active_intent=self.intent,
            active_tools=self.active_tools,
            tools=self.tools,
            tool_results=self.tool_results,
            total_tokens=self.total_tokens,
            completion_tokens_used=self.completion_tokens_used,
            emit_round_started=self.emit_round_started,
        )

    async def _run_intent_retry_loop(self) -> None:
        self._register_budget_exit_if_needed()
        self.decision = self._decide_recovery()
        while self.decision is not None and self.decision.action == "retry_intent":
            decision = self.decision
            retry_intent = next(
                (
                    intent
                    for intent in self.state.intent_plan
                    if intent.intent_id == decision.target_intent_id
                ),
                None,
            )
            if intent_requires_clarification(retry_intent):
                await self._run_missing_args_clarification(retry_intent)
                self.decision = self._decide_recovery()
                continue

            self.state.register_retry(decision)
            self.messages.append(
                RecoveryManager.build_recovery_message(
                    decision=decision,
                    intents=self.state.intent_plan,
                )
            )
            retry_tools = self.io.restrict_tools_to_names(
                self.prep.all_tools or self.tools,
                decision.allowed_tool_names,
            )
            retry_policy = ToolUsePolicy(
                family=decision.retry_family or self.prep.tool_use_policy.family,
                mode="required",
                allowed_tool_names=decision.allowed_tool_names
                or [tool.name for tool in retry_tools],
                retry_on_contract_breach=False,
                reason=intent_retry_policy_reason(decision, retry_intent),
            )
            self.emit_round(
                round_kind="intent_retry",
                policy=retry_policy,
                tools=retry_tools,
                intent=retry_intent,
                reason=retry_policy.reason or "intent_retry",
            )
            if retry_policy.mode == "required" and retry_tools:
                self.io.log_tool_contract_diagnostics(
                    agent=self.agent,
                    messages=self.messages,
                    response=self.response,
                    tools=retry_tools,
                    policy=retry_policy,
                    conversation_id=self.request.conversation_id,
                    breach_type=retry_policy.reason or "intent_retry",
                    retry_result="retrying",
                    continuation=self.prep.continuation_context,
                )
            retry_round = await self.io.call_llm(
                messages=self.messages,
                tools=retry_tools or None,
                tool_use_policy=retry_policy,
                breach_retry_result="intent_retry",
            )
            self._apply_model_round(retry_round, replace_totals=False)
            if getattr(self.response, "tool_calls", None) and retry_tools:
                (
                    self.response,
                    extra_tool_results,
                    self.total_tokens,
                    self.completion_tokens_used,
                ) = await execute_tool_batch(
                    state=self.state,
                    io=self.io,
                    response=self.response,
                    tools=retry_tools,
                    all_tools=self.prep.all_tools or self.tools,
                    messages=self.messages,
                    turn_messages=self.turn_messages,
                    tool_use_policy=retry_policy,
                    input_variables=self.request.input_variables,
                    total_tokens=self.total_tokens,
                    completion_tokens_used=self.completion_tokens_used,
                )
                self.tool_results.extend(extra_tool_results)
            if self.state.intent_plan and not getattr(
                self.response, "tool_calls", None
            ):
                self.state.intent_plan = RecoveryManager.update_intent_statuses(
                    self.state.intent_plan,
                    messages=self.messages,
                    turn_messages=self.turn_messages,
                    tool_results=[],
                )
                if (
                    retry_policy.mode == "required"
                    and retry_tools
                    and self.response is not None
                ):
                    self.io.log_tool_contract_diagnostics(
                        agent=self.agent,
                        messages=self.messages,
                        response=self.response,
                        tools=retry_tools,
                        policy=retry_policy,
                        conversation_id=self.request.conversation_id,
                        breach_type=decision.reason or "intent_retry",
                        retry_result="failed",
                        continuation=self.prep.continuation_context,
                    )
            self._register_budget_exit_if_needed()
            self.decision = self._decide_recovery()

    def _should_run_post_tool_follow_up_round(self) -> bool:
        if self.state.preparation_diagnostics.get(
            "deterministic_shortcircuit_tool_call"
        ):
            # confirmation_replay shortcircuits the LLM for the tool call but
            # should still get a follow-up round to generate a natural summary.
            # confirmation_replay 跳过了工具调用前的 LLM，但仍需后续摘要轮次。
            if (
                self.state.preparation_diagnostics.get(
                    "deterministic_shortcircuit_intent_kind"
                )
                != "confirmation_replay"
            ):
                return False
        return bool(
            self.decision is None
            and self.tool_results
            and active_intent(self.state) is None
            and not response_has_visible_content(self.response)
            and not bool(getattr(self.response, "tool_calls", None))
        )

    async def _maybe_run_post_tool_follow_up_round(self) -> None:
        if not self._should_run_post_tool_follow_up_round():
            return

        self.ran_post_tool_follow_up = True
        follow_up_policy = ToolUsePolicy(
            family="none",
            mode="none",
            allowed_tool_names=[],
            retry_on_contract_breach=False,
            reason="post_tool_follow_up",
        )
        self.emit_round(
            round_kind="normal_follow_up_round",
            policy=follow_up_policy,
            tools=[],
            reason="post_tool_follow_up",
        )
        follow_up_round = await self.io.call_llm(
            messages=self.messages,
            tools=None,
            tool_use_policy=follow_up_policy,
            breach_retry_result="normal_follow_up_round",
        )
        self._apply_model_round(follow_up_round, replace_totals=False)

    async def _finalize_result(self) -> TurnExecutionResult:
        (
            output,
            partial,
            paused_for_consent,
            completion_reason,
            final_output_source,
            self.total_tokens,
            self.completion_tokens_used,
            self.response,
        ) = await finalize_turn_execution(
            state=self.state,
            io=self.io,
            messages=self.messages,
            response=self.response,
            decision=self.decision,
            tool_results=self.tool_results,
            total_tokens=self.total_tokens,
            completion_tokens_used=self.completion_tokens_used,
            ran_post_tool_follow_up=self.ran_post_tool_follow_up,
            emit_round_started_cb=self.emit_round_started,
        )

        return TurnExecutionResult(
            output=str(output or ""),
            total_tokens=int(self.total_tokens or 0),
            completion_tokens_used=int(self.completion_tokens_used or 0),
            tool_results=self.tool_results,
            response=self.response,
            partial=partial,
            paused_for_consent=paused_for_consent,
            completion_reason=completion_reason,
            final_output_source=final_output_source,
            action_buttons=None,
        )


class TurnExecutor:
    """State-machine-driven execution entrypoint shared by sync/stream paths."""

    @staticmethod
    def _scope_tools_to_active_intent(
        *,
        state: ExecutionStateMachine,
        tools: list[Any],
        policy: ToolUsePolicy | None,
        io: TurnIOAdapter,
    ) -> tuple[list[Any], ToolUsePolicy | None, Any | None]:
        intent = active_intent(state)
        if intent is None or policy is None:
            return list(tools), policy, intent

        allowed_tool_names = list(
            intent.allowed_tool_names or policy.allowed_tool_names or []
        )
        if not allowed_tool_names:
            return list(tools), policy, intent

        scoped_tools = list(io.restrict_tools_to_names(list(tools), allowed_tool_names))
        if not scoped_tools:
            return [], policy, intent

        scoped_tool_names = [tool.name for tool in scoped_tools]
        if scoped_tool_names == list(policy.allowed_tool_names or []):
            return scoped_tools, policy, intent

        return (
            scoped_tools,
            ToolUsePolicy(
                family=intent.family or policy.family,
                mode=policy.mode,
                allowed_tool_names=scoped_tool_names,
                retry_on_contract_breach=policy.retry_on_contract_breach,
                reason=policy.reason or f"intent:{intent.kind}",
            ),
            intent,
        )

    @staticmethod
    async def run(
        *,
        state: ExecutionStateMachine,
        io: TurnIOAdapter,
        prep: Any,
        request: Any,
        agent: Any,
    ) -> TurnExecutionResult:
        """Run one turn using a shared orchestration loop (sync path ready)."""
        return await _TurnRunLoop(
            state=state,
            io=io,
            prep=prep,
            request=request,
            agent=agent,
        ).run()


__all__ = [
    "ModelRoundResult",
    "RecoveryManager",
    "ToolBatchResult",
    "TurnExecutionResult",
    "TurnIOAdapter",
    "TurnExecutor",
    "assistant_tool_round_count",
    "finalize_turn_execution",
    "register_tool_round_delta",
]
