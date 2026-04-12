from __future__ import annotations

from types import SimpleNamespace

import httpx
import pytest
from openai import RateLimitError

from app.ai.adapters.openai_compatible.capabilities import OpenAIProtocolCapabilities
from app.ai.adapters.openai_compatible.compat.legacy_context_builder import (
    build_legacy_entrypoint_plan,
)
from app.ai.adapters.openai_compatible.compat.legacy_protocol_policy import (
    should_fallback_from_responses_error,
    should_skip_sync_rescue_after_stream_error,
)
from app.ai.exceptions import (
    ProviderConnectionError,
    ProviderError,
    ProviderRateLimitError,
    ProviderTimeoutError,
)
from app.ai.gateway_support.protocol_adapter_bridge import (
    resolve_gateway_protocol_wire_api,
)
from app.ai.runtime.contracts import ProtocolGuardContract, TurnCommand
from app.ai.runtime.protocol_planner import ProtocolPlanner
from app.ai.runtime.protocol_recovery_policy import ProtocolRecoveryPolicy
from app.ai.runtime.protocol_runner import ProtocolRunner
from app.ai.runtime.types import TurnRecord
from app.ai.types import ChatMessage, ChatResponse


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

_RUNTIME_FORCE_WIRE_API = "_runtime_force_wire_api"


def _runtime_overrides(payload: dict[str, object]) -> dict[str, object]:
    runtime_keys = (
        _RUNTIME_FORCE_WIRE_API,
        *ProtocolGuardContract.runtime_guard_keys(),
    )
    return {key: payload[key] for key in runtime_keys if key in payload}


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


@pytest.mark.asyncio
async def test_turn_command_guards_keep_responses_only_provider_consistent() -> None:
    capabilities = _ResponsesOnlyCapabilities()
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
        adapter=_LegacyPlanAdapter(),  # type: ignore[arg-type]
        messages=[ChatMessage(role="user", content="hello")],
        model="gpt-5.4",
        temperature=0.2,
        max_tokens=128,
        top_p=0.9,
        tools=TOOLS,
        tool_choice="required",
        stream=False,
        kwargs=legacy_runtime_kwargs,
    )

    assert plan.context.runtime_disable_cross_protocol_fallback is True
    assert plan.context.runtime_disable_sync_rescue is True
    adapter = SimpleNamespace(
        wire_api="responses",
        protocol_capabilities=capabilities,
    )
    assert ProtocolPlanner.build_protocol_chain("responses", adapter=adapter) == [
        "responses"
    ]
    assert (
        should_fallback_from_responses_error(
            capabilities=capabilities,
            error=_FakeStatusError(502, "bad gateway"),
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


def test_protocol_planner_keeps_legacy_fallback_when_contract_missing() -> None:
    adapter = SimpleNamespace(wire_api="responses")

    assert ProtocolPlanner.build_protocol_chain("responses", adapter=adapter) == [
        "responses",
        "chat_completions",
    ]


def test_protocol_planner_resolves_responses_alias_for_legacy_wire_api() -> None:
    adapter = SimpleNamespace(wire_api="responses_api")

    assert ProtocolPlanner.resolve_preferred_protocol(adapter) == "responses"


@pytest.mark.parametrize(
    ("allow_flag", "expected_chain"),
    [
        pytest.param(True, ["responses", "chat_completions"], id="allow-true"),
        pytest.param(False, ["responses"], id="allow-false"),
    ],
)
def test_protocol_planner_respects_allow_flag_with_explicit_fallback_map(
    allow_flag: bool,
    expected_chain: list[str],
) -> None:
    provider_config = {
        "protocol_capabilities": {
            "primary_wire_api": "responses_api",
            "allowed_wire_apis": ["responses_api", "chat/completions"],
            "allowed_cross_protocol_fallbacks": {"responses_api": ["chat/completions"]},
            "allow_adapter_cross_protocol_fallback": allow_flag,
        }
    }
    capabilities = OpenAIProtocolCapabilities.from_provider_config(
        provider_config=provider_config,
        configured_wire_api=None,
    )
    adapter = SimpleNamespace(
        wire_api="responses",
        protocol_capabilities=capabilities,
    )

    preferred = ProtocolPlanner.resolve_preferred_protocol(adapter)

    assert preferred == "responses"
    assert ProtocolPlanner.build_protocol_chain(preferred, adapter=adapter) == expected_chain
    assert (
        capabilities.is_cross_protocol_fallback_allowed(
            from_wire_api="responses",
            to_wire_api="chat_completions",
        )
        is allow_flag
    )


def test_protocol_planner_normalizes_contract_aliases() -> None:
    capabilities = SimpleNamespace(
        primary_wire_api="responses_api",
        allowed_wire_apis=("responses_api", "chat/completions"),
        allowed_cross_protocol_fallbacks={"responses_api": ("chat/completions",)},
        allow_adapter_cross_protocol_fallback=True,
    )
    adapter = SimpleNamespace(
        wire_api="responses",
        protocol_capabilities=capabilities,
    )

    preferred = ProtocolPlanner.resolve_preferred_protocol(adapter)

    assert preferred == "responses"
    assert ProtocolPlanner.build_protocol_chain(preferred, adapter=adapter) == [
        "responses",
        "chat_completions",
    ]


def test_protocol_planner_responses_only_contract_matches_capabilities() -> None:
    capabilities = OpenAIProtocolCapabilities.from_provider_config(
        provider_config={"protocol_capabilities": {"allowed_wire_apis": ["responses"]}},
        configured_wire_api="responses",
    )
    adapter = SimpleNamespace(
        wire_api="responses",
        protocol_capabilities=capabilities,
    )

    preferred = ProtocolPlanner.resolve_preferred_protocol(adapter)

    assert preferred == "responses"
    assert ProtocolPlanner.build_protocol_chain(preferred, adapter=adapter) == ["responses"]
    assert (
        capabilities.is_cross_protocol_fallback_allowed(
            from_wire_api="responses",
            to_wire_api="chat_completions",
        )
        is False
    )


@pytest.mark.parametrize(
    ("capabilities", "action"),
    [
        pytest.param(
            SimpleNamespace(
                primary_wire_api="respones",
                allowed_wire_apis=("responses",),
                allowed_cross_protocol_fallbacks={},
                allow_adapter_cross_protocol_fallback=False,
            ),
            "resolve",
            id="invalid-primary",
        ),
        pytest.param(
            SimpleNamespace(
                primary_wire_api="responses",
                allowed_wire_apis=("responses", "chat_completionz"),
                allowed_cross_protocol_fallbacks={},
                allow_adapter_cross_protocol_fallback=True,
            ),
            "chain",
            id="invalid-allowed",
        ),
        pytest.param(
            SimpleNamespace(
                primary_wire_api="responses",
                allowed_wire_apis=("responses", "chat_completions"),
                allowed_cross_protocol_fallbacks={"responses": ("respones",)},
                allow_adapter_cross_protocol_fallback=True,
            ),
            "chain",
            id="invalid-fallback",
        ),
    ],
)
def test_protocol_planner_rejects_invalid_contract_tokens(
    capabilities: SimpleNamespace,
    action: str,
) -> None:
    adapter = SimpleNamespace(
        wire_api="responses",
        protocol_capabilities=capabilities,
    )

    with pytest.raises(ProviderError) as exc_info:
        if action == "resolve":
            ProtocolPlanner.resolve_preferred_protocol(adapter)
        else:
            ProtocolPlanner.build_protocol_chain("responses", adapter=adapter)

    assert exc_info.value.error_code == "invalid_protocol_contract"


def test_protocol_planner_rejects_primary_not_in_allowed_wire_apis() -> None:
    capabilities = SimpleNamespace(
        primary_wire_api="responses",
        allowed_wire_apis=("chat_completions",),
        allowed_cross_protocol_fallbacks={},
        allow_adapter_cross_protocol_fallback=False,
    )
    adapter = SimpleNamespace(
        wire_api="responses",
        protocol_capabilities=capabilities,
    )

    preferred = ProtocolPlanner.resolve_preferred_protocol(adapter)

    with pytest.raises(ProviderError) as exc_info:
        ProtocolPlanner.build_protocol_chain(preferred, adapter=adapter)

    assert exc_info.value.error_code == "invalid_protocol_contract"


def test_protocol_planner_requires_explicit_fallback_map_for_contracts() -> None:
    capabilities = SimpleNamespace(
        allowed_wire_apis=("responses", "chat_completions"),
        allowed_cross_protocol_fallbacks={},
        allow_adapter_cross_protocol_fallback=True,
        primary_wire_api="responses",
    )
    adapter = SimpleNamespace(
        wire_api="responses",
        protocol_capabilities=capabilities,
    )

    assert ProtocolPlanner.build_protocol_chain("responses", adapter=adapter) == [
        "responses"
    ]


def test_legacy_transitional_fallback_does_not_relax_runtime_planner_contract() -> None:
    provider_config = {
        "protocol_capabilities": {
            "primary_wire_api": "responses_api",
            "allowed_wire_apis": ["responses_api", "chat/completions"],
            "allow_adapter_cross_protocol_fallback": True,
        }
    }
    capabilities = OpenAIProtocolCapabilities.from_provider_config(
        provider_config=provider_config,
        configured_wire_api=None,
    )
    adapter = SimpleNamespace(
        wire_api="responses",
        protocol_capabilities=capabilities,
    )
    error = _FakeStatusError(502, "bad gateway")

    assert capabilities.allowed_cross_protocol_fallbacks == {}
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
        is True
    )


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
    assert kwargs[_RUNTIME_FORCE_WIRE_API] == "responses"
    assert (
        kwargs[ProtocolGuardContract.RUNTIME_DISABLE_CROSS_PROTOCOL_FALLBACK] is True
    )
    assert kwargs[ProtocolGuardContract.RUNTIME_DISABLE_SYNC_RESCUE] is True


def test_turn_command_guard_contract_overrides_extra_runtime_kwargs() -> None:
    command = TurnCommand(
        messages=[ChatMessage(role="user", content="hello")],
        model="gpt-5.4",
        tools=TOOLS,
        tool_choice="required",
        extra_kwargs={
            ProtocolGuardContract.RUNTIME_DISABLE_CROSS_PROTOCOL_FALLBACK: False,
            ProtocolGuardContract.RUNTIME_DISABLE_SYNC_RESCUE: False,
        },
        protocol_guards=ProtocolGuardContract(
            disable_cross_protocol_fallback=True,
            disable_sync_rescue=True,
        ),
    )

    kwargs = command.to_adapter_kwargs(protocol_path="responses")

    assert kwargs[_RUNTIME_FORCE_WIRE_API] == "responses"
    assert (
        kwargs[ProtocolGuardContract.RUNTIME_DISABLE_CROSS_PROTOCOL_FALLBACK] is True
    )
    assert kwargs[ProtocolGuardContract.RUNTIME_DISABLE_SYNC_RESCUE] is True


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
    legacy_runtime_kwargs = _runtime_overrides(runtime_kwargs)

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
    assert _RUNTIME_FORCE_WIRE_API not in plan.context.protocol_kwargs
    assert (
        ProtocolGuardContract.RUNTIME_DISABLE_CROSS_PROTOCOL_FALLBACK
        not in plan.context.protocol_kwargs
    )
    assert (
        ProtocolGuardContract.RUNTIME_DISABLE_SYNC_RESCUE
        not in plan.context.protocol_kwargs
    )


@pytest.mark.asyncio
async def test_protocol_runner_turn_command_guards_match_legacy_plan_snapshot() -> None:
    command = TurnCommand(
        messages=[ChatMessage(role="user", content="hello")],
        model="gpt-5.4",
        temperature=0.2,
        max_tokens=128,
        top_p=0.9,
        tools=TOOLS,
        tool_choice="required",
    )
    adapter_kwargs = command.to_adapter_kwargs(protocol_path="responses")
    captured: dict[str, object] = {}

    async def _execute_protocol_chat(**kwargs):
        captured.update(kwargs)
        return ChatResponse(message=ChatMessage(role="assistant", content="ok"))

    runner = ProtocolRunner(adapter=SimpleNamespace(execute_protocol_chat=_execute_protocol_chat))
    await runner.chat(
        protocol_path="responses",
        command=command,
        turn_record=TurnRecord(),
    )

    assert adapter_kwargs[_RUNTIME_FORCE_WIRE_API] == "responses"
    assert (
        adapter_kwargs[ProtocolGuardContract.RUNTIME_DISABLE_CROSS_PROTOCOL_FALLBACK]
        is True
    )
    assert adapter_kwargs[ProtocolGuardContract.RUNTIME_DISABLE_SYNC_RESCUE] is True
    assert captured[_RUNTIME_FORCE_WIRE_API] == "responses"
    assert (
        captured[ProtocolGuardContract.RUNTIME_DISABLE_CROSS_PROTOCOL_FALLBACK] is True
    )
    assert captured[ProtocolGuardContract.RUNTIME_DISABLE_SYNC_RESCUE] is True

    legacy_runtime_kwargs = _runtime_overrides(adapter_kwargs)
    plan = await build_legacy_entrypoint_plan(
        adapter=_LegacyPlanAdapter(),  # type: ignore[arg-type]
        messages=command.messages,
        model=command.model,
        temperature=command.temperature,
        max_tokens=command.max_tokens,
        top_p=command.top_p,
        tools=command.tools,
        tool_choice=command.tool_choice,
        stream=False,
        kwargs=legacy_runtime_kwargs,
    )

    assert plan.context.active_wire_api == "responses"
    assert plan.context.runtime_disable_cross_protocol_fallback is True
    assert plan.context.runtime_disable_sync_rescue is True


@pytest.mark.asyncio
async def test_legacy_plan_snapshot_tracks_custom_guard_contract_values() -> None:
    guard_contract = ProtocolGuardContract(
        disable_cross_protocol_fallback=False,
        disable_sync_rescue=False,
    )
    command = TurnCommand(
        messages=[ChatMessage(role="user", content="hello")],
        model="gpt-5.4",
        temperature=0.2,
        max_tokens=128,
        top_p=0.9,
        tools=TOOLS,
        tool_choice="required",
        protocol_guards=guard_contract,
    )
    adapter_kwargs = command.to_adapter_kwargs(protocol_path="responses")
    legacy_runtime_kwargs = _runtime_overrides(adapter_kwargs)

    plan = await build_legacy_entrypoint_plan(
        adapter=_LegacyPlanAdapter(),  # type: ignore[arg-type]
        messages=command.messages,
        model=command.model,
        temperature=command.temperature,
        max_tokens=command.max_tokens,
        top_p=command.top_p,
        tools=command.tools,
        tool_choice=command.tool_choice,
        stream=False,
        kwargs=legacy_runtime_kwargs,
    )

    assert plan.context.guard_snapshot.runtime_disable_cross_protocol_fallback is False
    assert plan.context.guard_snapshot.runtime_disable_sync_rescue is False
    assert (
        ProtocolGuardContract.RUNTIME_DISABLE_CROSS_PROTOCOL_FALLBACK
        not in plan.context.protocol_kwargs
    )
    assert (
        ProtocolGuardContract.RUNTIME_DISABLE_SYNC_RESCUE
        not in plan.context.protocol_kwargs
    )


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
    assert _RUNTIME_FORCE_WIRE_API not in plan.context.protocol_kwargs
