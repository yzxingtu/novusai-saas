"""Test type: behavioral
Scope: structured orchestration routing helpers and runtime budget guards.
Mocked dependencies: runtime bridge seams only; routing and budget logic run real.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.ai.engine.budget_guard import BudgetGuard
from app.ai.engine.tool_router import ToolRouter
from app.ai.engine.types import (
    ExecutionBudget,
    IntentPlan,
)
from app.ai.exceptions import (
    AIGatewayError,
)
from app.ai.routing.routing_contracts import RouteResult
from app.ai.tools.types import ToolDefinition
from app.ai.types import ChatChunk, ChatMessage, ChatResponse


def _tool(name: str, description: str = "") -> ToolDefinition:
    return ToolDefinition(name=name, description=description or name)


def _mixed_tools() -> list[ToolDefinition]:
    return [
        _tool("get_current_weather", "Current weather"),
        _tool("get_weather_forecast", "Forecast"),
        _tool("get_current_time", "Current time"),
        _tool("crm_lookup", "CRM lookup"),
    ]


def _intent(
    intent_id: str,
    *,
    kind: str,
    family: str,
    order: int,
    label: str | None = None,
    status: str = "pending",
    allowed_tool_names: list[str] | None = None,
    metadata: dict | None = None,
) -> IntentPlan:
    return IntentPlan(
        intent_id=intent_id,
        kind=kind,
        family=family,
        order=order,
        user_visible_label=label or kind,
        source_text="user turn",
        status=status,
        allowed_tool_names=list(allowed_tool_names or []),
        completion_signals=list(allowed_tool_names or []),
        metadata=dict(metadata or {}),
    )


def test_tool_router_does_not_hardcode_plugin_owned_weather_tools() -> None:
    budget = BudgetGuard.build_default("fast", intent_count=1)
    intent = _intent("intent-1", kind="weather_query", family="weather", order=1)

    decision = ToolRouter.route(
        intents=[intent],
        tools=_mixed_tools(),
        budget=budget,
        input_variables={},
        user_text="帮我查一下北京现在的天气",
    )

    assert decision.intent_allowed_tools.get("intent-1") is None
    assert decision.intent_preferred_tools.get("intent-1") is None
    assert decision.candidate_tool_names() == []


def test_budget_guard_registers_preparation_and_detects_candidate_budget_exit() -> None:
    budget = ExecutionBudget(
        max_prompt_tokens=5000,
        max_completion_tokens=1000,
        max_tool_rounds=2,
        max_elapsed_ms=10000,
        max_retry_per_intent=1,
        max_candidate_tools=2,
        max_tool_result_bytes=4096,
    )

    BudgetGuard.register_preparation(
        budget,
        prompt_tokens=1200,
        candidate_tools_count=3,
    )

    assert budget.prompt_tokens_used == 1200
    assert budget.candidate_tools_count == 3
    assert budget.first_exceeded_reason() == "candidate_tool_budget_exceeded"


def test_budget_guard_completion_budget_uses_output_tokens_not_total_tokens() -> None:
    budget = BudgetGuard.build_default("fast", intent_count=1)

    assert (
        BudgetGuard.completion_reason(
            budget,
            completion_tokens=48,
            total_tokens=1359,
        )
        is None
    )
    assert (
        BudgetGuard.completion_reason(
            budget,
            completion_tokens=budget.max_completion_tokens + 1,
            total_tokens=budget.max_completion_tokens + 200,
        )
        == "completion_budget_exceeded"
    )


@pytest.mark.asyncio
async def test_call_runtime_query_turn_forwards_skip_metering_preflight(
    monkeypatch,
) -> None:
    from app.ai.engine import conversation_runtime_bridge as bridge

    captured: dict[str, object] = {}

    async def fake_prepare_stream_runtime(
        engine,
        *,
        agent,
        messages,
        tenant_id,
        route_result=None,
        skip_metering_preflight=False,
    ):
        _ = engine, agent, messages, tenant_id, route_result
        captured["skip_metering_preflight"] = skip_metering_preflight
        provider = SimpleNamespace(code="mock-provider", type="mock")
        return SimpleNamespace(
            provider=provider,
            model_code="mock-model",
            runtime_info={"model_id": 1},
        )

    async def fake_build_runtime_query_entrypoint_plan(
        engine,
        *,
        runtime_preparer,
        skip_metering_preflight=True,
        **kwargs,
    ):
        runtime_context = await runtime_preparer(
            engine,
            agent=kwargs["agent"],
            messages=kwargs["messages"],
            tenant_id=kwargs["tenant_id"],
            route_result=kwargs["route_result"],
            skip_metering_preflight=skip_metering_preflight,
        )

        class _Accounting:
            async def finalize_success(
                self,
                *,
                runtime_context,
                request_context,
                audit_context,
                output_text,
                input_tokens,
                output_tokens,
                total_tokens,
                start_time,
                turn_record,
                success_log_message,
            ):
                _ = (
                    runtime_context,
                    request_context,
                    audit_context,
                    output_text,
                    input_tokens,
                    output_tokens,
                    total_tokens,
                    start_time,
                    turn_record,
                    success_log_message,
                )
                return SimpleNamespace(
                    input_tokens=0,
                    output_tokens=0,
                    total_tokens=0,
                    usage_mode="test",
                )

            async def log_failure(self, **kwargs):
                _ = kwargs
                return None

        return SimpleNamespace(
            runtime_context=runtime_context,
            query_engine=SimpleNamespace(turn_record={}),
            accounting=_Accounting(),
            request_context=SimpleNamespace(),
            audit_context=SimpleNamespace(),
        )

    async def fake_run_runtime_query_entrypoint(*, plan, agent, selected_skill_names):
        _ = plan, agent, selected_skill_names
        return ChatResponse(
            message=ChatMessage(role="assistant", content="ok"),
            total_tokens=0,
            input_tokens=0,
            output_tokens=0,
        )

    monkeypatch.setattr(bridge, "prepare_stream_runtime", fake_prepare_stream_runtime)
    monkeypatch.setattr(
        bridge,
        "build_runtime_query_entrypoint_plan",
        fake_build_runtime_query_entrypoint_plan,
    )
    monkeypatch.setattr(
        bridge,
        "run_runtime_query_entrypoint",
        fake_run_runtime_query_entrypoint,
    )

    engine = SimpleNamespace(
        db=SimpleNamespace(commit=AsyncMock()),
        gateway=SimpleNamespace(),
    )
    response, _query_engine = await bridge.call_runtime_query_turn(
        engine,
        agent=SimpleNamespace(id=1),
        messages=[ChatMessage(role="user", content="hi")],
        tools=None,
        all_tool_names=None,
        tool_use_policy=None,
        breach_retry_result=None,
        tenant_id=1,
        user_id=1,
        conversation_id=2,
        billing_context=None,
        route_result=None,
        log_user_type=None,
        selected_skill_names=None,
        context_sources=None,
        execution_path="normal",
        extra_kwargs=None,
        skip_metering_preflight=False,
    )

    assert captured["skip_metering_preflight"] is False
    assert response.metadata["runtime_model_info"]["model_id"] == 1


@pytest.mark.asyncio
async def test_call_runtime_query_turn_passes_model_request_override_builder(
    monkeypatch,
) -> None:
    from app.ai.engine import conversation_runtime_bridge as bridge

    captured: dict[str, object] = {}

    async def fake_prepare_stream_runtime(
        engine,
        *,
        agent,
        messages,
        tenant_id,
        route_result=None,
        skip_metering_preflight=False,
    ):
        _ = engine, agent, messages, tenant_id, route_result, skip_metering_preflight
        provider = SimpleNamespace(code="mock-provider", type="mock")
        return SimpleNamespace(
            provider=provider,
            model_code="mock-model",
            runtime_info={"model_id": 1},
        )

    def fake_model_request_override_builder(*, execution_path, tools):
        captured["execution_path"] = execution_path
        captured["tools"] = tools
        return {"_runtime_reasoning_effort_override": "low"}

    async def fake_build_runtime_query_entrypoint_plan(
        engine,
        *,
        runtime_preparer,
        model_request_override_builder,
        **kwargs,
    ):
        _ = await runtime_preparer(
            engine,
            agent=kwargs["agent"],
            messages=kwargs["messages"],
            tenant_id=kwargs["tenant_id"],
            route_result=kwargs["route_result"],
            skip_metering_preflight=kwargs["skip_metering_preflight"],
        )
        captured["builder_result"] = model_request_override_builder(
            execution_path=kwargs["execution_path"],
            tools=kwargs["tools"],
        )

        class _Accounting:
            async def finalize_success(self, **kwargs):
                _ = kwargs
                return SimpleNamespace(
                    input_tokens=0,
                    output_tokens=0,
                    total_tokens=0,
                    usage_mode="test",
                )

            async def log_failure(self, **kwargs):
                _ = kwargs
                return None

        return SimpleNamespace(
            runtime_context=SimpleNamespace(
                provider=SimpleNamespace(code="mock-provider"),
                model_code="mock-model",
                runtime_info={"model_id": 1},
            ),
            query_engine=SimpleNamespace(turn_record={}),
            accounting=_Accounting(),
            request_context=SimpleNamespace(),
            audit_context=SimpleNamespace(),
        )

    async def fake_run_runtime_query_entrypoint(*, plan, agent, selected_skill_names):
        _ = plan, agent, selected_skill_names
        return ChatResponse(
            message=ChatMessage(role="assistant", content="ok"),
            total_tokens=0,
            input_tokens=0,
            output_tokens=0,
        )

    monkeypatch.setattr(bridge, "prepare_stream_runtime", fake_prepare_stream_runtime)
    monkeypatch.setattr(
        bridge,
        "build_runtime_query_entrypoint_plan",
        fake_build_runtime_query_entrypoint_plan,
    )
    monkeypatch.setattr(
        bridge,
        "run_runtime_query_entrypoint",
        fake_run_runtime_query_entrypoint,
    )

    engine = SimpleNamespace(
        db=SimpleNamespace(commit=AsyncMock()),
        gateway=SimpleNamespace(),
    )
    response, _query_engine = await bridge.call_runtime_query_turn(
        engine,
        agent=SimpleNamespace(id=1),
        messages=[ChatMessage(role="user", content="hi")],
        tools=None,
        all_tool_names=None,
        tool_use_policy=None,
        breach_retry_result=None,
        tenant_id=1,
        user_id=1,
        conversation_id=2,
        billing_context=None,
        route_result=None,
        log_user_type=None,
        selected_skill_names=None,
        context_sources=None,
        execution_path="fast",
        extra_kwargs=None,
        skip_metering_preflight=False,
        model_request_override_builder=fake_model_request_override_builder,
    )

    assert captured["execution_path"] == "fast"
    assert captured["tools"] is None
    assert captured["builder_result"] == {"_runtime_reasoning_effort_override": "low"}
    assert response.metadata["runtime_model_info"]["model_id"] == 1


@pytest.mark.asyncio
async def test_stream_llm_chunks_forwards_skip_metering_preflight(
    monkeypatch,
) -> None:
    from app.ai.engine import conversation_runtime_bridge as bridge

    captured: dict[str, object] = {}

    async def fake_prepare_stream_runtime(
        engine,
        *,
        agent,
        messages,
        tenant_id,
        route_result=None,
        skip_metering_preflight=False,
    ):
        _ = engine, agent, messages, tenant_id, route_result
        captured["skip_metering_preflight"] = skip_metering_preflight
        provider = SimpleNamespace(code="mock-provider", type="mock")
        return SimpleNamespace(
            provider=provider,
            model_code="mock-model",
            ai_model=SimpleNamespace(supports_streaming=True),
            runtime_info={"model_id": 2},
        )

    async def fake_build_runtime_stream_entrypoint_plan(
        engine,
        *,
        runtime_preparer,
        skip_metering_preflight=False,
        **kwargs,
    ):
        runtime_context = await runtime_preparer(
            engine,
            agent=kwargs["agent"],
            messages=kwargs["messages"],
            tenant_id=kwargs["tenant_id"],
            route_result=kwargs["route_result"],
            skip_metering_preflight=skip_metering_preflight,
        )

        class _Accounting:
            async def finalize_success(self, **kwargs):
                _ = kwargs
                return None

            async def log_failure(self, **kwargs):
                _ = kwargs
                return None

        return SimpleNamespace(
            runtime_context=runtime_context,
            query_engine=SimpleNamespace(turn_record={}),
            accounting=_Accounting(),
            request_context=SimpleNamespace(),
            audit_context=SimpleNamespace(),
        )

    async def fake_iterate_runtime_stream_entrypoint(
        *,
        plan,
        agent,
        selected_skill_names,
    ):
        _ = plan, agent, selected_skill_names
        yield ChatChunk(delta="ok", finish_reason="stop", total_tokens=1)

    monkeypatch.setattr(bridge, "prepare_stream_runtime", fake_prepare_stream_runtime)
    monkeypatch.setattr(
        bridge,
        "build_runtime_stream_entrypoint_plan",
        fake_build_runtime_stream_entrypoint_plan,
    )
    monkeypatch.setattr(
        bridge,
        "iterate_runtime_stream_entrypoint",
        fake_iterate_runtime_stream_entrypoint,
    )

    engine = SimpleNamespace(
        logger=None,
        gateway=SimpleNamespace(),
        db=SimpleNamespace(),
    )
    chunks = []
    async for chunk in bridge.stream_llm_chunks(
        engine,
        agent=SimpleNamespace(id=1),
        messages=[ChatMessage(role="user", content="hi")],
        tenant_id=1,
        conversation_id=2,
        tools=None,
        skip_metering_preflight=True,
    ):
        chunks.append(chunk)

    assert captured["skip_metering_preflight"] is True
    assert len(chunks) == 1
    assert chunks[0].delta == "ok"


@pytest.mark.asyncio
async def test_stream_llm_chunks_forwards_extra_kwargs(
    monkeypatch,
) -> None:
    from app.ai.engine import conversation_runtime_bridge as bridge

    captured: dict[str, object] = {}

    async def fake_prepare_stream_runtime(
        engine,
        *,
        agent,
        messages,
        tenant_id,
        route_result=None,
        skip_metering_preflight=False,
    ):
        _ = engine, agent, messages, tenant_id, route_result, skip_metering_preflight
        provider = SimpleNamespace(code="mock-provider", type="mock")
        return SimpleNamespace(
            provider=provider,
            model_code="mock-model",
            ai_model=SimpleNamespace(supports_streaming=True),
            runtime_info={"model_id": 3},
        )

    async def fake_build_runtime_stream_entrypoint_plan(
        engine,
        *,
        runtime_preparer,
        extra_kwargs=None,
        **kwargs,
    ):
        runtime_context = await runtime_preparer(
            engine,
            agent=kwargs["agent"],
            messages=kwargs["messages"],
            tenant_id=kwargs["tenant_id"],
            route_result=kwargs["route_result"],
            skip_metering_preflight=kwargs["skip_metering_preflight"],
        )
        captured["extra_kwargs"] = extra_kwargs

        class _Accounting:
            async def finalize_success(self, **kwargs):
                _ = kwargs
                return None

            async def log_failure(self, **kwargs):
                _ = kwargs
                return None

        return SimpleNamespace(
            runtime_context=runtime_context,
            query_engine=SimpleNamespace(turn_record={}),
            accounting=_Accounting(),
            request_context=SimpleNamespace(),
            audit_context=SimpleNamespace(),
            request_extra_kwargs=extra_kwargs or {},
        )

    async def fake_iterate_runtime_stream_entrypoint(
        *,
        plan,
        agent,
        selected_skill_names,
    ):
        _ = plan, agent, selected_skill_names
        captured["plan_extra_kwargs"] = plan.request_extra_kwargs
        yield ChatChunk(delta="ok", finish_reason="stop", total_tokens=1)

    monkeypatch.setattr(bridge, "prepare_stream_runtime", fake_prepare_stream_runtime)
    monkeypatch.setattr(
        bridge,
        "build_runtime_stream_entrypoint_plan",
        fake_build_runtime_stream_entrypoint_plan,
    )
    monkeypatch.setattr(
        bridge,
        "iterate_runtime_stream_entrypoint",
        fake_iterate_runtime_stream_entrypoint,
    )

    engine = SimpleNamespace(
        logger=None,
        gateway=SimpleNamespace(),
        db=SimpleNamespace(),
    )
    extra_kwargs = {
        "_runtime_reasoning_effort_override": "low",
        "trace_id": "trace-1",
    }
    chunks = []
    async for chunk in bridge.stream_llm_chunks(
        engine,
        agent=SimpleNamespace(id=1),
        messages=[ChatMessage(role="user", content="hi")],
        tenant_id=1,
        conversation_id=2,
        tools=None,
        extra_kwargs=extra_kwargs,
    ):
        chunks.append(chunk)

    assert captured["extra_kwargs"] == extra_kwargs
    assert captured["plan_extra_kwargs"] == extra_kwargs
    assert len(chunks) == 1
    assert chunks[0].delta == "ok"


@pytest.mark.asyncio
async def test_call_runtime_query_turn_retries_with_runtime_failover_before_raising(
    monkeypatch,
) -> None:
    from app.ai.engine import conversation_runtime_bridge as bridge

    attempts: list[str] = []

    async def fake_prepare_stream_runtime(
        engine,
        *,
        agent,
        messages,
        tenant_id,
        route_result=None,
        skip_metering_preflight=False,
    ):
        _ = engine, agent, messages, tenant_id, skip_metering_preflight
        provider_code = (
            getattr(route_result, "provider_code", None) or "primary-provider"
        )
        model_code = getattr(route_result, "model_code", None) or "primary-model"
        model_id = getattr(route_result, "model_id", None) or 1
        return SimpleNamespace(
            provider=SimpleNamespace(code=provider_code, id=model_id),
            ai_model=SimpleNamespace(id=model_id),
            model_code=model_code,
            runtime_info={"model_id": model_id, "provider_name": provider_code},
            is_vision=False,
            is_audio=False,
            is_video=False,
            estimated_input=256,
        )

    async def fake_build_runtime_query_entrypoint_plan(
        engine,
        *,
        runtime_context=None,
        runtime_preparer,
        **kwargs,
    ):
        active_runtime_context = runtime_context or await runtime_preparer(
            engine,
            agent=kwargs["agent"],
            messages=kwargs["messages"],
            tenant_id=kwargs["tenant_id"],
            route_result=kwargs["route_result"],
            skip_metering_preflight=kwargs["skip_metering_preflight"],
        )

        class _Accounting:
            async def finalize_success(self, **kwargs):
                _ = kwargs
                return SimpleNamespace(
                    input_tokens=0,
                    output_tokens=0,
                    total_tokens=0,
                    usage_mode="test",
                )

            async def log_failure(self, **kwargs):
                _ = kwargs
                return None

        return SimpleNamespace(
            runtime_context=active_runtime_context,
            query_engine=SimpleNamespace(turn_record={"metadata": {}}),
            accounting=_Accounting(),
            request_context=SimpleNamespace(),
            audit_context=SimpleNamespace(),
            request_log_data={},
        )

    async def fake_run_runtime_query_entrypoint(*, plan, agent, selected_skill_names):
        _ = agent, selected_skill_names
        attempts.append(plan.runtime_context.model_code)
        if plan.runtime_context.model_code == "primary-model":
            raise AIGatewayError("bad gateway", status_code=502)
        return ChatResponse(
            message=ChatMessage(role="assistant", content="fallback ok"),
            total_tokens=0,
            input_tokens=0,
            output_tokens=0,
        )

    async def fake_resolve_runtime_model_failover(
        engine,
        *,
        runtime_context,
        tools,
        error,
        logger,
    ):
        _ = engine, tools, logger
        assert runtime_context.model_code == "primary-model"
        assert isinstance(error, AIGatewayError)
        return bridge.RuntimeModelFailoverSelection(
            route_result=RouteResult(
                provider_code="fallback-provider",
                model_code="fallback-model",
                model_id=2,
                tier="standard",
                reason="runtime_provider_failover",
                is_overridden=True,
            ),
            metadata={
                "from_model_code": "primary-model",
                "to_model_code": "fallback-model",
            },
        )

    monkeypatch.setattr(bridge, "prepare_stream_runtime", fake_prepare_stream_runtime)
    monkeypatch.setattr(
        bridge,
        "build_runtime_query_entrypoint_plan",
        fake_build_runtime_query_entrypoint_plan,
    )
    monkeypatch.setattr(
        bridge,
        "run_runtime_query_entrypoint",
        fake_run_runtime_query_entrypoint,
    )
    monkeypatch.setattr(
        bridge,
        "_resolve_runtime_model_failover",
        fake_resolve_runtime_model_failover,
    )

    engine = SimpleNamespace(
        db=SimpleNamespace(commit=AsyncMock()),
        gateway=SimpleNamespace(),
        logger=None,
    )
    response, _query_engine = await bridge.call_runtime_query_turn(
        engine,
        agent=SimpleNamespace(id=1),
        messages=[ChatMessage(role="user", content="hi")],
        tools=None,
        all_tool_names=None,
        tool_use_policy=None,
        breach_retry_result=None,
        tenant_id=1,
        user_id=1,
        conversation_id=2,
        billing_context=None,
        route_result=None,
        log_user_type=None,
        selected_skill_names=None,
        context_sources=None,
        execution_path="normal",
        extra_kwargs=None,
        skip_metering_preflight=False,
    )

    assert attempts == ["primary-model", "fallback-model"]
    assert response.message.content == "fallback ok"
    assert response.metadata["runtime_model_info"]["model_id"] == 2
    assert response.metadata["runtime_model_failover"] == {
        "from_model_code": "primary-model",
        "to_model_code": "fallback-model",
    }


@pytest.mark.asyncio
async def test_stream_llm_chunks_retries_with_runtime_failover_before_first_chunk(
    monkeypatch,
) -> None:
    from app.ai.engine import conversation_runtime_bridge as bridge

    attempts: list[str] = []

    async def fake_prepare_stream_runtime(
        engine,
        *,
        agent,
        messages,
        tenant_id,
        route_result=None,
        skip_metering_preflight=False,
    ):
        _ = engine, agent, messages, tenant_id, skip_metering_preflight
        provider_code = (
            getattr(route_result, "provider_code", None) or "primary-provider"
        )
        model_code = getattr(route_result, "model_code", None) or "primary-model"
        model_id = getattr(route_result, "model_id", None) or 1
        return SimpleNamespace(
            provider=SimpleNamespace(code=provider_code, id=model_id),
            ai_model=SimpleNamespace(id=model_id, supports_streaming=True),
            model_code=model_code,
            runtime_info={"model_id": model_id, "provider_name": provider_code},
            is_vision=False,
            is_audio=False,
            is_video=False,
            estimated_input=256,
        )

    async def fake_build_runtime_stream_entrypoint_plan(
        engine,
        *,
        runtime_context=None,
        runtime_preparer,
        **kwargs,
    ):
        active_runtime_context = runtime_context or await runtime_preparer(
            engine,
            agent=kwargs["agent"],
            messages=kwargs["messages"],
            tenant_id=kwargs["tenant_id"],
            route_result=kwargs["route_result"],
            skip_metering_preflight=kwargs["skip_metering_preflight"],
        )

        class _Accounting:
            async def finalize_success(self, **kwargs):
                _ = kwargs
                return None

            async def log_failure(self, **kwargs):
                _ = kwargs
                return None

        return SimpleNamespace(
            runtime_context=active_runtime_context,
            query_engine=SimpleNamespace(turn_record={"metadata": {}}),
            accounting=_Accounting(),
            request_context=SimpleNamespace(),
            audit_context=SimpleNamespace(),
            request_log_data={},
        )

    async def fake_iterate_runtime_stream_entrypoint(
        *,
        plan,
        agent,
        selected_skill_names,
    ):
        _ = agent, selected_skill_names
        attempts.append(plan.runtime_context.model_code)
        if plan.runtime_context.model_code == "primary-model":
            raise AIGatewayError("bad gateway", status_code=502)
        yield ChatChunk(delta="fallback stream", finish_reason="stop", total_tokens=1)

    async def fake_resolve_runtime_model_failover(
        engine,
        *,
        runtime_context,
        tools,
        error,
        logger,
    ):
        _ = engine, tools, logger
        assert runtime_context.model_code == "primary-model"
        assert isinstance(error, AIGatewayError)
        return bridge.RuntimeModelFailoverSelection(
            route_result=RouteResult(
                provider_code="fallback-provider",
                model_code="fallback-model",
                model_id=2,
                tier="standard",
                reason="runtime_provider_failover",
                is_overridden=True,
            ),
            metadata={
                "from_model_code": "primary-model",
                "to_model_code": "fallback-model",
            },
        )

    monkeypatch.setattr(bridge, "prepare_stream_runtime", fake_prepare_stream_runtime)
    monkeypatch.setattr(
        bridge,
        "build_runtime_stream_entrypoint_plan",
        fake_build_runtime_stream_entrypoint_plan,
    )
    monkeypatch.setattr(
        bridge,
        "iterate_runtime_stream_entrypoint",
        fake_iterate_runtime_stream_entrypoint,
    )
    monkeypatch.setattr(
        bridge,
        "_resolve_runtime_model_failover",
        fake_resolve_runtime_model_failover,
    )

    engine = SimpleNamespace(
        logger=None,
        gateway=SimpleNamespace(),
        db=SimpleNamespace(),
    )
    chunks = []
    async for chunk in bridge.stream_llm_chunks(
        engine,
        agent=SimpleNamespace(id=1),
        messages=[ChatMessage(role="user", content="hi")],
        tenant_id=1,
        conversation_id=2,
        tools=None,
    ):
        chunks.append(chunk)

    assert attempts == ["primary-model", "fallback-model"]
    assert [chunk.reasoning_delta for chunk in chunks if chunk.reasoning_delta] == []
    assert len(chunks) == 1
    assert [chunk.delta for chunk in chunks if chunk.delta] == ["fallback stream"]
    assert chunks[0].metadata["runtime_model_failover"] == {
        "from_model_code": "primary-model",
        "to_model_code": "fallback-model",
    }


@pytest.mark.asyncio
async def test_runtime_failover_uses_request_modalities_not_source_model_caps(
    monkeypatch,
) -> None:
    from app.ai.engine import conversation_runtime_bridge as bridge

    captured_requirements: dict[str, object] = {}

    class _Failover:
        def __init__(self, db):
            self.db = db

        @staticmethod
        def should_record_runtime_failure(error):
            return isinstance(error, AIGatewayError)

        async def record_provider_runtime_failure(self, provider_id, **kwargs):
            captured_requirements["recorded_provider_id"] = provider_id
            captured_requirements["recorded_model_id"] = kwargs.get("model_id")

        async def get_fallback_model(self, model_id, **kwargs):
            captured_requirements.update(kwargs)
            captured_requirements["model_id"] = model_id
            return SimpleNamespace(
                id=2,
                code="fallback-model",
                provider_id=20,
                provider=SimpleNamespace(code="fallback-provider"),
                tier="standard",
            )

    monkeypatch.setattr(bridge, "FailoverService", _Failover)

    selection = await bridge._resolve_runtime_model_failover(
        SimpleNamespace(db=SimpleNamespace()),
        runtime_context=SimpleNamespace(
            provider=SimpleNamespace(id=10, code="primary-provider"),
            ai_model=SimpleNamespace(id=9),
            model_code="gpt-5.5",
            is_vision=True,
            is_audio=True,
            is_video=True,
            request_needs_vision=False,
            request_needs_audio=False,
            request_needs_video=False,
            estimated_input=381,
        ),
        tools=None,
        error=AIGatewayError("bad gateway", status_code=502),
        logger=None,
    )

    assert selection is not None
    assert selection.route_result.model_code == "fallback-model"
    assert captured_requirements["recorded_provider_id"] == 10
    assert captured_requirements["recorded_model_id"] == 9
    assert captured_requirements["model_id"] == 9
    assert captured_requirements["needs_vision"] is False
    assert captured_requirements["needs_audio"] is False
    assert captured_requirements["needs_video"] is False
    assert captured_requirements["needs_fc"] is False
    assert captured_requirements["min_context_window"] == 381


@pytest.mark.asyncio
async def test_stream_llm_chunks_allows_runtime_failover_after_reasoning_only_chunk(
    monkeypatch,
) -> None:
    from app.ai.engine import conversation_runtime_bridge as bridge

    attempts: list[str] = []

    async def fake_prepare_stream_runtime(
        engine,
        *,
        agent,
        messages,
        tenant_id,
        route_result=None,
        skip_metering_preflight=False,
    ):
        _ = engine, agent, messages, tenant_id, skip_metering_preflight
        provider_code = (
            getattr(route_result, "provider_code", None) or "primary-provider"
        )
        model_code = getattr(route_result, "model_code", None) or "primary-model"
        model_id = getattr(route_result, "model_id", None) or 1
        return SimpleNamespace(
            provider=SimpleNamespace(code=provider_code, id=model_id),
            ai_model=SimpleNamespace(id=model_id, supports_streaming=True),
            model_code=model_code,
            runtime_info={"model_id": model_id, "provider_name": provider_code},
            is_vision=False,
            is_audio=False,
            is_video=False,
            estimated_input=256,
        )

    async def fake_build_runtime_stream_entrypoint_plan(
        engine,
        *,
        runtime_context=None,
        runtime_preparer,
        **kwargs,
    ):
        active_runtime_context = runtime_context or await runtime_preparer(
            engine,
            agent=kwargs["agent"],
            messages=kwargs["messages"],
            tenant_id=kwargs["tenant_id"],
            route_result=kwargs["route_result"],
            skip_metering_preflight=kwargs["skip_metering_preflight"],
        )

        class _Accounting:
            async def finalize_success(self, **kwargs):
                _ = kwargs
                return None

            async def log_failure(self, **kwargs):
                _ = kwargs
                return None

        return SimpleNamespace(
            runtime_context=active_runtime_context,
            query_engine=SimpleNamespace(turn_record={"metadata": {}}),
            accounting=_Accounting(),
            request_context=SimpleNamespace(),
            audit_context=SimpleNamespace(),
            request_log_data={},
        )

    async def fake_iterate_runtime_stream_entrypoint(
        *,
        plan,
        agent,
        selected_skill_names,
    ):
        _ = agent, selected_skill_names
        attempts.append(plan.runtime_context.model_code)
        if plan.runtime_context.model_code == "primary-model":
            yield ChatChunk(delta="", reasoning_delta="先整理中间推理")
            raise AIGatewayError("bad gateway", status_code=502)
        yield ChatChunk(delta="fallback stream", finish_reason="stop", total_tokens=1)

    async def fake_resolve_runtime_model_failover(
        engine,
        *,
        runtime_context,
        tools,
        error,
        logger,
    ):
        _ = engine, tools, logger
        assert runtime_context.model_code == "primary-model"
        assert isinstance(error, AIGatewayError)
        return bridge.RuntimeModelFailoverSelection(
            route_result=RouteResult(
                provider_code="fallback-provider",
                model_code="fallback-model",
                model_id=2,
                tier="standard",
                reason="runtime_provider_failover",
                is_overridden=True,
            ),
            metadata={
                "from_model_code": "primary-model",
                "to_model_code": "fallback-model",
            },
        )

    monkeypatch.setattr(bridge, "prepare_stream_runtime", fake_prepare_stream_runtime)
    monkeypatch.setattr(
        bridge,
        "build_runtime_stream_entrypoint_plan",
        fake_build_runtime_stream_entrypoint_plan,
    )
    monkeypatch.setattr(
        bridge,
        "iterate_runtime_stream_entrypoint",
        fake_iterate_runtime_stream_entrypoint,
    )
    monkeypatch.setattr(
        bridge,
        "_resolve_runtime_model_failover",
        fake_resolve_runtime_model_failover,
    )

    engine = SimpleNamespace(
        logger=None,
        gateway=SimpleNamespace(),
        db=SimpleNamespace(),
    )
    chunks = []
    async for chunk in bridge.stream_llm_chunks(
        engine,
        agent=SimpleNamespace(id=1),
        messages=[ChatMessage(role="user", content="hi")],
        tenant_id=1,
        conversation_id=3,
        tools=None,
    ):
        chunks.append(chunk)

    assert attempts == ["primary-model", "fallback-model"]
    assert [chunk.reasoning_delta for chunk in chunks if chunk.reasoning_delta] == [
        "先整理中间推理"
    ]
    assert len(chunks) == 2
    assert [chunk.delta for chunk in chunks if chunk.delta] == ["fallback stream"]


@pytest.mark.asyncio
async def test_stream_llm_chunks_blocks_runtime_failover_after_visible_output_chunk(
    monkeypatch,
) -> None:
    from app.ai.engine import conversation_runtime_bridge as bridge

    attempts: list[str] = []
    failover_requests: list[str] = []

    async def fake_prepare_stream_runtime(
        engine,
        *,
        agent,
        messages,
        tenant_id,
        route_result=None,
        skip_metering_preflight=False,
    ):
        _ = engine, agent, messages, tenant_id, skip_metering_preflight
        provider_code = (
            getattr(route_result, "provider_code", None) or "primary-provider"
        )
        model_code = getattr(route_result, "model_code", None) or "primary-model"
        model_id = getattr(route_result, "model_id", None) or 1
        return SimpleNamespace(
            provider=SimpleNamespace(code=provider_code, id=model_id),
            ai_model=SimpleNamespace(id=model_id, supports_streaming=True),
            model_code=model_code,
            runtime_info={"model_id": model_id, "provider_name": provider_code},
            is_vision=False,
            is_audio=False,
            is_video=False,
            estimated_input=256,
        )

    async def fake_build_runtime_stream_entrypoint_plan(
        engine,
        *,
        runtime_context=None,
        runtime_preparer,
        **kwargs,
    ):
        active_runtime_context = runtime_context or await runtime_preparer(
            engine,
            agent=kwargs["agent"],
            messages=kwargs["messages"],
            tenant_id=kwargs["tenant_id"],
            route_result=kwargs["route_result"],
            skip_metering_preflight=kwargs["skip_metering_preflight"],
        )

        class _Accounting:
            async def finalize_success(self, **kwargs):
                _ = kwargs
                return None

            async def log_failure(self, **kwargs):
                _ = kwargs
                return None

        return SimpleNamespace(
            runtime_context=active_runtime_context,
            query_engine=SimpleNamespace(turn_record={"metadata": {}}),
            accounting=_Accounting(),
            request_context=SimpleNamespace(),
            audit_context=SimpleNamespace(),
            request_log_data={},
        )

    async def fake_iterate_runtime_stream_entrypoint(
        *,
        plan,
        agent,
        selected_skill_names,
    ):
        _ = agent, selected_skill_names
        attempts.append(plan.runtime_context.model_code)
        if plan.runtime_context.model_code == "primary-model":
            yield ChatChunk(delta="partial answer", finish_reason=None, total_tokens=1)
            raise AIGatewayError("bad gateway", status_code=502)
        yield ChatChunk(delta="fallback stream", finish_reason="stop", total_tokens=2)

    async def fake_resolve_runtime_model_failover(
        engine,
        *,
        runtime_context,
        tools,
        error,
        logger,
    ):
        _ = engine, tools, error, logger
        failover_requests.append(runtime_context.model_code)
        return bridge.RuntimeModelFailoverSelection(
            route_result=RouteResult(
                provider_code="fallback-provider",
                model_code="fallback-model",
                model_id=2,
                tier="standard",
                reason="runtime_provider_failover",
                is_overridden=True,
            ),
            metadata={
                "from_model_code": "primary-model",
                "to_model_code": "fallback-model",
            },
        )

    monkeypatch.setattr(bridge, "prepare_stream_runtime", fake_prepare_stream_runtime)
    monkeypatch.setattr(
        bridge,
        "build_runtime_stream_entrypoint_plan",
        fake_build_runtime_stream_entrypoint_plan,
    )
    monkeypatch.setattr(
        bridge,
        "iterate_runtime_stream_entrypoint",
        fake_iterate_runtime_stream_entrypoint,
    )
    monkeypatch.setattr(
        bridge,
        "_resolve_runtime_model_failover",
        fake_resolve_runtime_model_failover,
    )

    engine = SimpleNamespace(
        logger=None,
        gateway=SimpleNamespace(),
        db=SimpleNamespace(),
    )
    chunks: list[ChatChunk] = []
    with pytest.raises(AIGatewayError):
        async for chunk in bridge.stream_llm_chunks(
            engine,
            agent=SimpleNamespace(id=1),
            messages=[ChatMessage(role="user", content="hi")],
            tenant_id=1,
            conversation_id=4,
            tools=None,
        ):
            chunks.append(chunk)

    assert attempts == ["primary-model"]
    assert failover_requests == []
    assert [chunk.delta for chunk in chunks if chunk.delta] == ["partial answer"]
