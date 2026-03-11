"""
AI 供应商 Repository / AI Provider Repository

处理 AI 供应商数据访问
Handles AI provider data access.
"""


from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.core.base_repository import BaseRepository
from app.models.ai import AIProvider
from app.schemas.common.query import FilterRule, QuerySpec


class AIProviderRepository(BaseRepository[AIProvider]):
    """
    AI 供应商 Repository

    提供 AI 供应商的数据访问操作
    """

    model = AIProvider

    async def query_list(
        self,
        spec: QuerySpec,
        scope: str | None = None,
        forced_filters: list[FilterRule] | None = None,
        include_deleted: bool = False,
    ) -> tuple[list[AIProvider], int]:
        """
        查询供应商列表，显式加载 models 关系以支持 model_count 属性
        """
        allowed_fields = self.get_allowed_fields(scope)
        all_fields = self.get_allowed_fields(None)

        query = select(self.model).options(selectinload(AIProvider.models))

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

        result = await self.db.execute(query)
        items = list(result.scalars().all())

        return items, total

    async def get_by_code(
        self,
        code: str,
        include_deleted: bool = False
    ) -> AIProvider | None:
        """
        根据代码获取供应商

        Args:
            code: 供应商代码
            include_deleted: 是否包含已删除的记录

        Returns:
            AIProvider 对象或 None
        """
        stmt = select(AIProvider).where(
            AIProvider.code == code
        )

        if not include_deleted:
            stmt = stmt.where(AIProvider.is_deleted.is_(False))

        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_active_providers(
        self,
        limit: int | None = None
    ) -> list[AIProvider]:
        """
        获取启用的供应商列表

        Args:
            limit: 限制返回数量

        Returns:
            AIProvider 列表
        """
        stmt = select(AIProvider).where(
            AIProvider.is_active.is_(True),
            AIProvider.is_deleted.is_(False)
        ).order_by(
            AIProvider.sort_order.asc(),
            AIProvider.created_at.desc()
        )

        if limit:
            stmt = stmt.limit(limit)

        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def code_exists(
        self,
        code: str,
        exclude_id: int | None = None
    ) -> bool:
        """
        检查代码是否已存在

        Args:
            code: 供应商代码
            exclude_id: 排除的 ID（用于更新时检查）

        Returns:
            是否存在
        """
        stmt = select(AIProvider.id).where(
            AIProvider.code == code,
            AIProvider.is_deleted.is_(False)
        )

        if exclude_id:
            stmt = stmt.where(AIProvider.id != exclude_id)

        result = await self.db.execute(stmt)
        return result.scalar_one_or_none() is not None


__all__ = [
    "AIProviderRepository",
]
