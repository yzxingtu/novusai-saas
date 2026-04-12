from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.ai.engine.conversation_runtime_context_builder import (
    build_runtime_query_entrypoint_plan,
    build_runtime_stream_entrypoint_plan,
)
from app.ai.engine.conversation_runtime_entrypoint_runner import (
    iterate_runtime_stream_entrypoint,
)
from app.ai.engine.conversation_runtime_preflight import ConversationRuntimeContext
from app.ai.engine.model_policy import build_model_request_overrides
from app.ai.tools.types import ToolDefinition
from app.ai.types import ChatChunk, ChatMessage


class _AdapterRegistryStub:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def create_adapter(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(name="adapter")


class _QueryEngineCaptureStub:
    created: list[dict] = []

    def __init__(self, *, adapter, strict_contract: bool = False) -> None:
        type(self).created.append(
            {"adapter": adapter, "strict_contract": strict_contract}
        )
        self.turn_record = SimpleNamespace(metadata={})


class _StreamIterStub:
    def __init__(self) -> None:
        self.iter_calls: list[dict] = []
        self.run_calls: list[dict] = []

    async def iter_stream_turn(self, **kwargs):
        self.iter_calls.append(kwargs)
        yield ChatChunk(delta="iter-path")

    async def run_stream_turn(self, **kwargs):
        self.run_calls.append(kwargs)
        return [ChatChunk(delta="legacy-run-path")]


class _StreamRunOnlyStub:
    def __init__(self) -> None:
        self.run_calls: list[dict] = []
        self.turn_record = SimpleNamespace(metadata={})

    async def run_stream_turn(self, **kwargs):
        self.run_calls.append(kwargs)
        return [ChatChunk(delta="legacy-run-path")]


def _build_runtime_context() -> ConversationRuntimeContext:
    provider = SimpleNamespace(
        id=101,
        type="openai_compatible",
        code="provider_1",
        base_url="https://api.example.com/v1",
        config={},
    )
    api_key = SimpleNamespace(decrypt_key=MagicMock(return_value="sk-test"))
    ai_model = SimpleNamespace(
        config={"default": True},
        supports_streaming=True,
    )
    return ConversationRuntimeContext(
        provider=provider,
        api_key=api_key,
        ai_model=ai_model,
        model_code="gpt-5.4",
        is_vision=False,
        is_audio=False,
        is_video=False,
        estimated_input=12,
        metering_context=None,
        should_meter_usage=False,
        should_record_call_log=False,
        runtime_info={"provider_name": "Provider One", "model_code": "gpt-5.4"},
    )


def _build_agent() -> SimpleNamespace:
    return SimpleNamespace(
        id=9,
        temperature=0.2,
        max_tokens=256,
        top_p=0.9,
    )


@pytest.mark.asyncio
async def test_build_runtime_query_entrypoint_plan_builds_context_once() -> None:
    adapter_registry = _AdapterRegistryStub()
    runtime_context = _build_runtime_context()

    async def _runtime_preparer(*args, **kwargs):
        _ = args, kwargs
        return runtime_context

    _QueryEngineCaptureStub.created.clear()

    plan = await build_runtime_query_entrypoint_plan(
        SimpleNamespace(db=MagicMock(), gateway=MagicMock()),
        agent=_build_agent(),
        messages=[ChatMessage(role="user", content="hello")],
        tools=[ToolDefinition(name="web_search", description="Search the web")],
        all_tool_names=None,
        tool_use_policy=None,
        breach_retry_result=None,
        tenant_id=7,
        user_id=5,
        conversation_id=42,
        billing_context=None,
        route_result=None,
        log_user_type="tenant_admin",
        context_sources=[],
        execution_path="normal",
        extra_kwargs={"tenant_id": 7},
        runtime_preparer=_runtime_preparer,
        adapter_registry=adapter_registry,
        query_engine_cls=_QueryEngineCaptureStub,
    )

    assert plan.effective_policy.mode == "auto"
    assert plan.effective_policy.allowed_tool_names == ["web_search"]
    assert plan.effective_tool_choice == "auto"
    assert plan.request_extra_kwargs == {"tenant_id": 7}
    assert plan.request_context.request_log_data["_runtime_v2_non_stream"] is True
    assert adapter_registry.calls
    assert _QueryEngineCaptureStub.created[-1]["strict_contract"] is False


@pytest.mark.asyncio
async def test_entrypoint_plans_share_default_skip_metering_preflight() -> None:
    adapter_registry = _AdapterRegistryStub()
    runtime_context = _build_runtime_context()
    captured: list[bool] = []

    async def _runtime_preparer(*args, **kwargs):
        _ = args
        captured.append(kwargs["skip_metering_preflight"])
        return runtime_context

    engine = SimpleNamespace(db=MagicMock(), gateway=MagicMock())

    await build_runtime_query_entrypoint_plan(
        engine,
        agent=_build_agent(),
        messages=[ChatMessage(role="user", content="hello")],
        tools=None,
        all_tool_names=None,
        tool_use_policy=None,
        breach_retry_result=None,
        tenant_id=7,
        user_id=None,
        conversation_id=None,
        billing_context=None,
        route_result=None,
        log_user_type=None,
        context_sources=None,
        execution_path=None,
        extra_kwargs=None,
        runtime_preparer=_runtime_preparer,
        adapter_registry=adapter_registry,
        query_engine_cls=_QueryEngineCaptureStub,
    )

    await build_runtime_stream_entrypoint_plan(
        engine,
        agent=_build_agent(),
        messages=[ChatMessage(role="user", content="hello")],
        tenant_id=7,
        conversation_id=None,
        route_result=None,
        tools=None,
        execution_path=None,
        user_id=None,
        log_user_type=None,
        billing_context=None,
        runtime_context=None,
        all_tool_names=None,
        context_sources=None,
        tool_use_policy=None,
        breach_retry_result=None,
        runtime_preparer=_runtime_preparer,
        adapter_registry=adapter_registry,
        query_engine_cls=_QueryEngineCaptureStub,
    )

    assert len(captured) == 2
    assert captured[0] == captured[1]


@pytest.mark.asyncio
async def test_entrypoint_plans_share_execution_path_overrides() -> None:
    adapter_registry = _AdapterRegistryStub()
    runtime_context = _build_runtime_context()

    async def _runtime_preparer(*args, **kwargs):
        _ = args, kwargs
        return runtime_context

    engine = SimpleNamespace(db=MagicMock(), gateway=MagicMock())
    expected = build_model_request_overrides(execution_path="fast", tools=None)

    assert expected

    query_plan = await build_runtime_query_entrypoint_plan(
        engine,
        agent=_build_agent(),
        messages=[ChatMessage(role="user", content="hello")],
        tools=None,
        all_tool_names=None,
        tool_use_policy=None,
        breach_retry_result=None,
        tenant_id=7,
        user_id=None,
        conversation_id=None,
        billing_context=None,
        route_result=None,
        log_user_type=None,
        context_sources=None,
        execution_path="fast",
        extra_kwargs=None,
        runtime_preparer=_runtime_preparer,
        adapter_registry=adapter_registry,
        query_engine_cls=_QueryEngineCaptureStub,
    )

    stream_plan = await build_runtime_stream_entrypoint_plan(
        engine,
        agent=_build_agent(),
        messages=[ChatMessage(role="user", content="hello")],
        tenant_id=7,
        conversation_id=None,
        route_result=None,
        tools=None,
        execution_path="fast",
        user_id=None,
        log_user_type=None,
        billing_context=None,
        runtime_context=None,
        all_tool_names=None,
        context_sources=None,
        tool_use_policy=None,
        breach_retry_result=None,
        runtime_preparer=_runtime_preparer,
        adapter_registry=adapter_registry,
        query_engine_cls=_QueryEngineCaptureStub,
    )

    assert query_plan.request_extra_kwargs == expected
    assert stream_plan.request_extra_kwargs == expected


@pytest.mark.asyncio
async def test_entrypoint_plans_share_extra_kwargs_merge_priority() -> None:
    adapter_registry = _AdapterRegistryStub()
    runtime_context = _build_runtime_context()

    async def _runtime_preparer(*args, **kwargs):
        _ = args, kwargs
        return runtime_context

    def _override_builder(*, execution_path, tools):
        assert execution_path == "fast"
        assert tools is None
        return {
            "_runtime_reasoning_effort_override": "low",
            "builder_only": "builder",
        }

    engine = SimpleNamespace(db=MagicMock(), gateway=MagicMock())
    extra_kwargs = {
        "_runtime_reasoning_effort_override": "high",
        "extra_only": "explicit",
    }
    expected = {
        "_runtime_reasoning_effort_override": "high",
        "builder_only": "builder",
        "extra_only": "explicit",
    }

    query_plan = await build_runtime_query_entrypoint_plan(
        engine,
        agent=_build_agent(),
        messages=[ChatMessage(role="user", content="hello")],
        tools=None,
        all_tool_names=None,
        tool_use_policy=None,
        breach_retry_result=None,
        tenant_id=7,
        user_id=5,
        conversation_id=42,
        billing_context=None,
        route_result=None,
        log_user_type="tenant_admin",
        context_sources=[],
        execution_path="fast",
        extra_kwargs=extra_kwargs,
        runtime_preparer=_runtime_preparer,
        adapter_registry=adapter_registry,
        query_engine_cls=_QueryEngineCaptureStub,
        model_request_override_builder=_override_builder,
    )

    stream_plan = await build_runtime_stream_entrypoint_plan(
        engine,
        agent=_build_agent(),
        messages=[ChatMessage(role="user", content="hello")],
        tenant_id=7,
        conversation_id=42,
        route_result=None,
        tools=None,
        execution_path="fast",
        user_id=5,
        log_user_type="tenant_admin",
        billing_context=None,
        runtime_context=None,
        all_tool_names=None,
        context_sources=[],
        tool_use_policy=None,
        breach_retry_result=None,
        extra_kwargs=extra_kwargs,
        runtime_preparer=_runtime_preparer,
        adapter_registry=adapter_registry,
        query_engine_cls=_QueryEngineCaptureStub,
        model_request_override_builder=_override_builder,
        engine_logger=None,
    )

    assert query_plan.request_extra_kwargs == expected
    assert stream_plan.request_extra_kwargs == expected


@pytest.mark.asyncio
async def test_entrypoint_plans_share_override_builder_parity() -> None:
    adapter_registry = _AdapterRegistryStub()
    runtime_context = _build_runtime_context()
    builder_calls: list[dict[str, object]] = []

    async def _runtime_preparer(*args, **kwargs):
        _ = args, kwargs
        return runtime_context

    def _override_builder(*, execution_path, tools):
        builder_calls.append({"execution_path": execution_path, "tools": tools})
        return {"_runtime_reasoning_effort_override": "low"}

    engine = SimpleNamespace(db=MagicMock(), gateway=MagicMock())
    tools = [ToolDefinition(name="web_search", description="Search the web")]

    query_plan = await build_runtime_query_entrypoint_plan(
        engine,
        agent=_build_agent(),
        messages=[ChatMessage(role="user", content="hello")],
        tools=tools,
        all_tool_names=None,
        tool_use_policy=None,
        breach_retry_result=None,
        tenant_id=7,
        user_id=5,
        conversation_id=42,
        billing_context=None,
        route_result=None,
        log_user_type="tenant_admin",
        context_sources=[],
        execution_path="fast",
        extra_kwargs={"tenant_id": 7},
        runtime_preparer=_runtime_preparer,
        adapter_registry=adapter_registry,
        query_engine_cls=_QueryEngineCaptureStub,
        model_request_override_builder=_override_builder,
    )

    stream_plan = await build_runtime_stream_entrypoint_plan(
        engine,
        agent=_build_agent(),
        messages=[ChatMessage(role="user", content="hello")],
        tenant_id=7,
        conversation_id=None,
        route_result=None,
        tools=tools,
        execution_path="fast",
        user_id=None,
        log_user_type=None,
        billing_context=None,
        runtime_context=None,
        all_tool_names=None,
        context_sources=None,
        tool_use_policy=None,
        breach_retry_result=None,
        runtime_preparer=_runtime_preparer,
        adapter_registry=adapter_registry,
        query_engine_cls=_QueryEngineCaptureStub,
        model_request_override_builder=_override_builder,
    )

    assert len(builder_calls) == 2
    assert [call["execution_path"] for call in builder_calls] == ["fast", "fast"]
    assert builder_calls[0]["tools"] is tools
    assert builder_calls[1]["tools"] is tools
    assert query_plan.request_extra_kwargs == {
        "_runtime_reasoning_effort_override": "low",
        "tenant_id": 7,
    }
    assert stream_plan.request_extra_kwargs == {
        "_runtime_reasoning_effort_override": "low"
    }


@pytest.mark.asyncio
async def test_build_runtime_query_entrypoint_plan_uses_override_builder_when_extra_kwargs_missing() -> None:
    adapter_registry = _AdapterRegistryStub()
    runtime_context = _build_runtime_context()

    async def _runtime_preparer(*args, **kwargs):
        _ = args, kwargs
        return runtime_context

    def _override_builder(*, execution_path, tools):
        assert execution_path == "fast"
        assert tools is None
        return {"_runtime_reasoning_effort_override": "low"}

    _QueryEngineCaptureStub.created.clear()

    plan = await build_runtime_query_entrypoint_plan(
        SimpleNamespace(db=MagicMock(), gateway=MagicMock()),
        agent=_build_agent(),
        messages=[ChatMessage(role="user", content="hello")],
        tools=None,
        all_tool_names=None,
        tool_use_policy=None,
        breach_retry_result=None,
        tenant_id=7,
        user_id=5,
        conversation_id=42,
        billing_context=None,
        route_result=None,
        log_user_type="tenant_admin",
        context_sources=[],
        execution_path="fast",
        extra_kwargs=None,
        runtime_preparer=_runtime_preparer,
        adapter_registry=adapter_registry,
        query_engine_cls=_QueryEngineCaptureStub,
        model_request_override_builder=_override_builder,
    )

    assert plan.request_extra_kwargs == {
        "_runtime_reasoning_effort_override": "low"
    }


@pytest.mark.asyncio
async def test_build_runtime_stream_entrypoint_plan_uses_override_builder_when_extra_kwargs_missing() -> None:
    adapter_registry = _AdapterRegistryStub()
    runtime_context = _build_runtime_context()

    async def _runtime_preparer(*args, **kwargs):
        _ = args, kwargs
        return runtime_context

    def _override_builder(*, execution_path, tools):
        assert execution_path == "fast"
        assert tools is None
        return {"_runtime_reasoning_effort_override": "low"}

    _QueryEngineCaptureStub.created.clear()

    plan = await build_runtime_stream_entrypoint_plan(
        SimpleNamespace(db=MagicMock(), gateway=MagicMock()),
        agent=_build_agent(),
        messages=[ChatMessage(role="user", content="hello")],
        tenant_id=7,
        conversation_id=42,
        route_result=None,
        tools=None,
        execution_path="fast",
        user_id=5,
        log_user_type="tenant_admin",
        billing_context=None,
        runtime_context=None,
        all_tool_names=None,
        context_sources=[],
        tool_use_policy=None,
        breach_retry_result=None,
        skip_metering_preflight=True,
        runtime_preparer=_runtime_preparer,
        adapter_registry=adapter_registry,
        query_engine_cls=_QueryEngineCaptureStub,
        model_request_override_builder=_override_builder,
        engine_logger=None,
    )

    assert plan.request_extra_kwargs == {
        "_runtime_reasoning_effort_override": "low"
    }


@pytest.mark.asyncio
async def test_iterate_runtime_stream_entrypoint_prefers_iter_stream_turn() -> None:
    query_engine = _StreamIterStub()
    plan = SimpleNamespace(
        query_engine=query_engine,
        runtime_context=_build_runtime_context(),
        request_context=SimpleNamespace(messages=[ChatMessage(role="user", content="hello")]),
        openai_tools=None,
        effective_tool_choice=None,
        runtime_context_sources=[],
        request_extra_kwargs={},
    )

    chunks = [
        chunk
        async for chunk in iterate_runtime_stream_entrypoint(
            plan=plan,  # type: ignore[arg-type]
            agent=_build_agent(),
            selected_skill_names=["skill.a"],
        )
    ]

    assert [chunk.delta for chunk in chunks] == ["iter-path"]
    assert len(query_engine.iter_calls) == 1
    assert query_engine.run_calls == []
    assert query_engine.iter_calls[0]["selected_skill_names"] == ["skill.a"]


@pytest.mark.asyncio
async def test_iterate_runtime_stream_entrypoint_falls_back_to_run_stream_turn() -> None:
    query_engine = _StreamRunOnlyStub()
    plan = SimpleNamespace(
        query_engine=query_engine,
        runtime_context=_build_runtime_context(),
        request_context=SimpleNamespace(messages=[ChatMessage(role="user", content="hello")]),
        openai_tools=None,
        effective_tool_choice=None,
        runtime_context_sources=[],
        request_extra_kwargs={"execution_path": "deep"},
    )

    chunks = [
        chunk
        async for chunk in iterate_runtime_stream_entrypoint(
            plan=plan,  # type: ignore[arg-type]
            agent=_build_agent(),
            selected_skill_names=["skill.b"],
        )
    ]

    assert [chunk.delta for chunk in chunks] == ["legacy-run-path"]
    assert len(query_engine.run_calls) == 1
    assert query_engine.run_calls[0]["extra_kwargs"] == {"execution_path": "deep"}
    assert query_engine.run_calls[0]["selected_skill_names"] == ["skill.b"]
