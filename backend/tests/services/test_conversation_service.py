"""ConversationService 单元测试 / Test.

覆盖：对话详情、归档、搜索、导出、聊天历史加载。"""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.services.conftest import make_mock_model


def _make_conversation(**overrides):
    defaults = {
        "id": 1,
        "tenant_id": 1,
        "agent_id": 1,
        "user_id": 1,
        "owner_type": "tenant_admin",
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


class TestGetPlatformAdminChatServiceForUser:

    @pytest.mark.asyncio
    async def test_scopes_to_current_platform_admin(self, mock_db):
        from app.configs.service import PLATFORM_TENANT_ID
        from app.services.ai.conversation_service import ConversationService

        conversation = _make_conversation(
            id=12,
            tenant_id=PLATFORM_TENANT_ID,
            user_id=88,
            owner_type="platform_admin",
        )

        with patch.object(
            ConversationService,
            "get_accessible_conversation",
            new=AsyncMock(return_value=conversation),
        ) as mock_access:
            service, result = await ConversationService.get_platform_admin_chat_service_for_user(
                mock_db,
                12,
                88,
            )

        assert service.tenant_id == PLATFORM_TENANT_ID
        assert result is conversation
        mock_access.assert_awaited_once_with(
            12,
            user_id=88,
            owner_type="platform_admin",
        )


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

    @pytest.mark.asyncio
    async def test_rejects_same_numeric_id_with_different_owner_type(self, mock_db):
        from app.exceptions import NotFoundException
        from app.services.ai.conversation_service import ConversationService

        existing = _make_conversation(id=10, user_id=1, owner_type="tenant_admin")
        service = ConversationService.__new__(ConversationService)
        service.db = mock_db
        service.tenant_id = 1
        service.repo = AsyncMock()
        service.repo.get_by_id = AsyncMock(return_value=existing)

        with pytest.raises(NotFoundException):
            await service.get_accessible_conversation(
                10,
                user_id=1,
                owner_type="tenant_user",
            )


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

        service.get_accessible_conversation.assert_awaited_once_with(
            10,
            user_id=1,
            owner_type=None,
        )
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
        service.get_accessible_conversation.assert_awaited_once_with(
            10,
            user_id=1,
            owner_type=None,
        )
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
        service.get_accessible_conversation.assert_awaited_once_with(
            10,
            user_id=1,
            owner_type=None,
        )
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
            agent_id=1,
            conversation_id=10,
            user_id=1,
            owner_type="tenant_admin",
            first_message="hello",
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
                agent_id=99,
                conversation_id=10,
                user_id=1,
                owner_type="tenant_admin",
                first_message="hello",
            )

    @pytest.mark.asyncio
    async def test_rejects_conversation_agent_mismatch(self, mock_db):
        from app.exceptions import BusinessException
        from app.services.ai.conversation_service import ConversationService

        existing = _make_conversation(id=10, is_archived=False, agent_id=1, user_id=1)
        service = ConversationService.__new__(ConversationService)
        service.db = mock_db
        service.tenant_id = 1
        service.repo = AsyncMock()
        service.repo.get_by_id = AsyncMock(return_value=existing)

        with pytest.raises(BusinessException):
            await service.get_or_create_for_chat(
                agent_id=2,
                conversation_id=10,
                user_id=1,
                owner_type="tenant_admin",
                first_message="hello",
            )

    @pytest.mark.asyncio
    async def test_creates_new_conversation_with_owner_type(self, mock_db):
        from app.services.ai.conversation_service import ConversationService

        created = _make_conversation(id=11, owner_type="tenant_user", user_id=8)
        service = ConversationService.__new__(ConversationService)
        service.db = mock_db
        service.tenant_id = 1
        service.repo = AsyncMock()
        service.repo.create = AsyncMock(return_value=created)

        result = await service.get_or_create_for_chat(
            agent_id=7,
            conversation_id=None,
            user_id=8,
            owner_type="tenant_user",
            first_message="hello world",
        )

        assert result is created
        payload = service.repo.create.await_args.args[0]
        assert payload["owner_type"] == "tenant_user"
        assert payload["user_id"] == 8


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


class TestThinkingPersistence:

    @pytest.mark.asyncio
    async def test_load_chat_history_restores_reasoning_content_and_strips_tool_round_content(self, mock_db):
        from app.services.ai.conversation_service import ConversationService

        assistant = _make_message(
            role="assistant",
            content="先查询数据库。",
            tool_calls=[{"id": "tc1"}],
            tool_call_id=None,
        )
        assistant.metadata_ = {"thinking_content": "先查询数据库。"}
        tool = _make_message(
            role="tool",
            content='{"ok": true}',
            tool_calls=None,
            tool_call_id="tc1",
        )
        tool.metadata_ = {"tool_success": True}

        service = ConversationService.__new__(ConversationService)
        service.db = mock_db
        service.tenant_id = 1
        service.repo = AsyncMock()
        service._message_repo = MagicMock()
        service._message_repo.get_last_n_messages = AsyncMock(
            return_value=[assistant, tool],
        )

        history = await service.load_chat_history(1)

        assert len(history) == 2
        assert history[0].role == "assistant"
        assert history[0].content == ""
        assert history[0].reasoning_content == "先查询数据库。"

    @pytest.mark.asyncio
    async def test_persist_chat_messages_stores_thinking_content_metadata(self, mock_db):
        from app.services.ai.conversation_service import ConversationService

        conversation = _make_conversation(id=88, message_count=0)
        result = SimpleNamespace(
            messages=[
                {"role": "user", "content": "你好"},
                {
                    "role": "assistant",
                    "content": "最终答复",
                    "tool_calls": None,
                    "tool_call_id": None,
                    "attachments": None,
                    "reasoning_content": "先分析上下文。",
                },
            ],
            tool_results=[],
            partial=False,
            interrupted=False,
            completion_reason="",
            runtime_model_id=None,
            runtime_model_name=None,
            runtime_provider_id=None,
            runtime_provider_name=None,
        )

        service = ConversationService.__new__(ConversationService)
        service.db = mock_db
        service.tenant_id = 1
        service.repo = AsyncMock()
        service._message_repo = MagicMock()
        service._message_repo.get_next_sequence = AsyncMock(return_value=1)
        service._message_repo.create = AsyncMock()

        await service.persist_chat_messages(
            conversation=conversation,
            result=result,
            history_count=0,
            agent_id=7,
        )

        create_calls = service._message_repo.create.await_args_list
        assistant_payload = create_calls[1].args[0]
        assert assistant_payload["metadata_"]["thinking_content"] == "先分析上下文。"

    @pytest.mark.asyncio
    async def test_persist_chat_messages_stores_runtime_model_snapshot(self, mock_db):
        from app.services.ai.conversation_service import ConversationService

        conversation = _make_conversation(id=89, message_count=0)
        result = SimpleNamespace(
            messages=[
                {"role": "user", "content": "你好"},
                {
                    "role": "assistant",
                    "content": "最终答复",
                    "tool_calls": None,
                    "tool_call_id": None,
                    "attachments": None,
                    "reasoning_content": None,
                },
            ],
            tool_results=[],
            partial=False,
            interrupted=False,
            completion_reason="",
            runtime_model_id=33,
            runtime_model_name="GPT-5.4 XHigh",
            runtime_provider_id=5,
            runtime_provider_name="OpenAI Compatible",
        )

        service = ConversationService.__new__(ConversationService)
        service.db = mock_db
        service.tenant_id = 1
        service.repo = AsyncMock()
        service._message_repo = MagicMock()
        service._message_repo.get_next_sequence = AsyncMock(return_value=1)
        service._message_repo.create = AsyncMock()

        await service.persist_chat_messages(
            conversation=conversation,
            result=result,
            history_count=0,
            agent_id=7,
        )

        assistant_payload = service._message_repo.create.await_args_list[1].args[0]
        assert assistant_payload["model_id"] == 33
        assert assistant_payload["metadata_"]["model_name"] == "GPT-5.4 XHigh"
        assert assistant_payload["metadata_"]["provider_id"] == 5
        assert assistant_payload["metadata_"]["provider_name"] == "OpenAI Compatible"


class TestSanitizeToolMessages:
    """Test sanitize_tool_messages atomic round logic / 原子 assistant-tool round 保留策略"""

    @staticmethod
    def _msg(role: str, content: str = "", tool_calls=None, tool_call_id=None):
        from app.ai.types import ChatMessage
        return ChatMessage(
            role=role,
            content=content,
            tool_calls=tool_calls,
            tool_call_id=tool_call_id,
        )

    def test_complete_round_kept(self):
        from app.services.ai.conversation_service import ConversationService
        msgs = [
            self._msg("user", "hi"),
            self._msg("assistant", "ok", tool_calls=[{"id": "tc1"}, {"id": "tc2"}]),
            self._msg("tool", "r1", tool_call_id="tc1"),
            self._msg("tool", "r2", tool_call_id="tc2"),
            self._msg("assistant", "done"),
        ]
        result = ConversationService.sanitize_tool_messages(msgs)
        assert len(result) == 5
        assert [m.role for m in result] == ["user", "assistant", "tool", "tool", "assistant"]

    def test_partial_round_dropped(self):
        from app.services.ai.conversation_service import ConversationService
        msgs = [
            self._msg("user", "hi"),
            self._msg("assistant", "ok", tool_calls=[{"id": "tc1"}, {"id": "tc2"}]),
            self._msg("tool", "r1", tool_call_id="tc1"),
            self._msg("assistant", "done"),
        ]
        result = ConversationService.sanitize_tool_messages(msgs)
        assert len(result) == 2
        assert [m.role for m in result] == ["user", "assistant"]

    def test_orphan_tool_dropped(self):
        from app.services.ai.conversation_service import ConversationService
        msgs = [
            self._msg("tool", "orphan", tool_call_id="x"),
            self._msg("user", "hi"),
        ]
        result = ConversationService.sanitize_tool_messages(msgs)
        assert len(result) == 1
        assert result[0].role == "user"

    def test_empty_preserved(self):
        from app.services.ai.conversation_service import ConversationService
        assert ConversationService.sanitize_tool_messages([]) == []
