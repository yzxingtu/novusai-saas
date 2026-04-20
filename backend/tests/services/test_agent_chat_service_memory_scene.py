"""AgentChatService 会话记忆场景参数测试 / Test.

覆盖：
1) AI 对话页场景（tenant chat）参数透传
2) 管理端代测场景参数透传（禁用）
3) 插件场景参数透传（禁用）
4) 非法场景参数归一化"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.enums.agent import MemoryChannelEnum, MemorySceneEnum
from app.enums.common import UserRoleEnum


def _make_agent():
    agent = MagicMock()
    agent.id = 1
    agent.status = "published"
    agent.context_config = {}
    return agent


def _make_conversation():
    conv = MagicMock()
    conv.id = 100
    conv.agent_id = 1
    conv.user_id = 10
    conv.owner_type = "tenant_admin"
    return conv


def _make_execution_result():
    result = MagicMock()
    result.success = True
    result.output = "ok"
    result.total_tokens = 11
    result.messages = []
    result.tool_results = []
    result.context_compacted = False
    result.memory_flush_triggered = False
    result.memory_recalled = False
    result.prune_stats = None
    result.rag_source_kinds = []
    result.rag_sources = []
    result.runtime_model_name = "test-model"
    result.runtime_provider_name = "test-provider"
    result.duration_ms = 12
    result.tool_planner = None
    return result


def _assert_memory_context(
    request,
    *,
    scene: str,
    channel: str,
    source: str,
    enabled: bool,
) -> None:
    assert request.memory_scene == scene
    assert request.memory_channel == channel
    assert request.memory_source == source
    assert request.memory_enabled is enabled


@pytest.mark.asyncio
async def test_chat_passes_memory_scene_for_tenant_page(mock_db):
    from app.services.ai.agent_chat_service import AgentChatService

    service = AgentChatService(mock_db, tenant_id=1)
    service._validate_agent = AsyncMock(return_value=_make_agent())
    service.conversation_svc.get_or_create_for_chat = AsyncMock(return_value=_make_conversation())
    service.conversation_svc.load_chat_history = AsyncMock(return_value=[])
    service.conversation_svc.persist_chat_messages = AsyncMock(return_value=([], 0))
    service.conversation_svc.update_stats = AsyncMock(return_value=None)
    service._resolve_effective_memory_enabled = AsyncMock(return_value=True)

    dispatcher = AsyncMock()
    dispatcher.dispatch = AsyncMock(return_value=_make_execution_result())

    from unittest.mock import patch

    with patch("app.services.ai.agent_chat_service.ExecutionDispatcher", return_value=dispatcher), \
            patch("app.services.ai.agent_chat_service.AgentQuotaManager.record_conversation", new=AsyncMock()), \
            patch("app.services.ai.agent_chat_service.AgentStatsManager.record_chat", new=AsyncMock()):
        await service.chat(
            agent_id=1,
            message="hello",
            user_id=10,
            user_role=UserRoleEnum.TENANT_ADMIN.value,
            memory_scene=MemorySceneEnum.AI_CHAT_PAGE.value,
            memory_channel=MemoryChannelEnum.TENANT_CHAT.value,
            memory_source=MemorySceneEnum.AI_CHAT_PAGE.value,
        )

    called_request = dispatcher.dispatch.call_args.args[0]
    _assert_memory_context(
        called_request,
        scene=MemorySceneEnum.AI_CHAT_PAGE.value,
        channel=MemoryChannelEnum.TENANT_CHAT.value,
        source=MemorySceneEnum.AI_CHAT_PAGE.value,
        enabled=True,
    )


@pytest.mark.asyncio
async def test_chat_runtime_memory_switch_can_disable_memory(mock_db):
    from app.services.ai.agent_chat_service import AgentChatService

    service = AgentChatService(mock_db, tenant_id=1)
    service._validate_agent = AsyncMock(return_value=_make_agent())
    service.conversation_svc.get_or_create_for_chat = AsyncMock(return_value=_make_conversation())
    service.conversation_svc.load_chat_history = AsyncMock(return_value=[])
    service.conversation_svc.persist_chat_messages = AsyncMock(return_value=([], 0))
    service.conversation_svc.update_stats = AsyncMock(return_value=None)
    service._resolve_effective_memory_enabled = AsyncMock(return_value=False)

    dispatcher = AsyncMock()
    dispatcher.dispatch = AsyncMock(return_value=_make_execution_result())

    from unittest.mock import patch

    with patch("app.services.ai.agent_chat_service.ExecutionDispatcher", return_value=dispatcher), \
            patch("app.services.ai.agent_chat_service.AgentQuotaManager.record_conversation", new=AsyncMock()), \
            patch("app.services.ai.agent_chat_service.AgentStatsManager.record_chat", new=AsyncMock()):
        await service.chat(
            agent_id=1,
            message="hello",
            user_id=10,
            user_role=UserRoleEnum.TENANT_ADMIN.value,
            memory_scene=MemorySceneEnum.AI_CHAT_PAGE.value,
            memory_channel=MemoryChannelEnum.TENANT_CHAT.value,
            memory_source=MemorySceneEnum.AI_CHAT_PAGE.value,
        )

    called_request = dispatcher.dispatch.call_args.args[0]
    _assert_memory_context(
        called_request,
        scene=MemorySceneEnum.AI_CHAT_PAGE.value,
        channel=MemoryChannelEnum.TENANT_CHAT.value,
        source=MemorySceneEnum.AI_CHAT_PAGE.value,
        enabled=False,
    )


@pytest.mark.asyncio
async def test_chat_passes_memory_scene_for_admin_chat(mock_db):
    from app.services.ai.agent_chat_service import AgentChatService

    service = AgentChatService(mock_db, tenant_id=0)
    service._validate_agent = AsyncMock(return_value=_make_agent())
    service.conversation_svc.get_or_create_for_chat = AsyncMock(return_value=_make_conversation())
    service.conversation_svc.load_chat_history = AsyncMock(return_value=[])
    service.conversation_svc.persist_chat_messages = AsyncMock(return_value=([], 0))
    service.conversation_svc.update_stats = AsyncMock(return_value=None)
    service._resolve_effective_memory_enabled = AsyncMock(return_value=False)

    dispatcher = AsyncMock()
    dispatcher.dispatch = AsyncMock(return_value=_make_execution_result())

    from unittest.mock import patch

    with patch("app.services.ai.agent_chat_service.ExecutionDispatcher", return_value=dispatcher), \
            patch("app.services.ai.agent_chat_service.AgentQuotaManager.record_conversation", new=AsyncMock()), \
            patch("app.services.ai.agent_chat_service.AgentStatsManager.record_chat", new=AsyncMock()):
        await service.chat(
            agent_id=1,
            message="hello",
            user_id=1,
            user_role=UserRoleEnum.PLATFORM_ADMIN.value,
            memory_scene=MemorySceneEnum.ADMIN_CHAT.value,
            memory_channel=MemoryChannelEnum.ADMIN_CHAT.value,
            memory_source=MemoryChannelEnum.ADMIN_CHAT.value,
        )

    called_request = dispatcher.dispatch.call_args.args[0]
    _assert_memory_context(
        called_request,
        scene=MemorySceneEnum.ADMIN_CHAT.value,
        channel=MemoryChannelEnum.ADMIN_CHAT.value,
        source=MemoryChannelEnum.ADMIN_CHAT.value,
        enabled=False,
    )


@pytest.mark.asyncio
async def test_chat_passes_memory_scene_for_plugin(mock_db):
    from app.services.ai.agent_chat_service import AgentChatService

    service = AgentChatService(mock_db, tenant_id=1)
    service._validate_agent = AsyncMock(return_value=_make_agent())
    service.conversation_svc.get_or_create_for_chat = AsyncMock(return_value=_make_conversation())
    service.conversation_svc.load_chat_history = AsyncMock(return_value=[])
    service.conversation_svc.persist_chat_messages = AsyncMock(return_value=([], 0))
    service.conversation_svc.update_stats = AsyncMock(return_value=None)

    dispatcher = AsyncMock()
    dispatcher.dispatch = AsyncMock(return_value=_make_execution_result())

    from unittest.mock import patch

    with patch("app.services.ai.agent_chat_service.ExecutionDispatcher", return_value=dispatcher), \
            patch("app.services.ai.agent_chat_service.AgentQuotaManager.record_conversation", new=AsyncMock()), \
            patch("app.services.ai.agent_chat_service.AgentStatsManager.record_chat", new=AsyncMock()):
        await service.chat(
            agent_id=1,
            message="hello",
            user_id=20,
            memory_scene=MemorySceneEnum.PLUGIN.value,
            memory_channel=MemoryChannelEnum.PLUGIN.value,
            memory_source="plugin.weather-widget",
        )

    called_request = dispatcher.dispatch.call_args.args[0]
    _assert_memory_context(
        called_request,
        scene=MemorySceneEnum.PLUGIN.value,
        channel=MemoryChannelEnum.PLUGIN.value,
        source="plugin.weather-widget",
        enabled=False,
    )


@pytest.mark.asyncio
async def test_chat_normalizes_invalid_memory_context(mock_db):
    from app.services.ai.agent_chat_service import AgentChatService

    service = AgentChatService(mock_db, tenant_id=1)
    service._validate_agent = AsyncMock(return_value=_make_agent())
    service.conversation_svc.get_or_create_for_chat = AsyncMock(return_value=_make_conversation())
    service.conversation_svc.load_chat_history = AsyncMock(return_value=[])
    service.conversation_svc.persist_chat_messages = AsyncMock(return_value=([], 0))
    service.conversation_svc.update_stats = AsyncMock(return_value=None)

    dispatcher = AsyncMock()
    dispatcher.dispatch = AsyncMock(return_value=_make_execution_result())

    from unittest.mock import patch

    with patch("app.services.ai.agent_chat_service.ExecutionDispatcher", return_value=dispatcher), \
            patch("app.services.ai.agent_chat_service.AgentQuotaManager.record_conversation", new=AsyncMock()), \
            patch("app.services.ai.agent_chat_service.AgentStatsManager.record_chat", new=AsyncMock()):
        await service.chat(
            agent_id=1,
            message="hello",
            user_id=30,
            memory_scene="bad_scene",
            memory_channel="bad_channel",
            memory_source="",
        )

    called_request = dispatcher.dispatch.call_args.args[0]
    _assert_memory_context(
        called_request,
        scene=MemorySceneEnum.UNKNOWN.value,
        channel=MemoryChannelEnum.SYSTEM.value,
        source=MemorySceneEnum.UNKNOWN.value,
        enabled=False,
    )


@pytest.mark.asyncio
async def test_chat_non_stream_persists_session_memory(mock_db):
    from app.services.ai.agent_chat_service import AgentChatService

    service = AgentChatService(mock_db, tenant_id=1)
    service._validate_agent = AsyncMock(return_value=_make_agent())
    service.conversation_svc.get_or_create_for_chat = AsyncMock(return_value=_make_conversation())
    service.conversation_svc.load_chat_history = AsyncMock(return_value=[MagicMock(), MagicMock()])
    service.conversation_svc.persist_chat_messages = AsyncMock(return_value=([], 0))
    service.conversation_svc.update_stats = AsyncMock(return_value=None)
    service._resolve_effective_memory_enabled = AsyncMock(return_value=True)
    service._persist_session_memory = AsyncMock(return_value=None)
    service._resolve_runtime_trust_policy_ref = AsyncMock(return_value={"policy_ids": [99]})

    dispatcher = AsyncMock()
    dispatcher.dispatch = AsyncMock(return_value=_make_execution_result())

    from unittest.mock import patch

    with patch("app.services.ai.agent_chat_service.ExecutionDispatcher", return_value=dispatcher), \
            patch("app.services.ai.agent_chat_service.AgentQuotaManager.record_conversation", new=AsyncMock()), \
            patch("app.services.ai.agent_chat_service.AgentStatsManager.record_chat", new=AsyncMock()):
        await service.chat(
            agent_id=1,
            message="hello",
            user_id=10,
            user_role=UserRoleEnum.TENANT_ADMIN.value,
            memory_scene=MemorySceneEnum.AI_CHAT_PAGE.value,
            memory_channel=MemoryChannelEnum.TENANT_CHAT.value,
            memory_source=MemorySceneEnum.AI_CHAT_PAGE.value,
        )

    service._persist_session_memory.assert_awaited_once()
    call_kwargs = service._persist_session_memory.call_args.kwargs
    assert call_kwargs["message"] == "hello"
    assert call_kwargs["response"] == "ok"
    assert call_kwargs["event_id"].startswith("memevt:100:")


@pytest.mark.asyncio
async def test_chat_marks_request_session_memory_injected_when_context_loaded(mock_db):
    from app.services.ai.agent_chat_service import AgentChatService

    service = AgentChatService(mock_db, tenant_id=1)
    service._validate_agent = AsyncMock(return_value=_make_agent())
    service.conversation_svc.get_or_create_for_chat = AsyncMock(return_value=_make_conversation())
    service.conversation_svc.load_chat_history = AsyncMock(return_value=[])
    service.conversation_svc.persist_chat_messages = AsyncMock(return_value=([], 0))
    service.conversation_svc.update_stats = AsyncMock(return_value=None)
    service._resolve_effective_memory_enabled = AsyncMock(return_value=True)
    service._load_session_memory_context = AsyncMock(
        return_value="[SESSION MEMORY CONTEXT]\npreferences: 喜欢简洁回答"
    )
    service._persist_session_memory = AsyncMock(return_value=None)
    service._resolve_runtime_trust_policy_ref = AsyncMock(return_value=None)

    dispatcher = AsyncMock()
    dispatcher.dispatch = AsyncMock(return_value=_make_execution_result())

    from unittest.mock import patch

    with patch("app.services.ai.agent_chat_service.ExecutionDispatcher", return_value=dispatcher), \
            patch("app.services.ai.agent_chat_service.AgentQuotaManager.record_conversation", new=AsyncMock()), \
            patch("app.services.ai.agent_chat_service.AgentStatsManager.record_chat", new=AsyncMock()):
        await service.chat(
            agent_id=1,
            message="hello",
            user_id=10,
            user_role=UserRoleEnum.TENANT_ADMIN.value,
            memory_scene=MemorySceneEnum.AI_CHAT_PAGE.value,
            memory_channel=MemoryChannelEnum.TENANT_CHAT.value,
            memory_source=MemorySceneEnum.AI_CHAT_PAGE.value,
        )

    called_request = dispatcher.dispatch.call_args.args[0]
    assert called_request.session_memory_injected is True
    assert called_request.messages[0].role == "system"
    assert "[SESSION MEMORY CONTEXT]" in (called_request.messages[0].content or "")


@pytest.mark.asyncio
async def test_chat_response_includes_tool_planner_diagnostics(mock_db):
    from unittest.mock import patch

    from app.services.ai.agent_chat_service import AgentChatService

    service = AgentChatService(mock_db, tenant_id=1)
    service._validate_agent = AsyncMock(return_value=_make_agent())
    service.conversation_svc.get_or_create_for_chat = AsyncMock(return_value=_make_conversation())
    service.conversation_svc.load_chat_history = AsyncMock(return_value=[])
    service.conversation_svc.persist_chat_messages = AsyncMock(return_value=([], 0))
    service.conversation_svc.update_stats = AsyncMock(return_value=None)
    service._resolve_effective_memory_enabled = AsyncMock(return_value=False)
    service._persist_session_memory = AsyncMock(return_value=None)
    service._resolve_runtime_trust_policy_ref = AsyncMock(return_value=None)

    result = _make_execution_result()
    result.tool_planner = {
        "intent": "direct_reply",
        "family": "none",
        "allow_no_tool": True,
        "allow_family_continuation": False,
        "reason": "smalltalk_or_support_no_tool",
        "confidence_band": "high",
    }

    dispatcher = AsyncMock()
    dispatcher.dispatch = AsyncMock(return_value=result)

    with patch("app.services.ai.agent_chat_service.ExecutionDispatcher", return_value=dispatcher), \
            patch("app.services.ai.agent_chat_service.AgentQuotaManager.record_conversation", new=AsyncMock()), \
            patch("app.services.ai.agent_chat_service.AgentStatsManager.record_chat", new=AsyncMock()):
        response = await service.chat(
            agent_id=1,
            message="你真聪明",
            user_id=10,
            user_role=UserRoleEnum.TENANT_ADMIN.value,
        )

    assert response.context_diagnostics["tool_planner"] == result.tool_planner
    assert response.last_run_summary["tool_planner"] == result.tool_planner


@pytest.mark.asyncio
async def test_persist_session_memory_captures_long_term_memory_candidates(mock_db):
    from unittest.mock import patch

    from app.services.ai.agent_chat_service import AgentChatService

    service = AgentChatService(mock_db, tenant_id=1)
    service._extract_memory_delta = AsyncMock(
        return_value={
            "preferences": ["以后邮件要正式一些"],
            "constraints": ["不要用口语化语气"],
            "task_states": ["正在整理邮件风格"],
            "verified_facts": ["用户偏好正式邮件风格"],
        }
    )
    provider = MagicMock()
    provider.capture = AsyncMock(return_value=[])

    request = MagicMock()
    request.memory_enabled = True
    request.conversation_id = 100
    request.user_id = 10
    request.agent_id = 1
    request.memory_channel = MemoryChannelEnum.TENANT_CHAT.value
    request.memory_source = MemorySceneEnum.AI_CHAT_PAGE.value
    request.memory_scene = MemorySceneEnum.AI_CHAT_PAGE.value
    request.long_term_memory_enabled = True

    with patch(
        "app.services.ai.agent_chat_service.get_long_term_memory_provider",
        return_value=provider,
    ), patch(
        "app.services.ai.agent_chat_service.SessionMemoryService.upsert_state",
        new=AsyncMock(return_value={}),
    ):
        delta = await service._persist_session_memory(
            request=request,
            message="以后帮我写邮件要正式一些，不要太口语化。",
            response="好的，我会采用更正式的邮件语气。",
            event_id="memevt:100:test",
        )

    assert delta is not None
    provider.capture.assert_awaited_once()
    capture_kwargs = provider.capture.await_args.kwargs
    assert capture_kwargs["agent_id"] == 1
    assert capture_kwargs["user_id"] == 10
    assert capture_kwargs["source_kind"] == "conversation_turn"
    assert capture_kwargs["items_by_type"] == {
        "preference": ["以后邮件要正式一些"],
        "constraint": ["不要用口语化语气"],
        "fact": ["用户偏好正式邮件风格"],
        "task_summary": ["正在整理邮件风格"],
    }


@pytest.mark.asyncio
async def test_persist_session_memory_allows_long_term_capture_without_session_memory(
    mock_db,
):
    from unittest.mock import patch

    from app.services.ai.agent_chat_service import AgentChatService

    service = AgentChatService(mock_db, tenant_id=1)
    service._extract_memory_delta = AsyncMock(
        return_value={
            "preferences": [],
            "constraints": [],
            "task_states": [],
            "verified_facts": ["用户名字是大致坡"],
        }
    )
    provider = MagicMock()
    provider.capture = AsyncMock(return_value=[])

    request = MagicMock()
    request.memory_enabled = False
    request.conversation_id = 100
    request.user_id = 10
    request.agent_id = 1
    request.memory_channel = MemoryChannelEnum.TENANT_CHAT.value
    request.memory_source = MemorySceneEnum.AI_CHAT_PAGE.value
    request.memory_scene = MemorySceneEnum.AI_CHAT_PAGE.value
    request.long_term_memory_enabled = True

    with patch(
        "app.services.ai.agent_chat_service.get_long_term_memory_provider",
        return_value=provider,
    ), patch(
        "app.services.ai.agent_chat_service.SessionMemoryService.upsert_state",
        new=AsyncMock(return_value={}),
    ) as mock_upsert:
        delta = await service._persist_session_memory(
            request=request,
            message="我叫大致坡，请把这个信息存入长期记忆。",
            response="好的，我会记住。",
            event_id="memevt:100:test",
        )

    assert delta is not None
    mock_upsert.assert_not_awaited()
    provider.capture.assert_awaited_once()
    assert provider.capture.await_args.kwargs["items_by_type"] == {
        "preference": [],
        "constraint": [],
        "fact": ["用户名字是大致坡"],
        "task_summary": [],
    }


@pytest.mark.asyncio
async def test_persist_session_memory_skips_long_term_capture_for_polluted_turn(
    mock_db,
):
    from unittest.mock import patch

    from app.services.ai.agent_chat_service import AgentChatService

    service = AgentChatService(mock_db, tenant_id=1)
    service._extract_memory_delta = AsyncMock(
        return_value={
            "preferences": [],
            "constraints": [],
            "task_states": [],
            "verified_facts": ["外部网页里提到用户名字是大致坡"],
        }
    )
    provider = MagicMock()
    provider.capture = AsyncMock(return_value=[])

    request = MagicMock()
    request.memory_enabled = False
    request.conversation_id = 100
    request.user_id = 10
    request.agent_id = 1
    request.memory_channel = MemoryChannelEnum.TENANT_CHAT.value
    request.memory_source = MemorySceneEnum.AI_CHAT_PAGE.value
    request.memory_scene = MemorySceneEnum.AI_CHAT_PAGE.value
    request.long_term_memory_enabled = True
    request.memory_runtime_policy = {
        "external_context_polluted": True,
        "external_context_reason": "tool:web_search",
    }

    with patch(
        "app.services.ai.agent_chat_service.get_long_term_memory_provider",
        return_value=provider,
    ), patch(
        "app.services.ai.agent_chat_service.SessionMemoryService.upsert_state",
        new=AsyncMock(return_value={}),
    ) as mock_upsert:
        delta = await service._persist_session_memory(
            request=request,
            message="网页说我叫大致坡，请记一下。",
            response="我先整理了一下网页内容。",
            event_id="memevt:100:test",
        )

    assert delta is None
    mock_upsert.assert_not_awaited()
    provider.capture.assert_not_awaited()


@pytest.mark.asyncio
async def test_chat_passes_explicit_trust_policy_ref_to_execution_request(mock_db):
    from app.services.ai.agent_chat_service import AgentChatService

    service = AgentChatService(mock_db, tenant_id=1)
    agent = _make_agent()
    service._validate_agent = AsyncMock(return_value=agent)
    service.conversation_svc.get_or_create_for_chat = AsyncMock(return_value=_make_conversation())
    service.conversation_svc.load_chat_history = AsyncMock(return_value=[])
    service.conversation_svc.persist_chat_messages = AsyncMock(return_value=([], 0))
    service.conversation_svc.update_stats = AsyncMock(return_value=None)
    service._resolve_effective_memory_enabled = AsyncMock(return_value=False)

    dispatcher = AsyncMock()
    dispatcher.dispatch = AsyncMock(return_value=_make_execution_result())

    from unittest.mock import patch

    with patch("app.services.ai.agent_chat_service.ExecutionDispatcher", return_value=dispatcher), \
            patch("app.services.ai.agent_chat_service.AgentQuotaManager.record_conversation", new=AsyncMock()), \
            patch("app.services.ai.agent_chat_service.AgentStatsManager.record_chat", new=AsyncMock()):
        await service.chat(
            agent_id=1,
            message="hello",
            user_id=10,
            user_role=UserRoleEnum.TENANT_ADMIN.value,
            trust_policy_ref={
                "policy_ids": [11],
                "allowed_tool_names": ["web_search"],
                "risk_level_cap": "read",
            },
        )

    called_request = dispatcher.dispatch.call_args.args[0]
    assert called_request.trust_policy_ref == {
        "policy_ids": [11],
        "allowed_tool_names": ["web_search"],
        "risk_level_cap": "read",
    }


@pytest.mark.asyncio
async def test_chat_grants_backend_trust_policy_from_pending_consent_when_trusted_auto_enabled(
    mock_db,
):
    from unittest.mock import patch

    from app.services.ai.agent_chat_service import AgentChatService

    service = AgentChatService(mock_db, tenant_id=1)
    agent = _make_agent()
    service._validate_agent = AsyncMock(return_value=agent)
    service.conversation_svc.get_or_create_for_chat = AsyncMock(return_value=_make_conversation())
    service.conversation_svc.load_chat_history = AsyncMock(return_value=[])
    service.conversation_svc.persist_chat_messages = AsyncMock(return_value=([], 0))
    service.conversation_svc.update_stats = AsyncMock(return_value=None)
    service.conversation_svc.update_last_assistant_interaction_state = AsyncMock(return_value=None)
    service._resolve_effective_memory_enabled = AsyncMock(return_value=False)
    service._resolve_runtime_trust_policy_ref = AsyncMock(return_value={"policy_ids": [99]})

    dispatcher = AsyncMock()
    dispatcher.dispatch = AsyncMock(return_value=_make_execution_result())

    with patch("app.services.ai.agent_chat_service.ExecutionDispatcher", return_value=dispatcher), \
            patch("app.services.ai.agent_chat_service.AgentQuotaManager.record_conversation", new=AsyncMock()), \
            patch("app.services.ai.agent_chat_service.AgentStatsManager.record_chat", new=AsyncMock()), \
            patch(
                "app.services.ai.agent_chat_service.ExecutionTrustPolicyService.grant_conversation_tool_trust",
                new_callable=AsyncMock,
            ) as grant_trust:
        await service.chat(
            agent_id=1,
            message="确认执行",
            user_id=10,
            user_role=UserRoleEnum.TENANT_ADMIN.value,
            interaction_mode="trusted_auto",
            interaction_updates=[
                {
                    "kind": "pending_consent",
                    "rejected": False,
                    "tool_name": "web_search",
                }
            ],
        )

    grant_trust.assert_awaited_once()


@pytest.mark.asyncio
async def test_chat_grants_backend_trust_policy_from_page_confirmation_when_trusted_auto_enabled(
    mock_db,
):
    from unittest.mock import patch

    from app.services.ai.agent_chat_service import AgentChatService

    service = AgentChatService(mock_db, tenant_id=1)
    agent = _make_agent()
    service._validate_agent = AsyncMock(return_value=agent)
    service.conversation_svc.get_or_create_for_chat = AsyncMock(return_value=_make_conversation())
    service.conversation_svc.load_chat_history = AsyncMock(return_value=[])
    service.conversation_svc.persist_chat_messages = AsyncMock(return_value=([], 0))
    service.conversation_svc.update_stats = AsyncMock(return_value=None)
    service.conversation_svc.update_last_assistant_interaction_state = AsyncMock(return_value=None)
    service._resolve_effective_memory_enabled = AsyncMock(return_value=False)
    service._resolve_runtime_trust_policy_ref = AsyncMock(return_value={"policy_ids": [99]})

    dispatcher = AsyncMock()
    dispatcher.dispatch = AsyncMock(return_value=_make_execution_result())

    with patch("app.services.ai.agent_chat_service.ExecutionDispatcher", return_value=dispatcher), \
            patch("app.services.ai.agent_chat_service.AgentQuotaManager.record_conversation", new=AsyncMock()), \
            patch("app.services.ai.agent_chat_service.AgentStatsManager.record_chat", new=AsyncMock()), \
            patch(
                "app.services.ai.agent_chat_service.ExecutionTrustPolicyService.grant_conversation_tool_trust",
                new_callable=AsyncMock,
            ) as grant_trust:
        await service.chat(
            agent_id=1,
            message="继续创建",
            user_id=10,
            user_role=UserRoleEnum.TENANT_ADMIN.value,
            interaction_mode="trusted_auto",
            interaction_updates=[
                {
                    "kind": "pending_confirmation",
                    "rejected": False,
                    "tool_name": "ui_fill_form",
                }
            ],
        )

    grant_trust.assert_awaited_once()


def test_memory_event_id_is_request_unique():
    from app.services.ai.agent_chat_service import AgentChatService

    first = AgentChatService._build_memory_event_id(100)
    second = AgentChatService._build_memory_event_id(100)

    assert first.startswith("memevt:100:")
    assert second.startswith("memevt:100:")
    assert first != second


@pytest.mark.asyncio
async def test_stream_chat_updates_pending_consent_state_with_string_owner_type(mock_db):
    from unittest.mock import patch

    from app.services.ai.agent_chat_service import AgentChatService

    service = AgentChatService(mock_db, tenant_id=1)
    agent = _make_agent()
    agent.quota_config = {}
    agent.model = None
    service._validate_agent = AsyncMock(return_value=agent)
    service._resolve_effective_memory_enabled = AsyncMock(return_value=False)
    service._load_session_memory_context = AsyncMock(return_value="")
    service._build_billing_context = AsyncMock(return_value={})
    service.conversation_svc.get_or_create_for_chat = AsyncMock(
        return_value=_make_conversation(),
    )
    service.conversation_svc.update_last_assistant_interaction_state = AsyncMock(
        return_value=None,
    )
    service.conversation_svc.load_chat_history = AsyncMock(return_value=[])
    service.conversation_svc.persist_user_messages = AsyncMock(return_value=1)
    service.conversation_svc.persist_chat_messages = AsyncMock(return_value=([], 0))

    engine = AsyncMock()
    engine.stream_execute = AsyncMock(return_value=MagicMock())

    with patch(
        "app.services.ai.agent_chat_service.ConversationEngine",
        return_value=engine,
    ), patch(
        "app.ai.skills.resolver.resolve_for_agent",
        new=AsyncMock(return_value=None),
    ), patch(
        "app.services.ai.agent_chat_service.AgentQuotaManager.check_quota",
        new=AsyncMock(),
    ), patch(
        "app.services.ai.agent_chat_service.AgentQuotaManager.check_user_quota",
        new=AsyncMock(),
    ), patch(
        "app.services.ai.agent_chat_service.AgentQuotaManager.record_conversation",
        new=AsyncMock(),
    ), patch(
        "app.services.ai.agent_chat_service.AgentConcurrencyLimiter.acquire",
        new=AsyncMock(return_value=""),
    ), patch(
        "app.services.ai.agent_chat_service.BaseEngine._publish_execution_started",
        new=AsyncMock(),
    ), patch(
        "app.services.tenant.quota_service.QuotaService.check_api_quota_for_tenant_id",
        new=AsyncMock(return_value=MagicMock(allowed=True, message=None)),
    ), patch(
        "app.configs.service.ConfigService.get_platform_config",
        new=AsyncMock(side_effect=["normal", 256]),
    ):
        await service.stream_chat(
            agent_id=1,
            message="确认执行",
            conversation_id=100,
            user_id=10,
            user_role=UserRoleEnum.TENANT_ADMIN.value,
            interaction_updates=[
                {
                    "kind": "pending_consent",
                    "rejected": False,
                    "tool_name": "get_current_weather",
                }
            ],
        )

    service.conversation_svc.update_last_assistant_interaction_state.assert_awaited_once_with(
        100,
        [
            {
                "kind": "pending_consent",
                "rejected": False,
                "tool_name": "get_current_weather",
                "auto_approve_source": "execution_trust_policy",
            }
        ],
        user_id=10,
        owner_type="tenant_admin",
        interaction_mode_requested="trusted_auto",
        interaction_mode_effective="trusted_auto",
        interaction_mode_downgrade_reason=None,
    )
