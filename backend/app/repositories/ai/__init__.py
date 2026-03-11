"""
AI 模块 Repository 层 / AI Module Repository Layer
"""

from app.repositories.ai.action_log_repository import AIActionLogRepository
from app.repositories.ai.agent_access_repository import AgentAccessRepository
from app.repositories.ai.agent_conversation_repository import (
    AdminAgentConversationRepository,
    AgentConversationRepository,
)
from app.repositories.ai.agent_memory_override_repository import (
    AgentMemoryOverrideRepository,
)
from app.repositories.ai.agent_repository import AdminAgentRepository, AgentRepository
from app.repositories.ai.agent_skill_binding_repository import (
    AgentSkillBindingRepository,
)
from app.repositories.ai.agent_version_repository import AgentVersionRepository
from app.repositories.ai.api_key_repository import ProviderApiKeyRepository
from app.repositories.ai.batch_run_repository import BatchRunRepository
from app.repositories.ai.call_log_repository import AICallLogRepository
from app.repositories.ai.conversation_message_repository import (
    ConversationMessageRepository,
)
from app.repositories.ai.knowledge_base_repository import (
    AdminKnowledgeBaseRepository,
    DocumentChunkRepository,
    KnowledgeBaseRepository,
    KnowledgeDocumentRepository,
)
from app.repositories.ai.model_repository import AIModelRepository
from app.repositories.ai.provider_repository import AIProviderRepository
from app.repositories.ai.skill_repository import AdminSkillRepository, SkillRepository
from app.repositories.ai.table_policy_override_repository import (
    AITablePolicyOverrideRepository,
)
from app.repositories.ai.table_policy_repository import AITablePolicyRepository
from app.repositories.ai.tenant_quota_repository import (
    AdminTenantQuotaRepository,
    TenantQuotaRepository,
)
from app.repositories.ai.tenant_rate_limit_repository import (
    TenantModelRateLimitRepository,
)
from app.repositories.ai.usage_stat_repository import UsageStatRepository

__all__ = [
    "AIProviderRepository",
    "AIModelRepository",
    "ProviderApiKeyRepository",
    "AICallLogRepository",
    "UsageStatRepository",
    "AgentRepository",
    "AdminAgentRepository",
    "AgentConversationRepository",
    "AdminAgentConversationRepository",
    "ConversationMessageRepository",
    "BatchRunRepository",
    "AgentAccessRepository",
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
    "AITablePolicyRepository",
    "AITablePolicyOverrideRepository",
    "SkillRepository",
    "AdminSkillRepository",
    "AgentSkillBindingRepository",
]
