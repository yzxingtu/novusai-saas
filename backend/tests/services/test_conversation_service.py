"""
ConversationService 单元测试

覆盖：对话详情、归档、搜索、导出、聊天历史加载。
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.services.conftest import make_mock_model


def _make_conversation(**overrides):
    defaults = {
        "id": 1,
        "tenant_id": 1,
        "agent_id": 1,
        "user_id": 1,
        "title": "Test Conversation",
        "status": "active",
        "is_archived": False,
        "message_count": 5,
        "token_count": 1000,
        "total_tokens": 1000,
    }
    defaults.update(overrides)
    obj = make_mock_model(**defaults)
    obj.to_dict.return_value = defaults
    return obj


def _make_message(**overrides):
    defaults = {
        "id": 1,
        "conversation_id": 1,
        "role": "user",
        "content": "Hello",
        "tokens": 10,
    }
    defaults.update(overrides)
    return make_mock_model(**defaults)


class TestGetConversationDetail:

    @pytest.mark.asyncio
    async def test_not_found_raises(self, mock_db):
        from app.exceptions import NotFoundException
        from app.services.ai.conversation_service import ConversationService

        service = ConversationService.__new__(ConversationService)
        service.db = mock_db
        service.tenant_id = 1
        service.repo = AsyncMock()
        service.repo.get_by_id = AsyncMock(return_value=None)

        with pytest.raises(NotFoundException):
            await service.get_conversation_detail(999)


class TestGetServiceForConversation:

    @pytest.mark.asyncio
    async def test_preserves_none_tenant_id_for_global_conversation(self, mock_db):
        from app.services.ai.conversation_service import ConversationService

        repo = AsyncMock()
        repo.get_by_id = AsyncMock(return_value=_make_conversation(tenant_id=None))

        with patch(
            "app.services.ai.conversation_service.AdminAgentConversationRepository",
            return_value=repo,
        ):
            service, conversation = await ConversationService.get_service_for_conversation(
                mock_db,
                1,
            )

        assert service.tenant_id is None
        assert conversation.tenant_id is None


class TestGetAccessibleConversation:

    @pytest.mark.asyncio
    async def test_rejects_other_users_conversation(self, mock_db):
        from app.exceptions import NotFoundException
        from app.services.ai.conversation_service import ConversationService

        existing = _make_conversation(id=10, user_id=2)
        service = ConversationService.__new__(ConversationService)
        service.db = mock_db
        service.tenant_id = 1
        service.repo = AsyncMock()
        service.repo.get_by_id = AsyncMock(return_value=existing)

        with pytest.raises(NotFoundException):
            await service.get_accessible_conversation(10, user_id=1)


class TestConversationAccessHelpers:

    @pytest.mark.asyncio
    async def test_delete_accessible_conversation_runs_delete_after_access(self, mock_db):
        from app.services.ai.conversation_service import ConversationService

        service = ConversationService.__new__(ConversationService)
        service.db = mock_db
        service.tenant_id = 1
        service.repo = AsyncMock()
        service.get_accessible_conversation = AsyncMock(return_value=_make_conversation())
        service.delete = AsyncMock()

        await service.delete_accessible_conversation(10, user_id=1)

        service.get_accessible_conversation.assert_awaited_once_with(10, user_id=1)
        service.delete.assert_awaited_once_with(10)

    @pytest.mark.asyncio
    async def test_get_conversation_memory_state_checks_access_first(self, mock_db):
        from app.services.ai.conversation_service import ConversationService

        service = ConversationService.__new__(ConversationService)
        service.db = mock_db
        service.tenant_id = 1
        service.repo = AsyncMock()
        service.get_accessible_conversation = AsyncMock(return_value=_make_conversation())

        memory_svc = MagicMock()
        memory_svc.get_conversation_memory_state = AsyncMock(
            return_value={"preferences": []},
        )

        with patch(
            "app.services.ai.conversation_service.SessionMemoryService",
            return_value=memory_svc,
        ):
            result = await service.get_conversation_memory_state(10, user_id=1)

        assert result == {"preferences": []}
        service.get_accessible_conversation.assert_awaited_once_with(10, user_id=1)
        memory_svc.get_conversation_memory_state.assert_awaited_once_with(10)

    @pytest.mark.asyncio
    async def test_clear_conversation_memory_state_checks_access_first(self, mock_db):
        from app.services.ai.conversation_service import ConversationService

        service = ConversationService.__new__(ConversationService)
        service.db = mock_db
        service.tenant_id = 1
        service.repo = AsyncMock()
        service.get_accessible_conversation = AsyncMock(return_value=_make_conversation())

        memory_svc = MagicMock()
        memory_svc.clear_conversation_memory = AsyncMock(return_value=2)

        with patch(
            "app.services.ai.conversation_service.SessionMemoryService",
            return_value=memory_svc,
        ):
            result = await service.clear_conversation_memory_state(10, user_id=1)

        assert result == 2
        service.get_accessible_conversation.assert_awaited_once_with(10, user_id=1)
        memory_svc.clear_conversation_memory.assert_awaited_once_with(10)

    @pytest.mark.asyncio
    async def test_global_conversation_memory_uses_zero_tenant_namespace(self, mock_db):
        from app.services.ai.conversation_service import ConversationService

        service = ConversationService.__new__(ConversationService)
        service.db = mock_db
        service.tenant_id = None
        service.repo = AsyncMock()
        service.get_accessible_conversation = AsyncMock(return_value=_make_conversation(tenant_id=None))

        memory_svc = MagicMock()
        memory_svc.get_conversation_memory_state = AsyncMock(return_value={"preferences": []})

        with patch(
            "app.services.ai.conversation_service.SessionMemoryService",
            return_value=memory_svc,
        ) as mock_memory_service:
            await service.get_conversation_memory_state(10)

        mock_memory_service.assert_called_once_with(0)
        memory_svc.get_conversation_memory_state.assert_awaited_once_with(10)


class TestArchiveConversation:

    @pytest.mark.asyncio
    async def test_archive_not_found_raises(self, mock_db):
        from app.exceptions import NotFoundException
        from app.services.ai.conversation_service import ConversationService

        service = ConversationService.__new__(ConversationService)
        service.db = mock_db
        service.tenant_id = 1
        service.repo = AsyncMock()
        service.repo.get_by_id = AsyncMock(return_value=None)

        with pytest.raises(NotFoundException):
            await service.archive_conversation(999)


class TestExportConversation:

    @pytest.mark.asyncio
    async def test_export_not_found_raises(self, mock_db):
        from app.exceptions import NotFoundException
        from app.services.ai.conversation_service import ConversationService

        service = ConversationService.__new__(ConversationService)
        service.db = mock_db
        service.tenant_id = 1
        service.repo = AsyncMock()
        service.repo.get_by_id = AsyncMock(return_value=None)

        with pytest.raises(NotFoundException):
            await service.export_conversation(999)

    def test_serializers_preserve_message_agent_metadata(self):
        from app.services.ai.conversation_service import ConversationService

        conversation = _make_conversation(created_at=None)
        message = _make_message(
            role="assistant",
            content="hello",
            token_count=12,
            tool_calls=None,
            tool_call_id=None,
            created_at=None,
            agent_id=42,
        )
        message.agent = make_mock_model(name="Router Agent", avatar="/router.png")

        json_content = ConversationService._to_json(conversation, [message])
        markdown_content = ConversationService._to_markdown(conversation, [message])
        payload = json.loads(json_content)

        assert payload["messages"][0]["agent_id"] == 42
        assert payload["messages"][0]["agent_name"] == "Router Agent"
        assert payload["messages"][0]["agent_avatar"] == "/router.png"
        assert "(Router Agent)" in markdown_content


class TestGetOrCreateForChat:

    @pytest.mark.asyncio
    async def test_returns_existing_conversation(self, mock_db):
        from app.services.ai.conversation_service import ConversationService

        existing = _make_conversation(id=10, is_archived=False, agent_id=1)
        service = ConversationService.__new__(ConversationService)
        service.db = mock_db
        service.tenant_id = 1
        service.repo = AsyncMock()
        service.repo.get_by_id = AsyncMock(return_value=existing)

        result = await service.get_or_create_for_chat(
            agent_id=1, conversation_id=10, user_id=1, first_message="hello"
        )

        assert result.id == 10

    @pytest.mark.asyncio
    async def test_rejects_other_users_conversation_in_tenant_context(self, mock_db):
        from app.exceptions import NotFoundException
        from app.services.ai.conversation_service import ConversationService

        existing = _make_conversation(id=10, is_archived=False, agent_id=1, user_id=2)
        service = ConversationService.__new__(ConversationService)
        service.db = mock_db
        service.tenant_id = 1
        service.repo = AsyncMock()
        service.repo.get_by_id = AsyncMock(return_value=existing)

        with pytest.raises(NotFoundException):
            await service.get_or_create_for_chat(
                agent_id=99, conversation_id=10, user_id=1, first_message="hello"
            )


class TestUpdateStats:

    @pytest.mark.asyncio
    async def test_prefers_current_agent_output_schema(self, mock_db):
        from app.services.ai.conversation_service import ConversationService

        conversation = _make_conversation(token_count=10, total_tokens=20)
        conversation.metadata_ = {}
        conversation.agent = make_mock_model(output_schema={"schema": "conversation"})
        current_agent = make_mock_model(output_schema={"schema": "current"})
        result = make_mock_model(total_tokens=5, output='{"value": 1}')

        service = ConversationService.__new__(ConversationService)
        service.db = mock_db
        service.tenant_id = 1
        service.repo = AsyncMock()

        with patch(
            "app.services.ai.conversation_service.parse_output",
            return_value={"value": 1},
        ) as mock_parse:
            await service.update_stats(
                conversation,
                result,
                current_agent=current_agent,
            )

        mock_parse.assert_called_once_with(result.output, current_agent.output_schema)
        service.repo.update.assert_awaited_once_with(
            conversation.id,
            {
                "token_count": 15,
                "total_tokens": 25,
                "metadata_": {"output_variables": {"value": 1}},
            },
        )


class TestDeleteConversationMemoryCleanup:

    @pytest.mark.asyncio
    async def test_after_delete_clears_session_memory(self, mock_db):
        from app.services.ai.conversation_service import ConversationService

        service = ConversationService.__new__(ConversationService)
        service.db = mock_db
        service.tenant_id = 1
        service.repo = AsyncMock()

        memory_svc = MagicMock()
        memory_svc.clear_conversation_memory = AsyncMock(return_value=2)

        with patch(
            "app.services.ai.conversation_service.SessionMemoryService",
            return_value=memory_svc,
        ):
            await service._after_delete(123)

        memory_svc.clear_conversation_memory.assert_awaited_once_with(123)

    @pytest.mark.asyncio
    async def test_after_delete_memory_cleanup_failure_not_raise(self, mock_db):
        from app.services.ai.conversation_service import ConversationService

        service = ConversationService.__new__(ConversationService)
        service.db = mock_db
        service.tenant_id = 1
        service.repo = AsyncMock()

        memory_svc = MagicMock()
        memory_svc.clear_conversation_memory = AsyncMock(side_effect=RuntimeError("redis down"))

        with patch(
            "app.services.ai.conversation_service.SessionMemoryService",
            return_value=memory_svc,
        ):
            await service._after_delete(456)

        memory_svc.clear_conversation_memory.assert_awaited_once_with(456)
