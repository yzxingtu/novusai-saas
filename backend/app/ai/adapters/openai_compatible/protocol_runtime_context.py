"""Protocol runtime-context helpers for OpenAI-compatible adapters."""

from __future__ import annotations

from typing import Any, Protocol

from app.ai.exceptions import ProviderError
from app.ai.runtime.contracts import ProtocolGuardContract


class ProtocolRuntimeContextAdapterProtocol(Protocol):
    protocol_capabilities: Any
    config: dict[str, Any]

    def resolve_effective_model_request(
        self,
        *,
        model: str,
        model_config: Any = None,
        wire_api: str | None = None,
    ) -> dict[str, Any]: ...

    def _apply_runtime_reasoning_effort_override(
        self,
        effective_request: dict[str, Any],
        *,
        reasoning_effort: Any,
        wire_api: str,
    ) -> dict[str, Any]: ...

    def _log_effective_model_request(
        self,
        *,
        effective_request: dict[str, Any],
        wire_api: str,
    ) -> None: ...

    def _normalize_timeout_seconds(self, timeout: Any) -> float | None: ...


def _ensure_runtime_guard_enabled(flag_name: str, enabled: bool) -> None:
    if enabled:
        return
    raise ProviderError(
        message=(
            "Runtime protocol guard must stay enabled for protocol-safe entrypoints: "
            f"{flag_name}={enabled}"
        ),
        provider_code="openai_compatible",
        error_code="invalid_runtime_guard",
    )


def prepare_protocol_execution_context(
    *,
    adapter: ProtocolRuntimeContextAdapterProtocol,
    wire_api: str,
    model: str,
    stream: bool,
    kwargs: dict[str, Any],
    default_stream_timeout_seconds: float,
) -> dict[str, Any]:
    runtime_kwargs = dict(kwargs or {})
    guard_contract = ProtocolGuardContract.pop_runtime_kwargs(
        runtime_kwargs,
        default=ProtocolGuardContract(),
    )
    _ensure_runtime_guard_enabled(
        ProtocolGuardContract.RUNTIME_DISABLE_CROSS_PROTOCOL_FALLBACK,
        guard_contract.disable_cross_protocol_fallback,
    )
    _ensure_runtime_guard_enabled(
        ProtocolGuardContract.RUNTIME_DISABLE_SYNC_RESCUE,
        guard_contract.disable_sync_rescue,
    )
    runtime_kwargs.pop("_runtime_force_protocol_path", None)
    runtime_kwargs.pop("_runtime_force_wire_api", None)
    runtime_reasoning_effort_override = runtime_kwargs.pop(
        "_runtime_reasoning_effort_override",
        None,
    )
    runtime_client_max_retries_override = runtime_kwargs.pop(
        "_runtime_client_max_retries_override",
        None,
    )
    hosted_web_search_required = bool(
        runtime_kwargs.get("_runtime_hosted_web_search_required")
    )
    runtime_model_config = runtime_kwargs.pop("model_config", None)
    if runtime_model_config is None:
        runtime_model_config = adapter.config.get("model_config")

    active_wire_api = adapter.protocol_capabilities.resolve_runtime_wire_api(wire_api)
    active_endpoint_path = (
        "responses" if active_wire_api == "responses" else "chat/completions"
    )
    effective_request = adapter.resolve_effective_model_request(
        model=model,
        model_config=runtime_model_config,
        wire_api=active_wire_api,
    )
    effective_request = adapter._apply_runtime_reasoning_effort_override(
        effective_request,
        reasoning_effort=runtime_reasoning_effort_override,
        wire_api=active_wire_api,
    )
    adapter._log_effective_model_request(
        effective_request=effective_request,
        wire_api=active_wire_api,
    )
    effective_error_model = str(effective_request.get("upstream_model") or model)

    vision_flag = runtime_kwargs.pop("supports_vision", True)
    audio_flag = runtime_kwargs.pop("supports_audio", False)
    video_flag = runtime_kwargs.pop("supports_video", False)
    timeout_seconds = adapter._normalize_timeout_seconds(
        runtime_kwargs.pop("timeout_seconds", None),
    )
    if runtime_client_max_retries_override is not None:
        runtime_kwargs["_client_max_retries"] = runtime_client_max_retries_override

    if runtime_kwargs.get("timeout") is None:
        if timeout_seconds is not None:
            runtime_kwargs["timeout"] = timeout_seconds
        elif stream or hosted_web_search_required:
            runtime_kwargs["timeout"] = default_stream_timeout_seconds

    return {
        "active_endpoint_path": active_endpoint_path,
        "active_wire_api": active_wire_api,
        "effective_request": effective_request,
        "effective_error_model": effective_error_model,
        "runtime_model_config": runtime_model_config,
        "supports_vision": vision_flag,
        "supports_audio": audio_flag,
        "supports_video": video_flag,
        "kwargs": runtime_kwargs,
    }


__all__ = ["prepare_protocol_execution_context"]
