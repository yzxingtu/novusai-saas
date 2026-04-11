from __future__ import annotations

from types import SimpleNamespace

import httpx
import pytest
from openai import RateLimitError

from app.ai.adapters.openai_compatible.compat.legacy_context_builder import (
    build_legacy_entrypoint_plan,
)
from app.ai.adapters.openai_compatible.compat.legacy_protocol_policy import (
    should_fallback_from_responses_error,
    should_skip_sync_rescue_after_stream_error,
)
from app.ai.exceptions import (
    ProviderConnectionError,
    ProviderRateLimitError,
    ProviderTimeoutError,
)
from app.ai.gateway_support.protocol_adapter_bridge import (
    resolve_gateway_protocol_wire_api,
)
from app.ai.runtime.contracts import TurnCommand
from app.ai.runtime.protocol_planner import ProtocolPlanner
from app.ai.runtime.protocol_recovery_policy import ProtocolRecoveryPolicy
from app.ai.types import ChatMessage


class _AllowAllCapabilities:
    def is_cross_protocol_fallback_allowed(
        self,
        *,
        from_wire_api: str,
        to_wire_api: str,
    ) -> bool:
        _ = from_wire_api, to_wire_api
        return True


class _ResponsesOnlyCapabilities:
    allowed_wire_apis = ("responses",)
    allowed_cross_protocol_fallbacks = {}
    allow_adapter_cross_protocol_fallback = False
    primary_wire_api = "responses"

    def is_cross_protocol_fallback_allowed(
        self,
        *,
        from_wire_api: str,
        to_wire_api: str,
    ) -> bool:
        _ = from_wire_api, to_wire_api
        return False


class _OneWayFallbackCapabilities:
    allowed_wire_apis = ("responses", "chat_completions")
    allowed_cross_protocol_fallbacks = {
        "responses": ("chat_completions",),
    }
    allow_adapter_cross_protocol_fallback = True
    primary_wire_api = "responses"

    def is_cross_protocol_fallback_allowed(
        self,
        *,
        from_wire_api: str,
        to_wire_api: str,
    ) -> bool:
        return to_wire_api in tuple(
            self.allowed_cross_protocol_fallbacks.get(from_wire_api, ())
        )


class _FakeStatusError(Exception):
    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.response = SimpleNamespace(status_code=status_code)


def _make_openai_rate_limit_error() -> RateLimitError:
    request = httpx.Request("POST", "https://api.example.com/v1/responses")
    response = httpx.Response(429, request=request)
    return RateLimitError(
        "Error code: 429",
        response=response,
        body={"type": "rate_limit_error", "message": "too many requests"},
    )


TOOLS = [
    {
        "type": "function",
        "function": {"name": "ui_get_snapshot", "parameters": {}},
    }
]


class _LegacyPlanAdapter:
    wire_api = "responses"

    def _prepare_protocol_execution_context(
        self,
        *,
        wire_api: str | None,
        model: str,
        stream: bool,
        kwargs: dict[str, object],
    ) -> dict[str, object]:
        _ = stream, kwargs
        active_wire_api = wire_api or self.wire_api
        return {
            "active_endpoint_path": f"/v1/{active_wire_api}",
            "active_wire_api": active_wire_api,
            "effective_request": {"upstream_model": model, "effective_params": {}},
            "effective_error_model": model,
            "runtime_model_config": None,
            "supports_vision": False,
            "supports_audio": False,
            "supports_video": False,
            "kwargs": {},
        }

    async def _convert_messages(self, messages, **kwargs):
        _ = kwargs
        return [{"role": message.role, "content": message.content} for message in messages]

    def _build_chat_completions_request(
        self,
        *,
        openai_messages,
        model: str,
        temperature: float,
        max_tokens: int | None,
        top_p: float,
        tools,
        tool_choice: str | None,
        stream: bool,
        **kwargs,
    ):
        _ = temperature, max_tokens, top_p, tools, tool_choice, kwargs
        return {"model": model, "messages": openai_messages, "stream": stream}

    def _augment_request_metadata(self, metadata, *, effective_request):
        _ = effective_request
        return dict(metadata or {})

    def _log_upstream_error(
        self,
        error: Exception,
        *,
        endpoint_path: str,
        model: str,
        wire_api: str,
    ) -> None:
        _ = error, endpoint_path, model, wire_api


@pytest.mark.parametrize(
    ("error", "expected_fallback", "expected_skip_rescue", "expected_block_reason"),
    [
        pytest.param(
            _make_openai_rate_limit_error(),
            False,
            True,
            "provider_rate_limit",
            id="sdk-rate-limit",
        ),
        pytest.param(
            ProviderRateLimitError("too many requests"),
            False,
            True,
            "provider_rate_limit",
            id="gateway-rate-limit",
        ),
        pytest.param(
            ProviderTimeoutError(
                "provider timed out",
                provider_code="openai_compatible",
                model_code="gpt-5.4",
            ),
            False,
            True,
            "provider_timeout",
            id="gateway-timeout",
        ),
        pytest.param(
            ProviderConnectionError("connection failed"),
            False,
            True,
            "provider_connection_error",
            id="gateway-connection",
        ),
        pytest.param(
            _FakeStatusError(429, "too many requests"),
            False,
            True,
            "provider_rate_limit",
            id="status-429",
        ),
        pytest.param(
            _FakeStatusError(408, "timed out"),
            False,
            True,
            "provider_timeout",
            id="status-408",
        ),
        pytest.param(
            _FakeStatusError(504, "gateway timed out"),
            False,
            True,
            "provider_timeout",
            id="status-504",
        ),
        pytest.param(
            _FakeStatusError(502, "bad gateway"),
            True,
            False,
            None,
            id="status-502",
        ),
    ],
)
def test_compat_and_runtime_block_matrix_stays_aligned(
    error: Exception,
    expected_fallback: bool,
    expected_skip_rescue: bool,
    expected_block_reason: str | None,
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
        is expected_fallback
    )
    assert (
        should_skip_sync_rescue_after_stream_error(error) is expected_skip_rescue
    )
    assert ProtocolRecoveryPolicy.fallback_block_reason(error) == expected_block_reason


def test_runtime_and_compat_both_disable_cross_protocol_fallback_for_responses_only_provider() -> (
    None
):
    capabilities = _ResponsesOnlyCapabilities()
    adapter = SimpleNamespace(
        wire_api="responses",
        protocol_capabilities=capabilities,
    )
    error = _FakeStatusError(502, "bad gateway")

    assert ProtocolPlanner.build_protocol_chain("responses", adapter=adapter) == [
        "responses"
    ]
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


def test_protocol_planner_preserves_one_way_fallback_contract() -> None:
    capabilities = _OneWayFallbackCapabilities()
    adapter = SimpleNamespace(
        wire_api="responses",
        protocol_capabilities=capabilities,
    )

    assert ProtocolPlanner.build_protocol_chain("responses", adapter=adapter) == [
        "responses",
        "chat_completions",
    ]
    assert ProtocolPlanner.build_protocol_chain(
        "chat_completions",
        adapter=adapter,
    ) == ["chat_completions"]


def test_turn_command_freezes_each_runtime_protocol_step_with_guard_flags() -> None:
    adapter = SimpleNamespace(
        wire_api="responses",
        protocol_capabilities=_OneWayFallbackCapabilities(),
    )
    chain = ProtocolPlanner.build_protocol_chain("responses", adapter=adapter)
    command = TurnCommand(
        messages=[ChatMessage(role="user", content="hello")],
        model="gpt-5.4",
        tools=TOOLS,
        tool_choice="required",
    )

    kwargs = command.to_adapter_kwargs(protocol_path=chain[0])

    assert chain == ["responses", "chat_completions"]
    assert kwargs["_runtime_force_wire_api"] == "responses"
    assert kwargs["_runtime_disable_cross_protocol_fallback"] is True
    assert kwargs["_runtime_disable_sync_rescue"] is True


@pytest.mark.asyncio
@pytest.mark.parametrize("protocol_path", ["responses", "chat_completions"])
async def test_turn_command_protocol_guards_stay_legacy_plan_compatible(
    protocol_path: str,
) -> None:
    runtime_kwargs = TurnCommand(
        messages=[ChatMessage(role="user", content="hello")],
        model="gpt-5.4",
        temperature=0.2,
        max_tokens=128,
        top_p=0.9,
        tools=TOOLS,
        tool_choice="required",
    ).to_adapter_kwargs(protocol_path=protocol_path)
    legacy_runtime_kwargs = {
        key: value
        for key, value in runtime_kwargs.items()
        if str(key).startswith("_runtime_")
    }

    plan = await build_legacy_entrypoint_plan(
        adapter=_LegacyPlanAdapter(),  # type: ignore[arg-type]
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

    assert plan.context.active_wire_api == protocol_path
    assert plan.context.runtime_disable_cross_protocol_fallback is True
    assert plan.context.runtime_disable_sync_rescue is True
    assert "_runtime_force_wire_api" not in plan.context.protocol_kwargs
    assert "_runtime_disable_cross_protocol_fallback" not in plan.context.protocol_kwargs
    assert "_runtime_disable_sync_rescue" not in plan.context.protocol_kwargs


@pytest.mark.asyncio
async def test_gateway_runtime_force_wire_api_and_legacy_plan_keep_same_responses_guardrails() -> (
    None
):
    runtime_kwargs = TurnCommand(
        messages=[ChatMessage(role="user", content="hello")],
        model="gpt-5.4",
        tools=TOOLS,
        tool_choice="required",
    ).to_adapter_kwargs(protocol_path="responses")
    provider = SimpleNamespace(type="openai_compatible", config={"wire_api": "chat_completions"})

    assert (
        resolve_gateway_protocol_wire_api(provider, extra_kwargs=runtime_kwargs)
        == "responses"
    )

    plan = await build_legacy_entrypoint_plan(
        adapter=_LegacyPlanAdapter(),  # type: ignore[arg-type]
        messages=[ChatMessage(role="user", content="hello")],
        model="gpt-5.4",
        temperature=0.2,
        max_tokens=128,
        top_p=0.9,
        tools=TOOLS,
        tool_choice="required",
        stream=False,
        kwargs=runtime_kwargs,
    )

    assert plan.context.active_wire_api == "responses"
    assert plan.context.runtime_disable_cross_protocol_fallback is True
    assert plan.context.runtime_disable_sync_rescue is True
    assert "_runtime_force_wire_api" not in plan.context.protocol_kwargs
