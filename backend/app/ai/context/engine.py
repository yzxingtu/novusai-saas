"""
Context engine abstraction / 上下文引擎抽象.
Provides a first-stage context lifecycle abstraction without changing current runtime truth.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from app.ai.context import (
    compaction_support,
    engine_runtime_support,
    prompt_addition_support,
)
from app.ai.context.assembly_initial_support import (
    PromptBridge,
    assemble_initial_context_state,
)
from app.ai.context.assembly_result_support import (
    ContextDiagnosticsInputs,
    build_context_assembly_payload,
    build_context_diagnostics,
    merge_capability_finalization,
)
from app.ai.context.budget_support import (
    append_budgeted_addition,
    resolve_context_budget,
    trim_text_to_token_limit,
)
from app.ai.context.contributors import MemoryContributor, RAGContributor
from app.ai.context.decision_helpers import (
    extract_last_user_text,
)
from app.ai.context.orchestrator import ContextPipelineOrchestrator
from app.ai.context.pruning import TransientPruner
from app.ai.runtime.contracts import (
    CapabilityBundle,
    ContextCapabilityBridge,
    ContextCapabilityInputs,
)
from app.ai.skills.activation import apply_turn_skill_activation
from app.ai.types import ChatMessage
from app.core.logging import LogManager

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.ai.context.long_term_memory import LongTermMemoryProvider
    from app.ai.engine.types import ExecutionRequest
    from app.ai.skills.resolver import SkillResolveResult
    from app.models.ai.agent import Agent


logger = LogManager.get_logger("ai.context_engine")


def get_context_capability_bridge() -> ContextCapabilityBridge:
    return engine_runtime_support.get_context_capability_bridge()


async def load_agent_kb_bindings(
    db: Any,
    agent_id: int,
    tenant_id: int | None,
) -> tuple[list[int] | None, dict[int, float]]:
    return await engine_runtime_support.load_agent_kb_bindings(
        db,
        agent_id,
        tenant_id,
    )


def get_long_term_memory_provider(
    *,
    db: Any,
    tenant_id: int,
) -> LongTermMemoryProvider:
    return engine_runtime_support.get_long_term_memory_provider(
        db=db,
        tenant_id=tenant_id,
    )


@dataclass
class ContextAssembly:
    """Assembled context payload / 已组装的上下文载荷"""

    messages: list[ChatMessage] = field(default_factory=list)
    estimated_tokens: int = 0
    system_prompt_additions: list[str] = field(default_factory=list)
    diagnostics: dict[str, Any] = field(default_factory=dict)
    rag_sources: list[dict[str, Any]] | None = None
    rag_source_kinds: list[str] = field(default_factory=list)
    compact_summary: str | None = None
    prune_stats: dict[str, Any] | None = None
    memory_recall_slice: dict[str, Any] | None = None
    context_compacted: bool = False
    memory_flush_triggered: bool = False
    memory_recalled: bool = False
    capability_bundle: CapabilityBundle | None = None


class ContextEngine(ABC):
    """Context engine interface / 上下文引擎接口"""

    @abstractmethod
    async def ingest(self, agent: Agent, request: ExecutionRequest) -> None:
        """Ingest runtime state before assembly / 在 assemble 前接收运行态输入"""

    @abstractmethod
    async def assemble(
        self,
        agent: Agent,
        request: ExecutionRequest,
        skill_result: SkillResolveResult | None = None,
    ) -> ContextAssembly:
        """Assemble model context / 组装模型上下文"""

    @abstractmethod
    async def compact(self, agent: Agent, request: ExecutionRequest) -> None:
        """Compact older history / 压缩旧上下文"""

    @abstractmethod
    async def after_turn(
        self,
        agent: Agent,
        request: ExecutionRequest,
        result: Any,
    ) -> None:
        """Post-turn hook / 轮次结束后钩子"""


class ConversationContextEngine(ContextEngine):
    """
    Default conversation context implementation / 默认对话上下文实现。

    Preserves current behavior while centralizing system prompt assembly, RAG
    injection, and transient prompt pruning.
    在保持当前行为的同时，收口 system prompt 组装、RAG 注入和 prompt 临时裁剪。
    """

    @staticmethod
    def _should_run_memory_vector_recall(user_text: str) -> bool:
        return engine_runtime_support.should_run_memory_vector_recall(user_text)

    def __init__(self, db: AsyncSession, base_engine: PromptBridge) -> None:
        self.db = db
        self.base_engine = base_engine
        self.pruner = TransientPruner()
        self.rag_contributor = RAGContributor()
        self.memory_contributor = MemoryContributor()
        self.capability_bridge = get_context_capability_bridge()
        # True after assemble() persisted a compaction snapshot; compact() skips duplicate persist.
        self._compaction_snapshot_written_in_assemble = False

    async def ingest(self, agent: Agent, request: ExecutionRequest) -> None:
        _ = agent, request

    async def assemble(
        self,
        agent: Agent,
        request: ExecutionRequest,
        skill_result: SkillResolveResult | None = None,
    ) -> ContextAssembly:
        self._compaction_snapshot_written_in_assemble = False
        from app.ai.engine.intent_planner import IntentPlanner

        initial_state = await assemble_initial_context_state(
            db=self.db,
            agent=agent,
            request=request,
            skill_result=skill_result,
            prompt_bridge=self.base_engine,
            capability_bridge=self.capability_bridge,
            load_agent_kb_bindings_fn=load_agent_kb_bindings,
            intent_plan_callable=IntentPlanner.plan_turn,
            intent_flag_resolver=(
                lambda intent_plan, active_request: (
                    ContextPipelineOrchestrator.compute_intent_flags(
                        intent_plan,
                        active_request,
                    ).to_dict()
                )
            ),
        )
        messages = list(initial_state.messages or [])
        requested_kb_ids = list(initial_state.kb_selection.requested_kb_ids or [])
        merged_kb_ids = list(initial_state.kb_selection.merged_kb_ids or [])
        dropped_kb_ids = list(initial_state.kb_selection.dropped_kb_ids or [])
        agent_kb_weights = dict(initial_state.kb_selection.agent_kb_weights or {})
        runtime_model_capabilities = dict(
            initial_state.runtime_model_capabilities or {}
        )
        intent_plan = list(initial_state.intent_plan or [])
        intent_flags = dict(initial_state.intent_flags or {})
        capability_injection_decision = dict(
            initial_state.capability_injection_decision or {}
        )
        apply_turn_skill_activation(
            skill_result=skill_result,
            request=request,
            intent_flags=intent_flags,
        )
        rag_sources = None
        rag_source_kinds: list[str] = []

        rag_contribution = await self.rag_contributor.contribute(
            db=self.db,
            agent=agent,
            tenant_id=request.tenant_id,
            messages=messages,
            kb_ids=list(merged_kb_ids or []),
            rag_config=agent.rag_config or {},
            kb_weights=agent_kb_weights,
            enabled=(
                not intent_flags["all_shortcircuit"]
                and intent_flags["has_knowledge_intent"]
            ),
        )
        messages = list(rag_contribution.messages or messages)
        rag_sources = rag_contribution.rag_sources
        rag_source_kinds = list(rag_contribution.rag_source_kinds or [])
        capability_injection_decision["kb_injected"] = bool(
            rag_contribution.kb_injected
        )

        context_config = getattr(agent, "context_config", None) or {}
        long_term_memory_enabled = bool(request.long_term_memory_enabled)
        compact_threshold_tokens = int(
            context_config.get("compact_threshold_tokens", 0) or 0
        )
        compact_keep_last_assistants = int(
            context_config.get("compact_keep_last_assistants", 3) or 3
        )
        compact_max_summary_chars = int(
            context_config.get("compact_max_summary_chars", 1600) or 1600
        )
        context_budget = resolve_context_budget(context_config)

        compact_summary: str | None = None
        system_prompt_additions: list[str] = []
        budget_usage: dict[str, Any] = {
            "used_tokens": 0,
            "trimmed_sections": [],
            "skipped_sections": [],
        }
        context_compacted = False
        memory_recalled = False
        memory_recall_slice: dict[str, Any] | None = None
        dynamic_capability_awareness_enabled = False
        capability_awareness_categories: list[str] = []
        capability_awareness_error: str | None = None
        compaction_source_tokens = compaction_support.messages_token_estimate(messages)
        existing_snapshot = await self._load_compaction_snapshot(request)
        visible_output_locale_hint = (
            prompt_addition_support.build_visible_output_locale_hint(request)
        )
        if visible_output_locale_hint:
            self._append_budgeted_addition(
                additions=system_prompt_additions,
                text=visible_output_locale_hint,
                category="visible_output_locale",
                per_item_token_limit=context_budget["page_locale_tokens"],
                total_token_limit=context_budget["system_additions_tokens"],
                budget_usage=budget_usage,
            )
        capability_awareness = await self.capability_bridge.compute_awareness(
            db=self.db,
            agent=agent,
            request=request,
            skill_result=skill_result,
            intent_flags=intent_flags,
            knowledge_base_ids=list(merged_kb_ids or []),
            long_term_memory_enabled=long_term_memory_enabled,
        )
        dynamic_capability_awareness_enabled = bool(capability_awareness.enabled)
        capability_awareness_categories = list(capability_awareness.categories or [])
        capability_awareness_error = capability_awareness.error

        split_index = compaction_support.compaction_split_index(
            messages,
            keep_last_assistants=compact_keep_last_assistants,
            pruner=self.pruner,
        )
        if split_index is not None and split_index > 1:
            prefix = messages[1:split_index]
            suffix = messages[split_index:]
            if existing_snapshot and isinstance(existing_snapshot.get("summary"), str):
                compact_summary = existing_snapshot["summary"].strip() or None

            if (
                compact_threshold_tokens > 0
                and compaction_source_tokens > compact_threshold_tokens
            ):
                rebuilt_summary = self._build_compact_summary(
                    prefix,
                    max_chars=compact_max_summary_chars,
                )
                if rebuilt_summary:
                    compact_summary = rebuilt_summary
                    await self._persist_compaction_snapshot(
                        request=request,
                        summary=rebuilt_summary,
                        source_message_count=len(prefix),
                        source_token_estimate=compaction_support.messages_token_estimate(
                            prefix
                        ),
                    )
                    self._compaction_snapshot_written_in_assemble = True

            if compact_summary:
                context_compacted = True
                block = "[COMPACTED CONTEXT SUMMARY]\n" + compact_summary
                self._append_budgeted_addition(
                    additions=system_prompt_additions,
                    text=block,
                    category="compacted_context_summary",
                    per_item_token_limit=context_budget["compact_summary_tokens"],
                    total_token_limit=context_budget["system_additions_tokens"],
                    budget_usage=budget_usage,
                )
                messages = [messages[0], *suffix]

        current_user_text = extract_last_user_text(messages)
        memory_contribution = await self.memory_contributor.contribute(
            db=self.db,
            enabled=bool(
                intent_flags["memory_context_enabled"] and long_term_memory_enabled
            ),
            user_id=request.user_id,
            tenant_id=request.tenant_id,
            agent_id=agent.id,
            current_user_text=current_user_text,
            should_run_memory_profile=bool(intent_flags["should_run_memory_profile"]),
            should_run_memory_vector_recall=bool(
                intent_flags["should_run_memory_vector_recall"]
            ),
            should_run_vector_recall_for_text=self._should_run_memory_vector_recall,
            provider_factory=get_long_term_memory_provider,
            append_budgeted_addition=self._append_budgeted_addition,
            additions=system_prompt_additions,
            budget_usage=budget_usage,
            context_budget=context_budget,
            build_profile_snapshot_block=(
                prompt_addition_support.build_profile_snapshot_block
            ),
            build_memory_recall_block=(
                prompt_addition_support.build_memory_recall_block
            ),
        )
        memory_recalled = bool(memory_contribution.memory_recalled)
        if memory_contribution.memory_recall_slice:
            memory_recall_slice = dict(memory_contribution.memory_recall_slice)
        capability_injection_decision["memory_injected"] = bool(
            capability_injection_decision["memory_injected"]
            or memory_contribution.memory_injected
        )

        messages = compaction_support.inject_system_prompt_additions(
            messages,
            system_prompt_additions,
        )

        estimated_tokens_before_prune = compaction_support.messages_token_estimate(
            messages
        )
        pruned_messages, prune_stats = self.pruner.prune(messages)
        estimated_tokens = compaction_support.messages_token_estimate(pruned_messages)
        diagnostics = build_context_diagnostics(
            ContextDiagnosticsInputs(
                prune_stats=prune_stats,
                compaction_source_tokens=compaction_source_tokens,
                estimated_tokens_before_prune=estimated_tokens_before_prune,
                estimated_tokens_after_prune=estimated_tokens,
                context_compacted=context_compacted,
                memory_recalled=memory_recalled,
                intent_plan=intent_plan,
                intent_flags=intent_flags,
                dynamic_capability_awareness_enabled=(
                    dynamic_capability_awareness_enabled
                ),
                capability_awareness_categories=capability_awareness_categories,
                capability_awareness_error=capability_awareness_error,
                requested_knowledge_base_ids=requested_kb_ids,
                effective_knowledge_base_ids=merged_kb_ids,
                dropped_knowledge_base_ids=dropped_kb_ids,
                context_budget=context_budget,
                budget_usage=budget_usage,
                capability_injection_decision=capability_injection_decision,
            )
        )

        capability_inputs = ContextCapabilityInputs(
            knowledge_base_ids=list(merged_kb_ids or []),
            requested_knowledge_base_ids=requested_kb_ids,
            dropped_knowledge_base_ids=dropped_kb_ids,
            rag_sources=list(rag_sources or []),
            rag_source_kinds=list(rag_source_kinds or []),
            memory_recalled=memory_recalled,
            session_memory_injected=bool(
                getattr(request, "session_memory_injected", False)
            ),
            memory_recall_slice=memory_recall_slice,
            runtime_model_capabilities=runtime_model_capabilities,
        )
        capability_finalization = await self.capability_bridge.finalize_capabilities(
            agent=agent,
            request=request,
            skill_result=skill_result,
            intent_plan=intent_plan,
            intent_flags=intent_flags,
            capability_inputs=capability_inputs,
            capability_injection_decision=capability_injection_decision,
        )
        merged_finalization = merge_capability_finalization(
            diagnostics=diagnostics,
            capability_finalization=capability_finalization,
        )
        payload = build_context_assembly_payload(
            messages=pruned_messages,
            estimated_tokens=estimated_tokens,
            system_prompt_additions=system_prompt_additions,
            diagnostics=merged_finalization.diagnostics,
            rag_sources=rag_sources,
            rag_source_kinds=rag_source_kinds,
            compact_summary=compact_summary,
            prune_stats=prune_stats,
            memory_recall_slice=memory_recall_slice,
            context_compacted=context_compacted,
            memory_recalled=memory_recalled,
            capability_bundle=merged_finalization.capability_bundle,
        )

        return ContextAssembly(**payload.__dict__)

    async def compact(self, agent: Agent, request: ExecutionRequest) -> None:
        if self._compaction_snapshot_written_in_assemble:
            self._compaction_snapshot_written_in_assemble = False
            return
        context_config = getattr(agent, "context_config", None) or {}
        messages = compaction_support.coerce_result_messages(
            getattr(request, "messages", None)
        )
        if not messages:
            return
        await self._compact_messages_if_needed(
            request=request,
            context_config=context_config,
            messages=messages,
        )

    async def after_turn(
        self,
        agent: Agent,
        request: ExecutionRequest,
        result: Any,
    ) -> None:
        if not request.conversation_id:
            return

        context_config = getattr(agent, "context_config", None) or {}
        result_messages = compaction_support.coerce_result_messages(
            getattr(result, "messages", None)
        )
        if not result_messages:
            return

        await self._compact_messages_if_needed(
            request=request,
            context_config=context_config,
            messages=result_messages,
        )

    @staticmethod
    def _build_compact_summary(
        messages: list[ChatMessage],
        *,
        max_chars: int,
    ) -> str:
        return compaction_support.build_compact_summary(
            messages,
            max_chars=max_chars,
        )

    def _append_budgeted_addition(
        self,
        *,
        additions: list[str],
        text: str,
        category: str,
        per_item_token_limit: int,
        total_token_limit: int,
        budget_usage: dict[str, Any],
    ) -> None:
        append_budgeted_addition(
            additions=additions,
            text=text,
            category=category,
            per_item_token_limit=per_item_token_limit,
            total_token_limit=total_token_limit,
            budget_usage=budget_usage,
            trim_text_fn=self._trim_text_to_token_limit,
        )

    @staticmethod
    def _trim_text_to_token_limit(text: str, token_limit: int) -> str:
        return trim_text_to_token_limit(text, token_limit)

    async def _load_compaction_snapshot(
        self,
        request: ExecutionRequest,
    ) -> dict[str, Any] | None:
        return await engine_runtime_support.load_compaction_snapshot(
            db=self.db,
            tenant_id=request.tenant_id,
            conversation_id=request.conversation_id,
        )

    async def _persist_compaction_snapshot(
        self,
        *,
        request: ExecutionRequest,
        summary: str,
        source_message_count: int,
        source_token_estimate: int,
    ) -> None:
        await engine_runtime_support.persist_compaction_snapshot(
            db=self.db,
            tenant_id=request.tenant_id,
            conversation_id=request.conversation_id,
            summary=summary,
            source_message_count=source_message_count,
            source_token_estimate=source_token_estimate,
        )

    async def _compact_messages_if_needed(
        self,
        *,
        request: ExecutionRequest,
        context_config: dict[str, Any],
        messages: list[ChatMessage],
    ) -> None:
        async def _persist_summary(**kwargs: Any) -> None:
            await self._persist_compaction_snapshot(request=request, **kwargs)

        def _split_index_via_facade(
            candidate_messages: list[ChatMessage],
            **kwargs: Any,
        ) -> int | None:
            kwargs.pop("pruner", None)
            return compaction_support.compaction_split_index(
                candidate_messages,
                pruner=self.pruner,
                **kwargs,
            )

        await engine_runtime_support.compact_messages_if_needed(
            context_config=context_config,
            messages=messages,
            persist_snapshot=_persist_summary,
            pruner=self.pruner,
            compaction_split_index_fn=_split_index_via_facade,
            build_compact_summary_fn=self._build_compact_summary,
        )


def get_context_engine(
    *,
    db: AsyncSession,
    base_engine: PromptBridge,
) -> ContextEngine:
    return ConversationContextEngine(db, base_engine)
