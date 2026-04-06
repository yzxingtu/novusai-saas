"""
Context engine abstraction / 上下文引擎抽象

Provides a first-stage context lifecycle abstraction without changing current
runtime truth. / 提供第一阶段上下文生命周期抽象，不改变现有运行时真相。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any

from app.ai.capabilities import CapabilityDescriptionBuilder
from app.ai.context.long_term_memory import get_long_term_memory_provider
from app.ai.context.pruning import TransientPruner
from app.ai.page_locale import page_language_name, resolve_page_locale
from app.ai.prompt_contracts import render_prompt_contract
from app.ai.runtime.capabilities import CapabilityContext, CapabilityRegistry
from app.ai.runtime.context_assembler import (
    ContextAssembler,
    ContextAssemblerState,
    LegacyContextAssemblerAdapter,
    get_context_assembler,
)
from app.ai.runtime.manifest import AIRuntimeInventoryService
from app.ai.runtime.types import CapabilityBundle
from app.ai.types import ChatMessage
from app.ai.utils.token_estimator import estimate_tokens
from app.core.base_model import utc_now
from app.core.config import settings
from app.core.logging import LogManager
from app.services.ai.capability_awareness_config import (
    get_tenant_capability_awareness_settings,
)
from app.services.ai.model_capability_lookup import resolve_runtime_model_capabilities

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.ai.engine.base import BaseEngine
    from app.ai.engine.types import ExecutionRequest
    from app.ai.skills.resolver import SkillResolveResult
    from app.models.ai.agent import Agent


logger = LogManager.get_logger("ai.context_engine")

_DEFAULT_CONTEXT_PROMPT_BUDGET_TOKENS = 8000
_DEFAULT_CONTEXT_OUTPUT_RESERVE_RATIO = 0.25
_DEFAULT_SYSTEM_ADDITIONS_BUDGET_TOKENS = 1600
_DEFAULT_CAPABILITY_BLOCK_BUDGET_TOKENS = 500
_DEFAULT_MEMORY_BLOCK_BUDGET_TOKENS = 400
_DEFAULT_COMPACT_SUMMARY_BUDGET_TOKENS = 700
_DEFAULT_DATE_ANCHOR_BUDGET_TOKENS = 160
_DEFAULT_PAGE_LOCALE_BUDGET_TOKENS = 96
_MIN_ADDITION_SECTION_TOKENS = 48


def _capability_description_category(description: Any) -> str:
    """Normalize category access for object and mapping descriptors."""
    if isinstance(description, dict):
        raw_category = description.get("category")
    else:
        raw_category = getattr(description, "category", None)
    return str(raw_category or "").strip()


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
    # Reserved for future explicit memory-flush signaling; current engine keeps False.
    # 预留给显式记忆 flush 信号；当前实现保持 False。
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

    def __init__(self, db: AsyncSession, base_engine: BaseEngine) -> None:
        self.db = db
        self.base_engine = base_engine
        self.pruner = TransientPruner()
        self.context_assembler = get_context_assembler()
        self.context_assembler_adapter = LegacyContextAssemblerAdapter()
        # True after assemble() persisted a compaction snapshot; compact() skips duplicate persist.
        self._compaction_snapshot_written_in_assemble = False

    async def ingest(self, agent: Agent, request: ExecutionRequest) -> None:
        _ = agent, request

    @staticmethod
    def _intent_plan_flags(
        intent_plan: list[Any],
        request: ExecutionRequest | None = None,
    ) -> dict[str, bool]:
        normalized_plan = list(intent_plan or [])
        intent_kinds = {
            str(getattr(intent, "kind", "") or "").strip()
            for intent in normalized_plan
        }
        all_shortcircuit = bool(normalized_plan) and all(
            bool(getattr(intent, "shortcircuit", False))
            for intent in normalized_plan
        )
        has_page_intent = any(kind.startswith("page_") for kind in intent_kinds)
        has_knowledge_intent = "knowledge_query" in intent_kinds
        has_web_research_intent = (
            "web_research" in intent_kinds
            or any(
                str(getattr(intent, "family", "") or "").strip() == "web_research"
                for intent in normalized_plan
            )
        )
        allow_memory_even_if_shortcircuit = bool(
            request is not None
            and getattr(request, "user_id", None)
            and (
                bool(getattr(request, "long_term_memory_enabled", False))
                or bool(getattr(request, "memory_enabled", False))
            )
        )
        has_memory_intent = allow_memory_even_if_shortcircuit or any(
            not bool(getattr(intent, "shortcircuit", False))
            for intent in normalized_plan
        )
        return {
            "all_shortcircuit": all_shortcircuit,
            "has_page_intent": has_page_intent,
            "has_knowledge_intent": has_knowledge_intent,
            "has_web_research_intent": has_web_research_intent,
            "has_memory_intent": has_memory_intent,
            "allow_memory_even_if_shortcircuit": allow_memory_even_if_shortcircuit,
        }

    def _build_provisional_capability_bundle(
        self,
        *,
        agent: Agent,
        request: ExecutionRequest,
        skill_result: SkillResolveResult | None,
        knowledge_base_ids: list[int],
        requested_knowledge_base_ids: list[int],
        dropped_knowledge_base_ids: list[int],
        runtime_model_capabilities: dict[str, Any] | None,
    ) -> CapabilityBundle:
        provisional_state = ContextAssemblerState(
            knowledge_base_ids=list(knowledge_base_ids or []),
            requested_knowledge_base_ids=list(requested_knowledge_base_ids or []),
            dropped_knowledge_base_ids=list(dropped_knowledge_base_ids or []),
            rag_sources=[],
            rag_source_kinds=[],
            memory_recalled=False,
            memory_recall_slice=None,
            runtime_model_capabilities=runtime_model_capabilities,
        )
        capability_context = CapabilityContext(
            agent=agent,
            request=request,
            skill_result=skill_result,
            state=provisional_state.to_state_dict(),
        )
        bundle = CapabilityBundle()
        fragments = (
            ContextAssembler._collect_skill_capabilities(capability_context),
            ContextAssembler._collect_page_context_capabilities(capability_context),
            ContextAssembler._collect_knowledge_capabilities(capability_context),
            ContextAssembler._collect_runtime_model_capabilities(capability_context),
        )
        for fragment in fragments:
            CapabilityRegistry._merge_fragment(bundle, fragment)
        return bundle

    async def assemble(
        self,
        agent: Agent,
        request: ExecutionRequest,
        skill_result: SkillResolveResult | None = None,
    ) -> ContextAssembly:
        self._compaction_snapshot_written_in_assemble = False
        messages: list[ChatMessage] = []
        system_msg = self.base_engine._build_system_message(
            agent, request.input_variables
        )
        messages.append(system_msg)
        if request.messages:
            messages.extend(request.messages)

        from app.ai.rag_injector import inject_rag_context, load_agent_kb_bindings

        rag_sources = None
        rag_source_kinds: list[str] = []
        requested_kb_ids = [
            int(kb_id)
            for kb_id in (request.knowledge_base_ids or [])
            if str(kb_id).strip()
        ]
        agent_kb_ids, agent_kb_weights = await load_agent_kb_bindings(
            self.db,
            agent.id,
            request.tenant_id,
        )
        if request.knowledge_base_ids:
            selected = set(request.knowledge_base_ids)
            merged_kb_ids = [kid for kid in (agent_kb_ids or []) if kid in selected]
            if not merged_kb_ids:
                merged_kb_ids = agent_kb_ids
        else:
            merged_kb_ids = agent_kb_ids
        dropped_kb_ids = (
            [kb_id for kb_id in requested_kb_ids if kb_id not in (merged_kb_ids or [])]
            if requested_kb_ids
            else []
        )

        try:
            runtime_model_capabilities = await resolve_runtime_model_capabilities(
                model=getattr(agent, "model", None),
            )
        except Exception as exc:
            runtime_model_capabilities = {}
            logger.warning(
                "Resolve runtime model capabilities degraded during provisional planning: agent_id={} err={}",
                getattr(agent, "id", None),
                str(exc),
            )
        provisional_bundle = self._build_provisional_capability_bundle(
            agent=agent,
            request=request,
            skill_result=skill_result,
            knowledge_base_ids=list(merged_kb_ids or []),
            requested_knowledge_base_ids=requested_kb_ids,
            dropped_knowledge_base_ids=dropped_kb_ids,
            runtime_model_capabilities=runtime_model_capabilities,
        )
        provisional_continuation_context = (
            self.base_engine._build_web_research_continuation_context(
                messages,
                list(provisional_bundle.tools),
            )
        )
        from app.ai.engine.intent_planner import IntentPlanner

        intent_plan = IntentPlanner.plan_turn(
            messages=messages,
            tools=list(provisional_bundle.tools),
            input_variables=request.input_variables,
            continuation_context=provisional_continuation_context,
            capability_bundle=provisional_bundle,
        )
        intent_flags = self._intent_plan_flags(intent_plan, request)
        capability_injection_decision: dict[str, Any] = {
            "all_shortcircuit": intent_flags["all_shortcircuit"],
            "skills_injected": False,
            "kb_injected": False,
            "memory_injected": False,
            "page_injected": False,
            "bypass_reason": (
                "all_shortcircuit" if intent_flags["all_shortcircuit"] else None
            ),
        }

        effective_rag_config = agent.rag_config or {}
        if (
            not intent_flags["all_shortcircuit"]
            and intent_flags["has_knowledge_intent"]
            and merged_kb_ids
        ):
            messages, rag_sources = await inject_rag_context(
                self.db,
                agent,
                messages,
                request.tenant_id,
                kb_ids=merged_kb_ids,
                rag_config=effective_rag_config or None,
                kb_weights=agent_kb_weights,
            )
            capability_injection_decision["kb_injected"] = True
            if rag_sources:
                rag_source_kinds.append("formal_kb")

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
        context_budget = self._resolve_context_budget(context_config)

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
        compaction_source_tokens = self._messages_token_estimate(messages)
        existing_snapshot = await self._load_compaction_snapshot(request)
        web_research_date_anchor = (
            self._build_web_research_date_anchor(
                messages,
                skill_result=skill_result,
            )
            if intent_flags["has_web_research_intent"]
            else ""
        )
        if web_research_date_anchor:
            self._append_budgeted_addition(
                additions=system_prompt_additions,
                text=web_research_date_anchor,
                category="web_research_date_anchor",
                per_item_token_limit=context_budget["date_anchor_tokens"],
                total_token_limit=context_budget["system_additions_tokens"],
                budget_usage=budget_usage,
            )
        page_locale_hint = (
            self._build_page_locale_hint(request)
            if intent_flags["has_page_intent"]
            else ""
        )
        if page_locale_hint:
            self._append_budgeted_addition(
                additions=system_prompt_additions,
                text=page_locale_hint,
                category="page_locale_thinking",
                per_item_token_limit=context_budget["page_locale_tokens"],
                total_token_limit=context_budget["system_additions_tokens"],
                budget_usage=budget_usage,
            )
            capability_injection_decision["page_injected"] = True

        try:
            capability_settings = await get_tenant_capability_awareness_settings(
                self.db,
                request.tenant_id,
            )
            dynamic_capability_awareness_enabled = bool(
                capability_settings.enable_dynamic_capability_awareness
            )
            if (
                dynamic_capability_awareness_enabled
                and not intent_flags["all_shortcircuit"]
            ):
                capability_builder = CapabilityDescriptionBuilder(
                    style=capability_settings.capability_description_style,
                    max_items_per_category=(
                        capability_settings.max_capability_items_per_category
                    ),
                )
                capability_descriptions = []

                if skill_result:
                    capability_descriptions.extend(
                        capability_builder.build_skill_descriptions(skill_result)
                    )

                if intent_flags["has_knowledge_intent"] and merged_kb_ids:
                    from app.services.ai.agent_kb_binding_service import (
                        AgentKBBindingService,
                    )

                    kb_service = AgentKBBindingService(self.db, request.tenant_id)
                    kb_bindings = await kb_service.get_agent_kb_bindings_with_metadata(
                        agent.id,
                        merge_platform_bindings=True,
                    )
                    effective_kb_ids = set(merged_kb_ids)
                    kb_bindings = [
                        binding
                        for binding in kb_bindings
                        if int(
                            binding.get("knowledge_base_id")
                            or binding.get("kb_id")
                            or 0
                        )
                        in effective_kb_ids
                    ]
                    kb_description = (
                        capability_builder.build_knowledge_base_descriptions(
                            kb_bindings
                        )
                    )
                    if kb_description:
                        capability_descriptions.append(kb_description)

                if intent_flags["has_page_intent"]:
                    page_context = None
                    if isinstance(request.input_variables, dict):
                        from app.schemas.ai.agent_chat import PAGE_CONTEXT_KEY

                        page_context = request.input_variables.get(PAGE_CONTEXT_KEY)
                    page_description = capability_builder.build_page_context_description(
                        page_context
                    )
                    if page_description:
                        capability_descriptions.append(page_description)

                if intent_flags["has_memory_intent"]:
                    memory_description = capability_builder.build_memory_description(
                        memory_enabled=request.memory_enabled,
                        long_term_memory_enabled=long_term_memory_enabled,
                    )
                    if memory_description:
                        capability_descriptions.append(memory_description)

                capability_awareness_categories = [
                    category
                    for description in capability_descriptions
                    if (category := _capability_description_category(description))
                ]
        except Exception as exc:
            capability_awareness_error = str(exc)
            logger.warning(
                "Dynamic capability awareness degraded: agent_id={} tenant_id={} err={}",
                getattr(agent, "id", None),
                request.tenant_id,
                str(exc),
            )

        if intent_flags["has_memory_intent"] and long_term_memory_enabled and request.user_id:
            current_user_text = self.base_engine._extract_last_user_text(messages)
            if current_user_text:
                provider = get_long_term_memory_provider(
                    db=self.db,
                    tenant_id=request.tenant_id,
                )
                profile_snapshot = await provider.profile(
                    agent_id=agent.id,
                    user_id=request.user_id,
                    limit=10,
                )
                if profile_snapshot:
                    profile_block = self._build_profile_snapshot_block(profile_snapshot)
                    if profile_block:
                        self._append_budgeted_addition(
                            additions=system_prompt_additions,
                            text=profile_block,
                            category="memory_profile_snapshot",
                            per_item_token_limit=context_budget["memory_block_tokens"],
                            total_token_limit=context_budget["system_additions_tokens"],
                            budget_usage=budget_usage,
                        )
                        memory_recalled = True
                        capability_injection_decision["memory_injected"] = True
                        memory_recall_slice = {
                            "count": 0,
                            "profile_snapshot": True,
                            "scope_type": "user_agent",
                        }
                recalled_records = await provider.recall(
                    agent_id=agent.id,
                    user_id=request.user_id,
                    query_text=current_user_text,
                    limit=5,
                )
                if recalled_records:
                    recall_block = self._build_memory_recall_block(recalled_records)
                    if recall_block:
                        self._append_budgeted_addition(
                            additions=system_prompt_additions,
                            text=recall_block,
                            category="memory_recall",
                            per_item_token_limit=context_budget["memory_block_tokens"],
                            total_token_limit=context_budget["system_additions_tokens"],
                            budget_usage=budget_usage,
                        )
                        memory_recalled = True
                        capability_injection_decision["memory_injected"] = True
                        memory_recall_slice = {
                            "count": len(recalled_records),
                            **(
                                {"profile_snapshot": True}
                                if memory_recall_slice
                                and memory_recall_slice.get("profile_snapshot")
                                else {}
                            ),
                            "scope_type": "user_agent",
                        }

        split_index = self._compaction_split_index(
            messages,
            keep_last_assistants=compact_keep_last_assistants,
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
                        source_token_estimate=self._messages_token_estimate(prefix),
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

        messages = self._inject_system_prompt_additions(
            messages,
            system_prompt_additions,
        )

        estimated_tokens_before_prune = self._messages_token_estimate(messages)
        pruned_messages, prune_stats = self.pruner.prune(messages)
        estimated_tokens = self._messages_token_estimate(pruned_messages)
        diagnostics = {
            "pruning_applied": bool(prune_stats.pruned_message_count),
            "compaction_source_tokens": compaction_source_tokens,
            "estimated_tokens_before_prune": estimated_tokens_before_prune,
            "estimated_tokens_after_prune": estimated_tokens,
            "context_compacted": context_compacted,
            "memory_recalled": memory_recalled,
            "web_research_date_anchor": bool(web_research_date_anchor),
            "intent_plan": [intent.to_dict() for intent in intent_plan],
            "allow_memory_even_if_shortcircuit": bool(
                intent_flags["allow_memory_even_if_shortcircuit"]
            ),
            "dynamic_capability_awareness_enabled": (
                dynamic_capability_awareness_enabled
            ),
            "dynamic_capability_awareness_categories": (
                capability_awareness_categories
            ),
            "requested_knowledge_base_ids": requested_kb_ids,
            "effective_knowledge_base_ids": list(merged_kb_ids or []),
            "dropped_knowledge_base_ids": dropped_kb_ids,
            "context_budget": {
                **context_budget,
                "system_additions_used_tokens": budget_usage["used_tokens"],
                "trimmed_sections": list(budget_usage["trimmed_sections"]),
                "skipped_sections": list(budget_usage["skipped_sections"]),
                "prompt_budget_exceeded": (
                    estimated_tokens > context_budget["prompt_target_tokens"]
                ),
            },
            "capability_injection_decision": capability_injection_decision,
        }
        if capability_awareness_error:
            diagnostics["dynamic_capability_awareness_error"] = (
                capability_awareness_error
            )

        capability_bundle: CapabilityBundle | None = None
        assembler_state = ContextAssemblerState(
            knowledge_base_ids=list(merged_kb_ids or []),
            requested_knowledge_base_ids=requested_kb_ids,
            dropped_knowledge_base_ids=dropped_kb_ids,
            rag_sources=list(rag_sources or []),
            rag_source_kinds=list(rag_source_kinds or []),
            memory_recalled=memory_recalled,
            memory_recall_slice=memory_recall_slice,
            runtime_model_capabilities=runtime_model_capabilities,
        )
        try:
            capability_bundle = await self.context_assembler.assemble_bundle(
                agent=agent,
                request=request,
                skill_result=skill_result,
                state=assembler_state,
                intent_plan=intent_plan,
            )
            self.context_assembler_adapter.apply_to_skill_result(
                skill_result=skill_result,
                bundle=capability_bundle,
            )
            diagnostics.update(
                self.context_assembler_adapter.to_diagnostics(capability_bundle),
            )
            if not diagnostics.get("selected_skill_names"):
                fallback_skill_names = list(
                    getattr(skill_result, "selected_skill_names", []) or []
                )
                if fallback_skill_names:
                    diagnostics["selected_skill_names"] = list(
                        dict.fromkeys(
                            str(name).strip()
                            for name in fallback_skill_names
                            if str(name).strip()
                        )
                    )
            if runtime_model_capabilities:
                diagnostics["runtime_model_capabilities"] = dict(
                    runtime_model_capabilities
                )
            context_source_kinds = {
                str(source.kind or "").strip()
                for source in capability_bundle.context_sources
                if bool(getattr(source, "active", True))
            }
            capability_injection_decision["kb_injected"] = bool(
                capability_injection_decision["kb_injected"]
                or "knowledge_base" in context_source_kinds
            )
            capability_injection_decision["memory_injected"] = bool(
                capability_injection_decision["memory_injected"]
                or "session_memory" in context_source_kinds
                or "long_term_memory" in context_source_kinds
            )
            capability_injection_decision["page_injected"] = bool(
                capability_injection_decision["page_injected"]
                or "page_context" in context_source_kinds
            )
        except Exception as exc:
            diagnostics["capability_bundle_error"] = str(exc)
            logger.warning(
                "Context capability assembly degraded: agent_id={} err={}",
                getattr(agent, "id", None),
                str(exc),
            )
        manifest_bundle = capability_bundle or CapabilityBundle()
        runtime_manifest = AIRuntimeInventoryService.build_manifest(
            agent=agent,
            request=request,
            bundle=manifest_bundle,
            state=assembler_state,
            capability_injection_decision=capability_injection_decision,
        )
        diagnostics["runtime_capability_manifest"] = runtime_manifest.to_dict()
        diagnostics["runtime_capability_summary"] = (
            AIRuntimeInventoryService.build_compact_summary(
                runtime_manifest,
                include_knowledge_base_hint=intent_flags["has_knowledge_intent"],
                include_page_context_hint=intent_flags["has_page_intent"],
                include_memory_hint=intent_flags["has_memory_intent"],
            )
        )
        diagnostics["capability_injection_decision"] = capability_injection_decision

        return ContextAssembly(
            messages=pruned_messages,
            estimated_tokens=estimated_tokens,
            system_prompt_additions=system_prompt_additions,
            diagnostics=diagnostics,
            rag_sources=rag_sources,
            rag_source_kinds=rag_source_kinds,
            compact_summary=compact_summary,
            prune_stats=prune_stats.to_dict(),
            memory_recall_slice=memory_recall_slice,
            context_compacted=context_compacted,
            memory_recalled=memory_recalled,
            capability_bundle=capability_bundle,
        )

    async def compact(self, agent: Agent, request: ExecutionRequest) -> None:
        if self._compaction_snapshot_written_in_assemble:
            self._compaction_snapshot_written_in_assemble = False
            return
        context_config = getattr(agent, "context_config", None) or {}
        messages = self._coerce_result_messages(getattr(request, "messages", None))
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
        result_messages = self._coerce_result_messages(
            getattr(result, "messages", None)
        )
        if not result_messages:
            return

        await self._compact_messages_if_needed(
            request=request,
            context_config=context_config,
            messages=result_messages,
        )

    async def _compact_messages_if_needed(
        self,
        *,
        request: ExecutionRequest,
        context_config: dict[str, Any],
        messages: list[ChatMessage],
    ) -> None:
        compact_threshold_tokens = int(
            context_config.get("compact_threshold_tokens", 0) or 0
        )
        if compact_threshold_tokens <= 0:
            return

        compact_keep_last_assistants = int(
            context_config.get("compact_keep_last_assistants", 3) or 3
        )
        compact_max_summary_chars = int(
            context_config.get("compact_max_summary_chars", 1600) or 1600
        )
        source_tokens = self._messages_token_estimate(messages)
        if source_tokens <= compact_threshold_tokens:
            return

        split_index = self._compaction_split_index(
            messages,
            keep_last_assistants=compact_keep_last_assistants,
        )
        if split_index is None or split_index <= 1:
            return

        prefix = messages[1:split_index]
        rebuilt_summary = self._build_compact_summary(
            prefix,
            max_chars=compact_max_summary_chars,
        )
        if not rebuilt_summary:
            return

        await self._persist_compaction_snapshot(
            request=request,
            summary=rebuilt_summary,
            source_message_count=len(prefix),
            source_token_estimate=self._messages_token_estimate(prefix),
        )

    @staticmethod
    def _messages_token_estimate(messages: list[ChatMessage]) -> int:
        return sum(estimate_tokens(message.content or "") for message in messages)

    @staticmethod
    def _coerce_result_messages(raw_messages: Any) -> list[ChatMessage]:
        if not isinstance(raw_messages, list):
            return []
        normalized: list[ChatMessage] = []
        for raw in raw_messages:
            if isinstance(raw, ChatMessage):
                normalized.append(raw)
                continue
            if not isinstance(raw, dict):
                continue
            try:
                normalized.append(
                    ChatMessage(
                        role=str(raw.get("role") or "assistant"),
                        content=str(raw.get("content") or ""),
                        metadata=raw.get("metadata"),
                        attachments=raw.get("attachments"),
                        reasoning_content=raw.get("reasoning_content"),
                        tool_calls=raw.get("tool_calls"),
                        tool_call_id=raw.get("tool_call_id"),
                    )
                )
            except Exception:
                continue
        return normalized

    async def _load_compaction_snapshot(
        self,
        request: ExecutionRequest,
    ) -> dict[str, Any] | None:
        if not request.conversation_id:
            return None
        from app.services.ai.conversation_service import ConversationService

        service = ConversationService(self.db, request.tenant_id)
        return await service.get_context_compaction_snapshot(request.conversation_id)

    async def _persist_compaction_snapshot(
        self,
        *,
        request: ExecutionRequest,
        summary: str,
        source_message_count: int,
        source_token_estimate: int,
    ) -> None:
        if not request.conversation_id:
            return
        from app.services.ai.conversation_service import ConversationService

        service = ConversationService(self.db, request.tenant_id)
        # Dedupe when assemble() and compact() both persist in the same turn: message lists
        # differ (system included vs request.messages only), so counts/tokens may not match even
        # when the generated summary text is identical — compare summary only.
        existing = await service.get_context_compaction_snapshot(
            request.conversation_id
        )
        if existing and isinstance(existing, dict):
            prev_summary = (existing.get("summary") or "").strip()
            new_summary = (summary or "").strip()
            if prev_summary and prev_summary == new_summary:
                return
        await service.upsert_context_compaction_snapshot(
            request.conversation_id,
            summary=summary,
            source_message_count=source_message_count,
            source_token_estimate=source_token_estimate,
        )

    @staticmethod
    def _inject_system_prompt_additions(
        messages: list[ChatMessage],
        additions: list[str],
    ) -> list[ChatMessage]:
        if not messages or not additions:
            return messages
        merged = [part.strip() for part in additions if part.strip()]
        if not merged:
            return messages
        messages[0].content = (
            (messages[0].content or "").rstrip() + "\n\n" + "\n\n".join(merged)
        )
        return messages

    def _compaction_split_index(
        self,
        messages: list[ChatMessage],
        *,
        keep_last_assistants: int,
    ) -> int | None:
        assistant_indexes = [
            idx for idx, message in enumerate(messages) if message.role == "assistant"
        ]
        if len(assistant_indexes) <= keep_last_assistants:
            return None

        split_index = assistant_indexes[-keep_last_assistants]

        unresolved_index = None
        for idx, message in enumerate(messages):
            if idx == 0:
                continue
            if message.role == "tool" and self.pruner._has_unresolved_tool_state(
                message
            ):
                unresolved_index = idx
                break
            if (
                message.role == "assistant"
                and message.tool_calls
                and self.pruner._assistant_has_unresolved_tool_state(message)
            ):
                unresolved_index = idx
                break

        if unresolved_index is not None:
            split_index = min(split_index, unresolved_index)

        return split_index if split_index > 1 else None

    @staticmethod
    def _build_compact_summary(
        messages: list[ChatMessage],
        *,
        max_chars: int,
    ) -> str:
        lines: list[str] = []
        remaining = max(300, max_chars)

        for message in messages:
            if message.role not in {"user", "assistant"}:
                continue

            content = (message.content or "").strip()
            if not content and message.reasoning_content:
                content = message.reasoning_content.strip()
            if not content:
                continue

            normalized = " ".join(content.split())
            if not normalized:
                continue

            prefix = "User" if message.role == "user" else "Assistant"
            line = f"- {prefix}: {normalized}"
            if len(line) > 220:
                line = line[:217].rstrip() + "..."

            projected = len(line) + (1 if lines else 0)
            if projected > remaining and lines:
                break
            lines.append(line)
            remaining -= projected

        return "\n".join(lines).strip()

    @staticmethod
    def _build_memory_recall_block(records: list[Any]) -> str:
        lines = ["[LONG-TERM MEMORY RECALL]"]
        for record in records:
            memory_type = str(getattr(record, "memory_type", "") or "").strip()
            summary = str(
                getattr(record, "summary", None) or getattr(record, "content", "") or ""
            ).strip()
            if not summary:
                continue
            label = memory_type.replace("_", " ").title() if memory_type else "Memory"
            lines.append(f"- {label}: {summary}")
        return "\n".join(lines) if len(lines) > 1 else ""

    @staticmethod
    def _build_profile_snapshot_block(snapshot: dict[str, Any]) -> str:
        profile = snapshot.get("profile") if isinstance(snapshot, dict) else None
        if not isinstance(profile, dict):
            return ""

        lines = ["[PROFILE SNAPSHOT]"]
        label_map = {
            "constraints": "Constraints",
            "corrections": "Corrections",
            "decisions": "Decisions",
            "facts": "Facts",
            "patterns": "Patterns",
            "preferences": "Preferences",
            "relationships": "Relationships",
            "task_summaries": "Task Summaries",
        }
        for key in (
            "preferences",
            "constraints",
            "facts",
            "decisions",
            "patterns",
            "corrections",
            "relationships",
            "task_summaries",
        ):
            values = profile.get(key)
            if not isinstance(values, list) or not values:
                continue
            compact_values = [
                str(value).strip() for value in values[:2] if str(value).strip()
            ]
            if not compact_values:
                continue
            lines.append(
                f"- {label_map.get(key, key.title())}: {'; '.join(compact_values)}"
            )
        return "\n".join(lines) if len(lines) > 1 else ""

    def _build_web_research_date_anchor(
        self,
        messages: list[ChatMessage],
        *,
        skill_result: Any = None,
    ) -> str:
        current_user_text = self.base_engine._extract_last_user_text(messages)
        if not current_user_text:
            return ""

        tools = getattr(skill_result, "tools", None) or []
        has_web_research_tools = any(
            getattr(t, "name", "") in {"web_search", "fetch_url"} for t in tools
        )
        recent_successful_tool_names = (
            self.base_engine._extract_recent_successful_tool_names(
                messages[:-1],
            )
        )
        continuing_web_research = (
            bool(recent_successful_tool_names)
            and recent_successful_tool_names[0] in {"web_search", "fetch_url"}
            and self.base_engine._looks_like_generic_follow_up(current_user_text)
        )
        if not has_web_research_tools and not continuing_web_research:
            return ""

        local_now = datetime.now(settings.tz)
        utc_today = utc_now().strftime("%Y-%m-%d")
        current_year = local_now.year
        return (
            "[RUNTIME CLOCK]\n"
            f"Current server-local date/time is {local_now.strftime('%Y-%m-%d %H:%M:%S')} ({settings.TIMEZONE}). "
            f"Current UTC date is {utc_today}. "
            f'The calendar year for "today" and "latest news" queries is {current_year}. '
            "When constructing web_search queries for current events, use this year in date filters—do not substitute a past training-data year. "
            "When the user says today/latest/current/recent or asks about the current time/date, interpret it against this runtime clock. "
            "Do not assume a different year or timezone unless a source or the user explicitly specifies one."
        )

    @staticmethod
    def _build_page_locale_hint(request: ExecutionRequest) -> str:
        page_locale = resolve_page_locale(getattr(request, "input_variables", None))
        return render_prompt_contract(
            "page_locale_thinking",
            page_locale=page_locale,
            page_language=page_language_name(page_locale),
        )

    @staticmethod
    def _resolve_context_budget(context_config: dict[str, Any]) -> dict[str, Any]:
        prompt_budget_tokens = int(
            context_config.get("prompt_budget_tokens")
            or context_config.get("max_prompt_tokens")
            or _DEFAULT_CONTEXT_PROMPT_BUDGET_TOKENS
        )
        reserve_ratio = float(
            context_config.get("output_reserve_ratio")
            or _DEFAULT_CONTEXT_OUTPUT_RESERVE_RATIO
        )
        reserve_ratio = min(max(reserve_ratio, 0.05), 0.5)
        prompt_target_tokens = max(
            1200,
            int(prompt_budget_tokens * (1 - reserve_ratio)),
        )
        system_additions_tokens = int(
            context_config.get("system_additions_budget_tokens")
            or min(
                _DEFAULT_SYSTEM_ADDITIONS_BUDGET_TOKENS,
                max(400, prompt_target_tokens // 4),
            )
        )
        return {
            "prompt_budget_tokens": prompt_budget_tokens,
            "prompt_target_tokens": prompt_target_tokens,
            "output_reserve_ratio": reserve_ratio,
            "system_additions_tokens": system_additions_tokens,
            "capability_block_tokens": int(
                context_config.get("capability_block_budget_tokens")
                or min(_DEFAULT_CAPABILITY_BLOCK_BUDGET_TOKENS, system_additions_tokens)
            ),
            "memory_block_tokens": int(
                context_config.get("memory_block_budget_tokens")
                or min(_DEFAULT_MEMORY_BLOCK_BUDGET_TOKENS, system_additions_tokens)
            ),
            "compact_summary_tokens": int(
                context_config.get("compact_summary_budget_tokens")
                or min(_DEFAULT_COMPACT_SUMMARY_BUDGET_TOKENS, system_additions_tokens)
            ),
            "date_anchor_tokens": int(
                context_config.get("date_anchor_budget_tokens")
                or min(_DEFAULT_DATE_ANCHOR_BUDGET_TOKENS, system_additions_tokens)
            ),
            "page_locale_tokens": int(
                context_config.get("page_locale_budget_tokens")
                or min(_DEFAULT_PAGE_LOCALE_BUDGET_TOKENS, system_additions_tokens)
            ),
        }

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
        normalized = str(text or "").strip()
        if not normalized:
            return

        used_tokens = int(budget_usage.get("used_tokens", 0) or 0)
        remaining_total = max(total_token_limit - used_tokens, 0)
        if remaining_total < _MIN_ADDITION_SECTION_TOKENS:
            budget_usage.setdefault("skipped_sections", []).append(category)
            return

        effective_limit = max(
            _MIN_ADDITION_SECTION_TOKENS,
            min(int(per_item_token_limit or remaining_total), remaining_total),
        )
        original_tokens = estimate_tokens(normalized)
        trimmed = self._trim_text_to_token_limit(normalized, effective_limit)
        if not trimmed:
            budget_usage.setdefault("skipped_sections", []).append(category)
            return

        additions.append(trimmed)
        budget_usage["used_tokens"] = used_tokens + estimate_tokens(trimmed)
        if original_tokens > estimate_tokens(trimmed):
            budget_usage.setdefault("trimmed_sections", []).append(category)

    @staticmethod
    def _trim_text_to_token_limit(text: str, token_limit: int) -> str:
        normalized = str(text or "").strip()
        if not normalized or token_limit <= 0:
            return ""
        if estimate_tokens(normalized) <= token_limit:
            return normalized

        low = 0
        high = len(normalized)
        best = ""
        while low <= high:
            mid = (low + high) // 2
            candidate = normalized[:mid].rstrip()
            if mid < len(normalized):
                candidate = candidate.rstrip(" .,;:") + "\n..."
            if estimate_tokens(candidate) <= token_limit:
                best = candidate
                low = mid + 1
            else:
                high = mid - 1
        return best


def get_context_engine(
    *,
    db: AsyncSession,
    base_engine: BaseEngine,
) -> ContextEngine:
    return ConversationContextEngine(db, base_engine)
