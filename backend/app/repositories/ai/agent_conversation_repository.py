"""
智能体对话 Repository / Agent Conversation Repository
"""


from sqlalchemy import and_, func, select

from app.core.base_repository import BaseRepository, TenantRepository
from app.models.ai.agent_conversation import AgentConversation


class AgentConversationRepository(TenantRepository[AgentConversation]):
    """
    企业级智能体对话 Repository / Tenant-scoped agent conversation repository.

    提供按智能体、按状态查询等方法
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

        # 总数 / Total count
        count_stmt = select(func.count(AgentConversation.id)).where(base_cond)
        count_result = await self.db.execute(count_stmt)
        total = count_result.scalar() or 0

        # 列表 / List rows
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

class AdminAgentConversationRepository(BaseRepository[AgentConversation]):
    """
    平台级智能体对话 Repository（无企业过滤）/ Admin-level agent conversation repo (no tenant filter).

    供管理端全企业只读审计使用
    """

    model = AgentConversation


__all__ = ["AgentConversationRepository", "AdminAgentConversationRepository"]
