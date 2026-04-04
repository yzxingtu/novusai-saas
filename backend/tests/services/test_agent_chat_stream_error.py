"""AgentChatService stream error persistence tests / 流式异常持久化测试。"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.ai.engine.types import ExecutionResult
from app.enums.common import UserRoleEnum


class _SessionManager:
    def __init__(self, db):
        self.db = db

    async def __aenter__(self):
        return self.db

    async def __aexit__(self, exc_type, exc, tb):
        return False


def _build_agent():
    return SimpleNamespace(
        id=1,
        status="published",
        quota_config={},
        context_config={},
        model=None,
    )


def _build_conversation():
    return SimpleNamespace(
        id=100,
        agent_id=1,
        user_id=10,
        owner_type="tenant_admin",
        metadata_={},
    )


def _build_failed_result(
    *, output: str = "", error: str = "Upstream API failed: 502 Bad Gateway"
):
    return ExecutionResult(
        success=False,
        output=output,
        messages=[],
        tool_results=[],
        total_tokens=150 if output else 0,
        duration_ms=1000,
        conversation_id=100,
        error=error,
        partial=bool(output),
        interrupted=False,
        completion_reason="error",
        rag_sources=None,
        rag_source_kinds=[],
        context_compacted=False,
        memory_flush_triggered=False,
        memory_recalled=False,
        prune_stats=None,
        tool_planner=None,
    )


async def _build_stream_service(mock_db):
    from app.services.ai.agent_chat_service import AgentChatService

    service = AgentChatService(mock_db, tenant_id=1)
    service._validate_agent = AsyncMock(return_value=_build_agent())
    service._resolve_effective_memory_enabled = AsyncMock(return_value=False)
    service._load_session_memory_context = AsyncMock(return_value="")
    service._build_billing_context = AsyncMock(return_value={})
    service._resolve_runtime_trust_policy_ref = AsyncMock(return_value=None)
    service.conversation_svc.get_or_create_for_chat = AsyncMock(
        return_value=_build_conversation(),
    )
    service.conversation_svc.load_chat_history = AsyncMock(return_value=[])
    service.conversation_svc.update_last_assistant_interaction_state = AsyncMock(
        return_value=None,
    )
    service._persist_session_memory = AsyncMock(return_value=None)
    return service


async def _capture_on_complete(service, mock_db):
    engine = AsyncMock()
    engine.stream_execute = AsyncMock(return_value=MagicMock())
    hook_registry = SimpleNamespace(
        has_hooks=MagicMock(return_value=False),
        trigger=AsyncMock(return_value={}),
    )

    with (
        patch(
            "app.services.ai.agent_chat_service.ConversationEngine",
            return_value=engine,
        ),
        patch(
            "app.ai.skills.resolver.resolve_for_agent",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "app.services.ai.agent_chat_service.AgentQuotaManager.check_quota",
            new=AsyncMock(),
        ),
        patch(
            "app.services.ai.agent_chat_service.AgentQuotaManager.check_user_quota",
            new=AsyncMock(),
        ),
        patch(
            "app.services.ai.agent_chat_service.AgentQuotaManager.record_conversation",
            new=AsyncMock(),
        ),
        patch(
            "app.services.ai.agent_chat_service.AgentConcurrencyLimiter.acquire",
            new=AsyncMock(return_value=""),
        ),
        patch(
            "app.services.ai.agent_chat_service.BaseEngine._publish_execution_started",
            new=AsyncMock(),
        ),
        patch(
            "app.services.ai.agent_chat_service.get_hook_registry",
            return_value=hook_registry,
        ),
        patch(
            "app.services.tenant.quota_service.QuotaService.check_api_quota_for_tenant_id",
            new=AsyncMock(return_value=SimpleNamespace(allowed=True, message=None)),
        ),
        patch(
            "app.configs.service.ConfigService.get_platform_config",
            new=AsyncMock(side_effect=["normal", 256]),
        ),
    ):
        await service.stream_chat(
            agent_id=1,
            message="通过页面感知能力添加一个测试的智能体",
            user_id=10,
            user_role=UserRoleEnum.TENANT_ADMIN.value,
        )

    return engine.stream_execute.await_args.kwargs["on_complete"], hook_registry


@pytest.mark.asyncio
async def test_stream_chat_defers_new_conversation_commit_until_api_quota_passes(
    mock_db,
):
    from app.exceptions import BusinessException

    service = await _build_stream_service(mock_db)
    engine = AsyncMock()
    engine.stream_execute = AsyncMock(return_value=MagicMock())
    record_conversation = AsyncMock()
    hook_registry = SimpleNamespace(
        has_hooks=MagicMock(return_value=False),
        trigger=AsyncMock(return_value={}),
    )

    with (
        patch(
            "app.services.ai.agent_chat_service.ConversationEngine",
            return_value=engine,
        ),
        patch(
            "app.ai.skills.resolver.resolve_for_agent",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "app.services.ai.agent_chat_service.AgentQuotaManager.check_quota",
            new=AsyncMock(),
        ),
        patch(
            "app.services.ai.agent_chat_service.AgentQuotaManager.check_user_quota",
            new=AsyncMock(),
        ),
        patch(
            "app.services.ai.agent_chat_service.AgentQuotaManager.record_conversation",
            new=record_conversation,
        ),
        patch(
            "app.services.ai.agent_chat_service.AgentConcurrencyLimiter.acquire",
            new=AsyncMock(return_value=""),
        ),
        patch(
            "app.services.ai.agent_chat_service.BaseEngine._publish_execution_started",
            new=AsyncMock(),
        ),
        patch(
            "app.services.ai.agent_chat_service.get_hook_registry",
            return_value=hook_registry,
        ),
        patch(
            "app.services.tenant.quota_service.QuotaService.check_api_quota_for_tenant_id",
            new=AsyncMock(
                return_value=SimpleNamespace(allowed=False, message="monthly quota hit")
            ),
        ),
        patch(
            "app.configs.service.ConfigService.get_platform_config",
            new=AsyncMock(side_effect=["normal", 256]),
        ),
        pytest.raises(BusinessException, match="monthly quota hit"),
    ):
        await service.stream_chat(
            agent_id=1,
            message="blocked before stream starts",
            conversation_id=None,
            user_id=10,
            user_role=UserRoleEnum.TENANT_ADMIN.value,
        )

    record_conversation.assert_not_awaited()
    mock_db.commit.assert_not_awaited()
    engine.stream_execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_stream_on_complete_persists_error_message_when_failed_without_new_messages(
    mock_db,
):
    from app.core.i18n import _

    service = await _build_stream_service(mock_db)
    on_complete, _hook_registry = await _capture_on_complete(service, mock_db)

    cb_db = AsyncMock()
    cb_db.commit = AsyncMock()
    cb_db.rollback = AsyncMock()
    conversation = _build_conversation()
    cb_conv_svc = MagicMock()
    cb_conv_svc.repo.get_by_id = AsyncMock(return_value=conversation)
    cb_conv_svc.message_repo.get_next_sequence = AsyncMock(return_value=2)
    cb_conv_svc.message_repo.create = AsyncMock()

    with (
        patch(
            "app.services.ai.agent_chat_service.async_session_factory",
            return_value=_SessionManager(cb_db),
        ),
        patch(
            "app.services.ai.agent_chat_service.ConversationService",
            return_value=cb_conv_svc,
        ),
        patch(
            "app.services.ai.agent_chat_service.AgentQuotaManager.adjust_usage",
            new=AsyncMock(),
        ),
        patch(
            "app.services.ai.agent_chat_service.AgentQuotaManager.record_user_usage",
            new=AsyncMock(),
        ),
        patch(
            "app.services.ai.agent_chat_service.AgentStatsManager.record_chat",
            new=AsyncMock(),
        ),
        patch(
            "app.services.ai.agent_chat_service.BaseEngine._publish_execution_failed",
            new=AsyncMock(),
        ),
        patch(
            "app.services.ai.agent_chat_service.BaseEngine._publish_execution_completed",
            new=AsyncMock(),
        ),
    ):
        await on_complete(_build_failed_result())

    cb_conv_svc.message_repo.create.assert_awaited_once()
    payload = cb_conv_svc.message_repo.create.await_args.args[0]
    assert payload["role"] == "assistant"
    assert payload["content"] == _("ai.stream.error.service_unavailable")
    assert payload["metadata_"]["error"] is True
    assert payload["metadata_"]["error_type"] == "stream_execution_error"
    assert cb_db.commit.await_count == 1


@pytest.mark.asyncio
async def test_stream_on_complete_updates_conversation_last_error_metadata(mock_db):
    service = await _build_stream_service(mock_db)
    on_complete, _hook_registry = await _capture_on_complete(service, mock_db)

    cb_db = AsyncMock()
    cb_db.commit = AsyncMock()
    cb_db.rollback = AsyncMock()
    conversation = _build_conversation()
    cb_conv_svc = MagicMock()
    cb_conv_svc.repo.get_by_id = AsyncMock(return_value=conversation)
    cb_conv_svc.message_repo.get_next_sequence = AsyncMock(return_value=2)
    cb_conv_svc.message_repo.create = AsyncMock()

    with (
        patch(
            "app.services.ai.agent_chat_service.async_session_factory",
            return_value=_SessionManager(cb_db),
        ),
        patch(
            "app.services.ai.agent_chat_service.ConversationService",
            return_value=cb_conv_svc,
        ),
        patch(
            "app.services.ai.agent_chat_service.AgentQuotaManager.adjust_usage",
            new=AsyncMock(),
        ),
        patch(
            "app.services.ai.agent_chat_service.AgentQuotaManager.record_user_usage",
            new=AsyncMock(),
        ),
        patch(
            "app.services.ai.agent_chat_service.AgentStatsManager.record_chat",
            new=AsyncMock(),
        ),
        patch(
            "app.services.ai.agent_chat_service.BaseEngine._publish_execution_failed",
            new=AsyncMock(),
        ),
        patch(
            "app.services.ai.agent_chat_service.BaseEngine._publish_execution_completed",
            new=AsyncMock(),
        ),
    ):
        await on_complete(_build_failed_result(error="Fallback crashed hard"))

    assert "last_error" in conversation.metadata_
    assert (
        conversation.metadata_["last_error"]["error_type"] == "stream_execution_error"
    )
    assert "friendly_message" in conversation.metadata_["last_error"]


@pytest.mark.asyncio
async def test_stream_on_complete_preserves_partial_output_in_error_metadata(mock_db):
    service = await _build_stream_service(mock_db)
    on_complete, _hook_registry = await _capture_on_complete(service, mock_db)

    cb_db = AsyncMock()
    cb_db.commit = AsyncMock()
    cb_db.rollback = AsyncMock()
    conversation = _build_conversation()
    cb_conv_svc = MagicMock()
    cb_conv_svc.repo.get_by_id = AsyncMock(return_value=conversation)
    cb_conv_svc.message_repo.get_next_sequence = AsyncMock(return_value=2)
    cb_conv_svc.message_repo.create = AsyncMock()

    with (
        patch(
            "app.services.ai.agent_chat_service.async_session_factory",
            return_value=_SessionManager(cb_db),
        ),
        patch(
            "app.services.ai.agent_chat_service.ConversationService",
            return_value=cb_conv_svc,
        ),
        patch(
            "app.services.ai.agent_chat_service.AgentQuotaManager.adjust_usage",
            new=AsyncMock(),
        ),
        patch(
            "app.services.ai.agent_chat_service.AgentQuotaManager.record_user_usage",
            new=AsyncMock(),
        ),
        patch(
            "app.services.ai.agent_chat_service.AgentStatsManager.record_chat",
            new=AsyncMock(),
        ),
        patch(
            "app.services.ai.agent_chat_service.BaseEngine._publish_execution_failed",
            new=AsyncMock(),
        ),
        patch(
            "app.services.ai.agent_chat_service.BaseEngine._publish_execution_completed",
            new=AsyncMock(),
        ),
    ):
        await on_complete(_build_failed_result(output="这是部分输出"))

    payload = cb_conv_svc.message_repo.create.await_args.args[0]
    assert payload["metadata_"]["partial_output"] == "这是部分输出"
    assert payload["metadata_"]["total_tokens"] == 150


@pytest.mark.asyncio
async def test_stream_on_complete_skips_extra_error_message_when_partial_assistant_already_exists(
    mock_db,
):
    service = await _build_stream_service(mock_db)
    on_complete, _hook_registry = await _capture_on_complete(service, mock_db)

    cb_db = AsyncMock()
    cb_db.commit = AsyncMock()
    cb_db.rollback = AsyncMock()
    conversation = _build_conversation()
    cb_conv_svc = MagicMock()
    cb_conv_svc.repo.get_by_id = AsyncMock(return_value=conversation)
    cb_conv_svc.persist_chat_messages = AsyncMock(return_value=([], 1))
    cb_conv_svc.update_stats = AsyncMock()
    cb_conv_svc.message_repo.get_next_sequence = AsyncMock(return_value=2)
    cb_conv_svc.message_repo.create = AsyncMock()

    partial_result = _build_failed_result(output="partial text")
    partial_result.messages = [
        {"role": "system", "content": "sys"},
        {"role": "assistant", "content": "partial text"},
    ]

    with (
        patch(
            "app.services.ai.agent_chat_service.async_session_factory",
            return_value=_SessionManager(cb_db),
        ),
        patch(
            "app.services.ai.agent_chat_service.ConversationService",
            return_value=cb_conv_svc,
        ),
        patch(
            "app.services.ai.agent_chat_service.AgentQuotaManager.adjust_usage",
            new=AsyncMock(),
        ),
        patch(
            "app.services.ai.agent_chat_service.AgentQuotaManager.record_user_usage",
            new=AsyncMock(),
        ),
        patch(
            "app.services.ai.agent_chat_service.AgentStatsManager.record_chat",
            new=AsyncMock(),
        ),
        patch(
            "app.services.ai.agent_chat_service.BaseEngine._publish_execution_failed",
            new=AsyncMock(),
        ),
        patch(
            "app.services.ai.agent_chat_service.BaseEngine._publish_execution_completed",
            new=AsyncMock(),
        ),
    ):
        await on_complete(partial_result)

    cb_conv_svc.persist_chat_messages.assert_awaited_once()
    cb_conv_svc.message_repo.create.assert_not_awaited()


@pytest.mark.asyncio
async def test_stream_on_complete_persists_error_message_when_sanitized_messages_are_empty(
    mock_db,
):
    from app.core.i18n import _

    service = await _build_stream_service(mock_db)
    on_complete, _hook_registry = await _capture_on_complete(service, mock_db)

    cb_db = AsyncMock()
    cb_db.commit = AsyncMock()
    cb_db.rollback = AsyncMock()
    conversation = _build_conversation()
    cb_conv_svc = MagicMock()
    cb_conv_svc.repo.get_by_id = AsyncMock(return_value=conversation)
    cb_conv_svc.persist_chat_messages = AsyncMock(return_value=([], 0))
    cb_conv_svc.update_stats = AsyncMock()
    cb_conv_svc.message_repo.get_next_sequence = AsyncMock(return_value=2)
    cb_conv_svc.message_repo.create = AsyncMock()

    partial_result = _build_failed_result(output="partial text")
    partial_result.messages = [
        {"role": "system", "content": "sys"},
        {"role": "assistant", "content": "", "tool_calls": [{"id": "call_1"}]},
    ]

    with (
        patch(
            "app.services.ai.agent_chat_service.async_session_factory",
            return_value=_SessionManager(cb_db),
        ),
        patch(
            "app.services.ai.agent_chat_service.ConversationService",
            return_value=cb_conv_svc,
        ),
        patch(
            "app.services.ai.agent_chat_service.AgentQuotaManager.adjust_usage",
            new=AsyncMock(),
        ),
        patch(
            "app.services.ai.agent_chat_service.AgentQuotaManager.record_user_usage",
            new=AsyncMock(),
        ),
        patch(
            "app.services.ai.agent_chat_service.AgentStatsManager.record_chat",
            new=AsyncMock(),
        ),
        patch(
            "app.services.ai.agent_chat_service.BaseEngine._publish_execution_failed",
            new=AsyncMock(),
        ),
        patch(
            "app.services.ai.agent_chat_service.BaseEngine._publish_execution_completed",
            new=AsyncMock(),
        ),
    ):
        await on_complete(partial_result)

    cb_conv_svc.persist_chat_messages.assert_awaited_once()
    cb_conv_svc.message_repo.create.assert_awaited_once()
    payload = cb_conv_svc.message_repo.create.await_args.args[0]
    assert payload["content"] == _("ai.stream.error.service_unavailable")
