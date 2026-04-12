from __future__ import annotations

from dataclasses import replace

import pytest

from app.ai.adapters.openai_compatible import legacy_entrypoints as legacy_ep
from app.ai.adapters.openai_compatible.compat import (
    legacy_entrypoint_facade as legacy_facade,
)
from app.ai.adapters.openai_compatible.compat.legacy_context_builder import (
    LegacyEntrypointContext,
    LegacyEntrypointGuardSnapshot,
    LegacyEntrypointPlan,
)
from app.ai.adapters.openai_compatible.compat.legacy_entrypoint_dispatch import (
    LegacyEntrypointDispatchError,
)
from app.ai.types import ChatChunk, ChatMessage, ChatResponse


class _AdapterStub:
    wire_api = "responses"

    def __init__(self) -> None:
        self.logged: list[dict] = []

    def _log_upstream_error(
        self,
        error: Exception,
        *,
        endpoint_path: str,
        model: str,
        wire_api: str,
    ) -> None:
        self.logged.append(
            {
                "error": error,
                "endpoint_path": endpoint_path,
                "model": model,
                "wire_api": wire_api,
            }
        )


def _build_plan(*, wire_api: str = "responses") -> LegacyEntrypointPlan:
    context = LegacyEntrypointContext(
        active_endpoint_path=f"/v1/{wire_api}",
        active_wire_api=wire_api,
        effective_request={"upstream_model": "gpt-5.4", "effective_params": {}},
        effective_error_model="gpt-5.4",
        runtime_model_config=None,
        supports_vision=False,
        supports_audio=False,
        supports_video=False,
        protocol_kwargs={},
        guard_snapshot=LegacyEntrypointGuardSnapshot(
            runtime_disable_cross_protocol_fallback=True,
            runtime_disable_sync_rescue=True,
        ),
    )
    return LegacyEntrypointPlan(
        context=context,
        request_params={"model": "gpt-5.4"},
        responses_kwargs={"messages": [ChatMessage(role="user", content="hi")]},
        sync_request_params={"model": "gpt-5.4"},
    )


def test_legacy_entrypoints_module_reexports_compat_facade() -> None:
    assert (
        legacy_ep.execute_legacy_adapter_chat_entrypoint
        is legacy_facade.execute_legacy_adapter_chat_entrypoint
    )
    assert (
        legacy_ep.execute_legacy_adapter_stream_entrypoint
        is legacy_facade.execute_legacy_adapter_stream_entrypoint
    )


@pytest.mark.asyncio
async def test_chat_entrypoint_delegates_to_builder_and_runner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = _AdapterStub()
    calls: dict[str, object] = {}

    async def _fake_dispatch(**kwargs):
        calls["dispatch"] = kwargs
        return _build_plan(wire_api="responses"), ChatResponse(
            message=ChatMessage(role="assistant", content="ok")
        )

    monkeypatch.setattr(
        legacy_facade,
        "dispatch_legacy_chat_entrypoint",
        _fake_dispatch,
    )

    response = await legacy_facade.execute_legacy_adapter_chat_entrypoint(
        adapter=adapter,  # type: ignore[arg-type]
        messages=[ChatMessage(role="user", content="hello")],
        model="gpt-5.4",
    )

    assert response.message.content == "ok"
    dispatch_kwargs = calls["dispatch"]
    assert isinstance(dispatch_kwargs, dict)
    assert dispatch_kwargs["adapter"] is adapter
    assert dispatch_kwargs["model"] == "gpt-5.4"


@pytest.mark.asyncio
async def test_stream_entrypoint_delegates_to_builder_and_runner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = _AdapterStub()
    calls: dict[str, object] = {}

    async def _fake_stream():
        yield ChatChunk(delta="a")
        yield ChatChunk(delta="b")

    async def _fake_dispatch(**kwargs):
        calls["dispatch"] = kwargs
        return _build_plan(wire_api="chat_completions"), _fake_stream()

    monkeypatch.setattr(
        legacy_facade,
        "dispatch_legacy_stream_entrypoint",
        _fake_dispatch,
    )

    chunks = [
        chunk
        async for chunk in legacy_facade.execute_legacy_adapter_stream_entrypoint(
            adapter=adapter,  # type: ignore[arg-type]
            messages=[ChatMessage(role="user", content="hello")],
            model="gpt-5.4",
        )
    ]

    assert [chunk.delta for chunk in chunks] == ["a", "b"]
    dispatch_kwargs = calls["dispatch"]
    assert isinstance(dispatch_kwargs, dict)
    assert dispatch_kwargs["adapter"] is adapter
    assert dispatch_kwargs["model"] == "gpt-5.4"


@pytest.mark.asyncio
@pytest.mark.parametrize("runtime_wire_api", ["responses", "chat_completions"])
async def test_chat_entrypoint_facade_preserves_runtime_protocol_guard_kwargs_for_builder(
    monkeypatch: pytest.MonkeyPatch,
    runtime_wire_api: str,
) -> None:
    adapter = _AdapterStub()
    calls: dict[str, object] = {}

    async def _fake_dispatch(**kwargs):
        calls["dispatch"] = kwargs
        return _build_plan(wire_api=runtime_wire_api), ChatResponse(
            message=ChatMessage(role="assistant", content="ok")
        )

    monkeypatch.setattr(
        legacy_facade,
        "dispatch_legacy_chat_entrypoint",
        _fake_dispatch,
    )

    response = await legacy_facade.execute_legacy_adapter_chat_entrypoint(
        adapter=adapter,  # type: ignore[arg-type]
        messages=[ChatMessage(role="user", content="hello")],
        model="gpt-5.4",
        _runtime_force_wire_api=runtime_wire_api,
        _runtime_disable_cross_protocol_fallback=True,
        _runtime_disable_sync_rescue=True,
    )

    assert response.message.content == "ok"
    dispatch_kwargs = calls["dispatch"]
    assert isinstance(dispatch_kwargs, dict)
    assert dispatch_kwargs["kwargs"]["_runtime_force_wire_api"] == runtime_wire_api
    assert (
        dispatch_kwargs["kwargs"]["_runtime_disable_cross_protocol_fallback"] is True
    )
    assert dispatch_kwargs["kwargs"]["_runtime_disable_sync_rescue"] is True


@pytest.mark.asyncio
async def test_chat_entrypoint_logs_with_final_plan_context_on_runner_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = _AdapterStub()
    planned = _build_plan(wire_api="chat_completions")
    planned = replace(
        planned,
        context=replace(
            planned.context,
            active_endpoint_path="/v1/chat/completions",
            effective_error_model="gpt-5.4-fallback",
        ),
    )

    def _fake_convert_openai_error(
        error: Exception,
        *,
        provider_code: str,
        model_code: str,
    ) -> Exception:
        _ = provider_code
        return ValueError(f"converted:{model_code}:{type(error).__name__}")

    async def _fake_dispatch(**kwargs):
        _ = kwargs
        raise LegacyEntrypointDispatchError(plan=planned, cause=RuntimeError("boom"))

    monkeypatch.setattr(
        legacy_facade,
        "dispatch_legacy_chat_entrypoint",
        _fake_dispatch,
    )
    monkeypatch.setattr(
        "app.ai.adapters.openai_compatible.compat.legacy_entrypoint_errors.convert_openai_error",
        _fake_convert_openai_error,
    )

    with pytest.raises(ValueError, match="converted:gpt-5.4-fallback:RuntimeError"):
        await legacy_facade.execute_legacy_adapter_chat_entrypoint(
            adapter=adapter,  # type: ignore[arg-type]
            messages=[ChatMessage(role="user", content="hello")],
            model="gpt-5.4",
        )

    assert adapter.logged
    logged = adapter.logged[-1]
    assert logged["endpoint_path"] == "/v1/chat/completions"
    assert logged["wire_api"] == "chat_completions"
    assert logged["model"] == "gpt-5.4-fallback"


@pytest.mark.asyncio
@pytest.mark.parametrize("runtime_wire_api", ["responses", "chat_completions"])
async def test_stream_entrypoint_facade_preserves_runtime_protocol_guard_kwargs_for_builder(
    monkeypatch: pytest.MonkeyPatch,
    runtime_wire_api: str,
) -> None:
    adapter = _AdapterStub()
    calls: dict[str, object] = {}

    async def _fake_stream():
        yield ChatChunk(delta="ok")

    async def _fake_dispatch(**kwargs):
        calls["dispatch"] = kwargs
        return _build_plan(wire_api=runtime_wire_api), _fake_stream()

    monkeypatch.setattr(
        legacy_facade,
        "dispatch_legacy_stream_entrypoint",
        _fake_dispatch,
    )

    chunks = [
        chunk
        async for chunk in legacy_facade.execute_legacy_adapter_stream_entrypoint(
            adapter=adapter,  # type: ignore[arg-type]
            messages=[ChatMessage(role="user", content="hello")],
            model="gpt-5.4",
            _runtime_force_wire_api=runtime_wire_api,
            _runtime_disable_cross_protocol_fallback=True,
            _runtime_disable_sync_rescue=True,
        )
    ]

    assert [chunk.delta for chunk in chunks] == ["ok"]
    dispatch_kwargs = calls["dispatch"]
    assert isinstance(dispatch_kwargs, dict)
    assert dispatch_kwargs["kwargs"]["_runtime_force_wire_api"] == runtime_wire_api
    assert (
        dispatch_kwargs["kwargs"]["_runtime_disable_cross_protocol_fallback"] is True
    )
    assert dispatch_kwargs["kwargs"]["_runtime_disable_sync_rescue"] is True
