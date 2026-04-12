from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import app.ai.engine.base_execution_support as base_execution_support
import app.ai.engine.base_tool_loop_support as base_tool_loop_support
from app.ai.engine.base import BaseEngine, log_user_type_for_call_log
from app.ai.types import ChatMessage, ChatResponse
from app.enums.common import UserRoleEnum
from app.enums.log import UserTypeEnum as LogUserTypeEnum


class _EngineStub(BaseEngine):
    async def execute(self, agent, request):  # type: ignore[override]
        _ = agent, request
        raise NotImplementedError


def test_base_engine_facade_keeps_support_contracts() -> None:
    engine = _EngineStub(
        db=SimpleNamespace(),
        gateway=SimpleNamespace(),
        sandbox=None,
    )

    assert callable(engine._prepare_execution)
    assert callable(engine._call_llm)
    assert callable(engine._handle_tool_calls)
    assert callable(engine._publish_execution_started)
    assert callable(engine._publish_execution_completed)
    assert callable(engine._publish_execution_failed)
    payload = BaseEngine._messages_to_dicts([ChatMessage(role="user", content="hello")])
    assert payload[0]["role"] == "user"
    assert payload[0]["content"] == "hello"


def test_base_engine_facade_does_not_override_support_mixins() -> None:
    assert "_prepare_execution" not in BaseEngine.__dict__
    assert "_call_llm" not in BaseEngine.__dict__
    assert "_handle_tool_calls" not in BaseEngine.__dict__
    assert (
        BaseEngine._prepare_execution
        is base_execution_support.BaseEngineExecutionSupport._prepare_execution
    )
    assert (
        BaseEngine._call_llm is base_execution_support.BaseEngineExecutionSupport._call_llm
    )
    assert (
        BaseEngine._handle_tool_calls
        is base_tool_loop_support.BaseToolLoopSupport._handle_tool_calls
    )


async def test_base_engine_call_llm_facade_delegates_with_runtime_callables(
    monkeypatch,
) -> None:
    engine = _EngineStub(
        db=SimpleNamespace(name="db"),
        gateway=SimpleNamespace(name="gateway"),
        sandbox=None,
    )
    captured: dict[str, object] = {}

    async def _fake_execute_llm_call(**kwargs):
        captured.update(kwargs)
        return ChatResponse(message=ChatMessage(role="assistant", content="ok"))

    monkeypatch.setattr(base_execution_support, "execute_llm_call", _fake_execute_llm_call)
    monkeypatch.setattr(
        engine,
        "_prepare_llm_gateway_call",
        AsyncMock(name="prepare_llm_gateway_call"),
    )
    monkeypatch.setattr(
        engine,
        "_apply_llm_response_metadata",
        AsyncMock(name="apply_llm_response_metadata"),
    )

    response = await engine._call_llm(
        agent=SimpleNamespace(id=1),
        messages=[ChatMessage(role="user", content="hello")],
        tenant_id=7,
        conversation_id=42,
    )

    assert response.message.content == "ok"
    assert captured["db"] is engine.db
    assert captured["gateway"] is engine.gateway
    assert captured["prepare_llm_gateway_call"] is engine._prepare_llm_gateway_call
    assert (
        captured["apply_llm_response_metadata"] is engine._apply_llm_response_metadata
    )
    assert captured["tenant_id"] == 7
    assert captured["conversation_id"] == 42


def test_log_user_type_for_call_log_keeps_public_mapping() -> None:
    assert (
        log_user_type_for_call_log(UserRoleEnum.PLATFORM_ADMIN.value)
        == LogUserTypeEnum.ADMIN.value
    )
    assert (
        log_user_type_for_call_log(UserRoleEnum.TENANT_USER.value)
        == LogUserTypeEnum.TENANT_USER.value
    )
    assert (
        log_user_type_for_call_log(UserRoleEnum.TENANT_ADMIN.value)
        == LogUserTypeEnum.TENANT_ADMIN.value
    )
