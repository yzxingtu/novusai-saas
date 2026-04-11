"""
Long-term memory context contributor.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass
class MemoryContextContribution:
    memory_recalled: bool = False
    memory_recall_slice: dict[str, Any] | None = None
    memory_injected: bool = False


class MemoryContributor:
    async def contribute(
        self,
        *,
        db: Any,
        enabled: bool,
        user_id: int | None,
        tenant_id: int,
        agent_id: int,
        current_user_text: str,
        should_run_memory_profile: bool,
        should_run_memory_vector_recall: bool,
        should_run_vector_recall_for_text: Callable[[str], bool],
        provider_factory: Callable[..., Any],
        append_budgeted_addition: Callable[..., None],
        additions: list[str],
        budget_usage: dict[str, Any],
        context_budget: dict[str, Any],
        build_profile_snapshot_block: Callable[[dict[str, Any]], str],
        build_memory_recall_block: Callable[[list[Any]], str],
    ) -> MemoryContextContribution:
        if not enabled or not user_id:
            return MemoryContextContribution()
        if not current_user_text:
            return MemoryContextContribution()
        if not should_run_memory_profile and not should_run_memory_vector_recall:
            return MemoryContextContribution()

        provider = provider_factory(
            db=db,
            tenant_id=tenant_id,
        )
        contribution = MemoryContextContribution()

        if should_run_memory_profile:
            profile_snapshot = await provider.profile(
                agent_id=agent_id,
                user_id=user_id,
                limit=10,
            )
            if profile_snapshot:
                profile_block = build_profile_snapshot_block(profile_snapshot)
                if profile_block:
                    append_budgeted_addition(
                        additions=additions,
                        text=profile_block,
                        category="memory_profile_snapshot",
                        per_item_token_limit=context_budget["memory_block_tokens"],
                        total_token_limit=context_budget["system_additions_tokens"],
                        budget_usage=budget_usage,
                    )
                    contribution.memory_recalled = True
                    contribution.memory_injected = True
                    contribution.memory_recall_slice = {
                        "count": 0,
                        "profile_snapshot": True,
                        "scope_type": "user_agent",
                    }

        if (
            should_run_memory_vector_recall
            and should_run_vector_recall_for_text(current_user_text)
        ):
            recalled_records = await provider.recall(
                agent_id=agent_id,
                user_id=user_id,
                query_text=current_user_text,
                limit=5,
            )
            if recalled_records:
                recall_block = build_memory_recall_block(recalled_records)
                if recall_block:
                    append_budgeted_addition(
                        additions=additions,
                        text=recall_block,
                        category="memory_recall",
                        per_item_token_limit=context_budget["memory_block_tokens"],
                        total_token_limit=context_budget["system_additions_tokens"],
                        budget_usage=budget_usage,
                    )
                    contribution.memory_recalled = True
                    contribution.memory_injected = True
                    contribution.memory_recall_slice = {
                        "count": len(recalled_records),
                        **(
                            {"profile_snapshot": True}
                            if contribution.memory_recall_slice
                            and contribution.memory_recall_slice.get(
                                "profile_snapshot"
                            )
                            else {}
                        ),
                        "scope_type": "user_agent",
                    }

        return contribution


__all__ = ["MemoryContributor", "MemoryContextContribution"]
