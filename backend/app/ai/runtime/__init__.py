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
        ContextCapabilityBundleProjection,
        get_context_assembler,
    )
    from app.ai.runtime.contracts import (
        ProtocolExecutionPlan,
        ProtocolGuardContract,
        TurnCommand,
        TurnExecutionResult,
    )
    from app.ai.runtime.manifest import (
        AIRuntimeInventoryService,
        RuntimeCapabilityItem,
        RuntimeCapabilityManifest,
        RuntimeCapabilityStatus,
    )
    from app.ai.runtime.protocol_recovery_policy import (
        ObservedStream,
        ProtocolRecoveryPolicy,
        StreamObservationError,
    )
    from app.ai.runtime.protocol_turn_session import ProtocolTurnSession
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
    from app.ai.runtime.usage_metrics import CostCalculator, TokenCounter

_EXPORT_MAP = {
    "CapabilityContext": "app.ai.runtime.capabilities",
    "CapabilityFragment": "app.ai.runtime.capabilities",
    "CapabilityProvider": "app.ai.runtime.capabilities",
    "CapabilityRegistry": "app.ai.runtime.capabilities",
    "ContextAssembler": "app.ai.runtime.context_assembler",
    "ContextAssemblerState": "app.ai.runtime.context_assembler",
    "ContextCapabilityBundleProjection": "app.ai.runtime.context_assembler",
    "get_context_assembler": "app.ai.runtime.context_assembler",
    "AIRuntimeInventoryService": "app.ai.runtime.manifest",
    "RuntimeCapabilityItem": "app.ai.runtime.manifest",
    "RuntimeCapabilityManifest": "app.ai.runtime.manifest",
    "RuntimeCapabilityStatus": "app.ai.runtime.manifest",
    "ProtocolExecutionPlan": "app.ai.runtime.contracts",
    "ProtocolGuardContract": "app.ai.runtime.contracts",
    "TurnCommand": "app.ai.runtime.contracts",
    "TurnExecutionResult": "app.ai.runtime.contracts",
    "ObservedStream": "app.ai.runtime.protocol_recovery_policy",
    "ProtocolRecoveryPolicy": "app.ai.runtime.protocol_recovery_policy",
    "StreamObservationError": "app.ai.runtime.protocol_recovery_policy",
    "ProtocolTurnSession": "app.ai.runtime.protocol_turn_session",
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
    "CostCalculator": "app.ai.runtime.usage_metrics",
    "TokenCounter": "app.ai.runtime.usage_metrics",
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
    "AIRuntimeInventoryService",
    "CapabilityBundle",
    "CapabilityContext",
    "CapabilityDescriptor",
    "CapabilityFragment",
    "CapabilityKind",
    "CapabilityProvider",
    "CapabilityRegistry",
    "ContextAssembler",
    "ContextAssemblerState",
    "ContextCapabilityBundleProjection",
    "ContextSource",
    "ConversationQueryEngine",
    "CostCalculator",
    "FallbackRecord",
    "ProtocolExecutionPlan",
    "ProtocolGuardContract",
    "ObservedStream",
    "ProtocolPath",
    "ProtocolRecoveryPolicy",
    "ProtocolTurnSession",
    "RuntimeCapabilityItem",
    "RuntimeCapabilityManifest",
    "RuntimeCapabilityStatus",
    "StreamObservationError",
    "TerminationReason",
    "TokenCounter",
    "TurnCommand",
    "TurnExecutionResult",
    "TurnOutcome",
    "TurnRecord",
    "ToolExecutor",
    "get_context_assembler",
]
