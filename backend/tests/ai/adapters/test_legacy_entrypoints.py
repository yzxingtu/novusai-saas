from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.ai.adapters.openai_compatible.compat.legacy_context_builder import (
    build_legacy_entrypoint_plan,
)
from app.ai.adapters.openai_compatible.compat.legacy_entrypoint_dispatch import (
    LegacyEntrypointDispatchError,
    dispatch_legacy_chat_entrypoint,
    dispatch_legacy_stream_entrypoint,
)
from app.ai.adapters.openai_compatible.compat.legacy_entrypoint_runner import (
    run_legacy_chat_plan,
    run_legacy_stream_plan,
)
from app.ai.adapters.openai_compatible.protocol_runtime_context import (
    prepare_protocol_execution_context,
)
from app.ai.types import ChatChunk, ChatMessage, ChatResponse

TOOLS = [
    {
        "type": "function",
        "function": {"name": "ui_get_snapshot", "parameters": {}},
    }
]


class _LegacyAdapterStub:
    wire_api = "responses"

    def __init__(self) -> None:
        def _allow_cross_protocol_fallback(*, from_wire_api, to_wire_api) -> bool:
            _ = from_wire_api, to_wire_api
            return True

        self.protocol_capabilities = SimpleNamespace(
            resolve_runtime_wire_api=lambda wire_api: wire_api or self.wire_api,
            is_cross_protocol_fallback_allowed=_allow_cross_protocol_fallback,
        )
        self.config = {"model_config": {"reasoning": {"effort": "low"}}}
        self.provider_config = {}
        self.converted_messages = [{"role": "user", "content": "hello"}]
        self.prepared_contexts: list[dict] = []
        self.requests: list[dict] = []
        self.metadata_calls: list[dict] = []
        self.logged_effective_request = None

    def _prepare_protocol_execution_context(self, **kwargs):
        self.prepared_contexts.append(kwargs)
        return prepare_protocol_execution_context(
            adapter=self,
            wire_api=kwargs["wire_api"],
            model=kwargs["model"],
            stream=kwargs["stream"],
            kwargs=kwargs["kwargs"],
            default_stream_timeout_seconds=20.0,
        )

    def resolve_effective_model_request(self, *, model: str, **kwargs):
        _ = kwargs
        return {"upstream_model": model, "effective_params": {}}

    def _apply_runtime_reasoning_effort_override(
        self,
        effective_request: dict[str, object],
        *,
        reasoning_effort,
        wire_api: str,
    ) -> dict[str, object]:
        _ = reasoning_effort, wire_api
        return effective_request

    def _log_effective_model_request(
        self,
        *,
        effective_request: dict[str, object],
        wire_api: str,
    ) -> None:
        self.logged_effective_request = (effective_request, wire_api)

    def _normalize_timeout_seconds(self, timeout):
        if timeout is None:
            return None
        return float(timeout)

    async def _convert_messages(self, messages, **kwargs):
        _ = messages, kwargs
        return list(self.converted_messages)

    def _build_chat_completions_request(self, **kwargs):
        self.requests.append(kwargs)
        return {
            "model": "gpt-5.4",
            "messages": kwargs["openai_messages"],
            "stream": kwargs["stream"],
        }

    def _augment_request_metadata(self, metadata, *, effective_request):
        metadata = dict(metadata or {})
        metadata["effective_model"] = effective_request["upstream_model"]
        self.metadata_calls.append(metadata)
        return metadata


@pytest.mark.asyncio
async def test_build_legacy_entrypoint_plan_chat_preserves_runtime_context() -> None:
    adapter = _LegacyAdapterStub()

    plan = await build_legacy_entrypoint_plan(
        adapter=adapter,
        messages=[ChatMessage(role="user", content="hello")],
        model="gpt-5.4",
        temperature=0.2,
        max_tokens=128,
        top_p=0.9,
        tools=None,
        tool_choice=None,
        stream=False,
        kwargs={
            "_runtime_force_wire_api": "responses",
            "_runtime_disable_cross_protocol_fallback": True,
            "_runtime_disable_sync_rescue": True,
            "tenant_id": 7,
        },
    )

    assert plan.context.active_wire_api == "responses"
    assert plan.context.runtime_disable_cross_protocol_fallback is True
    assert plan.context.runtime_disable_sync_rescue is True
    assert adapter.prepared_contexts[0]["kwargs"]["_runtime_force_wire_api"] == "responses"
    assert "_runtime_force_wire_api" not in plan.context.protocol_kwargs
    assert "_runtime_disable_cross_protocol_fallback" not in plan.context.protocol_kwargs
    assert "_runtime_disable_sync_rescue" not in plan.context.protocol_kwargs
    assert plan.request_params["stream"] is False
    assert plan.responses_kwargs["tenant_id"] == 7
    assert plan.sync_request_params is None


@pytest.mark.asyncio
async def test_build_legacy_entrypoint_plan_stream_builds_sync_rescue_payload() -> None:
    adapter = _LegacyAdapterStub()

    plan = await build_legacy_entrypoint_plan(
        adapter=adapter,
        messages=[ChatMessage(role="user", content="hello")],
        model="gpt-5.4",
        temperature=0.2,
        max_tokens=128,
        top_p=0.9,
        tools=None,
        tool_choice=None,
        stream=True,
        kwargs={"_runtime_disable_sync_rescue": True},
    )

    assert plan.context.runtime_disable_sync_rescue is True
    assert plan.request_params["stream"] is True
    assert plan.sync_request_params is not None
    assert plan.sync_request_params["stream"] is False


@pytest.mark.asyncio
async def test_run_legacy_chat_plan_attaches_final_protocol_metadata_after_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = _LegacyAdapterStub()
    plan = await build_legacy_entrypoint_plan(
        adapter=adapter,
        messages=[ChatMessage(role="user", content="hello")],
        model="gpt-5.4",
        temperature=0.2,
        max_tokens=128,
        top_p=0.9,
        tools=TOOLS,
        tool_choice="required",
        stream=False,
        kwargs={},
    )

    async def _fake_execute_legacy_chat(**kwargs):
        kwargs["execution_state"]["active_wire_api"] = "chat_completions"
        return ChatResponse(
            message=ChatMessage(role="assistant", content="ok"),
            metadata={},
        )

    monkeypatch.setattr(
        "app.ai.adapters.openai_compatible.compat.legacy_entrypoint_runner.execute_legacy_chat",
        _fake_execute_legacy_chat,
    )

    response = await run_legacy_chat_plan(
        adapter=adapter,
        plan=plan,
        messages=[ChatMessage(role="user", content="hello")],
        model="gpt-5.4",
        tools=TOOLS,
        tool_choice="required",
    )

    assert response.metadata["protocol_path"] == "chat_completions"
    assert response.metadata["effective_model"] == "gpt-5.4"


@pytest.mark.asyncio
async def test_run_legacy_stream_plan_augments_each_chunk_request_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = _LegacyAdapterStub()
    plan = await build_legacy_entrypoint_plan(
        adapter=adapter,
        messages=[ChatMessage(role="user", content="hello")],
        model="gpt-5.4",
        temperature=0.2,
        max_tokens=128,
        top_p=0.9,
        tools=None,
        tool_choice=None,
        stream=True,
        kwargs={},
    )

    async def _fake_execute_legacy_stream(**kwargs):
        _ = kwargs
        yield ChatChunk(delta="a", metadata={})
        yield ChatChunk(delta="b", metadata={})

    monkeypatch.setattr(
        "app.ai.adapters.openai_compatible.compat.legacy_entrypoint_runner.execute_legacy_stream",
        _fake_execute_legacy_stream,
    )

    chunks = [
        chunk
        async for chunk in run_legacy_stream_plan(
            adapter=adapter,
            plan=plan,
            messages=[ChatMessage(role="user", content="hello")],
            model="gpt-5.4",
            tools=None,
            tool_choice=None,
        )
    ]

    assert [chunk.metadata["effective_model"] for chunk in chunks] == [
        "gpt-5.4",
        "gpt-5.4",
    ]


@pytest.mark.asyncio
async def test_dispatch_legacy_chat_entrypoint_wraps_runner_error_with_plan(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = _LegacyAdapterStub()

    async def _fake_run(**kwargs):
        _ = kwargs
        raise RuntimeError("runner boom")

    monkeypatch.setattr(
        "app.ai.adapters.openai_compatible.compat.legacy_entrypoint_dispatch.run_legacy_chat_plan",
        _fake_run,
    )

    with pytest.raises(LegacyEntrypointDispatchError) as exc_info:
        await dispatch_legacy_chat_entrypoint(
            adapter=adapter,
            messages=[ChatMessage(role="user", content="hello")],
            model="gpt-5.4",
            temperature=0.2,
            max_tokens=128,
            top_p=0.9,
            tools=TOOLS,
            tool_choice="required",
            kwargs={},
        )

    assert exc_info.value.plan.context.active_wire_api == "responses"
    assert str(exc_info.value.cause) == "runner boom"


@pytest.mark.asyncio
async def test_dispatch_legacy_stream_entrypoint_wraps_iterator_error_with_plan(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = _LegacyAdapterStub()

    async def _fake_stream(**kwargs):
        _ = kwargs
        yield ChatChunk(delta="partial")
        raise RuntimeError("stream boom")

    monkeypatch.setattr(
        "app.ai.adapters.openai_compatible.compat.legacy_entrypoint_dispatch.run_legacy_stream_plan",
        _fake_stream,
    )

    plan, stream_iter = await dispatch_legacy_stream_entrypoint(
        adapter=adapter,
        messages=[ChatMessage(role="user", content="hello")],
        model="gpt-5.4",
        temperature=0.2,
        max_tokens=128,
        top_p=0.9,
        tools=TOOLS,
        tool_choice="required",
        kwargs={},
    )

    chunks: list[ChatChunk] = []
    with pytest.raises(LegacyEntrypointDispatchError) as exc_info:
        async for chunk in stream_iter:
            chunks.append(chunk)

    assert [chunk.delta for chunk in chunks] == ["partial"]
    assert exc_info.value.plan == plan
    assert str(exc_info.value.cause) == "stream boom"
