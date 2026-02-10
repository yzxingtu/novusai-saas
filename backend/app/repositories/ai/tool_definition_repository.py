"""
工具定义 Repository
"""

from typing import Optional, List

from sqlalchemy import select, and_

from app.models.ai.tool_definition import ToolDefinition
from app.core.base_repository import TenantRepository, BaseRepository


class ToolDefinitionRepository(TenantRepository[ToolDefinition]):
    """
    租户级工具定义 Repository

    提供基于租户隔离的工具定义数据访问
    """

    model = ToolDefinition

    async def get_by_name(
        self,
        name: str,
        exclude_id: Optional[int] = None,
    ) -> Optional[ToolDefinition]:
        """
        按名称查找工具定义（同租户内唯一性检查）

        Args:
            name: 工具名称
            exclude_id: 排除的 ID（用于更新时排除自身）

        Returns:
            ToolDefinition 实例或 None
        """
        conditions = [
            ToolDefinition.tenant_id == self.tenant_id,
            ToolDefinition.name == name,
            ToolDefinition.is_deleted == False,
        ]
        if exclude_id is not None:
            conditions.append(ToolDefinition.id != exclude_id)

        stmt = select(ToolDefinition).where(and_(*conditions))
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_active_tools(self) -> List[ToolDefinition]:
        """
        获取当前租户所有已激活的工具

        Returns:
            已激活的 ToolDefinition 列表
        """
        stmt = (
            select(ToolDefinition)
            .where(
                and_(
                    ToolDefinition.tenant_id == self.tenant_id,
                    ToolDefinition.is_active == True,
                    ToolDefinition.is_deleted == False,
                )
            )
            .order_by(ToolDefinition.created_at.desc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_system_tools(self) -> List[ToolDefinition]:
        """
        获取所有系统内置工具

        Returns:
            系统工具 ToolDefinition 列表
        """
        stmt = (
            select(ToolDefinition)
            .where(
                and_(
                    ToolDefinition.is_system == True,
                    ToolDefinition.is_active == True,
                    ToolDefinition.is_deleted == False,
                )
            )
            .order_by(ToolDefinition.name)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())


class AdminToolDefinitionRepository(BaseRepository[ToolDefinition]):
    """
    管理端工具定义 Repository

    无租户隔离，供平台管理端全局查询使用
    """

    model = ToolDefinition


__all__ = [
    "ToolDefinitionRepository",
    "AdminToolDefinitionRepository",
]
