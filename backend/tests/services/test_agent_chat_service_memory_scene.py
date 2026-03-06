"""
AgentChatService 会话记忆场景参数测试

覆盖：
1) AI 对话页场景（tenant chat）参数透传
2) 管理端代测场景参数透传（禁用）
3) 插件场景参数透传（禁用）
4) 非法场景参数归一化
"""

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
    return conv


def _make_execution_result():
    result = MagicMock()
    result.success = True
    result.output = "ok"
    result.total_tokens = 11
    result.messages = []
    result.tool_results = []
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
    service.conversation_svc.persist_chat_messages = AsyncMock(return_value=[])
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
    service.conversation_svc.persist_chat_messages = AsyncMock(return_value=[])
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
    service.conversation_svc.persist_chat_messages = AsyncMock(return_value=[])
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
    service.conversation_svc.persist_chat_messages = AsyncMock(return_value=[])
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
    service.conversation_svc.persist_chat_messages = AsyncMock(return_value=[])
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
    service.conversation_svc.persist_chat_messages = AsyncMock(return_value=[])
    service.conversation_svc.update_stats = AsyncMock(return_value=None)
    service._resolve_effective_memory_enabled = AsyncMock(return_value=True)
    service._persist_session_memory = AsyncMock(return_value=None)

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
    assert call_kwargs["event_id"].startswith("100:2:")
