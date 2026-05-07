"""
Test type: behavioral
Scope: runtime-v2 replay/query-engine handoff and provider fallback behavior.
Mock strategy: runtime query engine and adapter are fakes at transport seams;
conversation engine routing and request assembly run real code.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.ai.engine.conversation import (
    ConversationEngine,
    _StreamRuntimeContext,
)
from app.ai.tools.types import ToolDefinition
from app.ai.types import ChatChunk, ChatMessage, ChatResponse


class _AdapterStub:
    def __init__(
        self,
        *,
        delta: str = "adapter-path",
        stream_error: Exception | None = None,
        chat_error: Exception | None = None,
        chat_content: str = "sync-fallback",
    ) -> None:
        self.delta = delta
        self.stream_error = stream_error
        self.chat_error = chat_error
        self.chat_content = chat_content
        self.stream_calls: list[dict] = []
        self.chat_calls: list[dict] = []

    async def stream_chat(self, **kwargs):
        self.stream_calls.append(kwargs)
        if self.stream_error is not None:
            raise self.stream_error
        yield ChatChunk(
            delta=self.delta,
            finish_reason="stop",
            input_tokens=4,
            output_tokens=3,
            total_tokens=7,
            metadata={},
        )

    async def chat(self, **kwargs):
        self.chat_calls.append(kwargs)
        if self.chat_error is not None:
            raise self.chat_error
        return ChatResponse(
            message=ChatMessage(role="assistant", content=self.chat_content),
            finish_reason="stop",
            input_tokens=6,
            output_tokens=5,
            total_tokens=11,
            tool_calls=None,
            metadata={},
        )


class _RuntimeQueryEngineStub:
    created_count = 0
    run_stream_count = 0

    def __init__(self, *, adapter, strict_contract: bool = False) -> None:
        _ = adapter, strict_contract
        type(self).created_count += 1
        self.turn_record = SimpleNamespace(
            turn_outcome="success",
            termination_reason="completed",
            protocol_path="responses",
            selected_tool_names=["query_records"],
            selected_skill_names=["runtime.query_records"],
            context_sources=[],
            fallback_history=[
                {
                    "from_protocol": "responses",
                    "to_protocol": "chat_completions",
                    "reason": "stream_empty_no_output",
                    "recovered": True,
                    "metadata": {"recovery_path": "sync_chat_completions"},
                }
            ],
            metadata={
                "diagnostics_diff": {
                    "selected_tool_names": {
                        "previous": [],
                        "runtime_v2": ["query_records"],
                    }
                }
            },
        )

    async def iter_stream_turn(self, **kwargs):
        _ = kwargs
        type(self).run_stream_count += 1
        yield ChatChunk(
            delta="runtime-v2-path",
            finish_reason="stop",
            input_tokens=5,
            output_tokens=6,
            total_tokens=11,
            metadata={},
        )

    async def run_stream_turn(self, **kwargs):
        return [chunk async for chunk in self.iter_stream_turn(**kwargs)]


class _RuntimeQueryEngineFailBeforeMeaningfulChunkStub:
    created_count = 0
    run_stream_count = 0

    def __init__(self, *, adapter, strict_contract: bool = False) -> None:
        _ = adapter, strict_contract
        type(self).created_count += 1
        self.turn_record = SimpleNamespace(
            turn_outcome="failed",
            termination_reason="error",
            protocol_path="responses",
            selected_tool_names=["query_records"],
            selected_skill_names=[],
            context_sources=[],
            fallback_history=[],
            metadata={"stream_failure_has_meaningful_chunk": False},
        )

    async def iter_stream_turn(self, **kwargs):
        _ = kwargs
        type(self).run_stream_count += 1
        raise RuntimeError("runtime-v2 stream failed before first meaningful chunk")
        yield ChatChunk(delta="")  # pragma: no cover

    async def run_stream_turn(self, **kwargs):
        return [chunk async for chunk in self.iter_stream_turn(**kwargs)]


class _RuntimeQueryEngineFailAfterMeaningfulChunkStub:
    created_count = 0
    run_stream_count = 0

    def __init__(self, *, adapter, strict_contract: bool = False) -> None:
        _ = adapter, strict_contract
        type(self).created_count += 1
        self.turn_record = SimpleNamespace(
            turn_outcome="partial",
            termination_reason="error",
            protocol_path="responses",
            selected_tool_names=["query_records"],
            selected_skill_names=["runtime.query_records"],
            context_sources=[],
            fallback_history=[],
            metadata={"stream_failure_has_meaningful_chunk": True},
        )

    async def iter_stream_turn(self, **kwargs):
        _ = kwargs
        type(self).run_stream_count += 1
        raise RuntimeError("runtime-v2 stream failed after meaningful chunk")
        yield ChatChunk(delta="")  # pragma: no cover

    async def run_stream_turn(self, **kwargs):
        return [chunk async for chunk in self.iter_stream_turn(**kwargs)]


class _RuntimeQueryEngineFailAfterReasoningOnlyStub:
    created_count = 0
    run_stream_count = 0

    def __init__(self, *, adapter, strict_contract: bool = False) -> None:
        _ = adapter, strict_contract
        type(self).created_count += 1
        self.turn_record = SimpleNamespace(
            turn_outcome="failed",
            termination_reason="error",
            protocol_path="responses",
            selected_tool_names=["query_records"],
            selected_skill_names=[],
            context_sources=[],
            fallback_history=[],
            metadata={
                "stream_failure_has_meaningful_chunk": True,
                "stream_failure_blocks_fallback": False,
                "stream_failure_reasoning_only_before_visible_output": True,
            },
        )

    async def iter_stream_turn(self, **kwargs):
        _ = kwargs
        type(self).run_stream_count += 1
        raise RuntimeError("runtime-v2 stream failed after reasoning-only chunk")
        yield ChatChunk(delta="")  # pragma: no cover

    async def run_stream_turn(self, **kwargs):
        return [chunk async for chunk in self.iter_stream_turn(**kwargs)]


class _RuntimeQueryEngineCaptureOverridesStub:
    created_count = 0
    run_stream_count = 0
    last_stream_kwargs: dict | None = None

    def __init__(self, *, adapter, strict_contract: bool = False) -> None:
        _ = adapter, strict_contract
        type(self).created_count += 1
        self.turn_record = SimpleNamespace(
            turn_outcome="success",
            termination_reason="completed",
            protocol_path="responses",
            selected_tool_names=[],
            selected_skill_names=[],
            context_sources=[],
            fallback_history=[],
            metadata={},
        )

    async def iter_stream_turn(self, **kwargs):
        type(self).run_stream_count += 1
        type(self).last_stream_kwargs = dict(kwargs)
        yield ChatChunk(
            delta="fast reply",
            finish_reason="stop",
            input_tokens=3,
            output_tokens=2,
            total_tokens=5,
            metadata={},
        )

    async def run_stream_turn(self, **kwargs):
        return [chunk async for chunk in self.iter_stream_turn(**kwargs)]


def _build_runtime_context(
    *, should_record_call_log: bool = False
) -> _StreamRuntimeContext:
    provider = SimpleNamespace(
        id=101,
        code="provider_1",
        name="Provider One",
        type="openai_compatible",
        base_url="https://api.example.com/v1",
        config={},
    )
    api_key = SimpleNamespace(
        decrypt_key=MagicMock(return_value="sk-test"),
        increment_usage=MagicMock(),
    )
    ai_model = SimpleNamespace(
        id=202,
        code="gpt-5.4-xhigh",
        name="gpt-5.4-xhigh",
        input_price_per_1k=0.02,
        output_price_per_1k=0.06,
        supports_streaming=True,
    )
    return _StreamRuntimeContext(
        provider=provider,
        api_key=api_key,
        ai_model=ai_model,
        model_code="gpt-5.4-xhigh",
        is_vision=False,
        is_audio=False,
        is_video=False,
        estimated_input=16,
        metering_context=None,
        should_meter_usage=False,
        should_record_call_log=should_record_call_log,
        runtime_info={
            "provider_id": provider.id,
            "provider_name": provider.name,
            "model_id": ai_model.id,
            "model_name": ai_model.name,
            "model_code": ai_model.code,
        },
    )


def _build_engine(mock_db):
    gateway = MagicMock()
    gateway.usage_recorder = MagicMock()
    gateway.usage_recorder.record_usage_and_adjust = AsyncMock()
    gateway.usage_recorder.log_call_failure = AsyncMock()
    gateway.usage_recorder.call_log_service = MagicMock()
    gateway.usage_recorder.call_log_service.log_call_async = AsyncMock()
    gateway._merge_model_provider_snapshots = MagicMock(
        side_effect=lambda billing_context, **_: billing_context
    )
    return ConversationEngine(db=mock_db, gateway=gateway, sandbox=MagicMock())


@pytest.mark.asyncio
async def test_runtime_v2_active_mode_uses_query_engine(mock_db) -> None:
    engine = _build_engine(mock_db)
    adapter = _AdapterStub()
    runtime_context = _build_runtime_context(should_record_call_log=False)
    agent = SimpleNamespace(
        id=1,
        model=runtime_context.ai_model,
        temperature=0.7,
        max_tokens=256,
        top_p=1.0,
    )
    _RuntimeQueryEngineStub.created_count = 0
    _RuntimeQueryEngineStub.run_stream_count = 0

    with (
        patch(
            "app.ai.engine.conversation.AdapterRegistry.create_adapter",
            return_value=adapter,
        ),
        patch(
            "app.ai.engine.conversation.ConversationQueryEngine",
            new=_RuntimeQueryEngineStub,
        ),
    ):
        chunks = [
            chunk
            async for chunk in engine._stream_llm_chunks(
                agent=agent,
                messages=[ChatMessage(role="user", content="hello")],
                tenant_id=1,
                conversation_id=66,
                tools=[ToolDefinition(name="query_records", description="Query data")],
                runtime_context=runtime_context,
            )
        ]

    assert _RuntimeQueryEngineStub.created_count == 1
    assert _RuntimeQueryEngineStub.run_stream_count == 1
    assert len(chunks) == 1
    assert "".join(chunk.delta for chunk in chunks) == "runtime-v2-path"
    runtime_turn_record_raw = (chunks[0].metadata or {}).get("runtime_turn_record")
    if isinstance(runtime_turn_record_raw, dict):
        runtime_turn_record = runtime_turn_record_raw
    elif hasattr(runtime_turn_record_raw, "__dict__"):
        runtime_turn_record = dict(vars(runtime_turn_record_raw))
    else:
        runtime_turn_record = {}
    assert runtime_turn_record
    assert runtime_turn_record.get("selected_skill_names") == ["runtime.query_records"]
    assert runtime_turn_record.get("fallback_history")
    assert runtime_turn_record.get("metadata", {}).get("diagnostics_diff")
    assert adapter.stream_calls == []
    runtime_context.api_key.increment_usage.assert_called_once()
    mock_db.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_runtime_v2_stream_path_uses_query_engine_for_query_tools(
    mock_db,
) -> None:
    engine = _build_engine(mock_db)
    adapter = _AdapterStub(delta="unused-adapter")
    runtime_context = _build_runtime_context(should_record_call_log=False)
    agent = SimpleNamespace(
        id=2,
        model=runtime_context.ai_model,
        temperature=0.7,
        max_tokens=256,
        top_p=1.0,
    )
    _RuntimeQueryEngineStub.created_count = 0
    _RuntimeQueryEngineStub.run_stream_count = 0

    with (
        patch(
            "app.ai.engine.conversation.AdapterRegistry.create_adapter",
            return_value=adapter,
        ),
        patch(
            "app.ai.engine.conversation.ConversationQueryEngine",
            new=_RuntimeQueryEngineStub,
        ),
    ):
        chunks = [
            chunk
            async for chunk in engine._stream_llm_chunks(
                agent=agent,
                messages=[ChatMessage(role="user", content="hello")],
                tenant_id=1,
                conversation_id=67,
                tools=[
                    ToolDefinition(
                        name="query_records",
                        description="Query platform data",
                    )
                ],
                runtime_context=runtime_context,
            )
        ]

    assert _RuntimeQueryEngineStub.created_count == 1
    assert _RuntimeQueryEngineStub.run_stream_count == 1
    assert len(chunks) == 1
    assert "".join(chunk.delta for chunk in chunks) == "runtime-v2-path"
    assert (chunks[0].metadata or {}).get("runtime_turn_record") is not None
    assert len(adapter.stream_calls) == 0
    runtime_context.api_key.increment_usage.assert_called_once()
    mock_db.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_runtime_v2_fast_text_round_passes_low_reasoning_override(
    mock_db,
) -> None:
    engine = _build_engine(mock_db)
    adapter = _AdapterStub(delta="unused-adapter")
    runtime_context = _build_runtime_context(should_record_call_log=False)
    agent = SimpleNamespace(
        id=3,
        model=runtime_context.ai_model,
        temperature=0.7,
        max_tokens=256,
        top_p=1.0,
    )
    _RuntimeQueryEngineCaptureOverridesStub.created_count = 0
    _RuntimeQueryEngineCaptureOverridesStub.run_stream_count = 0
    _RuntimeQueryEngineCaptureOverridesStub.last_stream_kwargs = None

    with (
        patch(
            "app.ai.engine.conversation.AdapterRegistry.create_adapter",
            return_value=adapter,
        ),
        patch(
            "app.ai.engine.conversation.ConversationQueryEngine",
            new=_RuntimeQueryEngineCaptureOverridesStub,
        ),
    ):
        chunks = [
            chunk
            async for chunk in engine._stream_llm_chunks(
                agent=agent,
                messages=[ChatMessage(role="user", content="你好")],
                tenant_id=1,
                conversation_id=68,
                tools=None,
                execution_path="fast",
                runtime_context=runtime_context,
            )
        ]

    assert _RuntimeQueryEngineCaptureOverridesStub.created_count == 1
    assert _RuntimeQueryEngineCaptureOverridesStub.run_stream_count == 1
    assert len(chunks) == 1
    assert "".join(chunk.delta for chunk in chunks) == "fast reply"
    assert _RuntimeQueryEngineCaptureOverridesStub.last_stream_kwargs is not None
    assert _RuntimeQueryEngineCaptureOverridesStub.last_stream_kwargs[
        "extra_kwargs"
    ] == {"_runtime_reasoning_effort_override": "low"}


def test_agent_chat_service_context_diagnostics_infers_partial_interrupted_without_turn_record() -> (
    None
):
    from app.services.ai.agent_chat_service import AgentChatService

    result = SimpleNamespace(
        total_tokens=9,
        context_compacted=False,
        memory_recalled=False,
        memory_flush_triggered=False,
        prune_stats=None,
        rag_source_kinds=[],
        interrupted=True,
        tool_planner={"family": "none"},
        turn_record=None,
        completion_reason="interrupted",
        partial=True,
    )

    payload = AgentChatService._build_context_diagnostics(
        result,
        interaction_mode_effective="confirm",
    )

    assert payload["turn_outcome"] == "partial"
    assert payload["termination_reason"] == "interrupted"
    assert payload["last_interrupted"] is True


def test_agent_chat_service_last_run_summary_carries_turn_record_skill_and_protocol() -> (
    None
):
    from app.services.ai.agent_chat_service import AgentChatService

    result = SimpleNamespace(
        duration_ms=123,
        runtime_model_name="gpt-5.4-xhigh",
        runtime_provider_name="Provider One",
        success=True,
        total_tokens=21,
        tool_planner={"family": "runtime_v2"},
        turn_record={
            "turn_outcome": "success",
            "termination_reason": "protocol_fallback",
            "protocol_path": "chat_completions",
            "selected_tool_names": ["query_records"],
            "selected_skill_names": ["runtime.query_records"],
            "context_sources": [{"kind": "query_records", "name": "admin.ai"}],
        },
        completion_reason="",
        partial=False,
        interrupted=False,
    )

    payload = AgentChatService._build_last_run_summary(
        result,
        interaction_mode_effective="trusted_auto",
        downgrade_reason=None,
    )

    assert payload["completion_reason"] == "protocol_fallback"
    assert payload["termination_reason"] == "protocol_fallback"
    assert payload["protocol_path"] == "chat_completions"
    assert payload["selected_tool_names"] == ["query_records"]
    assert payload["selected_skill_names"] == ["runtime.query_records"]


@pytest.mark.asyncio
async def test_runtime_v2_stream_failure_before_first_chunk_raises_without_fallback(
    mock_db,
) -> None:
    engine = _build_engine(mock_db)
    adapter = _AdapterStub(delta="unused-fallback-stream")
    runtime_context = _build_runtime_context(should_record_call_log=False)
    agent = SimpleNamespace(
        id=3,
        model=runtime_context.ai_model,
        temperature=0.7,
        max_tokens=256,
        top_p=1.0,
    )
    _RuntimeQueryEngineFailBeforeMeaningfulChunkStub.created_count = 0
    _RuntimeQueryEngineFailBeforeMeaningfulChunkStub.run_stream_count = 0

    with (
        patch(
            "app.ai.engine.conversation.AdapterRegistry.create_adapter",
            return_value=adapter,
        ),
        patch(
            "app.ai.engine.conversation.ConversationQueryEngine",
            new=_RuntimeQueryEngineFailBeforeMeaningfulChunkStub,
        ),
        pytest.raises(
            RuntimeError,
            match="runtime-v2 stream failed before first meaningful chunk",
        ),
    ):
        async for _ in engine._stream_llm_chunks(
            agent=agent,
            messages=[ChatMessage(role="user", content="hello")],
            tenant_id=1,
            conversation_id=68,
            tools=[ToolDefinition(name="query_records", description="Query data")],
            runtime_context=runtime_context,
        ):
            pass

    assert _RuntimeQueryEngineFailBeforeMeaningfulChunkStub.created_count == 1
    assert _RuntimeQueryEngineFailBeforeMeaningfulChunkStub.run_stream_count == 1
    assert len(adapter.stream_calls) == 0
    assert len(adapter.chat_calls) == 0


@pytest.mark.asyncio
async def test_runtime_v2_stream_failure_before_first_chunk_does_not_fallback_to_sync_chat(
    mock_db,
) -> None:
    engine = _build_engine(mock_db)
    adapter = _AdapterStub(
        delta="ignored",
        stream_error=RuntimeError("adapter stream failed"),
        chat_content="sync-once",
    )
    runtime_context = _build_runtime_context(should_record_call_log=False)
    agent = SimpleNamespace(
        id=4,
        model=runtime_context.ai_model,
        temperature=0.7,
        max_tokens=256,
        top_p=1.0,
    )

    with (
        patch(
            "app.ai.engine.conversation.AdapterRegistry.create_adapter",
            return_value=adapter,
        ),
        patch(
            "app.ai.engine.conversation.ConversationQueryEngine",
            new=_RuntimeQueryEngineFailBeforeMeaningfulChunkStub,
        ),
        pytest.raises(
            RuntimeError,
            match="runtime-v2 stream failed before first meaningful chunk",
        ),
    ):
        async for _ in engine._stream_llm_chunks(
            agent=agent,
            messages=[ChatMessage(role="user", content="hello")],
            tenant_id=1,
            conversation_id=69,
            tools=[ToolDefinition(name="query_records", description="Query data")],
            runtime_context=runtime_context,
        ):
            pass

    assert len(adapter.stream_calls) == 0
    assert len(adapter.chat_calls) == 0


@pytest.mark.asyncio
async def test_runtime_v2_stream_success_with_call_log_enabled_records_success_log(
    mock_db,
) -> None:
    engine = _build_engine(mock_db)
    adapter = _AdapterStub()
    runtime_context = _build_runtime_context(should_record_call_log=True)
    agent = SimpleNamespace(
        id=5,
        model=runtime_context.ai_model,
        temperature=0.7,
        max_tokens=256,
        top_p=1.0,
    )
    _RuntimeQueryEngineStub.created_count = 0
    _RuntimeQueryEngineStub.run_stream_count = 0

    with (
        patch(
            "app.ai.engine.conversation.AdapterRegistry.create_adapter",
            return_value=adapter,
        ),
        patch(
            "app.ai.engine.conversation.ConversationQueryEngine",
            new=_RuntimeQueryEngineStub,
        ),
    ):
        chunks = [
            chunk
            async for chunk in engine._stream_llm_chunks(
                agent=agent,
                messages=[ChatMessage(role="user", content="hello")],
                tenant_id=1,
                user_id=11,
                conversation_id=70,
                tools=[ToolDefinition(name="query_records", description="Query data")],
                runtime_context=runtime_context,
            )
        ]

    assert "".join(chunk.delta for chunk in chunks) == "runtime-v2-path"
    assert engine.gateway.usage_recorder.log_call_failure.await_count == 0
    assert (
        engine.gateway.usage_recorder.call_log_service.log_call_async.await_count == 1
    )
    log_kwargs = (
        engine.gateway.usage_recorder.call_log_service.log_call_async.await_args.kwargs
    )
    assert log_kwargs["status"] == "success"
    assert log_kwargs["turn_record"]["protocol_path"] == "responses"
    assert log_kwargs["protocol_path"] == "responses"


@pytest.mark.asyncio
async def test_runtime_v2_stream_failure_with_call_log_enabled_records_failure_log(
    mock_db,
) -> None:
    engine = _build_engine(mock_db)
    adapter = _AdapterStub(delta="ignored")
    runtime_context = _build_runtime_context(should_record_call_log=True)
    agent = SimpleNamespace(
        id=6,
        model=runtime_context.ai_model,
        temperature=0.7,
        max_tokens=256,
        top_p=1.0,
    )

    with (
        patch(
            "app.ai.engine.conversation.AdapterRegistry.create_adapter",
            return_value=adapter,
        ),
        patch(
            "app.ai.engine.conversation.ConversationQueryEngine",
            new=_RuntimeQueryEngineFailBeforeMeaningfulChunkStub,
        ),
        pytest.raises(
            RuntimeError,
            match="runtime-v2 stream failed before first meaningful chunk",
        ),
    ):
        async for _ in engine._stream_llm_chunks(
            agent=agent,
            messages=[ChatMessage(role="user", content="hello")],
            tenant_id=1,
            user_id=12,
            conversation_id=71,
            tools=[ToolDefinition(name="query_records", description="Query data")],
            runtime_context=runtime_context,
        ):
            pass

    assert engine.gateway.usage_recorder.log_call_failure.await_count == 1
    assert (
        engine.gateway.usage_recorder.call_log_service.log_call_async.await_count == 0
    )
    failure_kwargs = engine.gateway.usage_recorder.log_call_failure.await_args.kwargs
    assert failure_kwargs["protocol_path"] == "responses"
    assert failure_kwargs["turn_record"]["termination_reason"] == "error"
    assert len(adapter.stream_calls) == 0
    assert len(adapter.chat_calls) == 0


@pytest.mark.asyncio
async def test_runtime_v2_stream_failure_after_chunk_records_flag(mock_db) -> None:
    engine = _build_engine(mock_db)
    adapter = _AdapterStub()
    runtime_context = _build_runtime_context(should_record_call_log=True)
    agent = SimpleNamespace(
        id=7,
        model=runtime_context.ai_model,
        temperature=0.7,
        max_tokens=256,
        top_p=1.0,
    )

    with (
        patch(
            "app.ai.engine.conversation.AdapterRegistry.create_adapter",
            return_value=adapter,
        ),
        patch(
            "app.ai.engine.conversation.ConversationQueryEngine",
            new=_RuntimeQueryEngineFailAfterMeaningfulChunkStub,
        ),
        pytest.raises(
            RuntimeError, match="runtime-v2 stream failed after meaningful chunk"
        ),
    ):
        async for _ in engine._stream_llm_chunks(
            agent=agent,
            messages=[ChatMessage(role="user", content="hello after chunk")],
            tenant_id=1,
            user_id=13,
            conversation_id=72,
            tools=[ToolDefinition(name="query_records", description="Query data")],
            runtime_context=runtime_context,
        ):
            pass

    assert engine.gateway.usage_recorder.log_call_failure.await_count == 1
    failure_kwargs = engine.gateway.usage_recorder.log_call_failure.await_args.kwargs
    metadata = failure_kwargs["turn_record"]["metadata"]
    assert metadata["runtime_v2_stream_failure_after_chunk"] is True


@pytest.mark.asyncio
async def test_runtime_v2_stream_failure_after_reasoning_only_chunk_does_not_set_after_chunk_flag(
    mock_db,
) -> None:
    engine = _build_engine(mock_db)
    adapter = _AdapterStub()
    runtime_context = _build_runtime_context(should_record_call_log=True)
    agent = SimpleNamespace(
        id=8,
        model=runtime_context.ai_model,
        temperature=0.7,
        max_tokens=256,
        top_p=1.0,
    )

    with (
        patch(
            "app.ai.engine.conversation.AdapterRegistry.create_adapter",
            return_value=adapter,
        ),
        patch(
            "app.ai.engine.conversation.ConversationQueryEngine",
            new=_RuntimeQueryEngineFailAfterReasoningOnlyStub,
        ),
        pytest.raises(
            RuntimeError,
            match="runtime-v2 stream failed after reasoning-only chunk",
        ),
    ):
        async for _ in engine._stream_llm_chunks(
            agent=agent,
            messages=[ChatMessage(role="user", content="hello after reasoning")],
            tenant_id=1,
            user_id=14,
            conversation_id=73,
            tools=[ToolDefinition(name="query_records", description="Query data")],
            runtime_context=runtime_context,
        ):
            pass

    assert engine.gateway.usage_recorder.log_call_failure.await_count == 1
    failure_kwargs = engine.gateway.usage_recorder.log_call_failure.await_args.kwargs
    metadata = failure_kwargs["turn_record"]["metadata"]
    assert metadata.get("runtime_v2_stream_failure_after_chunk") is not True
    assert metadata["stream_failure_reasoning_only_before_visible_output"] is True
