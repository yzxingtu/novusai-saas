"""
Test type: structural
Scope: OpenAI-compatible protocol runtime-context kwarg normalization.
Mocked dependencies: local adapter stub only; runtime-context logic runs real.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.ai.adapters.openai_compatible.protocol_runtime_context import (
    prepare_protocol_execution_context,
)
from app.ai.exceptions import ProviderError
from app.ai.runtime.contracts import ProtocolGuardContract


class _RuntimeContextAdapterStub:
    def __init__(self) -> None:
        self.protocol_capabilities = SimpleNamespace(
            resolve_runtime_wire_api=lambda wire_api: wire_api
        )
        self.config = {"model_config": {"default": True}}
        self.logged_effective_request = None

    def resolve_effective_model_request(
        self,
        *,
        model: str,
        model_config=None,
        wire_api: str | None = None,
    ) -> dict:
        _ = model_config, wire_api
        return {"upstream_model": model, "effective_params": {}}

    def _apply_runtime_reasoning_effort_override(
        self,
        effective_request: dict,
        *,
        reasoning_effort,
        wire_api: str,
    ) -> dict:
        _ = reasoning_effort, wire_api
        return effective_request

    def _log_effective_model_request(
        self,
        *,
        effective_request: dict,
        wire_api: str,
    ) -> None:
        self.logged_effective_request = (effective_request, wire_api)

    def _normalize_timeout_seconds(self, timeout):
        if timeout is None:
            return None
        return float(timeout)


def test_prepare_protocol_execution_context_pops_runtime_flags_and_applies_default_timeout() -> (
    None
):
    adapter = _RuntimeContextAdapterStub()

    context = prepare_protocol_execution_context(
        adapter=adapter,
        wire_api="responses",
        model="gpt-5.4",
        stream=True,
        kwargs={
            "_runtime_force_wire_api": "responses",
            ProtocolGuardContract.RUNTIME_DISABLE_CROSS_PROTOCOL_FALLBACK: True,
            ProtocolGuardContract.RUNTIME_DISABLE_SYNC_RESCUE: True,
            "supports_vision": False,
            "supports_audio": True,
            "tenant_id": 9,
        },
        default_stream_timeout_seconds=20.0,
    )

    assert context["active_wire_api"] == "responses"
    assert context["active_endpoint_path"] == "responses"
    assert context["supports_vision"] is False
    assert context["supports_audio"] is True
    assert context["supports_video"] is False
    assert context["kwargs"]["tenant_id"] == 9
    assert context["kwargs"]["timeout"] == 20.0
    assert "_runtime_force_wire_api" not in context["kwargs"]


def test_prepare_protocol_execution_context_maps_non_stream_timeout_seconds_to_timeout() -> (
    None
):
    adapter = _RuntimeContextAdapterStub()

    context = prepare_protocol_execution_context(
        adapter=adapter,
        wire_api="responses",
        model="gpt-5.4",
        stream=False,
        kwargs={
            ProtocolGuardContract.RUNTIME_DISABLE_CROSS_PROTOCOL_FALLBACK: True,
            ProtocolGuardContract.RUNTIME_DISABLE_SYNC_RESCUE: True,
            "timeout_seconds": 7,
            "tenant_id": 9,
        },
        default_stream_timeout_seconds=20.0,
    )

    assert context["kwargs"]["tenant_id"] == 9
    assert context["kwargs"]["timeout"] == 7.0
    assert "timeout_seconds" not in context["kwargs"]


def test_prepare_protocol_execution_context_bounds_non_stream_hosted_search_timeout() -> (
    None
):
    adapter = _RuntimeContextAdapterStub()

    context = prepare_protocol_execution_context(
        adapter=adapter,
        wire_api="responses",
        model="gpt-5.4",
        stream=False,
        kwargs={
            ProtocolGuardContract.RUNTIME_DISABLE_CROSS_PROTOCOL_FALLBACK: True,
            ProtocolGuardContract.RUNTIME_DISABLE_SYNC_RESCUE: True,
            "_runtime_hosted_web_search_required": True,
            "tenant_id": 9,
        },
        default_stream_timeout_seconds=20.0,
    )

    assert context["kwargs"]["tenant_id"] == 9
    assert context["kwargs"]["_runtime_hosted_web_search_required"] is True
    assert context["kwargs"]["timeout"] == 20.0


@pytest.mark.parametrize(
    "runtime_flag",
    [
        ProtocolGuardContract.RUNTIME_DISABLE_CROSS_PROTOCOL_FALLBACK,
        ProtocolGuardContract.RUNTIME_DISABLE_SYNC_RESCUE,
    ],
)
def test_prepare_protocol_execution_context_rejects_disabled_runtime_guards(
    runtime_flag: str,
) -> None:
    adapter = _RuntimeContextAdapterStub()

    with pytest.raises(ProviderError) as exc_info:
        prepare_protocol_execution_context(
            adapter=adapter,
            wire_api="responses",
            model="gpt-5.4",
            stream=False,
            kwargs={
                runtime_flag: False,
            },
            default_stream_timeout_seconds=20.0,
        )

    assert exc_info.value.error_code == "invalid_runtime_guard"
