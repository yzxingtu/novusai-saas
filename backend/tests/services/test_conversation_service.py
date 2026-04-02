"""ConversationService 单元测试 / Test.

覆盖：对话详情、归档、搜索、导出、聊天历史加载。"""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.ai.tools.types import ToolResult
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

    @pytest.mark.asyncio
    async def test_refreshes_attachment_urls_from_attachment_id(self, mock_db):
        from app.services.ai.conversation_service import ConversationService

        conversation = _make_conversation()
        message = _make_message(role="user", content="See attachment")
        message.to_dict.return_value = {
            "id": 1,
            "role": "user",
            "content": "See attachment",
            "metadata": {
                "attachments": [
                    {
                        "attachment_id": 7,
                        "type": "image",
                        "url": "/api/public/attachments/7/access",
                    },
                    {
                        "attachment_id": 8,
                        "type": "file",
                        "url": "/api/public/attachments/8/access",
                    },
                ]
            },
        }
        message.metadata_ = {
            "attachments": [
                {
                    "attachment_id": 7,
                    "type": "image",
                    "url": "/api/public/attachments/7/access",
                },
                {
                    "attachment_id": 8,
                    "type": "file",
                    "url": "/api/public/attachments/8/access",
                },
            ]
        }

        image_attachment = SimpleNamespace(
            id=7,
            tenant_id=1,
            visibility="private",
            original_name="secret.png",
            name="secret.png",
            mime_type="image/png",
        )
        file_attachment = SimpleNamespace(
            id=8,
            tenant_id=1,
            visibility="private",
            original_name="secret.pdf",
            name="secret.pdf",
            mime_type="application/pdf",
        )

        service = ConversationService.__new__(ConversationService)
        service.db = mock_db
        service.tenant_id = 1
        service.repo = AsyncMock()
        service.get_accessible_conversation = AsyncMock(return_value=conversation)
        service._message_repo = MagicMock()
        service._message_repo.get_by_conversation = AsyncMock(return_value=[message])
        service._message_repo.count_by_conversation = AsyncMock(return_value=1)
        mock_db.execute = AsyncMock(
            return_value=SimpleNamespace(
                scalars=lambda: [image_attachment, file_attachment]
            )
        )

        detail = await service.get_conversation_detail(1, user_id=1)

        attachments = detail["message_list"][0]["metadata"]["attachments"]
        assert attachments[0]["attachment_id"] == 7
        assert attachments[0]["url"].startswith("/api/public/attachments/7/image?")
        assert "token=" in attachments[0]["url"]
        assert attachments[1]["attachment_id"] == 8
        assert attachments[1]["url"].startswith("/api/public/attachments/8/access?")
        assert "token=" in attachments[1]["url"]

    @pytest.mark.asyncio
    async def test_conversation_detail_includes_interaction_mode_metadata(self, mock_db):
        from app.services.ai.conversation_service import ConversationService

        conversation = _make_conversation()
        conversation.metadata_ = {
            "interaction_mode": "confirm",
        }
        message = _make_message(role="user", content="hello")
        message.to_dict.return_value = {
            "id": 1,
            "role": "user",
            "content": "hello",
            "metadata": {},
        }
        message.metadata_ = {}

        service = ConversationService.__new__(ConversationService)
        service.db = mock_db
        service.tenant_id = 1
        service.repo = AsyncMock()
        service.get_accessible_conversation = AsyncMock(return_value=conversation)
        service._message_repo = MagicMock()
        service._message_repo.get_by_conversation = AsyncMock(return_value=[message])
        service._message_repo.count_by_conversation = AsyncMock(return_value=1)
        mock_db.execute = AsyncMock(
            return_value=SimpleNamespace(scalars=lambda: [])
        )

        detail = await service.get_conversation_detail(1, user_id=1)

        assert detail["interaction_mode_effective"] == "confirm"
        assert detail["context_diagnostics"]["interaction_mode_effective"] == "confirm"
        assert detail["last_run_summary"]["interaction_mode_effective"] == "confirm"
        assert detail["last_run_summary"]["downgrade_reason"] is None

    @pytest.mark.asyncio
    async def test_conversation_detail_surfaces_selected_skills_and_interrupted_signal(
        self, mock_db
    ):
        from app.services.ai.conversation_service import ConversationService

        conversation = _make_conversation()
        conversation.metadata_ = {"interaction_mode": "confirm"}
        message = _make_message(role="assistant", content="处理中")
        message.to_dict.return_value = {
            "id": 1,
            "role": "assistant",
            "content": "处理中",
            "metadata": {
                "completion_reason": "interrupted",
                "turn_record": {
                    "selected_skill_names": ["runtime.page_context"],
                },
            },
        }
        message.metadata_ = {
            "completion_reason": "interrupted",
            "turn_record": {
                "selected_skill_names": ["runtime.page_context"],
            },
        }

        service = ConversationService.__new__(ConversationService)
        service.db = mock_db
        service.tenant_id = 1
        service.repo = AsyncMock()
        service.get_accessible_conversation = AsyncMock(return_value=conversation)
        service._message_repo = MagicMock()
        service._message_repo.get_by_conversation = AsyncMock(return_value=[message])
        service._message_repo.count_by_conversation = AsyncMock(return_value=1)
        mock_db.execute = AsyncMock(
            return_value=SimpleNamespace(scalars=lambda: [])
        )

        detail = await service.get_conversation_detail(1, user_id=1)

        assert detail["context_diagnostics"]["selected_skill_names"] == [
            "runtime.page_context"
        ]
        assert detail["last_run_summary"]["selected_skill_names"] == [
            "runtime.page_context"
        ]
        assert detail["context_diagnostics"]["last_interrupted"] is True
        assert detail["last_run_summary"]["interrupted"] is True


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
            (
                service,
                conversation,
            ) = await ConversationService.get_service_for_conversation(
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
            (
                service,
                result,
            ) = await ConversationService.get_platform_admin_chat_service_for_user(
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
    async def test_delete_accessible_conversation_runs_delete_after_access(
        self, mock_db
    ):
        from app.services.ai.conversation_service import ConversationService

        service = ConversationService.__new__(ConversationService)
        service.db = mock_db
        service.tenant_id = 1
        service.repo = AsyncMock()
        service.get_accessible_conversation = AsyncMock(
            return_value=_make_conversation()
        )
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
        service.get_accessible_conversation = AsyncMock(
            return_value=_make_conversation()
        )

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
        service.get_accessible_conversation = AsyncMock(
            return_value=_make_conversation()
        )

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
        service.get_accessible_conversation = AsyncMock(
            return_value=_make_conversation(tenant_id=None)
        )

        memory_svc = MagicMock()
        memory_svc.get_conversation_memory_state = AsyncMock(
            return_value={"preferences": []}
        )

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


class TestSearchMessages:
    @pytest.mark.asyncio
    async def test_search_messages_hydrates_attachment_metadata(self, mock_db):
        from app.services.ai.conversation_service import ConversationService

        message = _make_message(role="user", content="See attachment")
        message.to_dict.return_value = {
            "id": 1,
            "role": "user",
            "content": "See attachment",
        }
        message.metadata_ = {
            "attachments": [
                {
                    "attachment_id": 9,
                    "type": "image",
                    "url": "/api/public/attachments/9/access",
                }
            ]
        }

        image_attachment = SimpleNamespace(
            id=9,
            tenant_id=1,
            visibility="private",
            original_name="result.png",
            name="result.png",
            mime_type="image/png",
        )

        service = ConversationService.__new__(ConversationService)
        service.db = mock_db
        service.tenant_id = 1
        service.repo = AsyncMock()
        service._message_repo = MagicMock()
        service._message_repo.search_by_content = AsyncMock(
            return_value=([message], 1)
        )
        mock_db.execute = AsyncMock(
            return_value=SimpleNamespace(scalars=lambda: [image_attachment])
        )

        result = await service.search_messages("attachment")

        attachments = result["items"][0]["metadata"]["attachments"]
        assert attachments[0]["attachment_id"] == 9
        assert attachments[0]["url"].startswith("/api/public/attachments/9/image?")
        assert "token=" in attachments[0]["url"]


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

    @pytest.mark.asyncio
    async def test_export_conversation_preserves_hydrated_attachments(self, mock_db):
        from app.services.ai.conversation_service import ConversationService

        conversation = _make_conversation(created_at=None)
        message = _make_message(
            role="user",
            content="Look at this image",
            token_count=10,
            tool_calls=None,
            tool_call_id=None,
            created_at=None,
        )
        message.metadata_ = {
            "attachments": [
                {
                    "attachment_id": 11,
                    "type": "image",
                    "url": "/api/public/attachments/11/access",
                }
            ]
        }

        image_attachment = SimpleNamespace(
            id=11,
            tenant_id=1,
            visibility="private",
            original_name="shot.png",
            name="shot.png",
            mime_type="image/png",
        )

        service = ConversationService.__new__(ConversationService)
        service.db = mock_db
        service.tenant_id = 1
        service.repo = AsyncMock()
        service.repo.get_by_id = AsyncMock(return_value=conversation)
        service._message_repo = MagicMock()
        service._message_repo.get_by_conversation = AsyncMock(return_value=[message])
        service._message_repo.count_by_conversation = AsyncMock(return_value=1)
        mock_db.execute = AsyncMock(
            return_value=SimpleNamespace(scalars=lambda: [image_attachment])
        )

        result = await service.export_conversation(1, export_format="json")
        payload = json.loads(result["content"])
        attachments = payload["messages"][0]["metadata"]["attachments"]

        assert attachments[0]["attachment_id"] == 11
        assert attachments[0]["url"].startswith("/api/public/attachments/11/image?")
        assert "token=" in attachments[0]["url"]

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
        message.metadata_ = {
            "attachments": [
                {
                    "attachment_id": 7,
                    "type": "file",
                    "name": "report.pdf",
                    "url": "/api/public/attachments/7/access",
                }
            ]
        }

        json_content = ConversationService._to_json(conversation, [message])
        markdown_content = ConversationService._to_markdown(conversation, [message])
        payload = json.loads(json_content)

        assert payload["messages"][0]["agent_id"] == 42
        assert payload["messages"][0]["agent_name"] == "Router Agent"
        assert payload["messages"][0]["agent_avatar"] == "/router.png"
        assert payload["messages"][0]["metadata"]["attachments"][0]["attachment_id"] == 7
        assert "**Attachments:**" in markdown_content
        assert "report.pdf" in markdown_content
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
        memory_svc.clear_conversation_memory = AsyncMock(
            side_effect=RuntimeError("redis down")
        )

        with patch(
            "app.services.ai.conversation_service.SessionMemoryService",
            return_value=memory_svc,
        ):
            await service._after_delete(456)

        memory_svc.clear_conversation_memory.assert_awaited_once_with(456)


class TestThinkingPersistence:
    @pytest.mark.asyncio
    async def test_load_chat_history_restores_reasoning_content_and_strips_tool_round_content(
        self, mock_db
    ):
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
    async def test_persist_chat_messages_stores_thinking_content_metadata(
        self, mock_db
    ):
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

    @pytest.mark.asyncio
    async def test_persist_chat_messages_keeps_rich_tool_contract_and_interaction_metadata(
        self, mock_db
    ):
        from app.services.ai.conversation_service import ConversationService

        conversation = _make_conversation(id=891, message_count=0)
        result = SimpleNamespace(
            messages=[
                {"role": "user", "content": "统计今天调用情况"},
                {
                    "role": "assistant",
                    "content": "先查询数据库。",
                    "tool_calls": [
                        {
                            "id": "tc_data_1",
                            "function": {
                                "name": "data_query",
                                "arguments": '{"question":"统计今天调用情况"}',
                            },
                            "pending_consent": {
                                "arguments": {"question": "统计今天调用情况"},
                                "tool_name": "data_query",
                            },
                            "summary_payload": {"tables": ["ai_call_logs"]},
                        }
                    ],
                    "metadata": {
                        "pending_confirmation": {
                            "action": "query",
                            "preview": {"sql": "SELECT 1"},
                            "table": "ai_call_logs",
                        }
                    },
                    "reasoning_content": "先查询数据库。",
                    "tool_call_id": None,
                },
                {
                    "role": "tool",
                    "content": '{"success": true}',
                    "tool_calls": None,
                    "tool_call_id": "tc_data_1",
                },
            ],
            tool_results=[
                ToolResult(
                    tool_call_id="tc_data_1",
                    name="data_query",
                    success=True,
                    duration_ms=123,
                    display_name="平台数据管理",
                    summary="按今天范围统计调用",
                    result_link="/admin/ai/chat",
                    summary_payload={
                        "filters": ["today"],
                        "tables": ["ai_call_logs"],
                        "tool_kind": "data_query",
                    },
                )
            ],
            partial=False,
            interrupted=False,
            completion_reason="",
            runtime_model_id=None,
            runtime_model_name=None,
            runtime_provider_id=None,
            runtime_provider_name=None,
            rag_sources=None,
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
        tool_payload = create_calls[2].args[0]

        assert assistant_payload["tool_calls"][0]["display_name"] == "平台数据管理"
        assert assistant_payload["tool_calls"][0]["summary"] == "按今天范围统计调用"
        assert assistant_payload["tool_calls"][0]["summary_payload"] == {
            "filters": ["today"],
            "tables": ["ai_call_logs"],
            "tool_kind": "data_query",
        }
        assert assistant_payload["metadata_"]["pending_confirmation"] == {
            "action": "query",
            "preview": {"sql": "SELECT 1"},
            "table": "ai_call_logs",
        }
        assert tool_payload["metadata_"]["tool_summary"] == "按今天范围统计调用"
        assert tool_payload["metadata_"]["tool_summary_payload"] == {
            "filters": ["today"],
            "tables": ["ai_call_logs"],
            "tool_kind": "data_query",
        }

    @pytest.mark.asyncio
    async def test_persist_chat_messages_stores_context_diagnostics_on_final_assistant(
        self, mock_db
    ):
        from app.services.ai.conversation_service import ConversationService

        conversation = _make_conversation(id=892, message_count=0)
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
            runtime_model_id=None,
            runtime_model_name=None,
            runtime_provider_id=None,
            runtime_provider_name=None,
            rag_sources=[{"source": "KB", "chunk_id": 1}],
            rag_source_kinds=["formal_kb"],
            context_compacted=False,
            memory_flush_triggered=False,
            memory_recalled=True,
            prune_stats={"mode": "transient_tool_result_pruning", "pruned_message_count": 1},
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
        assert assistant_payload["metadata_"]["rag_source_kinds"] == ["formal_kb"]
        assert assistant_payload["metadata_"]["memory_recalled"] is True
        assert assistant_payload["metadata_"]["prune_stats"] == {
            "mode": "transient_tool_result_pruning",
            "pruned_message_count": 1,
        }

    @pytest.mark.asyncio
    async def test_persist_chat_messages_records_context_and_summary_metadata(
        self, mock_db
    ):
        from app.services.ai.conversation_service import ConversationService

        conversation = _make_conversation(id=900, message_count=0)
        result = SimpleNamespace(
            messages=[
                {"role": "user", "content": "请问"},
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
            runtime_model_id=None,
            runtime_model_name=None,
            runtime_provider_id=None,
            runtime_provider_name=None,
        )

        context_diag = {"dummy": "value"}
        last_summary = {"duration_ms": 42}

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
            context_diagnostics=context_diag,
            last_run_summary=last_summary,
        )

        assistant_payload = service._message_repo.create.await_args_list[1].args[0]
        assert assistant_payload["metadata_"]["context_diagnostics"]["dummy"] == "value"
        assert (
            assistant_payload["metadata_"]["context_diagnostics"]["last_interrupted"]
            is False
        )
        assert assistant_payload["metadata_"]["last_run_summary"] == last_summary

    @pytest.mark.asyncio
    async def test_persist_chat_messages_persists_turn_record_shadow_diff_metadata(
        self, mock_db
    ):
        from app.services.ai.conversation_service import ConversationService

        conversation = _make_conversation(id=901, message_count=0)
        result = SimpleNamespace(
            messages=[
                {"role": "user", "content": "请继续"},
                {
                    "role": "assistant",
                    "content": "这是最终结果",
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
            runtime_model_id=None,
            runtime_model_name=None,
            runtime_provider_id=None,
            runtime_provider_name=None,
            turn_record={
                "turn_outcome": "success",
                "termination_reason": "protocol_fallback",
                "protocol_path": "shadow",
                "selected_tool_names": ["web_search", "fetch_url"],
                "selected_skill_names": ["runtime.page_context", "runtime.route"],
                "context_sources": [
                    {
                        "kind": "page_context",
                        "name": "admin.ai.conversations",
                        "active": True,
                        "metadata": {"page_key": "admin.ai.conversations"},
                    }
                ],
                "fallback_history": [
                    {
                        "from_protocol": "responses",
                        "to_protocol": "chat_completions",
                        "reason": "stream_empty_no_output",
                        "recovered": True,
                        "metadata": {"recovery_path": "sync_chat_completions"},
                    }
                ],
                "metadata": {
                    "shadow_diff": {
                        "selected_tool_names": {
                            "legacy": [],
                            "runtime_v2": ["web_search", "fetch_url"],
                        }
                    }
                },
            },
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
        metadata = assistant_payload["metadata_"]
        assert metadata["turn_outcome"] == "success"
        assert metadata["termination_reason"] == "protocol_fallback"
        assert metadata["protocol_path"] == "shadow"
        assert metadata["selected_tool_names"] == ["web_search", "fetch_url"]
        assert metadata["selected_skill_names"] == [
            "runtime.page_context",
            "runtime.route",
        ]
        assert metadata["turn_record"]["fallback_history"][0]["recovered"] is True
        assert metadata["turn_record"]["metadata"]["shadow_diff"] == {
            "selected_tool_names": {
                "legacy": [],
                "runtime_v2": ["web_search", "fetch_url"],
            }
        }
        assert metadata["context_diagnostics"]["protocol_path"] == "shadow"
        assert metadata["context_diagnostics"]["selected_skill_names"] == [
            "runtime.page_context",
            "runtime.route",
        ]
        assert metadata["last_run_summary"]["termination_reason"] == "protocol_fallback"
        assert metadata["last_run_summary"]["selected_skill_names"] == [
            "runtime.page_context",
            "runtime.route",
        ]

    @pytest.mark.asyncio
    async def test_persist_chat_messages_marks_interrupted_on_tool_round_without_final_plain_assistant(
        self, mock_db
    ):
        from app.services.ai.conversation_service import ConversationService

        conversation = _make_conversation(id=905, message_count=0)
        result = SimpleNamespace(
            success=False,
            messages=[
                {"role": "user", "content": "继续执行"},
                {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {
                            "id": "tc_interrupted_1",
                            "function": {
                                "name": "data_query",
                                "arguments": '{"query":"today"}',
                            },
                        }
                    ],
                    "tool_call_id": None,
                    "attachments": None,
                    "reasoning_content": None,
                    "metadata": {},
                },
                {
                    "role": "tool",
                    "content": '{"ok": true}',
                    "tool_calls": None,
                    "tool_call_id": "tc_interrupted_1",
                    "attachments": None,
                    "reasoning_content": None,
                },
            ],
            tool_results=[],
            partial=True,
            interrupted=True,
            completion_reason="interrupted",
            runtime_model_id=None,
            runtime_model_name=None,
            runtime_provider_id=None,
            runtime_provider_name=None,
            turn_record=None,
            rag_sources=None,
            rag_source_kinds=[],
            context_compacted=False,
            memory_flush_triggered=False,
            memory_recalled=False,
            prune_stats=None,
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
        metadata = assistant_payload["metadata_"]
        assert metadata["partial"] is True
        assert metadata["interrupted"] is True
        assert metadata["completion_reason"] == "interrupted"
        assert metadata["turn_outcome"] == "partial"
        assert metadata["termination_reason"] == "interrupted"
        assert metadata["context_diagnostics"]["last_interrupted"] is True
        assert metadata["last_run_summary"]["interrupted"] is True

    def test_extract_turn_diagnostics_infers_partial_from_interrupted_completion_reason(
        self,
    ):
        from app.services.ai.conversation_service import ConversationService

        payload = ConversationService._extract_turn_diagnostics_from_metadata(
            {"completion_reason": "interrupted"}
        )

        assert payload["turn_outcome"] == "partial"
        assert payload["termination_reason"] == "interrupted"

    @pytest.mark.asyncio
    async def test_persist_chat_messages_skips_internal_only_messages(self, mock_db):
        from app.services.ai.conversation_service import ConversationService

        conversation = _make_conversation(id=90, message_count=0)
        result = SimpleNamespace(
            messages=[
                {"role": "user", "content": "请看这个页面"},
                {
                    "role": "user",
                    "content": "Analyze the attached screenshot internally.",
                    "attachments": [{"type": "image", "url": "/uploads/s1.jpg"}],
                    "internal_only": True,
                    "tool_calls": None,
                    "tool_call_id": None,
                    "reasoning_content": None,
                },
                {
                    "role": "assistant",
                    "content": "我已完成分析",
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
        assert len(create_calls) == 2
        assert [call.args[0]["role"] for call in create_calls] == ["user", "assistant"]

    @pytest.mark.asyncio
    async def test_update_last_assistant_interaction_state_marks_metadata_and_tool_calls(
        self, mock_db
    ):
        from app.services.ai.conversation_service import ConversationService

        assistant = _make_message(
            id=101,
            role="assistant",
            content="需要确认",
            tool_calls=[
                {
                    "id": "tc_confirm_1",
                    "function": {"name": "data_query", "arguments": "{}"},
                    "pending_consent": {"tool_name": "data_query"},
                }
            ],
        )
        assistant.metadata_ = {
            "action_buttons": [{"label": "查看明细", "value": "查看明细"}],
            "pending_confirmation": {"action": "query", "table": "ai_call_logs"},
            "pending_consent": {"tool_name": "data_query"},
        }

        service = ConversationService.__new__(ConversationService)
        service.db = mock_db
        service.tenant_id = 1
        service.repo = AsyncMock()
        service.repo.get_by_id = AsyncMock(return_value=_make_conversation(id=88))
        service._message_repo = MagicMock()
        service._message_repo.get_last_n_messages = AsyncMock(return_value=[assistant])
        service._message_repo.update = AsyncMock()

        updated = await service.update_last_assistant_interaction_state(
            conversation_id=88,
            updates=[
                {"kind": "action_buttons", "value": "查看明细"},
                {
                    "action": "query",
                    "kind": "pending_confirmation",
                    "rejected": False,
                    "table": "ai_call_logs",
                },
                {
                    "kind": "pending_consent",
                    "rejected": True,
                    "tool_name": "data_query",
                },
            ],
        )

        assert updated == 1
        final_update = service._message_repo.update.await_args_list[-1].args[1]
        assert final_update["metadata_"]["action_buttons_used"] is True
        assert final_update["metadata_"]["pending_confirmation"]["resolved"] is True
        assert final_update["metadata_"]["pending_consent"]["resolved"] is True
        assert final_update["metadata_"]["pending_consent"]["rejected"] is True
        assert final_update["tool_calls"][0]["pending_consent"]["resolved"] is True

    @pytest.mark.asyncio
    async def test_update_last_assistant_interaction_state_records_execution_decisions(
        self, mock_db
    ):
        from app.services.ai.conversation_service import ConversationService

        assistant = _make_message(
            id=202,
            role="assistant",
            content="需要确认",
            tool_calls=[
                {
                    "id": "tc_confirm_2",
                    "function": {"name": "web_search", "arguments": "{}"},
                    "pending_consent": {"tool_name": "web_search"},
                }
            ],
        )
        assistant.metadata_ = {
            "pending_confirmation": {"action": "delete", "table": "agents"},
            "pending_consent": {"tool_name": "web_search"},
            "context_diagnostics": {
                "tool_planner": {
                    "intent": "direct_reply",
                    "family": "none",
                    "allow_no_tool": True,
                    "allow_family_continuation": False,
                    "reason": "smalltalk_or_support_no_tool",
                }
            },
        }

        service = ConversationService.__new__(ConversationService)
        service.db = mock_db
        service.tenant_id = 1
        service.repo = AsyncMock()
        service.repo.get_by_id = AsyncMock(return_value=_make_conversation(id=99, agent_id=7))
        service._message_repo = MagicMock()
        service._message_repo.get_last_n_messages = AsyncMock(return_value=[assistant])
        service._message_repo.update = AsyncMock()

        with patch(
            "app.services.ai.conversation_service.ExecutionDecisionService.record_decision",
            new=AsyncMock(),
        ) as record_decision:
            updated = await service.update_last_assistant_interaction_state(
                conversation_id=99,
                user_id=1,
                owner_type="tenant_admin",
                updates=[
                    {
                        "action": "delete",
                        "kind": "pending_confirmation",
                        "rejected": False,
                        "table": "agents",
                    },
                    {
                        "kind": "pending_consent",
                        "rejected": False,
                        "auto_approved": True,
                        "tool_name": "web_search",
                    },
                ],
            )

        assert updated == 1
        assert record_decision.await_count == 2
        first_payload = record_decision.await_args_list[0].args[0]
        second_payload = record_decision.await_args_list[1].args[0]
        assert first_payload["decision_type"] == "confirmation"
        assert first_payload["evidence"]["tool_planner"]["reason"] == "smalltalk_or_support_no_tool"
        assert second_payload["decision_type"] == "consent"
        assert second_payload["evidence"]["tool_planner"]["reason"] == "smalltalk_or_support_no_tool"
        assert second_payload["status"] == "auto_approved"

    @pytest.mark.asyncio
    async def test_update_last_assistant_interaction_state_also_writes_ai_action_log(
        self, mock_db
    ):
        from app.services.ai.conversation_service import ConversationService

        assistant = _make_message(
            id=303,
            role="assistant",
            content="需要授权",
            tool_calls=[
                {
                    "id": "tc_auto_1",
                    "function": {"name": "web_search", "arguments": "{}"},
                    "pending_consent": {"tool_name": "web_search"},
                }
            ],
        )
        assistant.metadata_ = {
            "pending_consent": {"tool_name": "web_search"},
        }

        service = ConversationService.__new__(ConversationService)
        service.db = mock_db
        service.tenant_id = 1
        service.repo = AsyncMock()
        service.repo.get_by_id = AsyncMock(return_value=_make_conversation(id=77, agent_id=7))
        service._message_repo = MagicMock()
        service._message_repo.get_last_n_messages = AsyncMock(return_value=[assistant])
        service._message_repo.update = AsyncMock()

        with patch(
            "app.services.ai.conversation_service.ExecutionDecisionService.record_decision",
            new=AsyncMock(return_value=SimpleNamespace(id=901)),
        ), patch(
            "app.services.ai.conversation_service.write_ai_action_log",
            new=AsyncMock(),
        ) as write_action_log:
            await service.update_last_assistant_interaction_state(
                conversation_id=77,
                user_id=1,
                owner_type="tenant_admin",
                updates=[
                    {
                        "kind": "pending_consent",
                        "rejected": False,
                        "auto_approved": True,
                        "tool_name": "web_search",
                    },
                ],
            )

        write_action_log.assert_awaited_once()
        log_kwargs = write_action_log.await_args.kwargs
        assert log_kwargs["action_name"] == "web_search"
        assert log_kwargs["action_type"] == "confirm"
        assert log_kwargs["status"] == "success"
        assert log_kwargs["execution_decision_id"] == 901
        assert log_kwargs["response_data"]["decision_status"] == "auto_approved"


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
        assert [m.role for m in result] == [
            "user",
            "assistant",
            "tool",
            "tool",
            "assistant",
        ]

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
