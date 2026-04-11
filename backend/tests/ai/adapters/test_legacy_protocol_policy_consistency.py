from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.ai.adapters.openai_compatible import legacy_entrypoints as legacy_ep
from app.ai.adapters.openai_compatible.compat.legacy_context_builder import (
    build_legacy_entrypoint_plan,
)
from app.ai.adapters.openai_compatible.compat.legacy_protocol_policy import (
    should_fallback_from_responses_error,
    should_skip_sync_rescue_after_stream_error,
)
from app.ai.adapters.openai_compatible.protocol_runtime_context import (
    prepare_protocol_execution_context,
)
from app.ai.exceptions import (
    ProviderConnectionError,
    ProviderRateLimitError,
    ProviderTimeoutError,
)
from app.ai.runtime.contracts import TurnCommand
from app.ai.runtime.protocol_recovery_policy import ProtocolRecoveryPolicy
from app.ai.types import ChatChunk, ChatMessage, ChatResponse


class _AllowAllCapabilities:
    primary_wire_api = "responses"

    def is_cross_protocol_fallback_allowed(
        self,
        *,
        from_wire_api: str,
        to_wire_api: str,
    ) -> bool:
        _ = from_wire_api, to_wire_api
        return True

    def resolve_runtime_wire_api(self, runtime_force_wire_api: str | None) -> str:
        return runtime_force_wire_api or self.primary_wire_api


class _ResponsesOnlyCapabilities:
    primary_wire_api = "responses"

    def is_cross_protocol_fallback_allowed(
        self,
        *,
        from_wire_api: str,
        to_wire_api: str,
    ) -> bool:
        _ = from_wire_api, to_wire_api
        return False

    def resolve_runtime_wire_api(self, runtime_force_wire_api: str | None) -> str:
        return runtime_force_wire_api or self.primary_wire_api


class _FakeStatusError(Exception):
    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.response = SimpleNamespace(status_code=status_code)


TOOLS = [{"type": "function", "function": {"name": "ui_get_snapshot"}}]


class _LegacyEntrypointExecutionAdapter:
    def __init__(
        self,
        *,
        capabilities,
        wire_api: str = "responses",
    ) -> None:
        self.protocol_capabilities = capabilities
        self.wire_api = wire_api
        self.config = {"model_config": {"default": True}}
        self.provider_config = {}
        self.logged: list[dict] = []
        self.responses_calls = 0
        self.responses_stream_calls = 0
        self.chat_completions_calls = 0
        self.chat_completions_stream_calls = 0
        self.responses_error: Exception | None = None
        self.responses_stream_error: Exception | None = None
        self.chat_completions_error: Exception | None = None
        self.chat_completions_stream_error: Exception | None = None

    def _prepare_protocol_execution_context(self, **kwargs):
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
        _ = effective_request, wire_api

    def _normalize_timeout_seconds(self, timeout):
        if timeout is None:
            return None
        return float(timeout)

    async def _convert_messages(self, messages, **kwargs):
        _ = messages, kwargs
        return [{"role": "user", "content": "hello"}]

    def _build_chat_completions_request(self, **kwargs):
        return {
            "model": kwargs["model"],
            "messages": kwargs["openai_messages"],
            "stream": kwargs["stream"],
        }

    def _augment_request_metadata(self, metadata, *, effective_request):
        metadata = dict(metadata or {})
        metadata["effective_model"] = effective_request["upstream_model"]
        return metadata

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

    async def _chat_via_responses(self, **kwargs) -> ChatResponse:
        _ = kwargs
        self.responses_calls += 1
        if self.responses_error is not None:
            raise self.responses_error
        return ChatResponse(message=ChatMessage(role="assistant", content="ok"))

    async def _stream_chat_via_responses(self, **kwargs):
        _ = kwargs
        self.responses_stream_calls += 1
        if self.responses_stream_error is not None:
            raise self.responses_stream_error
        yield ChatChunk(delta="ok")

    async def _chat_via_chat_completions(self, **kwargs) -> ChatResponse:
        _ = kwargs
        self.chat_completions_calls += 1
        if self.chat_completions_error is not None:
            raise self.chat_completions_error
        return ChatResponse(message=ChatMessage(role="assistant", content="fallback"))

    async def _stream_chat_via_chat_completions(self, **kwargs):
        _ = kwargs
        self.chat_completions_stream_calls += 1
        if self.chat_completions_stream_error is not None:
            raise self.chat_completions_stream_error
        yield ChatChunk(delta="fallback")

    @staticmethod
    def _stream_chunk_blocks_fallback(chunk: ChatChunk) -> bool:
        if chunk is None:
            return False
        if str(getattr(chunk, "delta", "") or "").strip():
            return True
        return bool(getattr(chunk, "tool_calls", None))

    def _chat_response_to_stream_chunk(self, response: ChatResponse) -> ChatChunk:
        return ChatChunk(delta=response.message.content, metadata=response.metadata)


@pytest.mark.parametrize(
    ("error", "expected_block_reason"),
    [
        pytest.param(ProviderRateLimitError("too many requests"), "provider_rate_limit"),
        pytest.param(
            ProviderTimeoutError(
                "timeout",
                provider_code="openai_compatible",
                model_code="gpt-5.4",
            ),
            "provider_timeout",
        ),
        pytest.param(ProviderConnectionError("connection failed"), "provider_connection_error"),
        pytest.param(_FakeStatusError(408, "timed out"), "provider_timeout"),
        pytest.param(_FakeStatusError(504, "gateway timeout"), "provider_timeout"),
    ],
)
def test_compat_and_runtime_block_reason_alignment_for_forbidden_cross_protocol(
    error: Exception,
    expected_block_reason: str,
) -> None:
    capabilities = _AllowAllCapabilities()

    assert (
        should_fallback_from_responses_error(
            capabilities=capabilities,
            error=error,
            tools=TOOLS,
            tool_choice="required",
            use_responses_api=True,
            fallback_switch_enabled=True,
        )
        is False
    )
    assert should_skip_sync_rescue_after_stream_error(error) is True
    assert ProtocolRecoveryPolicy.fallback_block_reason(error) == expected_block_reason


def test_compat_and_runtime_allow_5xx_when_not_explicitly_blocked() -> None:
    capabilities = _AllowAllCapabilities()
    error = _FakeStatusError(502, "bad gateway")

    assert (
        should_fallback_from_responses_error(
            capabilities=capabilities,
            error=error,
            tools=TOOLS,
            tool_choice="required",
            use_responses_api=True,
            fallback_switch_enabled=True,
        )
        is True
    )
    assert should_skip_sync_rescue_after_stream_error(error) is False
    assert ProtocolRecoveryPolicy.fallback_block_reason(error) is None


def test_responses_only_capabilities_forbid_cross_protocol_in_compat_and_runtime() -> None:
    capabilities = _ResponsesOnlyCapabilities()
    error = _FakeStatusError(502, "bad gateway")

    assert (
        should_fallback_from_responses_error(
            capabilities=capabilities,
            error=error,
            tools=TOOLS,
            tool_choice="required",
            use_responses_api=True,
            fallback_switch_enabled=True,
        )
        is False
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("capabilities", "extra_kwargs"),
    [
        pytest.param(_ResponsesOnlyCapabilities(), {}, id="responses-only-provider"),
        pytest.param(
            _AllowAllCapabilities(),
            {"_runtime_disable_cross_protocol_fallback": True},
            id="runtime-disable-cross-protocol",
        ),
    ],
)
async def test_legacy_chat_entrypoint_respects_forbidden_cross_protocol_fallback(
    monkeypatch: pytest.MonkeyPatch,
    capabilities,
    extra_kwargs: dict[str, object],
) -> None:
    adapter = _LegacyEntrypointExecutionAdapter(capabilities=capabilities)
    adapter.responses_error = _FakeStatusError(502, "bad gateway")

    monkeypatch.setattr(
        "app.ai.adapters.openai_compatible.compat.legacy_entrypoint_facade.convert_openai_error",
        lambda error, **kwargs: ValueError(f"converted:{kwargs['model_code']}:{error}"),
    )

    with pytest.raises(ValueError, match="converted:gpt-5.4:bad gateway"):
        await legacy_ep.execute_legacy_adapter_chat_entrypoint(
            adapter=adapter,  # type: ignore[arg-type]
            messages=[ChatMessage(role="user", content="hello")],
            model="gpt-5.4",
            tools=TOOLS,
            tool_choice="required",
            **extra_kwargs,
        )

    assert adapter.responses_calls == 1
    assert adapter.chat_completions_calls == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("capabilities", "extra_kwargs"),
    [
        pytest.param(_ResponsesOnlyCapabilities(), {}, id="responses-only-provider"),
        pytest.param(
            _AllowAllCapabilities(),
            {"_runtime_disable_cross_protocol_fallback": True},
            id="runtime-disable-cross-protocol",
        ),
    ],
)
async def test_legacy_stream_entrypoint_respects_forbidden_cross_protocol_fallback(
    monkeypatch: pytest.MonkeyPatch,
    capabilities,
    extra_kwargs: dict[str, object],
) -> None:
    adapter = _LegacyEntrypointExecutionAdapter(capabilities=capabilities)
    adapter.responses_stream_error = _FakeStatusError(502, "bad gateway")

    monkeypatch.setattr(
        "app.ai.adapters.openai_compatible.compat.legacy_entrypoint_facade.convert_openai_error",
        lambda error, **kwargs: ValueError(f"converted:{kwargs['model_code']}:{error}"),
    )

    with pytest.raises(ValueError, match="converted:gpt-5.4:bad gateway"):
        async for _ in legacy_ep.execute_legacy_adapter_stream_entrypoint(
            adapter=adapter,  # type: ignore[arg-type]
            messages=[ChatMessage(role="user", content="hello")],
            model="gpt-5.4",
            tools=TOOLS,
            tool_choice="required",
            **extra_kwargs,
        ):
            pass

    assert adapter.responses_stream_calls == 1
    assert adapter.chat_completions_stream_calls == 0
    assert adapter.chat_completions_calls == 0


@pytest.mark.asyncio
async def test_legacy_stream_entrypoint_respects_runtime_disable_sync_rescue(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = _LegacyEntrypointExecutionAdapter(
        capabilities=_AllowAllCapabilities(),
        wire_api="chat_completions",
    )
    adapter.chat_completions_stream_error = _FakeStatusError(502, "bad gateway")

    monkeypatch.setattr(
        "app.ai.adapters.openai_compatible.compat.legacy_entrypoint_facade.convert_openai_error",
        lambda error, **kwargs: ValueError(f"converted:{kwargs['model_code']}:{error}"),
    )

    with pytest.raises(ValueError, match="converted:gpt-5.4:bad gateway"):
        async for _ in legacy_ep.execute_legacy_adapter_stream_entrypoint(
            adapter=adapter,  # type: ignore[arg-type]
            messages=[ChatMessage(role="user", content="hello")],
            model="gpt-5.4",
            _runtime_force_wire_api="chat_completions",
            _runtime_disable_sync_rescue=True,
        ):
            pass

    assert adapter.chat_completions_stream_calls == 1
    assert adapter.chat_completions_calls == 0
    assert adapter.responses_stream_calls == 0


@pytest.mark.asyncio
async def test_legacy_entrypoint_plan_preserves_runtime_turn_command_protocol_guards() -> (
    None
):
    adapter = _LegacyEntrypointExecutionAdapter(capabilities=_AllowAllCapabilities())
    runtime_kwargs = TurnCommand(
        messages=[ChatMessage(role="user", content="hello")],
        model="gpt-5.4",
        temperature=0.2,
        max_tokens=128,
        top_p=0.9,
        tools=TOOLS,
        tool_choice="required",
    ).to_adapter_kwargs(protocol_path="responses")
    legacy_runtime_kwargs = {
        key: value
        for key, value in runtime_kwargs.items()
        if str(key).startswith("_runtime_")
    }

    plan = await build_legacy_entrypoint_plan(
        adapter=adapter,  # type: ignore[arg-type]
        messages=[ChatMessage(role="user", content="hello")],
        model="gpt-5.4",
        temperature=0.2,
        max_tokens=128,
        top_p=0.9,
        tools=TOOLS,
        tool_choice="required",
        stream=True,
        kwargs=legacy_runtime_kwargs,
    )

    assert plan.context.active_wire_api == "responses"
    assert plan.context.runtime_disable_cross_protocol_fallback is True
    assert plan.context.runtime_disable_sync_rescue is True
    assert "_runtime_force_wire_api" not in plan.context.protocol_kwargs
    assert "_runtime_disable_cross_protocol_fallback" not in plan.context.protocol_kwargs
    assert "_runtime_disable_sync_rescue" not in plan.context.protocol_kwargs
