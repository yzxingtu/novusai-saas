"""Context-engine runtime seams and compaction persistence helpers."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.ai.context import compaction_support
from app.ai.context.compaction_snapshot_store import ContextCompactionSnapshotStore
from app.ai.runtime.contracts import ContextCapabilityBridge

if TYPE_CHECKING:
    from app.ai.context.long_term_memory import LongTermMemoryProvider
    from app.ai.context.pruning import TransientPruner
    from app.ai.types import ChatMessage


def get_context_capability_bridge() -> ContextCapabilityBridge:
    from app.ai.runtime import context_capability_bridge as capability_bridge_module

    return capability_bridge_module.get_context_capability_bridge()


async def load_agent_kb_bindings(
    db: Any,
    agent_id: int,
    tenant_id: int | None,
) -> tuple[list[int] | None, dict[int, float]]:
    """Lazy KB binding seam so importing context engine stays side-effect light."""

    from app.ai.rag_injector import load_agent_kb_bindings as _load_agent_kb_bindings

    return await _load_agent_kb_bindings(db, agent_id, tenant_id)


def get_long_term_memory_provider(
    *,
    db: Any,
    tenant_id: int,
) -> LongTermMemoryProvider:
    """Lazy memory-provider seam retained as the engine-local patch point."""

    from app.services.ai import long_term_memory_provider as long_term_memory_module

    return long_term_memory_module.get_long_term_memory_provider(
        db=db, tenant_id=tenant_id
    )


def should_run_memory_vector_recall(user_text: str) -> bool:
    normalized = str(user_text or "").strip()
    if not normalized:
        return False
    collapsed = "".join(normalized.lower().split())
    if collapsed in {
        "嗯",
        "嗯嗯",
        "好",
        "好的",
        "收到",
        "谢谢",
        "thanks",
        "thankyou",
        "ok",
        "okay",
    }:
        return False
    from app.ai.context.decision_helpers import looks_like_generic_follow_up

    return not (len(collapsed) < 4 and looks_like_generic_follow_up(normalized))


async def load_compaction_snapshot(
    *,
    db: Any,
    tenant_id: int | None,
    conversation_id: int | None,
) -> dict[str, Any] | None:
    if not conversation_id:
        return None
    store = ContextCompactionSnapshotStore(db, tenant_id)
    return await store.get_snapshot(conversation_id)


async def persist_compaction_snapshot(
    *,
    db: Any,
    tenant_id: int | None,
    conversation_id: int | None,
    summary: str,
    source_message_count: int,
    source_token_estimate: int,
) -> None:
    if not conversation_id:
        return
    store = ContextCompactionSnapshotStore(db, tenant_id)
    existing = await store.get_snapshot(conversation_id)
    if existing and isinstance(existing, dict):
        prev_summary = (existing.get("summary") or "").strip()
        new_summary = (summary or "").strip()
        if prev_summary and prev_summary == new_summary:
            return
    await store.upsert_snapshot(
        conversation_id,
        summary=summary,
        source_message_count=source_message_count,
        source_token_estimate=source_token_estimate,
    )


async def compact_messages_if_needed(
    *,
    context_config: dict[str, Any],
    messages: list[ChatMessage],
    persist_snapshot: Any,
    pruner: TransientPruner,
    compaction_split_index_fn: Any,
    build_compact_summary_fn: Any,
) -> None:
    await compaction_support.compact_messages_if_needed(
        context_config=context_config,
        messages=messages,
        persist_snapshot=persist_snapshot,
        pruner=pruner,
        messages_token_estimate_fn=compaction_support.messages_token_estimate,
        compaction_split_index_fn=compaction_split_index_fn,
        build_compact_summary_fn=build_compact_summary_fn,
    )
