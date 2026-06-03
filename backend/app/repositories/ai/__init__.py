"""
AI 模块 Repository 层 / AI Module Repository Layer
"""

from app.repositories.ai.action_log_repository import AIActionLogRepository
from app.repositories.ai.admin_long_term_memory_repository import (
    AdminMemoryRecordRepository,
    AdminProfileSnapshotRepository,
)
from app.repositories.ai.agent_access_repository import AgentAccessRepository
from app.repositories.ai.agent_conversation_repository import (
    AdminAgentConversationRepository,
    AgentConversationRepository,
)
from app.repositories.ai.agent_memory_override_repository import (
    AgentMemoryOverrideRepository,
)
from app.repositories.ai.agent_repository import AdminAgentRepository, AgentRepository
from app.repositories.ai.agent_skill_grant_repository import (
    AgentSkillGrantRepository,
)
from app.repositories.ai.agent_version_repository import AgentVersionRepository
from app.repositories.ai.api_key_repository import ProviderApiKeyRepository
from app.repositories.ai.batch_run_repository import BatchRunRepository
from app.repositories.ai.call_log_repository import AICallLogRepository
from app.repositories.ai.conversation_message_repository import (
    ConversationMessageRepository,
)
from app.repositories.ai.execution_decision_repository import (
    AdminExecutionDecisionRepository,
    ExecutionDecisionRepository,
)
from app.repositories.ai.execution_trust_policy_repository import (
    ExecutionTrustPolicyRepository,
)
from app.repositories.ai.knowledge_base_repository import (
    AdminKnowledgeBaseRepository,
    DocumentChunkRepository,
    KnowledgeBaseRepository,
    KnowledgeDocumentRepository,
)
from app.repositories.ai.memory_record_repository import MemoryRecordRepository
from app.repositories.ai.model_repository import AIModelRepository
from app.repositories.ai.profile_snapshot_repository import ProfileSnapshotRepository
from app.repositories.ai.provider_repository import AIProviderRepository
from app.repositories.ai.skill_repository import AdminSkillRepository, SkillRepository
from app.repositories.ai.tenant_agent_publication_repository import (
    TenantAgentPublicationRepository,
)
from app.repositories.ai.tenant_quota_repository import (
    AdminTenantQuotaRepository,
    TenantQuotaRepository,
)
from app.repositories.ai.tenant_rate_limit_repository import (
    TenantModelRateLimitRepository,
)

__all__ = [
    "AIProviderRepository",
    "AIModelRepository",
    "AdminMemoryRecordRepository",
    "AdminProfileSnapshotRepository",
    "ProviderApiKeyRepository",
    "AICallLogRepository",
    "AgentRepository",
    "AdminAgentRepository",
    "AgentConversationRepository",
    "AdminAgentConversationRepository",
    "ConversationMessageRepository",
    "AdminExecutionDecisionRepository",
    "ExecutionDecisionRepository",
    "ExecutionTrustPolicyRepository",
    "BatchRunRepository",
    "AgentAccessRepository",
    "TenantAgentPublicationRepository",
    "AgentVersionRepository",
    "AgentMemoryOverrideRepository",
    "AIActionLogRepository",
    "TenantQuotaRepository",
    "AdminTenantQuotaRepository",
    "TenantModelRateLimitRepository",
    "KnowledgeBaseRepository",
    "AdminKnowledgeBaseRepository",
    "KnowledgeDocumentRepository",
    "DocumentChunkRepository",
    "MemoryRecordRepository",
    "ProfileSnapshotRepository",
    "SkillRepository",
    "AdminSkillRepository",
    "AgentSkillGrantRepository",
]
