from app.ai.agent_quota_concurrency import AgentConcurrencyLimiter
from app.ai.agent_quota_manager import AgentQuotaManager
from app.ai.agent_stats import AgentStatsManager
from app.ai.engine.base import BaseEngine
from app.core.database import async_session_factory
from app.services.ai.agent_chat_stream_runtime_dependencies import (
    default_agent_chat_stream_persistence_dependencies,
)
from app.services.ai.conversation_service import ConversationService


def test_default_stream_runtime_dependencies_bind_real_runtime_owners() -> None:
    dependencies = default_agent_chat_stream_persistence_dependencies()

    assert dependencies.session_factory is async_session_factory
    assert dependencies.conversation_service_cls is ConversationService
    assert dependencies.adjust_usage is AgentQuotaManager.adjust_usage
    assert dependencies.record_user_usage is AgentQuotaManager.record_user_usage
    assert dependencies.record_chat_stats is AgentStatsManager.record_chat
    assert dependencies.release_concurrency is AgentConcurrencyLimiter.release
    assert (
        dependencies.publish_execution_completed
        is BaseEngine._publish_execution_completed
    )
    assert dependencies.publish_execution_failed is BaseEngine._publish_execution_failed
