"""
Hook integration for retrieval.
"""

from __future__ import annotations

from app.ai.rag.retriever_types import ChunkSearchResult


async def apply_before_kb_search(
    *,
    tenant_id: int | None,
    query: str,
    kb_ids: list[int],
    top_k: int,
) -> tuple[str, list[int], int]:
    from app.ai.events.hooks import HookPoint, get_hook_registry

    hook_registry = get_hook_registry()
    if hook_registry.has_hooks(HookPoint.BEFORE_KB_SEARCH):
        hook_ctx = await hook_registry.trigger(
            HookPoint.BEFORE_KB_SEARCH,
            tenant_id=tenant_id,
            query=query,
            kb_ids=kb_ids,
            top_k=top_k,
        )
        query = hook_ctx.get("query", query)
        kb_ids = hook_ctx.get("kb_ids", kb_ids)
        top_k = hook_ctx.get("top_k", top_k)
    return query, kb_ids, top_k


async def apply_after_kb_search(
    *,
    tenant_id: int | None,
    query: str,
    results: list[ChunkSearchResult],
) -> list[ChunkSearchResult]:
    from app.ai.events.hooks import HookPoint, get_hook_registry

    hook_registry = get_hook_registry()
    if hook_registry.has_hooks(HookPoint.AFTER_KB_SEARCH):
        hook_ctx = await hook_registry.trigger(
            HookPoint.AFTER_KB_SEARCH,
            tenant_id=tenant_id,
            query=query,
            results=results,
        )
        results = hook_ctx.get("results", results)
    return results


__all__ = ["apply_before_kb_search", "apply_after_kb_search"]
