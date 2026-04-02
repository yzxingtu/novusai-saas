"""
Claude Code style runtime primitives / Claude Code 风格 runtime 原语
"""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.ai.runtime.capabilities import (
        CapabilityContext,
        CapabilityFragment,
        CapabilityProvider,
        CapabilityRegistry,
    )
    from app.ai.runtime.context_assembler import (
        ContextAssembler,
        ContextAssemblerState,
        LegacyContextAssemblerAdapter,
        get_context_assembler,
    )
    from app.ai.runtime.flags import RuntimeMode, get_runtime_mode
    from app.ai.runtime.query_engine import ConversationQueryEngine
    from app.ai.runtime.tool_executor import ToolExecutor
    from app.ai.runtime.types import (
        CapabilityBundle,
        CapabilityDescriptor,
        CapabilityKind,
        ContextSource,
        FallbackRecord,
        ProtocolPath,
        TerminationReason,
        TurnOutcome,
        TurnRecord,
    )

_EXPORT_MAP = {
    "CapabilityContext": "app.ai.runtime.capabilities",
    "CapabilityFragment": "app.ai.runtime.capabilities",
    "CapabilityProvider": "app.ai.runtime.capabilities",
    "CapabilityRegistry": "app.ai.runtime.capabilities",
    "ContextAssembler": "app.ai.runtime.context_assembler",
    "ContextAssemblerState": "app.ai.runtime.context_assembler",
    "LegacyContextAssemblerAdapter": "app.ai.runtime.context_assembler",
    "get_context_assembler": "app.ai.runtime.context_assembler",
    "RuntimeMode": "app.ai.runtime.flags",
    "get_runtime_mode": "app.ai.runtime.flags",
    "ConversationQueryEngine": "app.ai.runtime.query_engine",
    "ToolExecutor": "app.ai.runtime.tool_executor",
    "CapabilityBundle": "app.ai.runtime.types",
    "CapabilityDescriptor": "app.ai.runtime.types",
    "CapabilityKind": "app.ai.runtime.types",
    "ContextSource": "app.ai.runtime.types",
    "FallbackRecord": "app.ai.runtime.types",
    "ProtocolPath": "app.ai.runtime.types",
    "TerminationReason": "app.ai.runtime.types",
    "TurnOutcome": "app.ai.runtime.types",
    "TurnRecord": "app.ai.runtime.types",
}


def __getattr__(name: str) -> Any:
    module_path = _EXPORT_MAP.get(name)
    if not module_path:
        raise AttributeError(name)
    module = import_module(module_path)
    value = getattr(module, name)
    globals()[name] = value
    return value


__all__ = [
    "CapabilityContext",
    "CapabilityBundle",
    "CapabilityDescriptor",
    "CapabilityFragment",
    "CapabilityKind",
    "CapabilityProvider",
    "CapabilityRegistry",
    "ContextAssembler",
    "ContextAssemblerState",
    "ContextSource",
    "ConversationQueryEngine",
    "FallbackRecord",
    "LegacyContextAssemblerAdapter",
    "ProtocolPath",
    "RuntimeMode",
    "TerminationReason",
    "TurnOutcome",
    "TurnRecord",
    "ToolExecutor",
    "get_context_assembler",
    "get_runtime_mode",
]
