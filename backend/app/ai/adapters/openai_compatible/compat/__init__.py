"""Compatibility helpers for OpenAI-compatible legacy execution paths."""

from app.ai.adapters.openai_compatible.compat.legacy_context_builder import (
    LegacyEntrypointAdapterProtocol,
    LegacyEntrypointContext,
    LegacyEntrypointPlan,
    build_legacy_entrypoint_plan,
)
from app.ai.adapters.openai_compatible.compat.legacy_entrypoint_dispatch import (
    LegacyEntrypointDispatchError,
    dispatch_legacy_chat_entrypoint,
    dispatch_legacy_stream_entrypoint,
)
from app.ai.adapters.openai_compatible.compat.legacy_entrypoint_facade import (
    LegacyEntrypointErrorContext,
    default_legacy_entrypoint_error_context,
    execute_legacy_adapter_chat_entrypoint,
    execute_legacy_adapter_stream_entrypoint,
    planned_legacy_entrypoint_error_context,
    raise_legacy_entrypoint_error,
)
from app.ai.adapters.openai_compatible.compat.legacy_entrypoint_runner import (
    run_legacy_chat_plan,
    run_legacy_stream_plan,
)

__all__ = [
    "LegacyEntrypointAdapterProtocol",
    "LegacyEntrypointContext",
    "LegacyEntrypointDispatchError",
    "LegacyEntrypointErrorContext",
    "LegacyEntrypointPlan",
    "build_legacy_entrypoint_plan",
    "default_legacy_entrypoint_error_context",
    "dispatch_legacy_chat_entrypoint",
    "dispatch_legacy_stream_entrypoint",
    "execute_legacy_adapter_chat_entrypoint",
    "execute_legacy_adapter_stream_entrypoint",
    "planned_legacy_entrypoint_error_context",
    "raise_legacy_entrypoint_error",
    "run_legacy_chat_plan",
    "run_legacy_stream_plan",
]
