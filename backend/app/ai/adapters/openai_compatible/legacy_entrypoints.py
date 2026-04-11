"""Compatibility exports for legacy OpenAI-compatible adapter entrypoints."""

from __future__ import annotations

from app.ai.adapters.openai_compatible.compat.legacy_context_builder import (
    LegacyEntrypointAdapterProtocol,
    build_legacy_entrypoint_plan,
)
from app.ai.adapters.openai_compatible.compat.legacy_entrypoint_facade import (
    execute_legacy_adapter_chat_entrypoint,
    execute_legacy_adapter_stream_entrypoint,
)
from app.ai.adapters.openai_compatible.compat.legacy_entrypoint_runner import (
    run_legacy_chat_plan,
    run_legacy_stream_plan,
)

__all__ = [
    "LegacyEntrypointAdapterProtocol",
    "build_legacy_entrypoint_plan",
    "execute_legacy_adapter_chat_entrypoint",
    "execute_legacy_adapter_stream_entrypoint",
    "run_legacy_chat_plan",
    "run_legacy_stream_plan",
]
