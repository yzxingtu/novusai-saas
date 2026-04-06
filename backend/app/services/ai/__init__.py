"""
AI 模块 Service 层 / AI Module Service Layer
"""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.services.ai.agent_service import AgentService
    from app.services.ai.agent_skill_grant_service import AgentSkillGrantService
    from app.services.ai.api_key_service import ProviderApiKeyService
    from app.services.ai.call_log_service import CallLogService
    from app.services.ai.execution_decision_service import (
        AdminExecutionDecisionService,
        ExecutionDecisionService,
    )
    from app.services.ai.execution_trust_policy_service import (
        ExecutionTrustPolicyService,
    )
    from app.services.ai.long_term_memory_debug_service import (
        AdminMemoryRecordDebugService,
        AdminProfileSnapshotDebugService,
    )
    from app.services.ai.long_term_memory_service import LongTermMemoryService
    from app.services.ai.model_service import AIModelService
    from app.services.ai.monitoring_service import MonitoringService
    from app.services.ai.provider_service import AIProviderService
    from app.services.ai.session_memory_service import SessionMemoryService
    from app.services.ai.skill_registry_service import SkillRegistryService
    from app.services.ai.skill_service import SkillService
    from app.services.ai.usage_metrics import CostCalculator, TokenCounter

_EXPORT_MAP = {
    "AgentService": "app.services.ai.agent_service",
    "AgentSkillGrantService": "app.services.ai.agent_skill_grant_service",
    "ProviderApiKeyService": "app.services.ai.api_key_service",
    "CallLogService": "app.services.ai.call_log_service",
    "AdminExecutionDecisionService": "app.services.ai.execution_decision_service",
    "ExecutionDecisionService": "app.services.ai.execution_decision_service",
    "ExecutionTrustPolicyService": "app.services.ai.execution_trust_policy_service",
    "AdminMemoryRecordDebugService": "app.services.ai.long_term_memory_debug_service",
    "AdminProfileSnapshotDebugService": "app.services.ai.long_term_memory_debug_service",
    "LongTermMemoryService": "app.services.ai.long_term_memory_service",
    "AIModelService": "app.services.ai.model_service",
    "MonitoringService": "app.services.ai.monitoring_service",
    "AIProviderService": "app.services.ai.provider_service",
    "RuntimeInventoryService": "app.services.ai.runtime_inventory_service",
    "RuntimeDiagnosticsService": "app.services.ai.runtime_diagnostics_service",
    "AIRuntimeDiagnosticsService": "app.services.ai.runtime_diagnostics_service",
    "SessionMemoryService": "app.services.ai.session_memory_service",
    "SkillRegistryService": "app.services.ai.skill_registry_service",
    "SkillService": "app.services.ai.skill_service",
    "CostCalculator": "app.services.ai.usage_metrics",
    "TokenCounter": "app.services.ai.usage_metrics",
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
    "AIProviderService",
    "AIModelService",
    "MonitoringService",
    "ProviderApiKeyService",
    "TokenCounter",
    "CostCalculator",
    "CallLogService",
    "AdminExecutionDecisionService",
    "ExecutionDecisionService",
    "ExecutionTrustPolicyService",
    "AdminMemoryRecordDebugService",
    "AdminProfileSnapshotDebugService",
    "AgentService",
    "LongTermMemoryService",
    "SkillRegistryService",
    "SkillService",
    "AgentSkillGrantService",
    "SessionMemoryService",
    "RuntimeInventoryService",
    "RuntimeDiagnosticsService",
    "AIRuntimeDiagnosticsService",
]
