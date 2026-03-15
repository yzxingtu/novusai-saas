"""
智能体对话 Repository / Agent Conversation Repository
"""

from datetime import date, datetime

from sqlalchemy import and_, func, select, update

from app.core.base_repository import BaseRepository, TenantRepository
from app.enums.agent import ConversationStatusEnum
from app.models.ai.agent_conversation import AgentConversation


class AgentConversationRepository(TenantRepository[AgentConversation]):
    """
    企业级智能体对话 Repository / Tenant-scoped agent conversation repository.

    提供按智能体、按状态查询，批量归档等方法
    """

    model = AgentConversation

    async def get_by_agent(
        self,
        agent_id: int,
        skip: int = 0,
        limit: int = 50,
    ) -> list[AgentConversation]:
        """
        按智能体获取对话列表 / Get conversation list by agent.

        Args:
            agent_id: 智能体 ID
            skip: 跳过数量
            limit: 返回数量

        Returns:
            AgentConversation 列表
        """
        stmt = (
            select(AgentConversation)
            .where(
                and_(
                    AgentConversation.tenant_id == self.tenant_id,
                    AgentConversation.agent_id == agent_id,
                    AgentConversation.is_deleted.is_(False),
                )
            )
            .order_by(AgentConversation.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def search_by_title(
        self,
        keyword: str,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[AgentConversation], int]:
        """
        按标题模糊搜索对话 / Search conversations by title (fuzzy).

        Args:
            keyword: 搜索关键词
            skip: 跳过数量
            limit: 返回数量

        Returns:
            (AgentConversation 列表, 总数)
        """
        # 转义 LIKE 通配符防止用户输入的 % 和 _ 被误当通配符
        escaped = keyword.replace("%", "\\%").replace("_", "\\_")
        base_cond = and_(
            AgentConversation.tenant_id == self.tenant_id,
            AgentConversation.is_deleted.is_(False),
            AgentConversation.title.ilike(f"%{escaped}%"),
        )

        # 总数
        count_stmt = select(func.count(AgentConversation.id)).where(base_cond)
        count_result = await self.db.execute(count_stmt)
        total = count_result.scalar() or 0

        # 列表
        stmt = (
            select(AgentConversation)
            .where(base_cond)
            .order_by(AgentConversation.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        items = list(result.scalars().all())

        return items, total

    async def get_conversations_before(
        self,
        before_date: date,
        agent_id: int | None = None,
    ) -> list[AgentConversation]:
        """
        获取指定日期前的 active 对话（用于批量归档）/ Get active conversations before date (for batch archive).

        Args:
            before_date: 截止日期
            agent_id: 可选，按智能体过滤

        Returns:
            AgentConversation 列表
        """
        before_dt = datetime.combine(before_date, datetime.min.time())

        conditions = [
            AgentConversation.tenant_id == self.tenant_id,
            AgentConversation.is_deleted.is_(False),
            AgentConversation.status == ConversationStatusEnum.ACTIVE.value,
            AgentConversation.updated_at < before_dt,
        ]

        if agent_id is not None:
            conditions.append(AgentConversation.agent_id == agent_id)

        stmt = select(AgentConversation).where(and_(*conditions))
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_conversation_ids_before(
        self,
        before_date: date,
        agent_id: int | None = None,
        batch_size: int = 1000,
    ) -> list[int]:
        """
        获取指定日期前的 active 对话 ID 列表（仅查 ID，避免全量加载 ORM 对象）/ Get active conversation IDs before date (IDs only).

        Args:
            before_date: 截止日期
            agent_id: 可选，按智能体过滤
            batch_size: 每批最大查询数量

        Returns:
            对话 ID 列表
        """
        before_dt = datetime.combine(before_date, datetime.min.time())

        conditions = [
            AgentConversation.tenant_id == self.tenant_id,
            AgentConversation.is_deleted.is_(False),
            AgentConversation.status == ConversationStatusEnum.ACTIVE.value,
            AgentConversation.updated_at < before_dt,
        ]

        if agent_id is not None:
            conditions.append(AgentConversation.agent_id == agent_id)

        stmt = (
            select(AgentConversation.id)
            .where(and_(*conditions))
            .order_by(AgentConversation.id)
            .limit(batch_size)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def batch_update_status(
        self,
        ids: list[int],
        status: str,
    ) -> int:
        """
        批量更新对话状态 / Batch update conversation status.

        Args:
            ids: 对话 ID 列表
            status: 目标状态

        Returns:
            更新的记录数
        """
        if not ids:
            return 0

        stmt = (
            update(AgentConversation)
            .where(
                and_(
                    AgentConversation.tenant_id == self.tenant_id,
                    AgentConversation.id.in_(ids),
                    AgentConversation.is_deleted.is_(False),
                )
            )
            .values(status=status)
        )
        result = await self.db.execute(stmt)
        return result.rowcount


class AdminAgentConversationRepository(BaseRepository[AgentConversation]):
    """
    平台级智能体对话 Repository（无企业过滤）/ Admin-level agent conversation repo (no tenant filter).

    供管理端全企业只读审计使用
    """

    model = AgentConversation


__all__ = ["AgentConversationRepository", "AdminAgentConversationRepository"]
