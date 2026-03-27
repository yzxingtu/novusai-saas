from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.ai.engine.conversation import ConversationEngine
from app.ai.engine.types import ExecutionRequest
from app.ai.skills.resolver import SkillResolveResult
from app.ai.tools.types import ToolDefinition
from app.ai.types import ChatMessage


class _FakeRouter:
    def __init__(self, db):
        self.db = db

    async def route(self, agent, request, estimated_tokens, tools=None):
        _ = agent, request, estimated_tokens, tools
        return None


@pytest.mark.asyncio
async def test_prepare_execution_skips_tools_when_sandbox_is_missing() -> None:
    engine = ConversationEngine(db=MagicMock(), gateway=MagicMock(), sandbox=None)
    request = ExecutionRequest(
        agent_id=1,
        tenant_id=1,
        user_id=1,
        messages=[ChatMessage(role="user", content="优化一下这段文字")],
        input_variables={},
    )
    agent = SimpleNamespace(
        id=1,
        name="Writer",
        system_prompt="You are {{ agent_name }}.",
        rag_config=None,
        model=SimpleNamespace(
            supports_audio=False,
            supports_video=False,
            supports_vision=False,
        ),
    )
    skill_result = SkillResolveResult(
        tools=[ToolDefinition(name="web_search", description="Search the web")]
    )

    with (
        patch(
            "app.ai.rag_injector.load_agent_kb_bindings",
            new=AsyncMock(return_value=([], {})),
        ),
        patch("app.ai.routing.router.ModelRouter", new=_FakeRouter),
    ):
        prep = await engine._prepare_execution(
            agent,
            request,
            skill_result=skill_result,
        )

    assert prep.tools == []
    assert request.input_variables["runtime_model_capabilities"] == {
        "supports_audio": False,
        "supports_video": False,
        "supports_vision": False,
    }
