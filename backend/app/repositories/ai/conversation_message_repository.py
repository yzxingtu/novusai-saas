"""
对话消息 Repository / Conversation Message Repository
"""


from sqlalchemy import and_, func, select

from app.core.base_repository import TenantRepository
from app.models.ai.conversation_message import ConversationMessage


class ConversationMessageRepository(TenantRepository[ConversationMessage]):
    """
    租户级对话消息 Repository

    提供按对话获取消息、追加消息、统计等方法
    """

    model = ConversationMessage

    async def get_by_conversation(
        self,
        conversation_id: int,
        skip: int = 0,
        limit: int = 200,
    ) -> list[ConversationMessage]:
        """
        获取对话的消息列表（按 sequence 升序）

        Args:
            conversation_id: 对话 ID
            skip: 跳过数量
            limit: 返回数量

        Returns:
            ConversationMessage 列表
        """
        stmt = (
            select(ConversationMessage)
            .where(
                and_(
                    ConversationMessage.tenant_id == self.tenant_id,
                    ConversationMessage.conversation_id == conversation_id,
                    ConversationMessage.is_deleted.is_(False),
                )
            )
            .order_by(ConversationMessage.sequence.asc())
            .offset(skip)
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_next_sequence(self, conversation_id: int) -> int:
        """
        获取对话的下一个消息序号

        Args:
            conversation_id: 对话 ID

        Returns:
            下一个 sequence 值
        """
        stmt = select(func.max(ConversationMessage.sequence)).where(
            and_(
                ConversationMessage.tenant_id == self.tenant_id,
                ConversationMessage.conversation_id == conversation_id,
                ConversationMessage.is_deleted.is_(False),
            )
        )
        result = await self.db.execute(stmt)
        max_seq = result.scalar()
        return (max_seq or 0) + 1

    async def get_token_sum(self, conversation_id: int) -> int:
        """
        统计对话的总 token 数

        Args:
            conversation_id: 对话 ID

        Returns:
            token 总数
        """
        stmt = select(func.sum(ConversationMessage.token_count)).where(
            and_(
                ConversationMessage.tenant_id == self.tenant_id,
                ConversationMessage.conversation_id == conversation_id,
                ConversationMessage.is_deleted.is_(False),
            )
        )
        result = await self.db.execute(stmt)
        return result.scalar() or 0

    async def count_by_conversation(self, conversation_id: int) -> int:
        """
        统计对话的消息数量

        Args:
            conversation_id: 对话 ID

        Returns:
            消息数量
        """
        stmt = select(func.count(ConversationMessage.id)).where(
            and_(
                ConversationMessage.tenant_id == self.tenant_id,
                ConversationMessage.conversation_id == conversation_id,
                ConversationMessage.is_deleted.is_(False),
            )
        )
        result = await self.db.execute(stmt)
        return result.scalar() or 0

    async def search_by_content(
        self,
        keyword: str,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[ConversationMessage], int]:
        """
        跨对话消息内容全文搜索（ilike）

        Args:
            keyword: 搜索关键词
            skip: 跳过数量
            limit: 返回数量

        Returns:
            (ConversationMessage 列表, 总数)
        """
        # 转义 LIKE 通配符防止用户输入的 % 和 _ 被误当通配符
        escaped = keyword.replace("%", "\\%").replace("_", "\\_")
        base_cond = and_(
            ConversationMessage.tenant_id == self.tenant_id,
            ConversationMessage.is_deleted.is_(False),
            ConversationMessage.content.ilike(f"%{escaped}%"),
        )

        # 总数
        count_stmt = select(func.count(ConversationMessage.id)).where(base_cond)
        count_result = await self.db.execute(count_stmt)
        total = count_result.scalar() or 0

        # 列表
        stmt = (
            select(ConversationMessage)
            .where(base_cond)
            .order_by(ConversationMessage.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        items = list(result.scalars().all())

        return items, total

    async def get_last_n_messages(
        self,
        conversation_id: int,
        n: int = 10,
    ) -> list[ConversationMessage]:
        """
        获取对话最近 N 条消息（用于构建上下文窗口）

        Args:
            conversation_id: 对话 ID
            n: 消息数量

        Returns:
            ConversationMessage 列表（按 sequence 升序）
        """
        # 先取最新 N 条（倒序），再翻转为正序
        stmt = (
            select(ConversationMessage)
            .where(
                and_(
                    ConversationMessage.tenant_id == self.tenant_id,
                    ConversationMessage.conversation_id == conversation_id,
                    ConversationMessage.is_deleted.is_(False),
                )
            )
            .order_by(ConversationMessage.sequence.desc())
            .limit(n)
        )
        result = await self.db.execute(stmt)
        messages = list(result.scalars().all())
        messages.reverse()
        return messages


__all__ = ["ConversationMessageRepository"]
