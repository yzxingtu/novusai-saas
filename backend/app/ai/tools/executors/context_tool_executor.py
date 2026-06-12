"""
Executor for system context tools.

The executor runs knowledge-base search and long-term memory operations in the
current agent/user/tenant context. It intentionally does not share the
internal-api executor because these tools are not management-console API calls.
"""

from __future__ import annotations

import json
import time
from typing import Any

from app.ai.context_tools.tools import (
    TOOL_RECALL_LONG_TERM_MEMORY,
    TOOL_SAVE_LONG_TERM_MEMORY,
    TOOL_SEARCH_AGENT_KNOWLEDGE_BASE,
)
from app.ai.rag_injector import load_agent_kb_bindings
from app.ai.tools.executors.base import BaseToolExecutor
from app.ai.tools.types import ExecutionContext, ToolDefinition, ToolResult
from app.core.logging import LogManager
from app.enums.memory import MemorySourceKindEnum, MemoryTypeEnum

logger = LogManager.get_logger("ai.tool.context")


def _json_output(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, default=str)


def _normalize_limit(value: Any, *, default: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(1, min(parsed, maximum))


def _normalize_platform_tenant_id(value: int | None) -> int | None:
    if value is None:
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _memory_record_payload(record: Any) -> dict[str, Any]:
    return {
        "id": getattr(record, "id", None),
        "memory_type": getattr(record, "memory_type", None),
        "content": getattr(record, "summary", None)
        or getattr(record, "content", None),
        "importance": getattr(record, "importance", None),
        "confidence": getattr(record, "confidence", None),
        "updated_at": getattr(record, "updated_at", None),
    }


class ContextToolExecutor(BaseToolExecutor):
    async def validate(
        self,
        definition: ToolDefinition,
        arguments: dict[str, Any],
    ) -> bool:
        _ = definition, arguments
        return True

    async def execute(
        self,
        definition: ToolDefinition,
        tool_call_id: str,
        arguments: dict[str, Any],
        context: ExecutionContext | None = None,
    ) -> ToolResult:
        start = time.perf_counter()
        name = definition.name
        if context is None or context.db is None:
            return ToolResult.error_result(
                tool_call_id,
                "Context tools require an active database-backed conversation.",
                name=name,
            )

        try:
            if name == TOOL_SEARCH_AGENT_KNOWLEDGE_BASE:
                result = await self._search_agent_knowledge_base(
                    tool_call_id,
                    arguments,
                    context,
                )
            elif name == TOOL_SAVE_LONG_TERM_MEMORY:
                result = await self._save_long_term_memory(
                    tool_call_id,
                    arguments,
                    context,
                )
            elif name == TOOL_RECALL_LONG_TERM_MEMORY:
                result = await self._recall_long_term_memory(
                    tool_call_id,
                    arguments,
                    context,
                )
            else:
                result = ToolResult.error_result(
                    tool_call_id,
                    f"Unknown context tool: {name}",
                    name=name,
                )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Context tool {} failed: {}", name, exc, exc_info=True)
            result = ToolResult.error_result(
                tool_call_id,
                f"Context tool failed: {exc}",
                name=name,
            )

        result.duration_ms = int((time.perf_counter() - start) * 1000)
        return result

    async def _search_agent_knowledge_base(
        self,
        tool_call_id: str,
        arguments: dict[str, Any],
        context: ExecutionContext,
    ) -> ToolResult:
        query = str(arguments.get("query") or "").strip()
        if not query:
            return ToolResult.error_result(
                tool_call_id,
                "Argument 'query' is required.",
                name=TOOL_SEARCH_AGENT_KNOWLEDGE_BASE,
            )

        kb_ids, kb_weights = await load_agent_kb_bindings(
            context.db,
            context.agent_id,
            context.tenant_id,
        )
        if not kb_ids:
            return ToolResult(
                tool_call_id=tool_call_id,
                name=TOOL_SEARCH_AGENT_KNOWLEDGE_BASE,
                success=True,
                output=_json_output(
                    {
                        "status": "no_effective_knowledge_base",
                        "sources": [],
                        "snippets": [],
                    }
                ),
                summary="No bound knowledge base",
            )

        from app.ai.rag.retriever import HybridRetriever
        from app.repositories.ai.knowledge_base_repository import (
            AdminKnowledgeBaseRepository,
            KnowledgeBaseRepository,
        )

        effective_tenant_id = _normalize_platform_tenant_id(context.tenant_id)
        kb_repo = (
            KnowledgeBaseRepository(context.db, tenant_id=effective_tenant_id)
            if effective_tenant_id is not None
            else AdminKnowledgeBaseRepository(context.db)
        )
        validated_kbs = []
        validated_kb_ids: list[int] = []
        for kb_id in kb_ids:
            kb = await kb_repo.get_by_id(kb_id)
            if kb is None:
                continue
            validated_kbs.append(kb)
            validated_kb_ids.append(int(kb_id))

        if not validated_kb_ids:
            return ToolResult(
                tool_call_id=tool_call_id,
                name=TOOL_SEARCH_AGENT_KNOWLEDGE_BASE,
                success=True,
                output=_json_output(
                    {
                        "status": "no_accessible_knowledge_base",
                        "sources": [],
                        "snippets": [],
                    }
                ),
                summary="No accessible knowledge base",
            )

        rag_config = {}
        agent = context.agent
        if agent is not None and isinstance(getattr(agent, "rag_config", None), dict):
            rag_config = dict(agent.rag_config or {})
        top_k = _normalize_limit(
            arguments.get("top_k"),
            default=int(rag_config.get("top_k", 5) or 5),
            maximum=20,
        )
        retriever = HybridRetriever(context.db, effective_tenant_id)
        chunks = await retriever.search(
            query=query,
            top_k=top_k,
            score_threshold=rag_config.get("score_threshold", 0.5),
            search_mode=rag_config.get("search_mode", "hybrid"),
            kb_ids=validated_kb_ids,
            rewrite_strategy=rag_config.get("rewrite_strategy", "none"),
            reranker_enabled=rag_config.get("reranker_enabled", False),
            knowledge_bases=validated_kbs,
            kb_weights=kb_weights,
        )
        snippets = [
            {
                "chunk_id": getattr(chunk, "chunk_id", None),
                "knowledge_base_id": getattr(chunk, "knowledge_base_id", None),
                "document_id": getattr(chunk, "document_id", None),
                "document_name": getattr(chunk, "document_name", None),
                "chunk_index": getattr(chunk, "chunk_index", None),
                "score": getattr(chunk, "score", None),
                "content": getattr(chunk, "content", None),
                "recall_sources": list(getattr(chunk, "recall_sources", []) or []),
            }
            for chunk in chunks
        ]
        return ToolResult(
            tool_call_id=tool_call_id,
            name=TOOL_SEARCH_AGENT_KNOWLEDGE_BASE,
            success=True,
            output=_json_output(
                {
                    "status": "ok" if snippets else "no_results",
                    "query": query,
                    "knowledge_base_ids": validated_kb_ids,
                    "snippets": snippets,
                }
            ),
            summary=f"{len(snippets)} knowledge snippets matched",
        )

    async def _save_long_term_memory(
        self,
        tool_call_id: str,
        arguments: dict[str, Any],
        context: ExecutionContext,
    ) -> ToolResult:
        if not context.user_id:
            return ToolResult.error_result(
                tool_call_id,
                "Long-term memory requires an authenticated user.",
                name=TOOL_SAVE_LONG_TERM_MEMORY,
            )
        content = str(arguments.get("content") or "").strip()
        if not content:
            return ToolResult.error_result(
                tool_call_id,
                "Argument 'content' is required.",
                name=TOOL_SAVE_LONG_TERM_MEMORY,
            )
        memory_type = str(arguments.get("memory_type") or "").strip()
        if memory_type not in set(MemoryTypeEnum.values()):
            memory_type = MemoryTypeEnum.FACT.value

        from app.services.ai.long_term_memory_provider import (
            get_long_term_memory_provider,
        )

        provider = get_long_term_memory_provider(
            db=context.db,
            tenant_id=context.tenant_id,
        )
        records = await provider.capture(
            agent_id=context.agent_id,
            user_id=context.user_id,
            source_kind=MemorySourceKindEnum.CONVERSATION_TURN.value,
            source_ref=str(context.conversation_id or "") or None,
            items_by_type={memory_type: [content]},
        )
        return ToolResult(
            tool_call_id=tool_call_id,
            name=TOOL_SAVE_LONG_TERM_MEMORY,
            success=True,
            output=_json_output(
                {
                    "status": "saved",
                    "count": len(records),
                    "memory_type": memory_type,
                    "records": [_memory_record_payload(record) for record in records],
                }
            ),
            summary=f"Saved {len(records)} memory record(s)",
        )

    async def _recall_long_term_memory(
        self,
        tool_call_id: str,
        arguments: dict[str, Any],
        context: ExecutionContext,
    ) -> ToolResult:
        if not context.user_id:
            return ToolResult.error_result(
                tool_call_id,
                "Long-term memory requires an authenticated user.",
                name=TOOL_RECALL_LONG_TERM_MEMORY,
            )
        query = str(arguments.get("query") or "").strip()
        if not query:
            return ToolResult.error_result(
                tool_call_id,
                "Argument 'query' is required.",
                name=TOOL_RECALL_LONG_TERM_MEMORY,
            )
        limit = _normalize_limit(arguments.get("limit"), default=5, maximum=20)

        from app.services.ai.long_term_memory_provider import (
            get_long_term_memory_provider,
        )

        provider = get_long_term_memory_provider(
            db=context.db,
            tenant_id=context.tenant_id,
        )
        records = await provider.recall(
            agent_id=context.agent_id,
            user_id=context.user_id,
            query_text=query,
            limit=limit,
        )
        return ToolResult(
            tool_call_id=tool_call_id,
            name=TOOL_RECALL_LONG_TERM_MEMORY,
            success=True,
            output=_json_output(
                {
                    "status": "ok",
                    "query": query,
                    "count": len(records),
                    "records": [_memory_record_payload(record) for record in records],
                }
            ),
            summary=f"Recalled {len(records)} memory record(s)",
        )


__all__ = ["ContextToolExecutor"]
