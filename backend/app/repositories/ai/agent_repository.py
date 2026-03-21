"""
智能体 Repository / Agent Repository.

企业级智能体数据访问。
"""

from sqlalchemy import and_, false, func, or_, select, update
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import selectinload

from app.core.base_model import utc_now
from app.core.base_repository import BaseRepository, TenantRepository
from app.enums.agent import (
    AgentExecutionModeEnum,
    AgentPublicationAccessTypeEnum,
    AgentStatusEnum,
)
from app.enums.common import RecycleStageEnum, ResourceScopeEnum
from app.models.ai.agent import Agent
from app.models.ai.agent_conversation import AgentConversation
from app.models.ai.agent_skill_grant import AgentSkillGrant
from app.models.ai.tenant_agent_publication import TenantAgentPublication
from app.repositories.system.resource_tenant_assignment_repository import (
    assigned_resource_ids_subquery,
)
from app.schemas.common.query import FilterRule, QuerySpec


def _tenant_available_condition(tenant_id: int):
    assigned_subq = assigned_resource_ids_subquery("agent", tenant_id)
    platform_visible = or_(
        Agent.scope.in_(
            [
                ResourceScopeEnum.ALL_TENANTS.value,
                ResourceScopeEnum.GLOBAL_SHARED.value,
            ]
        ),
        and_(
            Agent.scope.in_(
                [
                    ResourceScopeEnum.SELECTED_TENANTS.value,
                    ResourceScopeEnum.ADMIN_AND_SELECTED_TENANTS.value,
                ]
            ),
            Agent.id.in_(assigned_subq),
        ),
    )
    return or_(
        Agent.owner_tenant_id == tenant_id,
        and_(Agent.owner_tenant_id.is_(None), platform_visible),
    )


class AgentRepository(TenantRepository[Agent]):
    """
    企业级智能体 Repository / Tenant-scoped Agent repository.

    提供基于企业隔离的智能体数据访问。
    查询时自动包含当前企业可用的平台共享智能体。
    """

    model = Agent

    async def get_by_id(
        self,
        id: int,
        include_deleted: bool = False,
    ) -> Agent | None:
        """根据 ID 获取当前企业可访问的智能体 / Get agent by ID accessible to current tenant."""
        instance = await BaseRepository.get_by_id(self, id, include_deleted)
        if not instance:
            return None
        chk = await self.db.execute(
            select(Agent.id).where(
                Agent.id == id,
                _tenant_available_condition(self.tenant_id),
            )
        )
        return instance if chk.scalar_one_or_none() is not None else None

    async def query_list(
        self,
        spec: QuerySpec,
        scope: str | None = None,
        forced_filters: list[FilterRule] | None = None,
        include_deleted: bool = False,
    ) -> tuple[list[Agent], int]:
        """
        企业级智能体列表查询 / Tenant-scoped agent list query.

        自动注入“企业可用”条件：企业自有 + 平台全量分发 + 平台定向分发。
        """
        allowed_fields = self.get_allowed_fields(scope)
        all_fields = self.get_allowed_fields(None)

        query = select(self.model)

        if not include_deleted:
            query = query.where(self.model.is_deleted.is_(False))

        query = query.where(_tenant_available_condition(self.tenant_id))

        # 应用额外的强制过滤（排除 tenant_id 强制规则）
        extra_forced = [
            f for f in (forced_filters or [])
            if f.field not in ("tenant_id", "owner_tenant_id")
        ]
        if extra_forced:
            query = self._apply_filters(query, extra_forced, all_fields)

        if spec.filters:
            query = self._apply_filters(query, spec.filters, allowed_fields)

        count_query = select(func.count()).select_from(query.subquery())
        count_result = await self.db.execute(count_query)
        total = count_result.scalar() or 0

        sortable_fields = self.get_sortable_fields()
        query = self._apply_sort(query, spec.sort, sortable_fields)
        query = query.offset(spec.offset).limit(spec.limit)
        query = query.options(
            selectinload(Agent.skill_grants).selectinload(AgentSkillGrant.skill),
        )

        result = await self.db.execute(query)
        items = list(result.scalars().all())
        return items, total

    async def query_user_accessible_list(
        self,
        spec: QuerySpec,
        user_id: int,
        user_role_id: int | None = None,
        scope: str | None = None,
        forced_filters: list[FilterRule] | None = None,
    ) -> tuple[list[Agent], int]:
        """
        查询终端用户可访问的智能体列表 / List agents accessible to end users.

        在企业可用范围基础上，强制要求存在启用中的 TenantAgentPublication。
        """
        allowed_fields = self.get_allowed_fields(scope)
        all_fields = self.get_allowed_fields(None)

        query = select(self.model)
        query = query.where(self.model.is_deleted.is_(False))
        query = query.where(_tenant_available_condition(self.tenant_id))
        publication_join_on = and_(
            TenantAgentPublication.tenant_id == self.tenant_id,
            TenantAgentPublication.agent_id == self.model.id,
            TenantAgentPublication.is_deleted.is_(False),
        )
        query = query.join(TenantAgentPublication, publication_join_on)
        query = query.where(self.model.status == AgentStatusEnum.PUBLISHED.value)
        query = query.where(self.model.execution_mode != AgentExecutionModeEnum.ROUTER.value)
        query = query.where(
            or_(
                and_(
                    TenantAgentPublication.enabled_for_users.is_(True),
                    TenantAgentPublication.access_type == AgentPublicationAccessTypeEnum.ALL_USERS.value,
                ),
                and_(
                    TenantAgentPublication.enabled_for_users.is_(True),
                    TenantAgentPublication.access_type == AgentPublicationAccessTypeEnum.SPECIFIC_USERS.value,
                    TenantAgentPublication.tenant_user_ids.cast(JSONB).contains([user_id]),
                ),
                and_(
                    TenantAgentPublication.enabled_for_users.is_(True),
                    TenantAgentPublication.access_type == AgentPublicationAccessTypeEnum.TENANT_USER_ROLES.value,
                    (
                        TenantAgentPublication.tenant_user_role_ids.cast(JSONB).contains([user_role_id])
                        if user_role_id is not None
                        else false()
                    ),
                ),
            )
        )

        extra_forced = [
            f for f in (forced_filters or [])
            if f.field not in ("tenant_id", "owner_tenant_id")
        ]
        if extra_forced:
            query = self._apply_filters(query, extra_forced, all_fields)

        if spec.filters:
            query = self._apply_filters(query, spec.filters, allowed_fields)

        count_query = select(func.count()).select_from(query.subquery())
        count_result = await self.db.execute(count_query)
        total = count_result.scalar() or 0

        sortable_fields = self.get_sortable_fields()
        query = self._apply_sort(query, spec.sort, sortable_fields)
        query = query.offset(spec.offset).limit(spec.limit)
        query = query.options(
            selectinload(Agent.skill_grants).selectinload(AgentSkillGrant.skill),
        )

        result = await self.db.execute(query)
        items = list(result.scalars().unique().all())
        return items, total

    async def list_conversation_memory_cleanup_targets(
        self,
        agent_id: int,
    ) -> list[tuple[int, int]]:
        """列出需要清理记忆的会话 (tenant_id, conversation_id) / List conversations whose session memory should be cleared."""
        result = await self.db.execute(
            select(AgentConversation.tenant_id, AgentConversation.id).where(
                AgentConversation.agent_id == agent_id,
                AgentConversation.is_deleted.is_(False),
            )
        )
        return [
            (int(tenant_id), int(conversation_id))
            for tenant_id, conversation_id in result.all()
        ]

    async def cascade_soft_delete_conversations(
        self, agent_id: int, delete_level: str,
    ) -> None:
        """级联软删除智能体的对话记录 / Cascade soft-delete agent conversations."""
        now = utc_now()
        await self.db.execute(
            update(AgentConversation)
            .where(
                AgentConversation.agent_id == agent_id,
                AgentConversation.is_deleted.is_(False),
            )
            .values(
                is_deleted=True,
                deleted_at=now,
                delete_level=delete_level,
                recycle_stage=RecycleStageEnum.MODULE.value,
                promoted_to_global_at=None,
                updated_at=now,
            )
        )

    async def cascade_promote_conversations(self, agent_id: int) -> None:
        """级联推进对话记录到总回收站 / Cascade promote conversations to global recycle bin."""
        now = utc_now()
        await self.db.execute(
            update(AgentConversation)
            .where(
                AgentConversation.agent_id == agent_id,
                AgentConversation.is_deleted.is_(True),
            )
            .values(
                recycle_stage=RecycleStageEnum.GLOBAL.value,
                promoted_to_global_at=now,
                updated_at=now,
            )
        )

    async def cascade_escalate_conversations(self, agent_id: int) -> None:
        """兼容旧接口：升级删除 → 推进总回收站 / Backward-compatible alias for cascade_promote_conversations."""
        await self.cascade_promote_conversations(agent_id)

    async def cascade_restore_conversations(self, agent_id: int) -> None:
        """级联恢复对话记录 / Cascade restore conversations."""
        now = utc_now()
        await self.db.execute(
            update(AgentConversation)
            .where(
                AgentConversation.agent_id == agent_id,
                AgentConversation.is_deleted.is_(True),
            )
            .values(
                is_deleted=False,
                deleted_at=None,
                delete_level=None,
                recycle_stage=None,
                promoted_to_global_at=None,
                updated_at=now,
            )
        )

    async def get_by_status(
        self,
        status: str,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Agent]:
        """
        按状态获取智能体列表（包含全局智能体）/ Get agents by status (including global).

        Args:
            status: 智能体状态
            skip: 跳过数量
            limit: 返回数量

        Returns:
            Agent 列表
        """
        stmt = (
            select(Agent)
            .where(
                and_(
                    _tenant_available_condition(self.tenant_id),
                    Agent.status == status,
                    Agent.is_deleted.is_(False),
                )
            )
            .order_by(Agent.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_published_agents(
        self,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Agent]:
        """
        获取已发布的智能体列表 / Get published agents list.

        Args:
            skip: 跳过数量
            limit: 返回数量

        Returns:
            已发布的 Agent 列表
        """
        from app.enums.agent import AgentStatusEnum

        return await self.get_by_status(
            AgentStatusEnum.PUBLISHED.value, skip, limit
        )

    async def get_by_name(
        self,
        name: str,
        exclude_id: int | None = None,
    ) -> Agent | None:
        """
        按名称查找智能体（同企业内唯一性检查）/ Find agent by name (uniqueness within tenant).

        Args:
            name: 智能体名称
            exclude_id: 排除的 ID（用于更新时排除自身）

        Returns:
            Agent 实例或 None
        """
        conditions = [
            Agent.owner_tenant_id == self.tenant_id,
            Agent.name == name,
            Agent.is_deleted.is_(False),
        ]
        if exclude_id is not None:
            conditions.append(Agent.id != exclude_id)

        stmt = select(Agent).where(and_(*conditions))
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()


class AdminAgentRepository(BaseRepository[Agent]):
    """
    管理端智能体 Repository / Admin-scoped agent repository.

    无企业隔离，供平台管理端全局查询使用
    """

    model = Agent

    async def list_conversation_memory_cleanup_targets(
        self,
        agent_id: int,
    ) -> list[tuple[int, int]]:
        """列出需要清理记忆的会话 (tenant_id, conversation_id) / List conversations whose session memory should be cleared."""
        result = await self.db.execute(
            select(AgentConversation.tenant_id, AgentConversation.id).where(
                AgentConversation.agent_id == agent_id,
                AgentConversation.is_deleted.is_(False),
            )
        )
        return [
            (int(tenant_id), int(conversation_id))
            for tenant_id, conversation_id in result.all()
        ]

    async def cascade_soft_delete_conversations(
        self, agent_id: int, delete_level: str,
    ) -> None:
        """级联软删除智能体的对话记录 / Cascade soft-delete agent conversations."""
        now = utc_now()
        await self.db.execute(
            update(AgentConversation)
            .where(
                AgentConversation.agent_id == agent_id,
                AgentConversation.is_deleted.is_(False),
            )
            .values(
                is_deleted=True,
                deleted_at=now,
                delete_level=delete_level,
                recycle_stage=RecycleStageEnum.MODULE.value,
                promoted_to_global_at=None,
                updated_at=now,
            )
        )

    async def cascade_promote_conversations(self, agent_id: int) -> None:
        """级联推进对话记录到总回收站 / Cascade promote conversations to global recycle bin."""
        now = utc_now()
        await self.db.execute(
            update(AgentConversation)
            .where(
                AgentConversation.agent_id == agent_id,
                AgentConversation.is_deleted.is_(True),
            )
            .values(
                recycle_stage=RecycleStageEnum.GLOBAL.value,
                promoted_to_global_at=now,
                updated_at=now,
            )
        )

    async def cascade_restore_conversations(self, agent_id: int) -> None:
        """级联恢复对话记录 / Cascade restore conversations."""
        now = utc_now()
        await self.db.execute(
            update(AgentConversation)
            .where(
                AgentConversation.agent_id == agent_id,
                AgentConversation.is_deleted.is_(True),
            )
            .values(
                is_deleted=False,
                deleted_at=None,
                delete_level=None,
                recycle_stage=None,
                promoted_to_global_at=None,
                updated_at=now,
            )
        )

    async def exists_by_name(
        self,
        name: str,
        owner_tenant_id: int | None,
        exclude_id: int | None = None,
    ) -> Agent | None:
        """检查同 owner_tenant_id 下名称是否重复 / Check name duplicate under same owner tenant."""
        conditions = [
            Agent.name == name,
            Agent.is_deleted.is_(False),
        ]
        if owner_tenant_id is not None:
            conditions.append(Agent.owner_tenant_id == owner_tenant_id)
        else:
            conditions.append(Agent.owner_tenant_id.is_(None))
        if exclude_id is not None:
            conditions.append(Agent.id != exclude_id)

        stmt = select(Agent).where(and_(*conditions))
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def query_list(
        self,
        spec: QuerySpec,
        scope: str | None = None,
        forced_filters: list[FilterRule] | None = None,
        include_deleted: bool = False,
    ) -> tuple[list[Agent], int]:
        """Override to eager load skill grants."""
        allowed_fields = self.get_allowed_fields(scope)
        all_fields = self.get_allowed_fields(None)

        query = select(self.model)

        if not include_deleted:
            query = query.where(self.model.is_deleted.is_(False))

        if forced_filters:
            query = self._apply_filters(query, forced_filters, all_fields)

        if spec.filters:
            query = self._apply_filters(query, spec.filters, allowed_fields)

        count_query = select(func.count()).select_from(query.subquery())
        count_result = await self.db.execute(count_query)
        total = count_result.scalar() or 0

        sortable_fields = self.get_sortable_fields()
        query = self._apply_sort(query, spec.sort, sortable_fields)
        query = query.offset(spec.offset).limit(spec.limit)
        query = query.options(
            selectinload(Agent.skill_grants).selectinload(AgentSkillGrant.skill),
        )

        result = await self.db.execute(query)
        items = list(result.scalars().all())
        return items, total


__all__ = ["AgentRepository", "AdminAgentRepository"]
