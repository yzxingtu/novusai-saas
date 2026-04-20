from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.enums.agent import AgentExecutionModeEnum, BatchRunStatusEnum
from app.tasks import agent_batch


class _AsyncSessionContext:
    def __init__(self, db):
        self.db = db

    async def __aenter__(self):
        return self.db

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _ScalarResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


def test_execute_batch_run_does_not_eager_resolve_agent_inventory(
    monkeypatch,
) -> None:
    import app.ai.engine.task as task_engine_module
    import app.ai.gateway as gateway_module
    import app.ai.skills.resolver as resolver_module
    import app.ai.tools.sandbox as sandbox_module
    import app.configs.service as config_service_module
    import app.repositories.ai.agent_repository as agent_repository_module
    import app.services.ai.agent_service as agent_service_module

    batch_run = SimpleNamespace(
        id=11,
        agent_id=77,
        status="pending",
        started_at=None,
        completed_at=None,
        completed_items=0,
        failed_items=0,
        results=None,
        errors=None,
        created_by=None,
        input_items=[
            {
                "item_id": "row-1",
                "input_variables": {"customer_name": "Acme"},
            }
        ],
    )
    agent = SimpleNamespace(id=77)
    db = AsyncMock()
    db.execute.return_value = _ScalarResult(batch_run)
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    monkeypatch.setattr(
        agent_batch,
        "_task_async_session",
        lambda: _AsyncSessionContext(db),
    )

    class _FakeAgentRepository:
        def __init__(self, db, tenant_id):
            self.db = db
            self.tenant_id = tenant_id

        async def get_by_id(self, agent_id):
            _ = agent_id
            return agent

    class _FakeAgentService:
        def __init__(self, db, tenant_id):
            self.db = db
            self.tenant_id = tenant_id

        async def build_usage_attribution_context(
            self,
            *,
            agent,
            user_id,
            user_role,
            user_role_id,
        ):
            _ = (agent, user_id, user_role, user_role_id)
            return {"source": "batch"}

    class _FakeConfigService:
        def __init__(self, db):
            self.db = db

        async def get_platform_config(self, key, default=None):
            _ = key
            return default

    class _FakeGateway:
        def __init__(self, db):
            self.db = db

    class _FakeSandbox:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    execute_calls: list[dict[str, object]] = []

    class _FakeTaskEngine:
        def __init__(self, *, db, gateway, sandbox):
            self.db = db
            self.gateway = gateway
            self.sandbox = sandbox

        async def execute(self, agent_arg, request_arg, skill_result=None):
            execute_calls.append(
                {
                    "agent": agent_arg,
                    "request": request_arg,
                    "skill_result": skill_result,
                }
            )
            return SimpleNamespace(
                success=True,
                output="done",
                total_tokens=5,
            )

    resolve_mock = AsyncMock(
        side_effect=AssertionError(
            "agent_batch should not eagerly resolve the full agent inventory"
        )
    )

    monkeypatch.setattr(
        agent_repository_module,
        "AgentRepository",
        _FakeAgentRepository,
    )
    monkeypatch.setattr(
        agent_service_module,
        "AgentService",
        _FakeAgentService,
    )
    monkeypatch.setattr(
        config_service_module,
        "ConfigService",
        _FakeConfigService,
    )
    monkeypatch.setattr(gateway_module, "AIGateway", _FakeGateway)
    monkeypatch.setattr(sandbox_module, "ToolSandbox", _FakeSandbox)
    monkeypatch.setattr(task_engine_module, "TaskEngine", _FakeTaskEngine)
    monkeypatch.setattr(resolver_module, "resolve_for_agent", resolve_mock)

    result = agent_batch.execute_batch_run.run(batch_run_id=11, tenant_id=9)

    assert result == {
        "batch_run_id": 11,
        "total": 1,
        "succeeded": 1,
        "failed": 0,
        "status": BatchRunStatusEnum.COMPLETED.value,
    }
    assert batch_run.status == BatchRunStatusEnum.COMPLETED.value
    assert batch_run.results == [
        {
            "item_id": "row-1",
            "output": "done",
            "total_tokens": 5,
        }
    ]
    assert batch_run.errors is None
    assert len(execute_calls) == 1
    assert execute_calls[0]["agent"] is agent
    assert execute_calls[0]["skill_result"] is None

    request = execute_calls[0]["request"]
    assert request.tenant_id == 9
    assert request.execution_mode == AgentExecutionModeEnum.TASK.value
    assert request.billing_context == {"source": "batch"}
    assert request.skip_quota is True
    assert request.skip_persistence is True
    resolve_mock.assert_not_awaited()
