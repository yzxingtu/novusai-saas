"""
Test type: behavioral
Scope: AgentChatService stream error persistence and terminal failure handling.
Mock strategy: transport/session seams are mocked, while conversation-side
stream persistence logic runs through the real persistence service.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.ai.engine.types import ExecutionResult
from app.core.i18n import _
from app.enums.common import UserRoleEnum
from app.middleware.trace import trace_id_var


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
        message_count=0,
    )


def _attach_stream_persistence_contract(conv_svc, db, *, tenant_id: int = 1) -> None:
    from app.services.ai.conversation_stream_persistence_service import (
        ConversationStreamPersistenceService,
    )

    conv_svc.db = db
    conv_svc.tenant_id = tenant_id
    stream_service = ConversationStreamPersistenceService(conv_svc)

    async def _save_stream_error_message(**kwargs):
        return await stream_service.save_stream_error_message(
            tenant_id=tenant_id,
            **kwargs,
        )

    conv_svc.persist_stream_completion = AsyncMock(
        side_effect=stream_service.persist_stream_completion
    )
    conv_svc.persist_stream_last_error_marker = AsyncMock(
        side_effect=stream_service.persist_stream_last_error_marker
    )
    conv_svc.save_stream_error_message = AsyncMock(
        side_effect=_save_stream_error_message
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


def _build_provider_timeout_result() -> ExecutionResult:
    result = _build_failed_result(
        output=_("ai.error.provider_timeout"),
        error="Request timed out.",
    )
    result.completion_reason = "provider_timeout"
    result.provider_failure_kind = "provider_timeout"
    result.diagnostics = {
        "failure_kind": "provider_timeout",
        "protocol_path": "responses",
        "final_output_source": "partial_output",
    }
    result.turn_record = {
        "turn_outcome": "failed",
        "termination_reason": "provider_timeout",
        "protocol_path": "responses",
        "failure_kind": "provider_timeout",
        "final_output_source": "partial_output",
        "metadata": {
            "stream_failure_error_type": "ProviderTimeoutError",
            "stream_failure_has_meaningful_chunk": False,
        },
    }
    result.messages = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "帮我添加一个测试智能体"},
        {"role": "assistant", "content": result.output},
    ]
    return result


def _build_success_result(
    *,
    output: str = "查到了，湖南学生暑假时间请以学校通知为准。",
):
    return ExecutionResult(
        success=True,
        output=output,
        messages=[
            {"role": "system", "content": "sys"},
            {"role": "user", "content": "帮我添加一个测试智能体"},
            {"role": "assistant", "content": output},
        ],
        tool_results=[],
        total_tokens=150,
        duration_ms=1000,
        conversation_id=100,
        runtime_model_name="gpt-5.4",
        runtime_provider_name="provider_1",
        error="",
        partial=False,
        interrupted=False,
        completion_reason="protocol_fallback",
        rag_sources=None,
        rag_source_kinds=[],
        context_compacted=False,
        memory_flush_triggered=False,
        memory_recalled=False,
        prune_stats=None,
        tool_planner=None,
        turn_record={
            "turn_outcome": "success",
            "termination_reason": "protocol_fallback",
            "protocol_path": "chat_completions",
            "selected_tool_names": ["get_current_weather"],
            "selected_skill_names": ["runtime.weather"],
            "provider_events": [
                {
                    "kind": "tool_execution_started",
                    "protocol_path": "responses",
                    "tool_family": "weather",
                }
            ],
            "fallback_history": [
                {
                    "from_protocol": "responses",
                    "to_protocol": "chat_completions",
                    "reason": "stream_exception_before_first_meaningful_chunk:RuntimeError",
                    "recovered": True,
                    "metadata": {"recovery_path": "sync_chat_completions"},
                }
            ],
            "metadata": {
                "stream_failure_reasoning_only_before_visible_output": True,
                "stream_failure_blocks_fallback": False,
            },
        },
    )


def test_friendly_stream_error_text_maps_cancelled_streams_to_interrupted_copy() -> (
    None
):
    from app.core.i18n import _
    from app.services.ai.agent_chat_service import AgentChatService

    assert AgentChatService._friendly_stream_error_text(
        "CancelledError: Cancelled via cancel scope 123"
    ) == _("ai.stream.error.interrupted")


def test_build_stream_error_display_keeps_traceable_provider_detail() -> None:
    from app.core.i18n import _
    from app.services.ai.agent_chat_service import AgentChatService

    token = trace_id_var.set("trace-provider-limit")
    try:
        display = AgentChatService._build_stream_error_display(
            "provider rate limit",
            failure_kind="provider_rate_limit",
        )
    finally:
        trace_id_var.reset(token)

    assert display["message"] == "provider rate limit"
    assert display["debug_message"] == _("ai.error.provider_rate_limit")
    assert display["trace_id"] == "trace-provider-limit"
    assert display["error_type"] == "provider_rate_limit"


def test_build_stream_error_display_suppresses_html_provider_payload() -> None:
    from app.core.i18n import _
    from app.services.ai.agent_chat_service import AgentChatService

    display = AgentChatService._build_stream_error_display(
        "<!DOCTYPE html><html><body>Bad gateway<div>Cloudflare Ray ID: 123</div></body></html>",
        failure_kind="provider_http_5xx",
    )

    assert display["message"] == _("ai.error.provider_server_error")
    assert display["debug_message"] == _("ai.error.provider_server_error")


async def _build_stream_service(mock_db):
    from app.services.ai.agent_chat_service import AgentChatService
    from app.services.ai.agent_chat_stream_runtime_dependencies import (
        AgentChatStreamPersistenceDependencies,
    )
    from app.services.ai.agent_chat_stream_support import AgentChatStreamSupport

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
    service.conversation_svc.persist_user_messages = AsyncMock(return_value=1)
    service.conversation_svc.update_last_assistant_interaction_state = AsyncMock(
        return_value=None,
    )
    service._persist_session_memory = AsyncMock(return_value=None)
    service_module = __import__(
        "app.services.ai.agent_chat_service",
        fromlist=["AgentChatService"],
    )
    service.stream_support = AgentChatStreamSupport(
        dependency_factory=lambda: AgentChatStreamPersistenceDependencies(
            session_factory=service_module.async_session_factory,
            conversation_service_cls=service_module.ConversationService,
            adjust_usage=service_module.AgentQuotaManager.adjust_usage,
            record_user_usage=service_module.AgentQuotaManager.record_user_usage,
            record_chat_stats=service_module.AgentStatsManager.record_chat,
            release_concurrency=service_module.AgentConcurrencyLimiter.release,
            publish_execution_completed=(
                service_module.BaseEngine._publish_execution_completed
            ),
            publish_execution_failed=service_module.BaseEngine._publish_execution_failed,
        )
    )
    return service


async def _capture_on_complete(
    service,
    mock_db,
    *,
    message: str = "帮我添加一个测试智能体",
):
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
            message=message,
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
    service.conversation_svc.persist_user_messages.assert_not_awaited()
    mock_db.commit.assert_not_awaited()
    engine.stream_execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_stream_chat_seeds_user_messages_before_stream_starts(mock_db):
    service = await _build_stream_service(mock_db)

    await _capture_on_complete(service, mock_db)

    service.conversation_svc.persist_user_messages.assert_awaited_once()
    seeded_messages = service.conversation_svc.persist_user_messages.await_args.kwargs[
        "messages"
    ]
    assert len(seeded_messages) == 1
    assert seeded_messages[0].role == "user"
    assert seeded_messages[0].content == "帮我添加一个测试智能体"


@pytest.mark.asyncio
async def test_stream_post_done_tail_contains_lock_release_failure(mock_db):
    from app.services.ai.agent_chat_stream_persistence_orchestrator import (
        AgentChatStreamPersistenceOrchestrator,
    )
    from app.services.ai.agent_chat_stream_runtime_dependencies import (
        AgentChatStreamPersistenceDependencies,
    )

    _ = mock_db
    hook_registry = SimpleNamespace(
        has_hooks=MagicMock(return_value=False),
        trigger=AsyncMock(return_value={}),
    )
    dependencies = AgentChatStreamPersistenceDependencies(
        session_factory=AsyncMock(),
        conversation_service_cls=MagicMock(),
        adjust_usage=AsyncMock(),
        record_user_usage=AsyncMock(),
        record_chat_stats=AsyncMock(),
        release_concurrency=AsyncMock(
            side_effect=RuntimeError("Redis not initialized")
        ),
        publish_execution_completed=AsyncMock(),
        publish_execution_failed=AsyncMock(),
    )
    orchestrator = AgentChatStreamPersistenceOrchestrator(
        tenant_id=1,
        agent_id=1,
        conversation_id=100,
        request=SimpleNamespace(tenant_id=1, skip_quota=True),
        agent=_build_agent(),
        message="帮我搜索一下2025年大模型使用token排行",
        first_message="帮我搜索一下2025年大模型使用token排行",
        history_count=0,
        history_messages=[],
        seeded_user_message_count=1,
        interaction_mode_effective="trusted_auto",
        interaction_mode_downgrade_reason=None,
        memory_event_id="memory-event-1",
        estimated_tokens=0,
        quota_config={},
        user_id=10,
        lock_token="lock-token",
        hook_registry=hook_registry,
        persist_session_memory=AsyncMock(return_value=None),
        commit_stream_memory_writes=AsyncMock(),
        rollback_stream_memory_writes=AsyncMock(),
        build_context_diagnostics=lambda _result: {},
        build_last_run_summary=lambda _result: {},
        assistant_message_has_visible_reply_payload=lambda _payload: False,
        friendly_stream_error_text=lambda _error: "stream failed",
        build_stream_error_display=lambda **_kwargs: {},
        runtime_dependencies=dependencies,
    )

    await orchestrator._run_stream_post_persist_tail(
        final_result=_build_success_result(output="已完成。"),
        extra={"memory_updated": True},
    )

    dependencies.release_concurrency.assert_awaited_once()


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
    cb_conv_svc.message_repo.count_by_conversation = AsyncMock(return_value=1)
    cb_conv_svc.message_repo.get_next_sequence = AsyncMock(return_value=2)
    cb_conv_svc.message_repo.create = AsyncMock()
    _attach_stream_persistence_contract(cb_conv_svc, cb_db)

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

    assert cb_conv_svc.message_repo.create.await_count == 1
    error_payload = cb_conv_svc.message_repo.create.await_args_list[0].args[0]
    assert error_payload["role"] == "assistant"
    assert error_payload["content"] == _("common.server_error")
    assert error_payload["metadata_"]["error"] is True
    assert error_payload["metadata_"]["error_type"] == "stream_execution_error"
    assert error_payload["metadata_"]["error_message"] == _("common.server_error")
    assert error_payload["metadata_"]["error_only"] is True
    assert conversation.message_count == 2
    assert cb_db.commit.await_count == 1


@pytest.mark.asyncio
async def test_stream_on_complete_uses_interrupted_copy_for_cancelled_streams(
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
    cb_conv_svc.persist_chat_messages = AsyncMock(return_value=([], 1))
    cb_conv_svc.update_stats = AsyncMock()
    cb_conv_svc.message_repo.count_by_conversation = AsyncMock(return_value=1)
    cb_conv_svc.message_repo.get_next_sequence = AsyncMock(return_value=2)
    cb_conv_svc.message_repo.create = AsyncMock()
    _attach_stream_persistence_contract(cb_conv_svc, cb_db)

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
        await on_complete(
            _build_failed_result(
                error="CancelledError: Cancelled via cancel scope 0xabc123"
            )
        )

    error_payload = cb_conv_svc.message_repo.create.await_args_list[0].args[0]
    assert error_payload["content"] == _("ai.stream.error.interrupted")


@pytest.mark.asyncio
async def test_stream_on_complete_skips_error_message_for_transport_disconnect(
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
    cb_conv_svc.message_repo.count_by_conversation = AsyncMock(return_value=1)
    cb_conv_svc.message_repo.get_next_sequence = AsyncMock(return_value=2)
    cb_conv_svc.message_repo.create = AsyncMock()
    _attach_stream_persistence_contract(cb_conv_svc, cb_db)

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
        disconnect_result = _build_failed_result(
            error=(
                "CancelledError: Cancelled via cancel scope 0xabc by <Task pending "
                "name='Task-118' coro=<RequestResponseCycle.run_asgi()>>"
            )
        )
        disconnect_result.interrupted = True
        disconnect_result.completion_reason = "interrupted"
        disconnect_result.diagnostics = {"transport_disconnect": True}
        disconnect_result.turn_record = {
            "transport_disconnect": True,
            "metadata": {"transport_disconnect": True},
        }
        extra = await on_complete(disconnect_result)

    assert extra is not None
    assert extra["persisted_message_count"] == 0
    assert cb_conv_svc.message_repo.create.await_count == 0
    assert "last_error" not in conversation.metadata_


@pytest.mark.asyncio
async def test_stream_on_complete_skips_provider_timeout_terminal_copy_persistence(
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
    cb_conv_svc.message_repo.count_by_conversation = AsyncMock(return_value=1)
    cb_conv_svc.message_repo.get_next_sequence = AsyncMock(return_value=2)
    cb_conv_svc.message_repo.create = AsyncMock()
    _attach_stream_persistence_contract(cb_conv_svc, cb_db)

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
        patch(
            "app.services.ai.agent_chat_stream_persistence_orchestrator.logger"
        ) as logger_mock,
    ):
        extra = await on_complete(_build_provider_timeout_result())

    assert extra is not None
    assert extra["persisted_message_count"] == 0
    cb_conv_svc.persist_chat_messages.assert_not_awaited()
    assert cb_conv_svc.message_repo.create.await_count == 0
    logger_mock.warning.assert_not_called()
    logger_mock.error.assert_not_called()


@pytest.mark.asyncio
async def test_stream_on_complete_uses_provider_message_when_failure_kind_is_provider_rate_limit(
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
    cb_conv_svc.message_repo.count_by_conversation = AsyncMock(return_value=1)
    cb_conv_svc.message_repo.get_next_sequence = AsyncMock(return_value=2)
    cb_conv_svc.message_repo.create = AsyncMock()
    _attach_stream_persistence_contract(cb_conv_svc, cb_db)

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
        provider_failed_result = _build_failed_result(
            error="并发 Session 超限：当前 3 个（限制：3 个）。"
        )
        provider_failed_result.provider_failure_kind = "provider_rate_limit"
        await on_complete(provider_failed_result)

    error_payload = cb_conv_svc.message_repo.create.await_args_list[0].args[0]
    assert error_payload["content"] == "并发 Session 超限：当前 3 个（限制：3 个）。"
    assert (
        error_payload["metadata_"]["error_message"]
        == "并发 Session 超限：当前 3 个（限制：3 个）。"
    )


@pytest.mark.asyncio
async def test_stream_post_persist_tail_skips_memory_extraction_after_failed_result(
    mock_db,
):
    service = await _build_stream_service(mock_db)
    on_complete, _hook_registry = await _capture_on_complete(service, mock_db)

    with (
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
        extra = await on_complete(_build_failed_result())
        assert extra is not None
        await extra["__post_done_callback__"]()

    service._persist_session_memory.assert_not_awaited()


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
    cb_conv_svc.message_repo.count_by_conversation = AsyncMock(return_value=1)
    cb_conv_svc.message_repo.get_next_sequence = AsyncMock(return_value=2)
    cb_conv_svc.message_repo.create = AsyncMock()
    _attach_stream_persistence_contract(cb_conv_svc, cb_db)

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
    assert conversation.metadata_["last_error"]["error_type"] == "stream_fallback_error"
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
    cb_conv_svc.message_repo.count_by_conversation = AsyncMock(return_value=1)
    cb_conv_svc.message_repo.get_next_sequence = AsyncMock(return_value=2)
    cb_conv_svc.message_repo.create = AsyncMock()
    _attach_stream_persistence_contract(cb_conv_svc, cb_db)

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
    cb_conv_svc.message_repo.count_by_conversation = AsyncMock(return_value=1)
    cb_conv_svc.message_repo.get_next_sequence = AsyncMock(return_value=2)
    cb_conv_svc.message_repo.create = AsyncMock()
    _attach_stream_persistence_contract(cb_conv_svc, cb_db)

    partial_result = _build_failed_result(output="partial text")
    partial_result.messages = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "帮我添加一个测试智能体"},
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
async def test_stream_on_complete_persists_error_message_when_only_tool_round_exists(
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
    cb_conv_svc.persist_chat_messages = AsyncMock(return_value=([], 2))
    cb_conv_svc.update_stats = AsyncMock()
    cb_conv_svc.message_repo.count_by_conversation = AsyncMock(return_value=1)
    cb_conv_svc.message_repo.get_next_sequence = AsyncMock(return_value=2)
    cb_conv_svc.message_repo.create = AsyncMock()
    _attach_stream_persistence_contract(cb_conv_svc, cb_db)

    partial_result = _build_failed_result(output="")
    partial_result.messages = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "现在几点了"},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [{"id": "call_time_1"}],
        },
        {
            "role": "tool",
            "content": "2026-04-09 18:45:59",
            "tool_call_id": "call_time_1",
        },
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
    assert cb_conv_svc.message_repo.create.await_count == 1
    payload = cb_conv_svc.message_repo.create.await_args_list[0].args[0]
    assert payload["content"] == _("common.server_error")


@pytest.mark.asyncio
async def test_stream_on_complete_reasoning_only_rescue_success_skips_error_message(
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
    cb_conv_svc.message_repo.count_by_conversation = AsyncMock(return_value=1)
    cb_conv_svc.message_repo.get_next_sequence = AsyncMock(return_value=2)
    cb_conv_svc.message_repo.create = AsyncMock()
    _attach_stream_persistence_contract(cb_conv_svc, cb_db)
    publish_failed = AsyncMock()
    publish_completed = AsyncMock()

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
            new=publish_failed,
        ),
        patch(
            "app.services.ai.agent_chat_service.BaseEngine._publish_execution_completed",
            new=publish_completed,
        ),
    ):
        extra = await on_complete(_build_success_result())
        await extra["__post_done_callback__"]()

    assert extra is not None
    assert extra["persistence_committed"] is True
    assert extra["persisted_message_count"] == 1
    cb_conv_svc.persist_chat_messages.assert_awaited_once()
    persist_kwargs = cb_conv_svc.persist_chat_messages.await_args.kwargs
    assert persist_kwargs["context_diagnostics"]["termination_reason"] == (
        "protocol_fallback"
    )
    assert persist_kwargs["context_diagnostics"]["protocol_path"] == (
        "chat_completions"
    )
    assert persist_kwargs["last_run_summary"]["completion_reason"] == (
        "protocol_fallback"
    )
    assert persist_kwargs["last_run_summary"]["protocol_path"] == "chat_completions"
    cb_conv_svc.message_repo.create.assert_not_awaited()
    assert "last_error" not in conversation.metadata_
    publish_completed.assert_awaited_once()
    publish_failed.assert_not_awaited()


@pytest.mark.asyncio
async def test_stream_post_persist_tail_commits_primary_memory_writes_on_success(
    mock_db,
):
    service = await _build_stream_service(mock_db)
    service._persist_session_memory = AsyncMock(
        return_value={
            "preferences": [],
            "constraints": [],
            "task_states": [],
            "verified_facts": ["用户名字是大致坡"],
        }
    )
    on_complete, _hook_registry = await _capture_on_complete(service, mock_db)

    cb_db = AsyncMock()
    cb_db.commit = AsyncMock()
    cb_db.rollback = AsyncMock()
    mem_db = AsyncMock()
    mem_db.commit = AsyncMock()
    mem_db.rollback = AsyncMock()
    conversation = _build_conversation()
    cb_conv_svc = MagicMock()
    cb_conv_svc.repo.get_by_id = AsyncMock(return_value=conversation)
    cb_conv_svc.persist_chat_messages = AsyncMock(return_value=([], 1))
    cb_conv_svc.update_stats = AsyncMock()
    mem_conv_svc = MagicMock()
    mem_conv_svc.mark_memory_updated = AsyncMock(return_value=None)
    _attach_stream_persistence_contract(cb_conv_svc, cb_db)
    initial_commit_count = mock_db.commit.await_count
    initial_rollback_count = mock_db.rollback.await_count

    with (
        patch(
            "app.services.ai.agent_chat_service.async_session_factory",
            side_effect=[_SessionManager(cb_db), _SessionManager(mem_db)],
        ),
        patch(
            "app.services.ai.agent_chat_service.ConversationService",
            side_effect=[cb_conv_svc, mem_conv_svc],
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
        extra = await on_complete(_build_success_result())
        assert extra is not None
        await extra["__post_done_callback__"]()

    service._persist_session_memory.assert_awaited_once()
    assert mock_db.commit.await_count == initial_commit_count + 1
    assert mock_db.rollback.await_count == initial_rollback_count
    mem_conv_svc.mark_memory_updated.assert_awaited_once_with(100)
    mem_db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_stream_explicit_memory_save_reports_memory_updated_before_done(
    mock_db,
):
    """Test type: behavioral
    Verifies explicit "please remember" turns persist memory before the SSE
    done payload is built, so the frontend can immediately refresh the panel.
    """

    service = await _build_stream_service(mock_db)
    service._persist_session_memory = AsyncMock(
        return_value={
            "preferences": [],
            "constraints": [],
            "task_states": [],
            "verified_facts": ["用户名字是ix long"],
        }
    )
    on_complete, _hook_registry = await _capture_on_complete(
        service,
        mock_db,
        message="我叫 ix long 请记住",
    )

    cb_db = AsyncMock()
    cb_db.commit = AsyncMock()
    cb_db.rollback = AsyncMock()
    mem_db = AsyncMock()
    mem_db.commit = AsyncMock()
    mem_db.rollback = AsyncMock()
    conversation = _build_conversation()
    cb_conv_svc = MagicMock()
    cb_conv_svc.repo.get_by_id = AsyncMock(return_value=conversation)
    cb_conv_svc.persist_chat_messages = AsyncMock(return_value=([], 1))
    cb_conv_svc.update_stats = AsyncMock()
    mem_conv_svc = MagicMock()
    mem_conv_svc.mark_memory_updated = AsyncMock(return_value=None)
    _attach_stream_persistence_contract(cb_conv_svc, cb_db)
    initial_commit_count = mock_db.commit.await_count

    with (
        patch(
            "app.services.ai.agent_chat_service.async_session_factory",
            side_effect=[_SessionManager(cb_db), _SessionManager(mem_db)],
        ),
        patch(
            "app.services.ai.agent_chat_service.ConversationService",
            side_effect=[cb_conv_svc, mem_conv_svc],
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
        extra = await on_complete(_build_success_result(output="已记住。"))
        assert extra is not None
        assert extra["memory_updated"] is True
        assert mock_db.commit.await_count == initial_commit_count + 1
        service._persist_session_memory.assert_awaited_once()
        mem_conv_svc.mark_memory_updated.assert_awaited_once_with(100)
        mem_db.commit.assert_awaited_once()

        await extra["__post_done_callback__"]()

    service._persist_session_memory.assert_awaited_once()


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
    cb_conv_svc.message_repo.count_by_conversation = AsyncMock(return_value=1)
    cb_conv_svc.message_repo.get_next_sequence = AsyncMock(return_value=2)
    cb_conv_svc.message_repo.create = AsyncMock()
    _attach_stream_persistence_contract(cb_conv_svc, cb_db)

    partial_result = _build_failed_result(output="partial text")
    partial_result.messages = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "帮我添加一个测试智能体"},
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
    assert cb_conv_svc.message_repo.create.await_count == 1
    payload = cb_conv_svc.message_repo.create.await_args_list[0].args[0]
    assert payload["content"] == _("common.server_error")


@pytest.mark.asyncio
async def test_stream_on_complete_falls_back_to_error_message_when_persistence_raises(
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
    cb_conv_svc.persist_chat_messages = AsyncMock(
        side_effect=TypeError("Object of type Decimal is not JSON serializable")
    )
    cb_conv_svc.update_stats = AsyncMock()
    cb_conv_svc.message_repo.count_by_conversation = AsyncMock(return_value=1)
    cb_conv_svc.message_repo.get_next_sequence = AsyncMock(return_value=2)
    cb_conv_svc.message_repo.create = AsyncMock()
    _attach_stream_persistence_contract(cb_conv_svc, cb_db)

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
        partial_result = _build_failed_result(output="partial text")
        partial_result.messages = [
            {"role": "system", "content": "sys"},
            {"role": "user", "content": "帮我添加一个测试智能体"},
            {"role": "assistant", "content": "partial text"},
        ]
        extra = await on_complete(partial_result)

    assert extra is not None
    assert extra["persistence_error"] is True
    assert extra["persistence_committed"] is True
    assert extra["persisted_message_count"] == 1
    cb_conv_svc.persist_chat_messages.assert_awaited_once()
    assert cb_conv_svc.message_repo.create.await_count == 1
    error_payload = cb_conv_svc.message_repo.create.await_args_list[0].args[0]
    assert error_payload["metadata_"]["error_type"] == "stream_execution_error"
    assert (
        error_payload["metadata_"]["context_diagnostics"]["persistence_error"] is True
    )


@pytest.mark.asyncio
async def test_stream_on_complete_marks_committed_when_only_last_error_marker_persists(
    mock_db,
):
    service = await _build_stream_service(mock_db)
    on_complete, _hook_registry = await _capture_on_complete(service, mock_db)

    persist_db = AsyncMock()
    persist_db.commit = AsyncMock()
    persist_db.rollback = AsyncMock()
    error_db = AsyncMock()
    error_db.commit = AsyncMock()
    error_db.rollback = AsyncMock()
    marker_db = AsyncMock()
    marker_db.commit = AsyncMock()
    marker_db.rollback = AsyncMock()

    conversation = _build_conversation()
    persist_conv_svc = MagicMock()
    persist_conv_svc.repo.get_by_id = AsyncMock(return_value=conversation)
    persist_conv_svc.persist_chat_messages = AsyncMock(
        side_effect=TypeError("Object of type Decimal is not JSON serializable")
    )
    persist_conv_svc.update_stats = AsyncMock()
    _attach_stream_persistence_contract(persist_conv_svc, persist_db)

    error_conv_svc = MagicMock()
    error_conv_svc.repo.get_by_id = AsyncMock(return_value=conversation)
    error_conv_svc.message_repo.count_by_conversation = AsyncMock(return_value=1)
    error_conv_svc.message_repo.get_next_sequence = AsyncMock(return_value=2)
    error_conv_svc.message_repo.create = AsyncMock(
        side_effect=RuntimeError("assistant insert failed")
    )
    _attach_stream_persistence_contract(error_conv_svc, error_db)

    marker_conv_svc = MagicMock()
    marker_conv_svc.repo.get_by_id = AsyncMock(return_value=conversation)
    _attach_stream_persistence_contract(marker_conv_svc, marker_db)

    partial_result = _build_failed_result(output="partial text")
    partial_result.messages = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "帮我添加一个测试智能体"},
        {"role": "assistant", "content": "partial text"},
    ]

    with (
        patch(
            "app.services.ai.agent_chat_service.async_session_factory",
            side_effect=[
                _SessionManager(persist_db),
                _SessionManager(error_db),
                _SessionManager(marker_db),
            ],
        ),
        patch(
            "app.services.ai.agent_chat_service.ConversationService",
            side_effect=[persist_conv_svc, error_conv_svc, marker_conv_svc],
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
        extra = await on_complete(partial_result)

    assert extra is not None
    assert extra["persistence_error"] is True
    assert extra["persistence_committed"] is True
    assert extra["persisted_message_count"] == 0
    assert conversation.metadata_["last_error"]["error_type"] == (
        "stream_on_complete_persistence_error"
    )
    persist_conv_svc.persist_chat_messages.assert_awaited_once()
    error_conv_svc.message_repo.create.assert_awaited_once()
    marker_db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_stream_on_complete_reports_uncommitted_when_error_message_and_marker_fail(
    mock_db,
):
    service = await _build_stream_service(mock_db)
    on_complete, _hook_registry = await _capture_on_complete(service, mock_db)

    persist_db = AsyncMock()
    persist_db.commit = AsyncMock()
    persist_db.rollback = AsyncMock()
    error_db = AsyncMock()
    error_db.commit = AsyncMock()
    error_db.rollback = AsyncMock()
    marker_db = AsyncMock()
    marker_db.commit = AsyncMock(side_effect=RuntimeError("marker commit failed"))
    marker_db.rollback = AsyncMock()

    conversation = _build_conversation()
    persist_conv_svc = MagicMock()
    persist_conv_svc.repo.get_by_id = AsyncMock(return_value=conversation)
    persist_conv_svc.persist_chat_messages = AsyncMock(
        side_effect=TypeError("Object of type Decimal is not JSON serializable")
    )
    persist_conv_svc.update_stats = AsyncMock()
    _attach_stream_persistence_contract(persist_conv_svc, persist_db)

    error_conv_svc = MagicMock()
    error_conv_svc.repo.get_by_id = AsyncMock(return_value=conversation)
    error_conv_svc.message_repo.count_by_conversation = AsyncMock(return_value=1)
    error_conv_svc.message_repo.get_next_sequence = AsyncMock(return_value=2)
    error_conv_svc.message_repo.create = AsyncMock(
        side_effect=RuntimeError("assistant insert failed")
    )
    _attach_stream_persistence_contract(error_conv_svc, error_db)

    marker_conv_svc = MagicMock()
    marker_conv_svc.repo.get_by_id = AsyncMock(return_value=conversation)
    _attach_stream_persistence_contract(marker_conv_svc, marker_db)

    partial_result = _build_failed_result(output="partial text")
    partial_result.messages = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "帮我添加一个测试智能体"},
        {"role": "assistant", "content": "partial text"},
    ]

    with (
        patch(
            "app.services.ai.agent_chat_service.async_session_factory",
            side_effect=[
                _SessionManager(persist_db),
                _SessionManager(error_db),
                _SessionManager(marker_db),
            ],
        ),
        patch(
            "app.services.ai.agent_chat_service.ConversationService",
            side_effect=[persist_conv_svc, error_conv_svc, marker_conv_svc],
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
        extra = await on_complete(partial_result)

    assert extra is not None
    assert extra["persistence_error"] is True
    assert extra["persistence_committed"] is False
    assert extra["persisted_message_count"] == 0
    persist_conv_svc.persist_chat_messages.assert_awaited_once()
    error_conv_svc.message_repo.create.assert_awaited_once()
    marker_db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_stream_on_complete_callback_exception_persists_error_marker(mock_db):
    from app.core.i18n import _

    service = await _build_stream_service(mock_db)
    on_complete, _hook_registry = await _capture_on_complete(service, mock_db)

    cb_db = AsyncMock()
    cb_db.commit = AsyncMock()
    cb_db.rollback = AsyncMock()
    conversation = _build_conversation()
    cb_conv_svc = MagicMock()
    cb_conv_svc.repo.get_by_id = AsyncMock(return_value=conversation)
    cb_conv_svc.message_repo.count_by_conversation = AsyncMock(return_value=1)
    cb_conv_svc.message_repo.get_next_sequence = AsyncMock(return_value=2)
    cb_conv_svc.message_repo.create = AsyncMock()
    cb_conv_svc.persist_chat_messages = AsyncMock(return_value=([], 0))
    cb_conv_svc.update_stats = AsyncMock()
    _attach_stream_persistence_contract(cb_conv_svc, cb_db)

    service._build_context_diagnostics = MagicMock(
        side_effect=RuntimeError("diagnostics serializer exploded")
    )

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
        failed_result = _build_failed_result(output="partial text")
        failed_result.messages = [
            {"role": "system", "content": "sys"},
            {"role": "user", "content": "帮我添加一个测试智能体"},
            {"role": "assistant", "content": "partial text"},
        ]
        extra = await on_complete(failed_result)

    assert extra is not None
    assert extra["on_complete_error"] is True
    assert cb_conv_svc.message_repo.create.await_count == 1
    payload = cb_conv_svc.message_repo.create.await_args_list[0].args[0]
    assert payload["content"] == _("common.server_error")
    assert "last_error" in conversation.metadata_
    assert (
        conversation.metadata_["last_error"]["error_type"]
        == "stream_on_complete_callback_error"
    )
