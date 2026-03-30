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

from app.ai.context.pruning import PruneStats, TransientPruner
from app.ai.context.long_term_memory import get_long_term_memory_provider
from app.ai.context.ephemeral_rag import EphemeralRAGProvider
from app.ai.types import ChatMessage
from app.ai.utils.token_estimator import estimate_tokens
from app.core.base_model import utc_now
from app.core.config import settings
from app.core.logging import LogManager

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.ai.engine.base import BaseEngine
    from app.ai.engine.types import ExecutionRequest
    from app.ai.skills.resolver import SkillResolveResult
    from app.models.ai.agent import Agent

logger = LogManager.get_logger("ai.context_engine")


@dataclass
class ContextAssembly:
    """Assembled context payload / 已组装的上下文载荷"""

    engine_id: str = "legacy"
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
    # Reserved for future explicit memory-flush signaling; legacy engine keeps False.
    # 预留给显式记忆 flush 信号；旧版引擎保持 False。
    memory_flush_triggered: bool = False
    memory_recalled: bool = False


class ContextEngine(ABC):
    """Context engine interface / 上下文引擎接口"""

    id = "legacy"

    @abstractmethod
    async def ingest(self, agent: Agent, request: ExecutionRequest) -> None:
        """Ingest runtime state before assembly / 在 assemble 前接收运行态输入"""

    @abstractmethod
    async def assemble(
        self,
        agent: Agent,
        request: ExecutionRequest,
        skill_result: "SkillResolveResult | None" = None,
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


class LegacyContextEngine(ContextEngine):
    """
    Legacy implementation / 传统实现。

    Preserves current behavior while centralizing system prompt assembly, RAG
    injection, and transient prompt pruning.
    在保持当前行为的同时，收口 system prompt 组装、RAG 注入和 prompt 临时裁剪。
    """

    id = "legacy"

    def __init__(self, db: AsyncSession, base_engine: BaseEngine) -> None:
        self.db = db
        self.base_engine = base_engine
        self.pruner = TransientPruner()
        self.ephemeral_rag_provider = EphemeralRAGProvider()
        # True after assemble() persisted a compaction snapshot; compact() skips duplicate persist.
        self._compaction_snapshot_written_in_assemble = False

    async def ingest(self, agent: Agent, request: ExecutionRequest) -> None:
        _ = agent, request

    async def assemble(
        self,
        agent: Agent,
        request: ExecutionRequest,
        skill_result: "SkillResolveResult | None" = None,
    ) -> ContextAssembly:
        self._compaction_snapshot_written_in_assemble = False
        messages: list[ChatMessage] = []
        system_msg = self.base_engine._build_system_message(agent, request.input_variables)
        messages.append(system_msg)
        if request.messages:
            messages.extend(request.messages)

        from app.ai.rag_injector import inject_rag_context, load_agent_kb_bindings

        rag_sources = None
        rag_source_kinds: list[str] = []
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

        effective_rag_config = agent.rag_config or {}
        if merged_kb_ids:
            messages, rag_sources = await inject_rag_context(
                self.db,
                agent,
                messages,
                request.tenant_id,
                kb_ids=merged_kb_ids,
                rag_config=effective_rag_config or None,
                kb_weights=agent_kb_weights,
            )
            if rag_sources:
                rag_source_kinds.append("formal_kb")

        messages, ephemeral_sources = await self.ephemeral_rag_provider.inject(
            messages=messages,
            ephemeral_rag_refs=request.ephemeral_rag_refs,
            db=self.db,
            tenant_id=request.tenant_id,
            conversation_id=request.conversation_id,
            agent_id=agent.id,
            user_id=request.user_id,
        )
        if ephemeral_sources:
            rag_sources = list(rag_sources or []) + ephemeral_sources
            rag_source_kinds.append("ephemeral_doc")

        context_config = getattr(agent, "context_config", None) or {}
        long_term_memory_enabled = bool(request.long_term_memory_enabled)
        compact_threshold_tokens = int(context_config.get("compact_threshold_tokens", 0) or 0)
        compact_keep_last_assistants = int(
            context_config.get("compact_keep_last_assistants", 3) or 3
        )
        compact_max_summary_chars = int(
            context_config.get("compact_max_summary_chars", 1600) or 1600
        )

        compact_summary: str | None = None
        system_prompt_additions: list[str] = []
        context_compacted = False
        memory_recalled = False
        memory_recall_slice: dict[str, Any] | None = None
        compaction_source_tokens = self._messages_token_estimate(messages)
        existing_snapshot = await self._load_compaction_snapshot(request)
        web_research_date_anchor = self._build_web_research_date_anchor(
            messages,
            skill_result=skill_result,
        )
        if web_research_date_anchor:
            system_prompt_additions.append(web_research_date_anchor)

        if long_term_memory_enabled and request.user_id:
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
                        system_prompt_additions.append(profile_block)
                        memory_recalled = True
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
                        system_prompt_additions.append(recall_block)
                        memory_recalled = True
                        memory_recall_slice = {
                            "count": len(recalled_records),
                            **(
                                {"profile_snapshot": True}
                                if memory_recall_slice and memory_recall_slice.get("profile_snapshot")
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

            if compact_threshold_tokens > 0 and compaction_source_tokens > compact_threshold_tokens:
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
                system_prompt_additions.append(block)
                messages = [messages[0], *suffix]

        messages = self._inject_system_prompt_additions(
            messages,
            system_prompt_additions,
        )

        pruned_messages, prune_stats = self.pruner.prune(messages)
        estimated_tokens = self._messages_token_estimate(pruned_messages)

        return ContextAssembly(
            engine_id=self.id,
            messages=pruned_messages,
            estimated_tokens=estimated_tokens,
            system_prompt_additions=system_prompt_additions,
            diagnostics={
                "context_engine_id": self.id,
                "pruning_applied": bool(prune_stats.pruned_message_count),
                "compaction_source_tokens": compaction_source_tokens,
                "context_compacted": context_compacted,
                "memory_recalled": memory_recalled,
                "web_research_date_anchor": bool(web_research_date_anchor),
            },
            rag_sources=rag_sources,
            rag_source_kinds=rag_source_kinds,
            compact_summary=compact_summary,
            prune_stats=prune_stats.to_dict(),
            memory_recall_slice=memory_recall_slice,
            context_compacted=context_compacted,
            memory_recalled=memory_recalled,
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
        result_messages = self._coerce_result_messages(getattr(result, "messages", None))
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
        compact_threshold_tokens = int(context_config.get("compact_threshold_tokens", 0) or 0)
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
        existing = await service.get_context_compaction_snapshot(request.conversation_id)
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
        messages[0].content = (messages[0].content or "").rstrip() + "\n\n" + "\n\n".join(merged)
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
            if message.role == "tool" and self.pruner._has_unresolved_tool_state(message):
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
                str(value).strip()
                for value in values[:2]
                if str(value).strip()
            ]
            if not compact_values:
                continue
            lines.append(f"- {label_map.get(key, key.title())}: {'; '.join(compact_values)}")
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
        recent_successful_tool_names = self.base_engine._extract_recent_successful_tool_names(
            messages[:-1],
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
            f"The calendar year for \"today\" and \"latest news\" queries is {current_year}. "
            "When constructing web_search queries for current events, use this year in date filters—do not substitute a past training-data year. "
            "When the user says today/latest/current/recent or asks about the current time/date, interpret it against this runtime clock. "
            "Do not assume a different year or timezone unless a source or the user explicitly specifies one."
        )


def get_context_engine(
    *,
    db: AsyncSession,
    base_engine: BaseEngine,
    request: ExecutionRequest,
) -> ContextEngine:
    engine_id = (request.context_engine_id or "legacy").strip().lower()
    if engine_id and engine_id != "legacy":
        logger.warning(
            "Unknown context_engine_id={}, fallback to legacy",
            engine_id,
        )
    return LegacyContextEngine(db, base_engine)
