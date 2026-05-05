"""
AI 相关 Schema 模块 / AI Schema Module

包含 AI 供应商、模型、API Key、调用日志等 Schema
Contains AI provider, model, API key, call log schemas.
"""

from app.schemas.ai.agent import (
    AgentCreate,
    AgentListItem,
    AgentResponse,
    AgentUpdate,
)
from app.schemas.ai.api_key import (
    ProviderApiKeyCreate,
    ProviderApiKeyResponse,
    ProviderApiKeyUpdate,
)
from app.schemas.ai.batch_run import (
    BatchRunCreate,
    BatchRunProgress,
    BatchRunResponse,
)
from app.schemas.ai.call_log import (
    AICallLogResponse,
    AICallLogSummary,
)
from app.schemas.ai.conversation_message import (
    ConversationMessageCreate,
    ConversationMessageResponse,
)
from app.schemas.ai.model import (
    AIModelCreate,
    AIModelResponse,
    AIModelUpdate,
)
from app.schemas.ai.monitoring import (
    MonitoringActorInfo,
    MonitoringCallTraceItem,
    MonitoringConversationDetail,
    MonitoringConversationListItem,
    MonitoringUsageBreakdownItem,
    MonitoringUsageDashboard,
    MonitoringUsageSeriesPoint,
    MonitoringUsageSummary,
)
from app.schemas.ai.plugin_runtime_audit import (
    ExtensionLifecycleAuditReport,
    ExtensionLifecycleAuditStageResult,
    ExtensionLifecycleExposedCapability,
    ExtensionLifecycleRecentFailure,
)
from app.schemas.ai.provider import (
    AIProviderCreate,
    AIProviderResponse,
    AIProviderUpdate,
)
from app.schemas.ai.runtime_diagnostics import (
    ExtensionLifecycleAuditReportSchema,
    RuntimeCapabilityItem,
    RuntimeCapabilityManifestSchema,
    RuntimeCheckItem,
    RuntimeDoctorReportSchema,
    RuntimeFailureAggregateItem,
    RuntimeRootCauseReportSchema,
    RuntimeSmokeReportSchema,
    RuntimeSmokeRequest,
)

__all__ = [
    # Provider / 供应商
    "AIProviderCreate",
    "AIProviderUpdate",
    "AIProviderResponse",
    "ExtensionLifecycleAuditReport",
    "ExtensionLifecycleAuditStageResult",
    "ExtensionLifecycleExposedCapability",
    "ExtensionLifecycleRecentFailure",
    # Model / 模型
    "AIModelCreate",
    "AIModelUpdate",
    "AIModelResponse",
    "MonitoringActorInfo",
    "MonitoringCallTraceItem",
    "MonitoringConversationDetail",
    "MonitoringConversationListItem",
    "MonitoringUsageBreakdownItem",
    "MonitoringUsageDashboard",
    "MonitoringUsageSeriesPoint",
    "MonitoringUsageSummary",
    # API Key / API 密钥
    "ProviderApiKeyCreate",
    "ProviderApiKeyUpdate",
    "ProviderApiKeyResponse",
    # Call Log / 调用日志
    "AICallLogResponse",
    "AICallLogSummary",
    # Agent / 智能体
    "AgentCreate",
    "AgentUpdate",
    "AgentResponse",
    "AgentListItem",
    # ConversationMessage / 会话消息
    "ConversationMessageCreate",
    "ConversationMessageResponse",
    # BatchRun / 批量运行
    "BatchRunCreate",
    "BatchRunResponse",
    "BatchRunProgress",
    # Runtime diagnostics / 运行时诊断
    "RuntimeCapabilityItem",
    "RuntimeCapabilityManifestSchema",
    "RuntimeCheckItem",
    "RuntimeFailureAggregateItem",
    "RuntimeDoctorReportSchema",
    "RuntimeSmokeRequest",
    "RuntimeSmokeReportSchema",
    "RuntimeRootCauseReportSchema",
    "ExtensionLifecycleAuditReportSchema",
]
