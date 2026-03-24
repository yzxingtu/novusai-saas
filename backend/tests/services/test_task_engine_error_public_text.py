from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.ai.engine.task import TaskEngine
from app.ai.engine.types import ExecutionRequest
from app.ai.types import ChatMessage
from app.core.config import settings
from app.middleware.trace import trace_id_var


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
