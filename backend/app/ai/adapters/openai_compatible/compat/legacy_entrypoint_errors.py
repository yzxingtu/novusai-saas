"""Error context helpers for legacy OpenAI-compatible entrypoints."""

from __future__ import annotations

from dataclasses import dataclass

from app.ai.adapters.openai_compatible.compat.legacy_context_builder import (
    LegacyEntrypointAdapterProtocol,
    LegacyEntrypointPlan,
)
from app.ai.adapters.openai_compatible.request_builder import resolve_chat_endpoint_path
from app.ai.exceptions import convert_openai_error


@dataclass(frozen=True)
class LegacyEntrypointErrorContext:
    endpoint_path: str
    wire_api: str
    effective_error_model: str


def default_legacy_entrypoint_error_context(
    *,
    adapter: LegacyEntrypointAdapterProtocol,
    model: str,
) -> LegacyEntrypointErrorContext:
    return LegacyEntrypointErrorContext(
        endpoint_path=resolve_chat_endpoint_path(wire_api=adapter.wire_api),
        wire_api=adapter.wire_api,
        effective_error_model=model,
    )


def planned_legacy_entrypoint_error_context(
    plan: LegacyEntrypointPlan,
) -> LegacyEntrypointErrorContext:
    return LegacyEntrypointErrorContext(
        endpoint_path=plan.context.active_endpoint_path,
        wire_api=plan.context.active_wire_api,
        effective_error_model=plan.context.effective_error_model,
    )


def raise_legacy_entrypoint_error(
    *,
    adapter: LegacyEntrypointAdapterProtocol,
    error: Exception,
    context: LegacyEntrypointErrorContext,
) -> None:
    adapter._log_upstream_error(
        error,
        endpoint_path=context.endpoint_path,
        model=context.effective_error_model,
        wire_api=context.wire_api,
    )
    raise convert_openai_error(
        error,
        provider_code="openai",
        model_code=context.effective_error_model,
    ) from error


__all__ = [
    "LegacyEntrypointErrorContext",
    "default_legacy_entrypoint_error_context",
    "planned_legacy_entrypoint_error_context",
    "raise_legacy_entrypoint_error",
]
