"""中文: AI 测试模块分类标记。

EN: AI test module classification marker.

Test type: structural / behavioral
Scope: Existing AI tests in this module; no real-dialogue smoke acceptance is claimed.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

import app.ai.engine.conversation as conversation
from app.ai.engine.conversation import ConversationEngine
from app.ai.engine.types import ExecutionRequest, ExecutionResult
from app.ai.types import ChatMessage


def _make_engine_agent_request() -> tuple[
    ConversationEngine, SimpleNamespace, ExecutionRequest
]:
    engine = ConversationEngine(
        db=MagicMock(),
        gateway=MagicMock(),
        sandbox=MagicMock(),
    )
    agent = SimpleNamespace(id=1)
    request = ExecutionRequest(
        agent_id=1,
        tenant_id=1,
        user_id=1,
        messages=[ChatMessage(role="user", content="hi")],
    )
    return engine, agent, request


@pytest.mark.asyncio
async def test_conversation_execute_facade_delegates_to_entrypoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine, agent, request = _make_engine_agent_request()
    sentinel = ExecutionResult(output="ok")
    captured: dict[str, object] = {}

    async def _fake_execute(engine_arg, *, agent, request, skill_result):
        captured["engine"] = engine_arg
        captured["agent"] = agent
        captured["request"] = request
        captured["skill_result"] = skill_result
        return sentinel

    monkeypatch.setattr(conversation, "_execute_conversation", _fake_execute)

    result = await engine.execute(agent, request, skill_result=None)

    assert result is sentinel
    assert captured["engine"] is engine
    assert captured["agent"] is agent
    assert captured["request"] is request
    assert captured["skill_result"] is None


@pytest.mark.asyncio
async def test_conversation_stream_execute_facade_delegates_to_entrypoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine, agent, request = _make_engine_agent_request()
    sentinel = MagicMock()
    captured: dict[str, object] = {}

    async def _fake_stream_execute(
        engine_arg,
        *,
        agent,
        request,
        on_complete,
        skill_result,
    ):
        captured["engine"] = engine_arg
        captured["agent"] = agent
        captured["request"] = request
        captured["on_complete"] = on_complete
        captured["skill_result"] = skill_result
        return sentinel

    monkeypatch.setattr(
        conversation, "_stream_execute_conversation", _fake_stream_execute
    )

    result = await engine.stream_execute(
        agent, request, on_complete=None, skill_result=None
    )

    assert result is sentinel
    assert captured["engine"] is engine
    assert captured["agent"] is agent
    assert captured["request"] is request
    assert captured["on_complete"] is None
    assert captured["skill_result"] is None
