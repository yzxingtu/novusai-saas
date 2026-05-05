"""
Test type: behavioral
Scope: ConversationService retained/detail/export/search read-model behavior.
覆盖：对话详情、归档、搜索、导出、聊天历史加载。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from enum import Enum
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.tools.types import ToolResult
from app.ai.types import ChatMessage
from tests.services.conftest import make_mock_model


class _MetadataEnum(Enum):
    READY = "ready"


@dataclass
class _MetadataDataclassPayload:
    amount: Decimal
    scheduled_for: date


class _PydanticLikePayload:
    def model_dump(self, _mode: str = "python"):
        return {
            "score": Decimal("9.5"),
            "state": _MetadataEnum.READY,
            "generated_at": datetime(2026, 4, 7, 9, 30, tzinfo=timezone.utc),
        }


class _DictLikePayload:
    def dict(self):
        return {"expires_on": date(2026, 4, 8), "attempts": Decimal("2")}


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


class _TestStatus(Enum):
    OK = "ok"


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
    async def test_conversation_detail_hides_legacy_interaction_mode_metadata(
        self, mock_db
    ):
        from app.services.ai.conversation_service import ConversationService

        conversation = _make_conversation(
            metadata={
                "interaction_mode": "confirm",
                "interaction_mode_requested": "trusted_auto",
                "topic": "demo",
            }
        )
        conversation.metadata_ = {
            "interaction_mode": "confirm",
            "interaction_mode_requested": "trusted_auto",
        }
        message = _make_message(role="user", content="hello")
        message.to_dict.return_value = {
            "id": 1,
            "role": "user",
            "content": "hello",
            "metadata": {},
        }
        message.metadata_ = {
            "interaction_mode_effective": "confirm",
            "nested": {
                "interaction_mode_requested": "trusted_auto",
                "keep": "ok",
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
        mock_db.execute = AsyncMock(return_value=SimpleNamespace(scalars=lambda: []))

        detail = await service.get_conversation_detail(1, user_id=1)

        assert "interaction_mode_requested" not in detail
        assert "interaction_mode_effective" not in detail
        assert "interaction_mode_effective" not in detail["context_diagnostics"]
        assert "interaction_mode_effective" not in detail["last_run_summary"]
        assert "downgrade_reason" not in detail["last_run_summary"]
        assert detail["metadata"] == {"topic": "demo"}
        assert detail["message_list"][0]["metadata"] == {"nested": {"keep": "ok"}}

    @pytest.mark.asyncio
    async def test_conversation_detail_surfaces_last_error_when_no_messages_exist(
        self, mock_db
    ):
        from app.services.ai.conversation_service import ConversationService

        conversation = _make_conversation(message_count=0)
        conversation.metadata_ = {
            "interaction_mode": "confirm",
            "last_error": {
                "timestamp": "2026-04-07T12:00:00+00:00",
                "error_type": "stream_execution_error",
                "friendly_message": "服务器内部错误",
                "partial": True,
            },
        }

        service = ConversationService.__new__(ConversationService)
        service.db = mock_db
        service.tenant_id = 1
        service.repo = AsyncMock()
        service.get_accessible_conversation = AsyncMock(return_value=conversation)
        service._message_repo = MagicMock()
        service._message_repo.get_by_conversation = AsyncMock(return_value=[])
        service._message_repo.count_by_conversation = AsyncMock(return_value=0)
        service._message_repo.get_latest_assistant_message = AsyncMock(
            return_value=None
        )
        mock_db.execute = AsyncMock(return_value=SimpleNamespace(scalars=lambda: []))

        detail = await service.get_conversation_detail(1, user_id=1)

        assert detail["context_diagnostics"]["failure_kind"] == "stream_execution_error"
        assert detail["context_diagnostics"]["persistence_error"] is True
        assert detail["last_run_summary"]["error_message"] == "服务器内部错误"
        assert detail["last_error"]["partial"] is True
        assert detail["turn_flow"]["completion_reason"] == "stream_execution_error"
        assert detail["turn_flow"]["timeline"][-1]["type"] == "failed"

    @pytest.mark.asyncio
    async def test_conversation_detail_sanitizes_stale_html_last_error_when_no_messages_exist(
        self, mock_db
    ):
        from app.core.i18n import _
        from app.services.ai.conversation_service import ConversationService

        conversation = _make_conversation(message_count=0)
        leaked_html = (
            "<!DOCTYPE html><html><body>Bad gateway"
            "<div>Cloudflare Ray ID: 123</div></body></html>"
        )
        conversation.metadata_ = {
            "interaction_mode": "confirm",
            "last_error": {
                "timestamp": "2026-04-07T12:00:00+00:00",
                "error_type": "provider_http_5xx",
                "debug_message": _("ai.error.provider_server_error"),
                "error_message": leaked_html,
                "friendly_message": leaked_html,
                "partial": True,
            },
        }

        service = ConversationService.__new__(ConversationService)
        service.db = mock_db
        service.tenant_id = 1
        service.repo = AsyncMock()
        service.get_accessible_conversation = AsyncMock(return_value=conversation)
        service._message_repo = MagicMock()
        service._message_repo.get_by_conversation = AsyncMock(return_value=[])
        service._message_repo.count_by_conversation = AsyncMock(return_value=0)
        service._message_repo.get_latest_assistant_message = AsyncMock(
            return_value=None
        )
        mock_db.execute = AsyncMock(return_value=SimpleNamespace(scalars=lambda: []))

        detail = await service.get_conversation_detail(1, user_id=1)

        assert detail["last_error"]["friendly_message"] == _(
            "ai.error.provider_server_error"
        )
        assert detail["last_error"]["error_message"] == _(
            "ai.error.provider_server_error"
        )
        assert detail["last_run_summary"]["error_message"] == _(
            "ai.error.provider_server_error"
        )
        assert "Cloudflare Ray ID" not in str(detail["last_error"])

    @pytest.mark.asyncio
    async def test_conversation_detail_sanitizes_stale_html_error_message_in_assistant_message(
        self, mock_db
    ):
        from app.core.i18n import _
        from app.services.ai.conversation_service import ConversationService

        conversation = _make_conversation()
        conversation.metadata_ = {"interaction_mode": "confirm"}
        leaked_html = (
            "<!DOCTYPE html><html><body>Bad gateway"
            "<div>Cloudflare Ray ID: 456</div></body></html>"
        )
        message = _make_message(role="assistant", content=leaked_html)
        message.to_dict.return_value = {
            "id": 1,
            "role": "assistant",
            "content": leaked_html,
            "metadata": {
                "error": True,
                "error_type": "provider_http_5xx",
                "error_message": leaked_html,
                "raw_error_message": leaked_html,
            },
        }
        message.metadata_ = {
            "error": True,
            "error_type": "provider_http_5xx",
            "error_message": leaked_html,
            "raw_error_message": leaked_html,
        }

        service = ConversationService.__new__(ConversationService)
        service.db = mock_db
        service.tenant_id = 1
        service.repo = AsyncMock()
        service.get_accessible_conversation = AsyncMock(return_value=conversation)
        service._message_repo = MagicMock()
        service._message_repo.get_by_conversation = AsyncMock(return_value=[message])
        service._message_repo.count_by_conversation = AsyncMock(return_value=1)
        mock_db.execute = AsyncMock(return_value=SimpleNamespace(scalars=lambda: []))

        detail = await service.get_conversation_detail(1, user_id=1)

        assistant = detail["message_list"][0]
        assert assistant["content"] == _("ai.error.provider_server_error")
        assert assistant["metadata"]["error_message"] == _(
            "ai.error.provider_server_error"
        )
        assert assistant["metadata"]["raw_error_message"] == _(
            "ai.error.provider_server_error"
        )
        assert "Cloudflare Ray ID" not in str(assistant)

    @pytest.mark.asyncio
    async def test_conversation_detail_uses_latest_assistant_for_diagnostics_even_when_page_is_older(
        self, mock_db
    ):
        from app.services.ai.conversation_service import ConversationService

        conversation = _make_conversation(message_count=120)
        older_assistant = _make_message(role="assistant", content="旧结果")
        older_assistant.to_dict.return_value = {
            "id": 11,
            "sequence": 50,
            "role": "assistant",
            "content": "旧结果",
            "token_count": 10,
            "created_at": "2026-04-01T00:00:00+00:00",
            "metadata": {
                "turn_record": {
                    "execution_path": "fast",
                    "termination_reason": "completed",
                }
            },
        }
        older_assistant.metadata_ = older_assistant.to_dict.return_value["metadata"]

        latest_assistant = _make_message(role="assistant", content="新结果")
        latest_assistant.to_dict.return_value = {
            "id": 99,
            "sequence": 120,
            "role": "assistant",
            "content": "新结果",
            "token_count": 20,
            "created_at": "2026-04-02T00:00:00+00:00",
            "metadata": {
                "turn_record": {
                    "execution_path": "deep",
                    "termination_reason": "tool_round_budget_exceeded",
                    "budget": {
                        "status": "exited",
                        "exit_reason": "tool_round_budget_exceeded",
                    },
                    "tool_loop_progress": {
                        "budget_exit_reason": "tool_round_budget_exceeded"
                    },
                }
            },
        }
        latest_assistant.metadata_ = latest_assistant.to_dict.return_value["metadata"]

        service = ConversationService.__new__(ConversationService)
        service.db = mock_db
        service.tenant_id = 1
        service.repo = AsyncMock()
        service.get_accessible_conversation = AsyncMock(return_value=conversation)
        service._message_repo = MagicMock()
        service._message_repo.get_by_conversation = AsyncMock(
            return_value=[older_assistant]
        )
        service._message_repo.count_by_conversation = AsyncMock(return_value=120)
        service._message_repo.get_latest_assistant_message = AsyncMock(
            return_value=latest_assistant
        )
        mock_db.execute = AsyncMock(return_value=SimpleNamespace(scalars=lambda: []))

        detail = await service.get_conversation_detail(
            1, message_skip=0, message_limit=50
        )

        assert detail["message_list"][0]["id"] == 11
        assert detail["context_diagnostics"]["execution_path"] == "deep"
        assert detail["context_diagnostics"]["budget_exit_reason"] == (
            "tool_round_budget_exceeded"
        )
        assert detail["last_run_summary"]["termination_reason"] == (
            "tool_round_budget_exceeded"
        )
        assert (
            detail["message_list"][0]["turn_flow"]["timeline"][-1]["type"]
            == "completed"
        )

    @pytest.mark.asyncio
    async def test_conversation_detail_normalizes_provider_failure_after_partial_progress_turn_flow(
        self, mock_db
    ):
        from app.services.ai.conversation_service import ConversationService

        conversation = _make_conversation()
        conversation.metadata_ = {"interaction_mode": "confirm"}
        message = _make_message(role="assistant", content="已输出部分内容")
        message.to_dict.return_value = {
            "id": 1,
            "role": "assistant",
            "content": "已输出部分内容",
            "metadata": {
                "turn_record": {
                    "turn_outcome": "partial",
                    "termination_reason": "provider_failure_after_partial_progress",
                    "metadata": {
                        "turn_diagnostics": {
                            "failures": {
                                "failure_kind": "provider_http_5xx",
                            }
                        }
                    },
                },
                "turn_flow": {
                    "timeline": [
                        {
                            "id": "answer_assembly",
                            "type": "answer_assembly",
                            "status": "completed",
                            "title": "答案生成",
                            "summary": "已生成最终答复",
                        },
                        {
                            "id": "terminal",
                            "type": "completed",
                            "status": "completed",
                            "title": "本轮结束",
                            "summary": "provider_failure_after_partial_progress",
                        },
                    ],
                    "completion_reason": "provider_failure_after_partial_progress",
                    "interrupted": False,
                    "error_surface": None,
                },
            },
        }
        message.metadata_ = message.to_dict.return_value["metadata"]

        service = ConversationService.__new__(ConversationService)
        service.db = mock_db
        service.tenant_id = 1
        service.repo = AsyncMock()
        service.get_accessible_conversation = AsyncMock(return_value=conversation)
        service._message_repo = MagicMock()
        service._message_repo.get_by_conversation = AsyncMock(return_value=[message])
        service._message_repo.count_by_conversation = AsyncMock(return_value=1)
        mock_db.execute = AsyncMock(return_value=SimpleNamespace(scalars=lambda: []))

        detail = await service.get_conversation_detail(1, user_id=1)

        turn_flow = detail["message_list"][0]["turn_flow"]
        answer_assembly = next(
            stage
            for stage in turn_flow["timeline"]
            if stage["type"] == "answer_assembly"
        )
        assert (
            turn_flow["completion_reason"] == "provider_failure_after_partial_progress"
        )
        assert answer_assembly["status"] == "error"
        assert turn_flow["timeline"][-1]["type"] == "failed"
        assert turn_flow["timeline"][-1]["status"] == "error"
        assert turn_flow["error_surface"]["message"]

    @pytest.mark.asyncio
    async def test_conversation_detail_projects_turn_flow_and_strips_legacy_assistant_fields(
        self, mock_db
    ):
        from app.services.ai.conversation_service import ConversationService

        conversation = _make_conversation()
        message = _make_message(role="assistant", content="最终答复")
        message.to_dict.return_value = {
            "id": 1,
            "role": "assistant",
            "content": "最终答复",
            "tool_calls": [
                {
                    "id": "tc_1",
                    "display_name": "数据查询",
                    "summary": "按今天范围统计调用",
                    "result_link": "/admin/ai/chat",
                }
            ],
            "metadata": {
                "thinking_content": "先分析上下文。",
                "rag_sources": [
                    {
                        "source": "KB",
                        "chunk_id": 1,
                        "title": "知识库证据",
                        "snippet": "命中了相关文档",
                    }
                ],
            },
        }
        message.metadata_ = dict(message.to_dict.return_value["metadata"])

        service = ConversationService.__new__(ConversationService)
        service.db = mock_db
        service.tenant_id = 1
        service.repo = AsyncMock()
        service.get_accessible_conversation = AsyncMock(return_value=conversation)
        service._message_repo = MagicMock()
        service._message_repo.get_by_conversation = AsyncMock(return_value=[message])
        service._message_repo.count_by_conversation = AsyncMock(return_value=1)
        mock_db.execute = AsyncMock(return_value=SimpleNamespace(scalars=lambda: []))

        detail = await service.get_conversation_detail(1, user_id=1)

        assistant_payload = detail["message_list"][0]
        assert "tool_calls" not in assistant_payload
        assert "thinking_content" not in assistant_payload["metadata"]
        assert "rag_sources" not in assistant_payload["metadata"]
        assert (
            assistant_payload["metadata"]["turn_flow"] == assistant_payload["turn_flow"]
        )
        assert any(
            stage["type"] == "thinking"
            for stage in assistant_payload["turn_flow"]["timeline"]
        )
        assert any(
            stage["type"] == "retrieval"
            for stage in assistant_payload["turn_flow"]["timeline"]
        )
        assert any(
            item["tool_call_id"] == "tc_1"
            for item in assistant_payload["turn_flow"]["evidence"]
        )


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
        memory_svc.get_state = AsyncMock(return_value={"preferences": []})
        service._memory_state_service = memory_svc

        result = await service.get_conversation_memory_state(10, user_id=1)

        assert result == {
            "constraints": [],
            "preferences": [],
            "task_states": [],
            "updated_at": 0,
            "verified_facts": [],
            "version": 0,
        }
        service.get_accessible_conversation.assert_awaited_once_with(
            10,
            user_id=1,
            owner_type=None,
        )
        memory_svc.get_state.assert_awaited_once_with(10)

    @pytest.mark.asyncio
    async def test_get_conversation_memory_state_attaches_long_term_preview(
        self,
    ):
        from app.services.ai.conversation_service import ConversationService

        conversation = _make_conversation(id=10, agent_id=15, user_id=1)
        service = ConversationService.__new__(ConversationService)
        service.db = MagicMock(spec=AsyncSession)
        service.tenant_id = 1
        service.repo = AsyncMock()
        service.get_accessible_conversation = AsyncMock(return_value=conversation)

        memory_svc = MagicMock()
        memory_svc.get_state = AsyncMock(
            return_value={
                "constraints": [],
                "preferences": [],
                "task_states": [],
                "updated_at": 0,
                "verified_facts": [],
                "version": 0,
            }
        )
        service._memory_state_service = memory_svc

        with patch(
            "app.repositories.ai.memory_record_repository.MemoryRecordRepository",
        ) as repo_cls:
            repo = repo_cls.return_value
            repo.list_for_scope = AsyncMock(
                return_value=[
                    SimpleNamespace(
                        content="我的项目代号是 Phoenix",
                        summary="我的项目代号是 Phoenix",
                    )
                ]
            )
            result = await service.get_conversation_memory_state(10, user_id=1)

        assert result["long_term_memories"] == ["我的项目代号是 Phoenix"]
        assert result["long_term_memory_count"] == 1
        repo.list_for_scope.assert_awaited_once_with(
            scope_type="user_agent",
            scope_key="user:1:agent:15",
            limit=12,
        )

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
        memory_svc.clear_state = AsyncMock(return_value=2)
        service._memory_state_service = memory_svc

        result = await service.clear_conversation_memory_state(10, user_id=1)

        assert result == 2
        service.get_accessible_conversation.assert_awaited_once_with(
            10,
            user_id=1,
            owner_type=None,
        )
        memory_svc.clear_state.assert_awaited_once_with(10)

    @pytest.mark.asyncio
    async def test_clear_conversation_memory_state_removes_long_term_preview_source(
        self,
    ):
        from app.services.ai.conversation_service import ConversationService
        from app.services.ai.long_term_memory_service import LongTermMemoryService

        conversation = _make_conversation(id=10, agent_id=15, user_id=1)
        service = ConversationService.__new__(ConversationService)
        service.db = MagicMock(spec=AsyncSession)
        service.tenant_id = 1
        service.repo = AsyncMock()
        service.get_accessible_conversation = AsyncMock(return_value=conversation)

        memory_svc = MagicMock()
        memory_svc.clear_state = AsyncMock(return_value=2)
        service._memory_state_service = memory_svc

        with patch(
            "app.services.ai.long_term_memory_service.LongTermMemoryService",
        ) as long_term_service_cls:
            long_term_service_cls.build_scope_key.side_effect = (
                LongTermMemoryService.build_scope_key
            )
            long_term_service = long_term_service_cls.return_value
            long_term_service.repo.delete_for_scope = AsyncMock(return_value=3)
            long_term_service.refresh_profile_snapshot = AsyncMock(return_value=None)

            result = await service.clear_conversation_memory_state(10, user_id=1)

        assert result == 5
        long_term_service_cls.assert_called_once_with(service.db, 1)
        long_term_service.repo.delete_for_scope.assert_awaited_once_with(
            scope_type="user_agent",
            scope_key="user:1:agent:15",
        )
        long_term_service.refresh_profile_snapshot.assert_awaited_once_with(
            agent_id=15,
            user_id=1,
            scope_type="user_agent",
        )

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

        with patch(
            "app.services.ai.conversation_facade_mixins.ConversationMemoryStateService",
        ) as mock_memory_service:
            memory_svc = mock_memory_service.return_value
            memory_svc.get_state = AsyncMock(return_value={"preferences": []})
            await service.get_conversation_memory_state(10)

        mock_memory_service.assert_called_once_with(memory_tenant_id=0)
        memory_svc.get_state.assert_awaited_once_with(10)


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
        service._message_repo.search_by_content = AsyncMock(return_value=([message], 1))
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

    @pytest.mark.asyncio
    async def test_export_conversation_projects_turn_flow_and_strips_legacy_assistant_fields(
        self, mock_db
    ):
        from app.services.ai.conversation_service import ConversationService

        conversation = _make_conversation(created_at=None)
        message = _make_message(
            role="assistant",
            content="最终答复",
            token_count=12,
            tool_calls=[
                {
                    "id": "tc_export_1",
                    "display_name": "数据查询",
                    "summary": "按今天范围统计调用",
                    "result_link": "/admin/ai/chat",
                }
            ],
            tool_call_id=None,
            created_at=None,
            agent_id=42,
        )
        message.agent = make_mock_model(name="Router Agent", avatar="/router.png")
        message.metadata_ = {
            "thinking_content": "先分析上下文。",
            "rag_sources": [
                {
                    "source": "KB",
                    "chunk_id": 1,
                    "title": "知识库证据",
                    "snippet": "命中了相关文档",
                }
            ],
        }

        service = ConversationService.__new__(ConversationService)
        service.db = mock_db
        service.tenant_id = 1
        service.repo = AsyncMock()
        service.repo.get_by_id = AsyncMock(return_value=conversation)
        service._message_repo = MagicMock()
        service._message_repo.get_by_conversation = AsyncMock(return_value=[message])
        service._message_repo.count_by_conversation = AsyncMock(return_value=1)
        mock_db.execute = AsyncMock(return_value=SimpleNamespace(scalars=lambda: []))

        result = await service.export_conversation(1, export_format="json")
        payload = json.loads(result["content"])
        assistant_payload = payload["messages"][0]

        assert "tool_calls" not in assistant_payload
        assert "thinking_content" not in assistant_payload["metadata"]
        assert "rag_sources" not in assistant_payload["metadata"]
        assert "turn_flow" not in assistant_payload
        assert assistant_payload["metadata"]["turn_flow"]["answer_card"]["summary"] == (
            "最终答复"
        )
        assert any(
            stage["type"] == "thinking"
            for stage in assistant_payload["metadata"]["turn_flow"]["timeline"]
        )
        assert any(
            item["tool_call_id"] == "tc_export_1"
            for item in assistant_payload["metadata"]["turn_flow"]["evidence"]
        )

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
        assert (
            payload["messages"][0]["metadata"]["attachments"][0]["attachment_id"] == 7
        )
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
            "app.services.ai.conversation_facade_mixins.parse_output",
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

    @pytest.mark.asyncio
    async def test_uses_output_schema_snapshot_without_lazy_loading_current_agent(
        self,
        mock_db,
    ):
        from app.services.ai.conversation_service import ConversationService

        class _ExpiredAgent:
            @property
            def output_schema(self):
                raise RuntimeError("expired ORM agent should not lazy-load")

        conversation = _make_conversation(token_count=10, total_tokens=20)
        conversation.metadata_ = {}
        conversation.agent = None
        result = make_mock_model(total_tokens=5, output='{"value": 1}')
        output_schema = {"schema": "snapshot"}

        service = ConversationService.__new__(ConversationService)
        service.db = mock_db
        service.tenant_id = 1
        service.repo = AsyncMock()

        with patch(
            "app.services.ai.conversation_facade_mixins.parse_output",
            return_value={"value": 1},
        ) as mock_parse:
            await service.update_stats(
                conversation,
                result,
                current_agent=_ExpiredAgent(),
                output_schema=output_schema,
            )

        mock_parse.assert_called_once_with(result.output, output_schema)
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
        memory_svc.clear_state = AsyncMock(return_value=2)
        service._memory_state_service = memory_svc

        await service._after_delete(123)

        memory_svc.clear_state.assert_awaited_once_with(123)

    @pytest.mark.asyncio
    async def test_after_delete_memory_cleanup_failure_not_raise(self, mock_db):
        from app.services.ai.conversation_service import ConversationService

        service = ConversationService.__new__(ConversationService)
        service.db = mock_db
        service.tenant_id = 1
        service.repo = AsyncMock()

        memory_svc = MagicMock()
        memory_svc.clear_state = AsyncMock(side_effect=RuntimeError("redis down"))
        service._memory_state_service = memory_svc

        await service._after_delete(456)

        memory_svc.clear_state.assert_awaited_once_with(456)


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
        assert assistant_payload["tool_calls"] == result.messages[1]["tool_calls"]
        assert "thinking_content" not in assistant_payload["metadata_"]
        thinking_stage = next(
            stage
            for stage in assistant_payload["metadata_"]["turn_flow"]["timeline"]
            if stage["type"] == "thinking"
        )
        assert thinking_stage["summary"] == "已完成思考与规划"
        assert (
            assistant_payload["metadata_"]["turn_flow"]["answer_card"]["summary"]
            == "最终答复"
        )

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
                                "name": "query_records",
                                "arguments": '{"question":"统计今天调用情况"}',
                            },
                            "pending_consent": {
                                "arguments": {"question": "统计今天调用情况"},
                                "tool_name": "query_records",
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
                    name="query_records",
                    success=True,
                    duration_ms=123,
                    display_name="数据查询",
                    summary="按今天范围统计调用",
                    result_link="/admin/ai/chat",
                    summary_payload={
                        "filters": ["today"],
                        "tables": ["ai_call_logs"],
                        "tool_kind": "query_records",
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

        assert assistant_payload["tool_calls"] is not None
        persisted_tool_call = assistant_payload["tool_calls"][0]
        assert persisted_tool_call["id"] == "tc_data_1"
        assert persisted_tool_call["function"]["name"] == "query_records"
        assert persisted_tool_call["pending_consent"] == {
            "arguments": {"question": "统计今天调用情况"},
            "tool_name": "query_records",
        }
        assert persisted_tool_call["summary_payload"] == {
            "filters": ["today"],
            "tables": ["ai_call_logs"],
            "tool_kind": "query_records",
        }
        assert assistant_payload["metadata_"]["pending_confirmation"] == {
            "action": "query",
            "preview": {"sql": "SELECT 1"},
            "table": "ai_call_logs",
        }
        assert not any(
            stage["type"] == "tool_execution"
            for stage in assistant_payload["metadata_"]["turn_flow"]["timeline"]
        )
        tool_evidence = next(
            item
            for item in assistant_payload["metadata_"]["turn_flow"]["evidence"]
            if item["tool_call_id"] == "tc_data_1"
        )
        assert tool_evidence["title"] == "数据查询"
        assert tool_evidence["snippet"] == "按今天范围统计调用"
        assert tool_evidence["url"] == "/admin/ai/chat"
        assert tool_payload["metadata_"]["tool_summary"] == "按今天范围统计调用"
        assert tool_payload["metadata_"]["tool_summary_payload"] == {
            "filters": ["today"],
            "tables": ["ai_call_logs"],
            "tool_kind": "query_records",
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
            prune_stats={
                "mode": "transient_tool_result_pruning",
                "pruned_message_count": 1,
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
        assert (
            assistant_payload["metadata_"]["turn_flow"]["timeline"][-1]["type"]
            == "completed"
        )
        assert (
            assistant_payload["metadata_"]["turn_flow"]["answer_card"]["summary"]
            == "最终答复"
        )

    @pytest.mark.asyncio
    async def test_persist_chat_messages_normalizes_nested_runtime_metadata_to_json_safe(
        self, mock_db
    ):
        from app.services.ai.conversation_service import ConversationService

        timestamp = datetime(2026, 4, 7, 8, 0, tzinfo=timezone.utc)
        naive_timestamp = datetime(2026, 4, 7, 8, 30)
        conversation = _make_conversation(id=906, message_count=0)
        result = SimpleNamespace(
            messages=[
                {"role": "user", "content": "请保存这个结果"},
                {
                    "role": "assistant",
                    "content": "已完成处理",
                    "tool_calls": None,
                    "tool_call_id": None,
                    "attachments": None,
                    "reasoning_content": None,
                    "metadata": {
                        "tool_summary_payload": {
                            "amount": Decimal("12.50"),
                            "scheduled_at": timestamp,
                            "naive_started_at": naive_timestamp,
                            "status": _MetadataEnum.READY,
                            "dataclass_payload": _MetadataDataclassPayload(
                                amount=Decimal("7"),
                                scheduled_for=date(2026, 4, 9),
                            ),
                            "pydantic_payload": _PydanticLikePayload(),
                            "dict_payload": _DictLikePayload(),
                        },
                        "action_buttons": [
                            {
                                "label": "提交",
                                "value": "submit",
                                "weight": Decimal("1"),
                            }
                        ],
                        "record_action_payload": {
                            "resource_key": "admin.runtime.records",
                            "limit": Decimal("10"),
                        },
                    },
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
            context_diagnostics={
                "latency_ms": Decimal("1.2"),
                "captured_at": timestamp,
            },
            last_run_summary={
                "status": _MetadataEnum.READY,
                "captured_at": naive_timestamp,
            },
        )

        assistant_payload = service._message_repo.create.await_args_list[1].args[0]
        metadata = assistant_payload["metadata_"]
        tool_summary_payload = metadata["tool_summary_payload"]

        assert tool_summary_payload["amount"] == 12.5
        assert tool_summary_payload["scheduled_at"] == "2026-04-07T08:00:00+00:00"
        assert tool_summary_payload["naive_started_at"] == "2026-04-07T08:30:00+00:00"
        assert tool_summary_payload["status"] == "ready"
        assert tool_summary_payload["dataclass_payload"]["amount"] == 7
        assert (
            tool_summary_payload["dataclass_payload"]["scheduled_for"] == "2026-04-09"
        )
        assert tool_summary_payload["pydantic_payload"]["score"] == 9.5
        assert tool_summary_payload["dict_payload"]["attempts"] == 2
        assert metadata["action_buttons"][0]["weight"] == 1
        assert metadata["context_diagnostics"]["latency_ms"] == 1.2
        assert metadata["last_run_summary"]["status"] == "ready"

    @pytest.mark.asyncio
    async def test_persist_chat_messages_normalizes_json_unsafe_metadata(self, mock_db):
        from app.services.ai.conversation_service import ConversationService

        conversation = _make_conversation(id=9001, message_count=0)
        result = SimpleNamespace(
            messages=[
                {"role": "user", "content": "hello"},
                {
                    "role": "assistant",
                    "content": "world",
                    "tool_calls": None,
                    "tool_call_id": None,
                    "attachments": None,
                    "reasoning_content": None,
                    "metadata": {
                        "enum_value": _TestStatus.OK,
                    },
                },
            ],
            tool_results=[],
            partial=False,
            interrupted=False,
            completion_reason="completed",
            runtime_model_id=None,
            runtime_model_name=None,
            runtime_provider_id=None,
            runtime_provider_name=None,
            turn_record={
                "cost": Decimal("12.34"),
                "status": _TestStatus.OK,
                "finished_at": datetime(2026, 4, 7, 12, 0, 0),
            },
        )

        context_diag = {
            "cost": Decimal("1.25"),
            "status": _TestStatus.OK,
            "finished_at": datetime(2026, 4, 7, 12, 30, 0),
        }
        last_summary = {
            "amount": Decimal("5.50"),
            "finished_at": datetime(2026, 4, 7, 13, 0, 0),
        }

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
        metadata = assistant_payload["metadata_"]
        assert metadata["context_diagnostics"]["cost"] == 1.25
        assert metadata["context_diagnostics"]["status"] == "ok"
        assert metadata["last_run_summary"]["amount"] == 5.5
        assert metadata["turn_record"]["cost"] == 12.34
        assert metadata["turn_record"]["status"] == "ok"
        assert metadata["turn_record"]["finished_at"].startswith("2026-04-07T12:00:00")

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
                                "name": "query_records",
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

    def test_extract_turn_diagnostics_prefers_partial_metadata_over_success_turn_record(
        self,
    ):
        from app.services.ai.conversation_service import ConversationService

        payload = ConversationService._extract_turn_diagnostics_from_metadata(
            {
                "turn_record": {
                    "turn_outcome": "success",
                    "termination_reason": "completed",
                    "protocol_path": "responses",
                },
                "partial": True,
                "completion_reason": "error",
            }
        )

        assert payload["turn_outcome"] == "partial"
        assert payload["termination_reason"] == "error"

    @pytest.mark.asyncio
    async def test_persist_chat_messages_marks_partial_error_on_tool_round_without_final_plain_assistant(
        self, mock_db
    ):
        from app.services.ai.conversation_service import ConversationService

        conversation = _make_conversation(id=906, message_count=0)
        result = SimpleNamespace(
            success=False,
            messages=[
                {"role": "user", "content": "现在几点了"},
                {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {
                            "id": "tc_time_1",
                            "function": {
                                "name": "get_current_time",
                                "arguments": '{"timezone_name":"Asia/Shanghai"}',
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
                    "content": "2026-04-09 18:45:59",
                    "tool_calls": None,
                    "tool_call_id": "tc_time_1",
                    "attachments": None,
                    "reasoning_content": None,
                },
            ],
            tool_results=[],
            partial=True,
            interrupted=False,
            completion_reason="error",
            runtime_model_id=None,
            runtime_model_name=None,
            runtime_provider_id=None,
            runtime_provider_name=None,
            turn_record={
                "turn_outcome": "success",
                "termination_reason": "completed",
                "protocol_path": "responses",
                "selected_tool_names": ["get_current_time"],
            },
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
        assert metadata["completion_reason"] == "error"
        assert metadata["turn_outcome"] == "partial"
        assert metadata["termination_reason"] == "error"
        assert metadata["context_diagnostics"]["turn_outcome"] == "partial"
        assert metadata["context_diagnostics"]["termination_reason"] == "error"
        assert metadata["last_run_summary"]["turn_outcome"] == "partial"
        assert metadata["last_run_summary"]["termination_reason"] == "error"

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
    async def test_persist_chat_messages_aligns_history_without_double_counting_leading_system_messages(
        self,
        mock_db,
    ):
        from app.services.ai.conversation_service import ConversationService

        conversation = _make_conversation(id=91, message_count=2)
        result = SimpleNamespace(
            messages=[
                {"role": "system", "content": "runtime system"},
                {"role": "system", "content": "persisted system"},
                {"role": "user", "content": "old question"},
                {"role": "user", "content": "new question"},
                {"role": "assistant", "content": "new answer"},
            ],
            tool_results=[],
            partial=False,
            interrupted=False,
            completion_reason="completed",
            runtime_model_id=None,
            runtime_model_name=None,
            runtime_provider_id=None,
            runtime_provider_name=None,
        )
        history_messages = [
            ChatMessage(role="system", content="persisted system"),
            ChatMessage(role="user", content="old question"),
        ]

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
            history_count=2,
            history_messages=history_messages,
            agent_id=7,
        )

        create_calls = service._message_repo.create.await_args_list
        assert [call.args[0]["role"] for call in create_calls] == ["user", "assistant"]
        assert create_calls[0].args[0]["content"] == "new question"

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
                    "function": {"name": "query_records", "arguments": "{}"},
                    "pending_consent": {"tool_name": "query_records"},
                }
            ],
        )
        assistant.metadata_ = {
            "action_buttons": [{"label": "查看明细", "value": "查看明细"}],
            "pending_confirmation": {"action": "query", "table": "ai_call_logs"},
            "pending_consent": {"tool_name": "query_records"},
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
                    "tool_name": "query_records",
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
    async def test_update_last_assistant_interaction_state_matches_pending_confirmation_by_tool_name(
        self, mock_db
    ):
        from app.services.ai.conversation_service import ConversationService

        assistant = _make_message(
            id=303,
            role="assistant",
            content="需要确认",
            tool_calls=[
                {
                    "id": "tc_confirm_3",
                    "function": {"name": "crm_open_record", "arguments": "{}"},
                    "pending_confirmation": {
                        "preview": {"target": "create-agent"},
                        "tool_name": "crm_open_record",
                    },
                }
            ],
        )
        assistant.metadata_ = {
            "pending_confirmation": {
                "preview": {"target": "create-agent"},
                "tool_name": "crm_open_record",
            }
        }

        service = ConversationService.__new__(ConversationService)
        service.db = mock_db
        service.tenant_id = 1
        service.repo = AsyncMock()
        service.repo.get_by_id = AsyncMock(return_value=_make_conversation(id=188))
        service._message_repo = MagicMock()
        service._message_repo.get_last_n_messages = AsyncMock(return_value=[assistant])
        service._message_repo.update = AsyncMock()

        updated = await service.update_last_assistant_interaction_state(
            conversation_id=188,
            updates=[
                {
                    "kind": "pending_confirmation",
                    "rejected": False,
                    "tool_name": "crm_open_record",
                }
            ],
        )

        assert updated == 1
        final_update = service._message_repo.update.await_args_list[-1].args[1]
        assert final_update["metadata_"]["pending_confirmation"]["resolved"] is True
        assert final_update["tool_calls"][0]["pending_confirmation"]["resolved"] is True


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


@pytest.mark.asyncio
async def test_conversation_memory_state_merges_persisted_metadata_when_session_store_empty(
    mock_db,
) -> None:
    """Test type: behavioral
    Verifies the memory panel read model includes the conversation metadata
    mirror when Redis-backed session memory has no rows.
    """
    from app.services.ai.conversation_memory_state_service import (
        CONVERSATION_MEMORY_STATE_METADATA_KEY,
    )
    from app.services.ai.conversation_service import ConversationService

    conversation = _make_conversation(id=42, user_id=9)
    conversation.metadata_ = {
        CONVERSATION_MEMORY_STATE_METADATA_KEY: {
            "preferences": [],
            "constraints": [],
            "task_states": [],
            "verified_facts": ["用户名字是ix long"],
            "version": 1,
            "updated_at": 123,
        }
    }

    service = ConversationService.__new__(ConversationService)
    service.db = mock_db
    service.tenant_id = 1
    service.repo = AsyncMock()
    service.get_accessible_conversation = AsyncMock(return_value=conversation)
    service._memory_state_service = SimpleNamespace(
        get_state=AsyncMock(
            return_value={
                "preferences": [],
                "constraints": [],
                "task_states": [],
                "verified_facts": [],
                "version": 0,
                "updated_at": 0,
            }
        )
    )

    state = await service.get_conversation_memory_state(
        42,
        user_id=9,
        owner_type="tenant_admin",
    )

    assert state["verified_facts"] == ["用户名字是ix long"]
    assert state["version"] == 1
    assert state["updated_at"] == 123


@pytest.mark.asyncio
async def test_clear_conversation_memory_state_removes_metadata_when_redis_down(
    mock_db,
) -> None:
    """Test type: behavioral
    Verifies clearing conversation memory removes the durable panel read-model
    mirror even when Redis cleanup is degraded.
    """
    from app.services.ai.conversation_memory_state_service import (
        CONVERSATION_MEMORY_STATE_METADATA_KEY,
    )
    from app.services.ai.conversation_service import ConversationService

    conversation = _make_conversation(id=43, user_id=9)
    conversation.metadata_ = {
        "thread_memory_state": {"session_memory_runtime_enabled": True},
        CONVERSATION_MEMORY_STATE_METADATA_KEY: {
            "verified_facts": ["用户名字是ix long"],
            "version": 1,
            "updated_at": 123,
        },
    }

    async def _update_conversation(conversation_id: int, payload: dict):
        assert conversation_id == 43
        conversation.metadata_ = payload["metadata_"]
        return conversation

    service = ConversationService.__new__(ConversationService)
    service.db = mock_db
    service.tenant_id = 1
    service.repo = AsyncMock()
    service.repo.update = AsyncMock(side_effect=_update_conversation)
    service.get_accessible_conversation = AsyncMock(return_value=conversation)
    service._memory_state_service = SimpleNamespace(
        clear_state=AsyncMock(side_effect=RuntimeError("redis down"))
    )
    service._clear_long_term_memory_scope = AsyncMock(return_value=0)

    deleted_count = await service.clear_conversation_memory_state(
        43,
        user_id=9,
        owner_type="tenant_admin",
    )

    assert deleted_count == 1
    assert CONVERSATION_MEMORY_STATE_METADATA_KEY not in conversation.metadata_
    assert conversation.metadata_["thread_memory_state"] == {
        "session_memory_runtime_enabled": True
    }
    service.repo.update.assert_awaited_once()
