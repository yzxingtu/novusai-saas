from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.ai.context.contributors.memory import MemoryContributor


@pytest.mark.asyncio
async def test_memory_contributor_skips_provider_without_profile_or_recall() -> None:
    contributor = MemoryContributor()
    provider_factory = MagicMock()
    should_run_vector_recall_for_text = MagicMock()

    result = await contributor.contribute(
        db=MagicMock(),
        enabled=True,
        user_id=7,
        tenant_id=1,
        agent_id=2,
        current_user_text="记住这个",
        should_run_memory_profile=False,
        should_run_memory_vector_recall=False,
        should_run_vector_recall_for_text=should_run_vector_recall_for_text,
        provider_factory=provider_factory,
        append_budgeted_addition=MagicMock(),
        additions=[],
        budget_usage={"used_tokens": 0, "trimmed_sections": [], "skipped_sections": []},
        context_budget={"memory_block_tokens": 120, "system_additions_tokens": 240},
        build_profile_snapshot_block=MagicMock(),
        build_memory_recall_block=MagicMock(),
    )

    assert result.memory_recalled is False
    assert result.memory_injected is False
    assert result.memory_recall_slice is None
    provider_factory.assert_not_called()
    should_run_vector_recall_for_text.assert_not_called()


@pytest.mark.asyncio
async def test_memory_contributor_skips_provider_when_vector_filter_rejects() -> None:
    contributor = MemoryContributor()
    provider_factory = MagicMock()
    should_run_vector_recall_for_text = MagicMock(return_value=False)

    result = await contributor.contribute(
        db=MagicMock(),
        enabled=True,
        user_id=7,
        tenant_id=1,
        agent_id=2,
        current_user_text="ok",
        should_run_memory_profile=False,
        should_run_memory_vector_recall=True,
        should_run_vector_recall_for_text=should_run_vector_recall_for_text,
        provider_factory=provider_factory,
        append_budgeted_addition=MagicMock(),
        additions=[],
        budget_usage={"used_tokens": 0, "trimmed_sections": [], "skipped_sections": []},
        context_budget={"memory_block_tokens": 120, "system_additions_tokens": 240},
        build_profile_snapshot_block=MagicMock(),
        build_memory_recall_block=MagicMock(),
    )

    assert result.memory_recalled is False
    assert result.memory_injected is False
    assert result.memory_recall_slice is None
    should_run_vector_recall_for_text.assert_called_once()
    provider_factory.assert_not_called()
