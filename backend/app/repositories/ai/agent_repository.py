"""
智能体 Repository
"""

from typing import List


from sqlalchemy import select, and_, or_, func, update
from sqlalchemy.orm import selectinload

from app.models.ai.agent import Agent
from app.models.ai.agent_conversation import AgentConversation
from app.core.base_repository import TenantRepository, BaseRepository
from app.enums.common import DeleteLevelEnum, ResourceScopeEnum
from app.repositories.system.resource_tenant_assignment_repository import assigned_resource_ids_subquery
from app.schemas.common.query import QuerySpec, FilterRule
from app.core.base_model import utc_now

_ASSIGNED_SCOPES = (
    ResourceScopeEnum.ASSIGNED_TENANTS.value,
    ResourceScopeEnum.ADMIN_AND_ASSIGNED.value,
)


class AgentRepository(TenantRepository[Agent]):
    """
    租户级智能体 Repository

    提供基于租户隔离的智能体数据访问。
    查询时自动包含 scope=global 的全局智能体。
    """

    model = Agent

    async def get_by_id(
        self,
        id: int,
        include_deleted: bool = False,
    ) -> Agent | None:
        """根据 ID 获取智能体，允许访问全局 + 已分配的智能体"""
        instance = await BaseRepository.get_by_id(self, id, include_deleted)
        if instance and hasattr(instance, "tenant_id"):
            # 全局共享
            if instance.scope == ResourceScopeEnum.ADMIN_AND_ALL.value:
                return instance
            # 已分配 scope：检查 resource_tenant_assignments
            if instance.scope in _ASSIGNED_SCOPES:
                from app.repositories.system.resource_tenant_assignment_repository import ResourceTenantAssignmentRepository
                repo = ResourceTenantAssignmentRepository(self.db)
                if await repo.check_assignment("agent", instance.id, self.tenant_id):
                    return instance
                return None
            # 同租户
            if instance.tenant_id == self.tenant_id:
                return instance
            return None
        return instance

    async def query_list(
        self,
        spec: QuerySpec,
        scope: str | None = None,
        forced_filters: list[FilterRule] | None = None,
        include_deleted: bool = False,
    ) -> tuple[list[Agent], int]:
        """
        租户级智能体列表查询

        自动注入条件：(tenant_id = X) OR (scope = 'admin_and_all')
        """
        allowed_fields = self.get_allowed_fields(scope)
        all_fields = self.get_allowed_fields(None)

        query = select(self.model)

        if not include_deleted:
            query = query.where(self.model.is_deleted.is_(False))

        # 替代 TenantRepository 的 tenant_id 强制过滤：包含全局 + 已分配资源
        assigned_subq = assigned_resource_ids_subquery("agent", self.tenant_id)
        query = query.where(
            or_(
                self.model.tenant_id == self.tenant_id,
                self.model.scope == ResourceScopeEnum.ADMIN_AND_ALL.value,
                and_(
                    self.model.scope.in_(_ASSIGNED_SCOPES),
                    self.model.id.in_(assigned_subq),
                ),
            )
        )

        # 应用额外的强制过滤（排除 tenant_id 强制规则）
        extra_forced = [
            f for f in (forced_filters or [])
            if f.field != "tenant_id"
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
        query = query.options(selectinload(Agent.skill_bindings))

        result = await self.db.execute(query)
        items = list(result.scalars().all())
        return items, total

    async def cascade_soft_delete_conversations(
        self, agent_id: int, delete_level: str,
    ) -> None:
        """级联软删除智能体的对话记录"""
        now = utc_now()
        await self.db.execute(
            update(AgentConversation)
            .where(
                AgentConversation.agent_id == agent_id,
                AgentConversation.is_deleted.is_(False),
            )
            .values(is_deleted=True, deleted_at=now, delete_level=delete_level, updated_at=now)
        )

    async def cascade_escalate_conversations(self, agent_id: int) -> None:
        """级联升级对话记录的删除层级"""
        now = utc_now()
        await self.db.execute(
            update(AgentConversation)
            .where(
                AgentConversation.agent_id == agent_id,
                AgentConversation.is_deleted.is_(True),
            )
            .values(delete_level=DeleteLevelEnum.ADMIN.value, deleted_at=now, updated_at=now)
        )

    async def cascade_restore_conversations(self, agent_id: int) -> None:
        """级联恢复对话记录"""
        now = utc_now()
        await self.db.execute(
            update(AgentConversation)
            .where(
                AgentConversation.agent_id == agent_id,
                AgentConversation.is_deleted.is_(True),
            )
            .values(is_deleted=False, deleted_at=None, delete_level=None, updated_at=now)
        )

    async def get_by_status(
        self,
        status: str,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Agent]:
        """
        按状态获取智能体列表（包含全局智能体）

        Args:
            status: 智能体状态
            skip: 跳过数量
            limit: 返回数量

        Returns:
            Agent 列表
        """
        assigned_subq = assigned_resource_ids_subquery("agent", self.tenant_id)
        stmt = (
            select(Agent)
            .where(
                and_(
                    or_(
                        Agent.tenant_id == self.tenant_id,
                        Agent.scope == ResourceScopeEnum.ADMIN_AND_ALL.value,
                        and_(
                            Agent.scope.in_(_ASSIGNED_SCOPES),
                            Agent.id.in_(assigned_subq),
                        ),
                    ),
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
    ) -> List[Agent]:
        """
        获取已发布的智能体列表

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
        按名称查找智能体（同租户内唯一性检查）

        Args:
            name: 智能体名称
            exclude_id: 排除的 ID（用于更新时排除自身）

        Returns:
            Agent 实例或 None
        """
        conditions = [
            Agent.tenant_id == self.tenant_id,
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
    管理端智能体 Repository

    无租户隔离，供平台管理端全局查询使用
    """

    model = Agent

    async def cascade_soft_delete_conversations(
        self, agent_id: int, delete_level: str,
    ) -> None:
        """级联软删除智能体的对话记录"""
        now = utc_now()
        await self.db.execute(
            update(AgentConversation)
            .where(
                AgentConversation.agent_id == agent_id,
                AgentConversation.is_deleted.is_(False),
            )
            .values(is_deleted=True, deleted_at=now, delete_level=delete_level, updated_at=now)
        )

    async def exists_by_name(
        self,
        name: str,
        tenant_id: int | None,
        scope: str,
        exclude_id: int | None = None,
    ) -> Agent | None:
        """检查同 scope+tenant_id 下名称是否重复"""
        conditions = [
            Agent.name == name,
            Agent.scope == scope,
            Agent.is_deleted.is_(False),
        ]
        if tenant_id is not None:
            conditions.append(Agent.tenant_id == tenant_id)
        else:
            conditions.append(Agent.tenant_id.is_(None))
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
        """重写以 eager load skill_bindings"""
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
        query = query.options(selectinload(Agent.skill_bindings))

        result = await self.db.execute(query)
        items = list(result.scalars().all())
        return items, total


__all__ = ["AgentRepository", "AdminAgentRepository"]
