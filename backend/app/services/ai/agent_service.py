"""
智能体 Service / Agent Service
"""

from __future__ import annotations

import inspect
from typing import TYPE_CHECKING, Any

from app.configs.service import PLATFORM_TENANT_ID
from app.core.base_service import GlobalService, TenantService
from app.core.i18n import _
from app.enums.common import UserRoleEnum
from app.exceptions import BusinessException
from app.models.ai.agent import Agent
from app.repositories.ai import AIModelRepository
from app.repositories.ai.agent_access_repository import AgentAccessRepository
from app.repositories.ai.agent_memory_override_repository import (
    AgentMemoryOverrideRepository,
)
from app.repositories.ai.agent_repository import AdminAgentRepository, AgentRepository
from app.repositories.ai.agent_version_repository import AgentVersionRepository
from app.repositories.ai.tenant_agent_publication_repository import (
    TenantAgentPublicationRepository,
)
from app.services.ai import agent_service_access as access_part
from app.services.ai import agent_service_admin as admin_part
from app.services.ai import agent_service_lifecycle as lifecycle_part
from app.services.ai import agent_service_memory as memory_part
from app.services.ai import agent_service_versioning as versioning_part
from app.services.ai.agent_service_support import (
    VERSION_SNAPSHOT_FIELDS as _VERSION_SNAPSHOT_FIELDS,
    audience_allows_role as _audience_allows_role,
    clear_cascaded_conversation_memories as _clear_cascaded_conversation_memories,
    normalize_agent_rag_config as _normalize_agent_rag_config,
    role_ids_allow as _role_ids_allow,
)

if TYPE_CHECKING:
    from app.schemas.common.query import QuerySpec


async def _validate_agent_max_tokens_against_model(
    db: Any,
    *,
    model_id: int | None,
    max_tokens: int | None,
) -> None:
    """Ensure agent max_tokens does not exceed model max_output_tokens / 校验智能体 max_tokens 不超过模型 max_output_tokens."""
    if model_id is None or max_tokens is None:
        return

    model_repo = AIModelRepository(db)
    model = await model_repo.get_by_id(model_id)
    if inspect.isawaitable(model):
        model = await model
    if not model:
        return

    model_limit = getattr(model, "max_output_tokens", None)
    if inspect.isawaitable(model_limit):
        model_limit = await model_limit
    if model_limit is None or max_tokens <= model_limit:
        return

    model_name = getattr(model, "name", model_id)
    if inspect.isawaitable(model_name):
        model_name = await model_name

    raise BusinessException(
        message=_("agent.error.max_tokens_exceeds_model_limit").format(
            max_tokens=max_tokens,
            model_limit=model_limit,
            model_name=model_name,
        ),
    )


class AgentService(TenantService[Agent, AgentRepository]):
    """智能体 Service / Agent service."""

    model = Agent
    repository_class = AgentRepository

    def _resolve_version_tenant_id(self) -> int:
        return versioning_part.resolve_version_tenant_id(self.tenant_id)

    def _get_version_repo(self) -> AgentVersionRepository:
        return AgentVersionRepository(self.db, self._resolve_version_tenant_id())

    async def _snapshot_skill_grants(self, agent_id: int) -> list[dict[str, Any]]:
        return await versioning_part.snapshot_skill_grants(self, agent_id)

    async def _restore_skill_grants(
        self,
        agent_id: int,
        grants_snapshot: list[dict[str, Any]] | None,
    ) -> None:
        await versioning_part.restore_skill_grants(self, agent_id, grants_snapshot)

    def _get_access_repo(self) -> AgentAccessRepository:
        return AgentAccessRepository(self.db, self.tenant_id)

    def _get_publication_repo(self) -> TenantAgentPublicationRepository:
        return TenantAgentPublicationRepository(self.db, self.tenant_id)

    def _get_memory_override_repo(self) -> AgentMemoryOverrideRepository:
        return AgentMemoryOverrideRepository(self.db, self.tenant_id)

    async def _get_platform_default_memory_enabled(self) -> bool:
        return await memory_part.get_platform_default_memory_enabled(self.db)

    async def resolve_memory_effective_config(self, agent_id: int) -> dict[str, bool]:
        return await memory_part.resolve_memory_effective_config(self, agent_id)

    async def get_memory_config(self, agent_id: int) -> dict[str, Any]:
        return await memory_part.get_memory_config(self, agent_id)

    async def set_memory_disabled(
        self,
        agent_id: int,
        disabled: bool,
    ) -> dict[str, Any]:
        return await memory_part.set_memory_disabled(self, agent_id, disabled)

    async def _before_create(self, data: dict[str, Any]) -> None:
        await super()._before_create(data)
        await lifecycle_part.tenant_before_create(self, data)

    async def _after_create(self, instance: Agent) -> None:
        await super()._after_create(instance)
        await lifecycle_part.tenant_after_create(self, instance)

    async def _before_update(self, id: int, data: dict[str, Any]) -> None:
        await super()._before_update(id, data)
        await lifecycle_part.tenant_before_update(self, id, data)

    async def _after_update(self, instance: Agent) -> None:
        await super()._after_update(instance)
        await lifecycle_part.tenant_after_update(self, instance)

    async def _before_delete(self, id: int) -> None:
        await super()._before_delete(id)
        await lifecycle_part.tenant_before_delete(self, id)

    async def _after_delete(self, instance: Agent) -> None:
        await super()._after_delete(instance)
        await lifecycle_part.tenant_after_delete(self, instance)

    async def promote_to_global(self, id: int) -> Agent | None:
        return await lifecycle_part.promote_to_global(self, id)

    async def _after_restore(self, instance: Agent) -> None:
        await lifecycle_part.after_restore(self, instance)

    async def get_agent_detail(self, agent_id: int) -> dict[str, Any]:
        return await lifecycle_part.get_agent_detail(self, agent_id)

    async def publish_agent(
        self,
        agent_id: int,
        change_log: str | None = None,
        created_by: int | None = None,
    ) -> Agent:
        return await versioning_part.publish_agent(
            self,
            agent_id,
            change_log,
            created_by,
        )

    async def rollback_agent(
        self,
        agent_id: int,
        version: int,
    ) -> Agent:
        return await versioning_part.rollback_agent(self, agent_id, version)

    async def get_versions(self, agent_id: int) -> list[dict[str, Any]]:
        return await versioning_part.get_versions(self, agent_id)

    async def get_version_detail(self, agent_id: int, version: int) -> dict[str, Any]:
        return await versioning_part.get_version_detail(self, agent_id, version)

    async def diff_versions(
        self,
        agent_id: int,
        v1: int,
        v2: int,
    ) -> dict[str, Any]:
        return await versioning_part.diff_versions(self, agent_id, v1, v2)

    async def get_access_config(self, agent_id: int) -> dict[str, Any]:
        return await access_part.get_access_config(self, agent_id)

    async def update_access_config(
        self,
        agent_id: int,
        patch: dict[str, Any],
    ) -> dict[str, Any]:
        return await access_part.update_access_config(self, agent_id, patch)

    async def get_publication_config(self, agent_id: int) -> dict[str, Any]:
        return await access_part.get_publication_config(self, agent_id)

    async def update_publication_config(
        self,
        agent_id: int,
        *,
        enabled_for_users: bool,
        access_type: str,
        tenant_user_role_ids: list[int] | None = None,
        tenant_user_ids: list[int] | None = None,
        org_node_ids: list[int] | None = None,
        published_by: int | None = None,
    ) -> dict[str, Any]:
        return await access_part.update_publication_config(
            self,
            agent_id,
            enabled_for_users=enabled_for_users,
            access_type=access_type,
            tenant_user_role_ids=tenant_user_role_ids,
            tenant_user_ids=tenant_user_ids,
            org_node_ids=org_node_ids,
            published_by=published_by,
        )

    def _publication_allows_user(
        self,
        publication: Any | None,
        *,
        user_id: int,
        user_role_id: int | None = None,
    ) -> bool:
        return access_part.publication_allows_user(
            publication,
            user_id=user_id,
            user_role_id=user_role_id,
        )

    async def check_user_access(
        self,
        agent_id: int,
        user_id: int,
        user_role: str = UserRoleEnum.TENANT_USER.value,
        user_role_id: int | None = None,
    ) -> bool:
        return await access_part.check_user_access(
            self,
            agent_id,
            user_id,
            user_role,
            user_role_id,
        )

    async def list_user_accessible_agents(
        self,
        user_id: int,
        user_role_id: int | None,
        spec: QuerySpec,
    ) -> tuple[list[Agent], int]:
        return await access_part.list_user_accessible_agents(
            self,
            user_id,
            user_role_id,
            spec,
        )

    async def build_usage_attribution_context(
        self,
        *,
        agent: Agent,
        user_id: int | None,
        user_role: str,
        user_role_id: int | None = None,
    ) -> dict[str, Any]:
        return await access_part.build_usage_attribution_context(
            self,
            agent=agent,
            user_id=user_id,
            user_role=user_role,
            user_role_id=user_role_id,
        )


class AdminAgentService(GlobalService[Agent, AdminAgentRepository]):
    """平台管理端智能体 Service / Admin agent service."""

    model = Agent
    repository_class = AdminAgentRepository

    @staticmethod
    def _validate_resource_scope(scope: str | None) -> str:
        return admin_part.validate_resource_scope(scope)

    async def _get_platform_default_memory_enabled(self) -> bool:
        return await memory_part.get_platform_default_memory_enabled(self.db)

    async def get_memory_config(self, agent_id: int) -> dict[str, Any]:
        return await memory_part.get_admin_memory_config(self, agent_id)

    async def set_memory_enabled(
        self,
        agent_id: int,
        enabled: bool,
    ) -> dict[str, Any]:
        return await memory_part.set_memory_enabled(self, agent_id, enabled)

    async def _before_create(self, data: dict[str, Any]) -> None:
        await super()._before_create(data)
        await admin_part.before_create(self, data)

    async def _before_update(self, id: int, data: dict[str, Any]) -> None:
        await super()._before_update(id, data)
        await admin_part.before_update(self, id, data)

    async def query_list(self, query: QuerySpec) -> tuple[list[Agent], int]:
        return await admin_part.query_list(self, query)

    async def _before_delete(self, id: int) -> None:
        await super()._before_delete(id)
        await admin_part.before_delete(self, id)

    async def promote_to_global(self, id: int) -> Agent | None:
        return await lifecycle_part.promote_to_global(self, id)

    async def _after_restore(self, instance: Agent) -> None:
        await lifecycle_part.after_restore(self, instance)

    def _get_platform_access_repo(self) -> AgentAccessRepository:
        return AgentAccessRepository(self.db, PLATFORM_TENANT_ID)

    async def get_access_config(self, agent_id: int) -> dict[str, Any]:
        return await admin_part.get_access_config(self, agent_id)

    async def update_access_config(
        self,
        agent_id: int,
        patch: dict[str, Any],
    ) -> dict[str, Any]:
        return await admin_part.update_access_config(self, agent_id, patch)

    async def build_usage_attribution_context(
        self,
        *,
        agent: Agent,
        user_id: int | None,
        user_role: str,
        user_role_id: int | None = None,
    ) -> dict[str, Any]:
        return await admin_part.build_usage_attribution_context(
            self,
            agent=agent,
            user_id=user_id,
            user_role=user_role,
            user_role_id=user_role_id,
        )

    async def update_status(self, agent_id: int, status: str) -> Agent:
        return await admin_part.update_status(self, agent_id, status)


__all__ = ["AgentService", "AdminAgentService"]
