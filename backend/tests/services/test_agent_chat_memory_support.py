"""Test type: behavioral
Scope: Request-startup memory policy priming and memory context-source metadata projection
Real dependencies: ExecutionRequest, prepare_request_memory_startup, memory policy normalization
Mocked dependencies: None
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.ai.engine.types import ExecutionRequest
from app.services.ai.agent_chat_memory_support import (
    load_session_memory_context,
    persist_session_memory,
)
from app.services.ai.conversation_memory_state_service import (
    CONVERSATION_MEMORY_STATE_METADATA_KEY,
    merge_conversation_memory_states,
)


def _make_request(
    *,
    memory_scene: str = "conversation",
    memory_channel: str = "system",
    memory_source: str = "conversation",
    memory_enabled: bool = True,
    long_term_memory_enabled: bool = False,
) -> ExecutionRequest:
    return ExecutionRequest(
        agent_id=1,
        tenant_id=1,
        user_id=10,
        conversation_id=100,
        memory_scene=memory_scene,
        memory_channel=memory_channel,
        memory_source=memory_source,
        memory_enabled=memory_enabled,
        long_term_memory_enabled=long_term_memory_enabled,
    )


class _MemoryLogger:
    def info(self, *_args, **_kwargs) -> None:
        return None

    def warning(self, *_args, **_kwargs) -> None:
        return None


class _RedisDownSessionMemory:
    def __init__(self, tenant_id: int):
        self.tenant_id = tenant_id

    async def get_state(self, **_kwargs):
        raise RuntimeError("redis down")

    async def upsert_state(self, **_kwargs):
        raise RuntimeError("redis down")


class _NoopLongTermProvider:
    async def capture(self, **_kwargs):
        raise AssertionError("long-term capture should not run in this case")


def _long_term_provider_factory(**kwargs):
    return _NoopLongTermProvider()


class _InMemoryConversationRepo:
    def __init__(self, db, tenant_id: int):
        self.db = db
        self.tenant_id = tenant_id

    async def get_by_id(self, conversation_id: int):
        conversation = self.db.conversation
        if (
            conversation.id != conversation_id
            or conversation.tenant_id != self.tenant_id
        ):
            return None
        return conversation

    async def update(self, conversation_id: int, payload: dict):
        conversation = self.db.conversation
        if conversation.id != conversation_id:
            return None
        if "metadata_" in payload:
            conversation.metadata_ = payload["metadata_"]
        self.db.updates.append((conversation_id, payload))
        return conversation


async def _fallback_extract_delta(*, message: str, response: str, agent_id: int):
    from app.services.ai.memory_extraction_service import MemoryExtractionService

    return MemoryExtractionService._fallback_extract_turn_memory(message)


def _empty_capture_payload(delta: dict[str, list[str]]) -> dict[str, list[str]]:
    return {}


def test_merge_conversation_memory_states_keeps_session_store_priority():
    """Test type: behavioral
    Verifies the Redis-backed hot-path state keeps list precedence while the
    conversation metadata mirror only fills missing facts.
    """

    merged = merge_conversation_memory_states(
        {
            "verified_facts": ["用户名字是ix long", "偏好中文回答"],
            "version": 4,
            "updated_at": 200,
        },
        {
            "verified_facts": ["旧称呼是ix", "用户名字是ix long"],
            "version": 2,
            "updated_at": 100,
        },
    )

    assert merged["verified_facts"] == [
        "用户名字是ix long",
        "偏好中文回答",
        "旧称呼是ix",
    ]
    assert merged["version"] == 4
    assert merged["updated_at"] == 200


@pytest.mark.asyncio
async def test_persist_session_memory_mirrors_to_conversation_metadata_when_redis_down(
    monkeypatch,
):
    """Test type: behavioral
    Verifies an explicit memory-save turn is still persisted into the
    conversation read model when Redis session memory is unavailable.
    """

    monkeypatch.setattr(
        "app.repositories.ai.agent_conversation_repository.AgentConversationRepository",
        _InMemoryConversationRepo,
    )
    conversation = SimpleNamespace(id=100, tenant_id=1, metadata_={})
    db = SimpleNamespace(conversation=conversation, updates=[])
    request = _make_request(
        memory_scene="ai_chat_page",
        memory_channel="user_chat",
        memory_source="ai_chat_page",
        memory_enabled=True,
        long_term_memory_enabled=False,
    )

    delta = await persist_session_memory(
        db=db,
        tenant_id=1,
        request=request,
        message="我叫 ix long",
        response="记住啦。",
        event_id="memevt:100:redis-down",
        logger=_MemoryLogger(),
        extract_delta=_fallback_extract_delta,
        build_capture_payload=_empty_capture_payload,
        long_term_provider_factory=_long_term_provider_factory,
        session_memory_service_cls=_RedisDownSessionMemory,
    )

    assert delta == {
        "preferences": [],
        "constraints": [],
        "task_states": [],
        "verified_facts": ["用户名字是ix long"],
    }
    persisted = conversation.metadata_[CONVERSATION_MEMORY_STATE_METADATA_KEY]
    assert persisted["verified_facts"] == ["用户名字是ix long"]
    assert persisted["version"] == 1
    assert persisted["last_event_id"] == "memevt:100:redis-down"
    assert (
        db.updates[-1][1]["metadata_"][CONVERSATION_MEMORY_STATE_METADATA_KEY][
            "conversation_id"
        ]
        == 100
    )


@pytest.mark.asyncio
async def test_persist_session_memory_saves_explicit_memory_request_when_runtime_disabled(
    monkeypatch,
):
    """Test type: behavioral
    Verifies an explicit "please remember" turn writes the conversation memory
    read model even when the runtime memory switch is disabled for the agent.
    """

    monkeypatch.setattr(
        "app.repositories.ai.agent_conversation_repository.AgentConversationRepository",
        _InMemoryConversationRepo,
    )
    conversation = SimpleNamespace(id=100, tenant_id=1, metadata_={})
    db = SimpleNamespace(conversation=conversation, updates=[])
    request = _make_request(
        memory_scene="ai_chat_page",
        memory_channel="user_chat",
        memory_source="ai_chat_page",
        memory_enabled=False,
        long_term_memory_enabled=False,
    )

    delta = await persist_session_memory(
        db=db,
        tenant_id=1,
        request=request,
        message="我叫 ix long  请记住",
        response="已记住。",
        event_id="memevt:100:explicit-disabled",
        logger=_MemoryLogger(),
        extract_delta=_fallback_extract_delta,
        build_capture_payload=_empty_capture_payload,
        long_term_provider_factory=_long_term_provider_factory,
        session_memory_service_cls=_RedisDownSessionMemory,
    )

    assert delta == {
        "preferences": [],
        "constraints": [],
        "task_states": [],
        "verified_facts": ["用户名字是ix long"],
    }
    persisted = conversation.metadata_[CONVERSATION_MEMORY_STATE_METADATA_KEY]
    assert persisted["verified_facts"] == ["用户名字是ix long"]
    assert persisted["last_event_id"] == "memevt:100:explicit-disabled"


@pytest.mark.asyncio
async def test_load_session_memory_context_reads_conversation_metadata_when_redis_down(
    monkeypatch,
):
    """Test type: behavioral
    Verifies the next turn can use the persisted conversation-memory mirror when
    Redis session memory cannot be read.
    """

    monkeypatch.setattr(
        "app.repositories.ai.agent_conversation_repository.AgentConversationRepository",
        _InMemoryConversationRepo,
    )
    conversation = SimpleNamespace(
        id=100,
        tenant_id=1,
        metadata_={
            CONVERSATION_MEMORY_STATE_METADATA_KEY: {
                "preferences": [],
                "constraints": [],
                "task_states": [],
                "verified_facts": ["用户名字是ix long"],
                "version": 1,
                "updated_at": 123,
            }
        },
    )
    db = SimpleNamespace(conversation=conversation, updates=[])
    request = _make_request(
        memory_scene="ai_chat_page",
        memory_channel="user_chat",
        memory_source="ai_chat_page",
        memory_enabled=True,
        long_term_memory_enabled=False,
    )

    context = await load_session_memory_context(
        db=db,
        tenant_id=1,
        request=request,
        logger=_MemoryLogger(),
        session_memory_service_cls=_RedisDownSessionMemory,
    )

    assert context == "[SESSION MEMORY CONTEXT]\nverified_facts: 用户名字是ix long"
