"""LongTermMemoryService 单元测试 / Unit tests for long-term memory helpers and service paths."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.enums.memory import MemoryScopeTypeEnum, MemoryTypeEnum
from app.models.ai.memory_record import MemoryRecord
from app.services.ai import long_term_memory_service as ltm_mod
from app.services.ai.long_term_memory_service import (
    LongTermMemoryService,
    build_memory_capture_payload_from_session_delta,
)


class TestModuleHelpers:
    def test_memory_hash_stable(self) -> None:
        h = ltm_mod._memory_hash("hello")
        assert len(h) == 32
        assert h == ltm_mod._memory_hash("hello")

    def test_extract_keywords_dedup_and_limit(self) -> None:
        text = "foo bar foo " + "x" * 100
        kw = ltm_mod._extract_keywords(text, limit=3)
        assert "foo" in kw
        assert "bar" in kw
        assert len(kw) <= 3

    def test_extract_keywords_empty(self) -> None:
        assert ltm_mod._extract_keywords("") == []
        assert ltm_mod._extract_keywords("   ") == []


class TestBuildScopeKey:
    def test_user_agent(self) -> None:
        k = LongTermMemoryService.build_scope_key(
            MemoryScopeTypeEnum.USER_AGENT.value,
            agent_id=2,
            user_id=9,
        )
        assert k == "user:9:agent:2"

    def test_tenant_agent(self) -> None:
        k = LongTermMemoryService.build_scope_key(
            MemoryScopeTypeEnum.TENANT_AGENT.value,
            agent_id=5,
        )
        assert k == "tenant_agent:5"

    def test_tenant_shared(self) -> None:
        k = LongTermMemoryService.build_scope_key(
            MemoryScopeTypeEnum.TENANT_SHARED.value,
        )
        assert k == "tenant_shared"

    def test_conversation_fallback(self) -> None:
        k = LongTermMemoryService.build_scope_key(
            MemoryScopeTypeEnum.CONVERSATION.value,
            agent_id=1,
            user_id=3,
        )
        assert k == "conversation:3:agent:1"


class TestBuildProfilePayload:
    def test_buckets_and_summary(self) -> None:
        r1 = MagicMock(spec=MemoryRecord)
        r1.memory_type = MemoryTypeEnum.PREFERENCE.value
        r1.summary = "likes dark mode"
        r1.content = ""

        r2 = MagicMock(spec=MemoryRecord)
        r2.memory_type = MemoryTypeEnum.FACT.value
        r2.summary = None
        r2.content = "works remotely"

        profile, summary = LongTermMemoryService._build_profile_payload([r1, r2])
        assert "preferences" in profile
        assert "facts" in profile
        assert summary
        assert "Preferences" in summary or "Facts" in summary

    def test_empty_records(self) -> None:
        profile, summary = LongTermMemoryService._build_profile_payload([])
        assert profile == {}
        assert summary is None


class TestBuildMemoryCapturePayloadFromSessionDelta:
    def test_maps_keys(self) -> None:
        out = build_memory_capture_payload_from_session_delta(
            {
                "preferences": ["a"],
                "constraints": ["b"],
                "verified_facts": ["c"],
                "task_states": ["d"],
            },
        )
        assert out[MemoryTypeEnum.PREFERENCE.value] == ["a"]
        assert out[MemoryTypeEnum.CONSTRAINT.value] == ["b"]
        assert out[MemoryTypeEnum.FACT.value] == ["c"]
        assert out[MemoryTypeEnum.TASK_SUMMARY.value] == ["d"]


class TestLongTermMemoryServiceAsync:
    @pytest.mark.asyncio
    async def test_capture_records_no_embedding_creates(self, mock_db) -> None:
        service = LongTermMemoryService.__new__(LongTermMemoryService)
        service.db = mock_db
        service.tenant_id = 1
        service.repo = AsyncMock()
        service.profile_repo = AsyncMock()
        service.repo.get_by_scope_type_hash = AsyncMock(return_value=None)
        service.repo.create = AsyncMock(side_effect=lambda d: make_record(d))
        service.create = AsyncMock(side_effect=lambda d: make_record(d))

        async def _no_embed(*_a, **_k):
            return None

        async def _no_gen(*_a, **_k):
            return []

        with (
            patch.object(LongTermMemoryService, "_resolve_embedding_target", new=_no_embed),
            patch.object(LongTermMemoryService, "_generate_embeddings", new=_no_gen),
            patch.object(
                LongTermMemoryService,
                "refresh_profile_snapshot",
                new=AsyncMock(return_value=None),
            ),
        ):
            captured = await service.capture_records(
                agent_id=1,
                user_id=2,
                source_kind="conversation_turn",
                source_ref="c1",
                items_by_type={MemoryTypeEnum.FACT.value: ["  hello world  "]},
            )
        assert len(captured) == 1
        service.create.assert_awaited()

    @pytest.mark.asyncio
    async def test_recall_updates_last_recalled(self, mock_db) -> None:
        service = LongTermMemoryService.__new__(LongTermMemoryService)
        service.db = mock_db
        service.tenant_id = 1
        service.repo = AsyncMock()
        service.profile_repo = AsyncMock()
        rec = make_record({"id": 1})
        service.repo.search_for_recall = AsyncMock(return_value=[rec])

        async def _no_embed(*_a, **_k):
            return None

        async def _no_gen(*_a, **_k):
            return []

        with (
            patch.object(LongTermMemoryService, "_resolve_embedding_target", new=_no_embed),
            patch.object(LongTermMemoryService, "_generate_embeddings", new=_no_gen),
        ):
            out = await service.recall(
                agent_id=1,
                user_id=2,
                query_text="q",
                limit=3,
            )
        assert out == [rec]
        mock_db.flush.assert_awaited()

    @pytest.mark.asyncio
    async def test_profile_returns_snapshot_dict(self, mock_db) -> None:
        service = LongTermMemoryService.__new__(LongTermMemoryService)
        service.db = mock_db
        service.tenant_id = 1
        service.repo = AsyncMock()
        snap = MagicMock()
        snap.scope_type = "user_agent"
        snap.scope_key = "user:1:agent:2"
        snap.summary = "s"
        snap.profile_json = {"a": 1}
        snap.record_count = 3
        service.profile_repo = AsyncMock()
        service.profile_repo.get_by_scope = AsyncMock(return_value=snap)

        with patch.object(
            LongTermMemoryService,
            "refresh_profile_snapshot",
            new=AsyncMock(return_value=None),
        ):
            data = await service.profile(agent_id=2, user_id=1)
        assert data is not None
        assert data["summary"] == "s"
        assert data["record_count"] == 3


def make_record(data: dict) -> MagicMock:
    m = MagicMock()
    for k, v in data.items():
        setattr(m, k, v)
    m.last_recalled_at = None
    return m
