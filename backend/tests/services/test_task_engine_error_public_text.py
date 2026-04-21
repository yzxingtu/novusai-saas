from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.ai.engine.conversation import ConversationEngine
from app.ai.engine.task import TaskEngine
from app.ai.engine.types import ExecutionRequest, ExecutionResult
from app.ai.types import ChatMessage
from app.core.config import settings
from app.middleware.trace import trace_id_var


@pytest.mark.asyncio
async def test_task_engine_delegates_to_shared_turn_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = TaskEngine(db=MagicMock(), gateway=MagicMock(), sandbox=MagicMock())
    request = ExecutionRequest(
        agent_id=1,
        tenant_id=1,
        user_id=1,
    )
    agent = SimpleNamespace(id=1, system_prompt=None)
    skill_result = SimpleNamespace(tools=[])
    captured: dict[str, object] = {}

    async def _fake_execute(
        self: ConversationEngine,
        agent: object,
        request: ExecutionRequest,
        skill_result: object | None = None,
    ) -> ExecutionResult:
        captured["agent"] = agent
        captured["request"] = request
        captured["skill_result"] = skill_result
        return ExecutionResult(success=True, output="shared-turn-contract")

    monkeypatch.setattr(ConversationEngine, "execute", _fake_execute)

    result = await engine.execute(agent, request, skill_result=skill_result)

    delegated_request = captured["request"]
    assert isinstance(delegated_request, ExecutionRequest)
    assert delegated_request is not request
    assert delegated_request.execution_mode == request.execution_mode
    assert delegated_request.messages
    assert delegated_request.messages[0].role == "user"
    assert delegated_request.messages[0].content
    assert request.messages == []
    assert captured["agent"] is agent
    assert captured["skill_result"] is skill_result
    assert result.output == "shared-turn-contract"


@pytest.mark.asyncio
async def test_task_engine_hides_generic_exception_in_production() -> None:
    engine = TaskEngine(db=MagicMock(), gateway=MagicMock(), sandbox=MagicMock())
    engine._call_llm = AsyncMock(side_effect=RuntimeError("task secret failure"))

    request = ExecutionRequest(
        agent_id=1,
        tenant_id=1,
        user_id=1,
        messages=[ChatMessage(role="user", content="hello")],
    )
    agent = SimpleNamespace(id=1, system_prompt=None)
    skill_result = SimpleNamespace(tools=[])

    original_debug = settings.DEBUG
    token = trace_id_var.set("trace-task-prod")
    settings.DEBUG = False
    try:
        result = await engine.execute(agent, request, skill_result=skill_result)
    finally:
        settings.DEBUG = original_debug
        trace_id_var.reset(token)

    assert result.success is False
    assert "task secret failure" not in (result.error or "")
    assert "trace-task-prod" in (result.error or "")
