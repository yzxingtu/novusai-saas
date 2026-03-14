"""
AI 表策略 Repository / AI Table Policy Repository

提供 AI 表策略的数据访问功能（平台级，无 tenant_id）
Provides AI table policy data access (platform-level, no tenant_id).
"""

from sqlalchemy import select, text

from app.core.base_repository import BaseRepository
from app.models.ai.table_policy import AITablePolicy


class AITablePolicyRepository(BaseRepository[AITablePolicy]):
    """
    AI 表策略 Repository

    继承 BaseRepository（平台级资源，无企业隔离）
    """

    model = AITablePolicy

    async def get_active_by_table_name(self, table_name: str) -> AITablePolicy | None:
        """按表名获取激活的策略"""
        stmt = select(AITablePolicy).where(
            AITablePolicy.table_name == table_name,
            AITablePolicy.is_active == True,  # noqa: E712
            AITablePolicy.is_deleted == False,  # noqa: E712
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_all_active(self) -> list[AITablePolicy]:
        """获取所有激活的全局策略"""
        stmt = select(AITablePolicy).where(
            AITablePolicy.is_active == True,  # noqa: E712
            AITablePolicy.is_deleted == False,  # noqa: E712
        ).order_by(AITablePolicy.sort_order)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_table_columns(self, table_name: str) -> list[dict]:
        """
        获取指定表的列信息（用于 blocked_columns / readonly_columns 选择器）

        Returns:
            [{"name": "col_name", "type": "int", "comment": "描述"}, ...]
        """
        query = text("""
            SELECT
                c.column_name,
                c.data_type,
                pgd.description AS column_comment
            FROM information_schema.columns c
            LEFT JOIN pg_catalog.pg_statio_all_tables st
                ON st.schemaname = c.table_schema AND st.relname = c.table_name
            LEFT JOIN pg_catalog.pg_description pgd
                ON pgd.objoid = st.relid AND pgd.objsubid = c.ordinal_position
            WHERE c.table_schema = 'public'
                AND c.table_name = :table_name
            ORDER BY c.ordinal_position
        """)
        result = await self.db.execute(query, {"table_name": table_name})
        rows = result.fetchall()

        return [
            {
                "name": row[0],
                "type": row[1],
                "comment": row[2] or "",
            }
            for row in rows
        ]


__all__ = ["AITablePolicyRepository"]
