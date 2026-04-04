"""
AI 模型 Repository / AI Model Repository

处理 AI 模型数据访问
Handles AI model data access.
"""

from sqlalchemy import nulls_last, select
from sqlalchemy.orm import selectinload

from app.core.base_repository import BaseRepository
from app.enums.ai import ModelTypeEnum
from app.models.ai import AIModel


class AIModelRepository(BaseRepository[AIModel]):
    """
    AI 模型 Repository / AI Model Repository.

    提供 AI 模型的数据访问操作
    """

    model = AIModel

    async def get_by_code(
        self, code: str, include_deleted: bool = False
    ) -> AIModel | None:
        """
        根据代码获取模型 / Get model by code.

        Args:
            code: 模型代码
            include_deleted: 是否包含已删除的记录

        Returns:
            AIModel 对象或 None
        """
        stmt = select(AIModel).where(AIModel.code == code)

        if not include_deleted:
            stmt = stmt.where(AIModel.is_deleted.is_(False))

        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_provider(
        self, provider_id: int, include_deleted: bool = False
    ) -> list[AIModel]:
        """
        获取供应商的所有模型 / Get all models for provider.

        Args:
            provider_id: 供应商 ID
            include_deleted: 是否包含已删除的记录

        Returns:
            AIModel 列表
        """
        stmt = select(AIModel).where(AIModel.provider_id == provider_id)

        if not include_deleted:
            stmt = stmt.where(AIModel.is_deleted.is_(False))

        stmt = stmt.order_by(AIModel.created_at.desc())

        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_active_models_by_provider(self, provider_id: int) -> list[AIModel]:
        """
        获取供应商的启用模型 / Get active models for provider.

        Args:
            provider_id: 供应商 ID

        Returns:
            AIModel 列表
        """
        stmt = (
            select(AIModel)
            .where(
                AIModel.provider_id == provider_id,
                AIModel.is_active.is_(True),
                AIModel.is_deleted.is_(False),
            )
            .order_by(AIModel.created_at.desc())
        )

        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def code_exists(self, code: str, exclude_id: int | None = None) -> bool:
        """
        检查模型代码是否全局存在 / Check if model code exists globally.

        保留该方法以兼容仍依赖旧全局唯一语义的调用方；新模型写路径应使用
        code_exists_for_provider()。
        """
        from sqlalchemy import func

        stmt = select(func.count(AIModel.id)).where(
            AIModel.code == code,
            AIModel.is_deleted.is_(False),
        )

        if exclude_id is not None:
            stmt = stmt.where(AIModel.id != exclude_id)

        result = await self.db.execute(stmt)
        count = result.scalar() or 0
        return count > 0

    async def code_exists_for_provider(
        self,
        code: str,
        provider_id: int,
        exclude_id: int | None = None,
    ) -> bool:
        """
        检查同一供应商下模型代码是否存在 / Check if model code exists under the same provider.

        Args:
            code: 模型代码
            provider_id: 供应商 ID
            exclude_id: 排除的 ID（用于更新时排除自己）

        Returns:
            是否存在
        """
        from sqlalchemy import func

        stmt = select(func.count(AIModel.id)).where(
            AIModel.code == code,
            AIModel.provider_id == provider_id,
            AIModel.is_deleted.is_(False),
        )

        if exclude_id is not None:
            stmt = stmt.where(AIModel.id != exclude_id)

        result = await self.db.execute(stmt)
        count = result.scalar() or 0
        return count > 0

    async def get_active_with_provider(self, model_id: int) -> AIModel | None:
        """
        获取启用的模型（预加载 provider 关系）/ Get active model with provider preloaded.

        Args:
            model_id: 模型 ID

        Returns:
            AIModel 对象或 None
        """
        from sqlalchemy.orm import selectinload

        stmt = (
            select(AIModel)
            .where(
                AIModel.id == model_id,
                AIModel.is_active.is_(True),
                AIModel.is_deleted.is_(False),
            )
            .options(selectinload(AIModel.provider))
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_active_by_name_and_provider(
        self, name: str, provider_id: int
    ) -> AIModel | None:
        """
        根据名称和供应商获取启用的模型 / Get active model by name and provider.

        Args:
            name: 模型名称
            provider_id: 供应商 ID

        Returns:
            AIModel 对象或 None
        """
        stmt = select(AIModel).where(
            AIModel.provider_id == provider_id,
            AIModel.name == name,
            AIModel.is_active.is_(True),
            AIModel.is_deleted.is_(False),
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_active_by_code_and_provider(
        self, code: str, provider_id: int
    ) -> AIModel | None:
        """
        根据代码和供应商获取启用模型 / Get active model by code and provider.

        Args:
            code: 模型代码
            provider_id: 供应商 ID

        Returns:
            AIModel 对象或 None
        """
        stmt = select(AIModel).where(
            AIModel.provider_id == provider_id,
            AIModel.code == code,
            AIModel.is_active.is_(True),
            AIModel.is_deleted.is_(False),
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_tier(
        self,
        tier: str,
        preferred_provider_id: int | None = None,
        supports_vision: bool = False,
        supports_audio: bool = False,
        supports_video: bool = False,
        supports_function_calling: bool = False,
        min_context_window: int | None = None,
    ) -> AIModel | None:
        """
        按 tier 查询最优 chat 模型 / Get best chat model by tier.

        选择策略：同 provider > 最低价格（input_price_per_1k ASC NULLS LAST） > id ASC
        必须：is_active=True, is_deleted=False, type='chat', tier=目标值

        Args:
            tier: 目标 tier（fast/standard/premium）
            preferred_provider_id: 优先的供应商 ID
            supports_vision: 是否需要视觉能力
            supports_audio: 是否需要音频能力
            supports_video: 是否需要视频能力
            supports_function_calling: 是否需要函数调用能力
            min_context_window: 最小上下文窗口（tokens）

        Returns:
            最优 AIModel 或 None
        """
        conditions = [
            AIModel.is_active.is_(True),
            AIModel.is_deleted.is_(False),
            AIModel.type == ModelTypeEnum.CHAT.value,
            AIModel.tier == tier,
        ]

        if supports_vision:
            conditions.append(AIModel.supports_vision.is_(True))

        if supports_audio:
            conditions.append(AIModel.supports_audio.is_(True))

        if supports_video:
            conditions.append(AIModel.supports_video.is_(True))

        if supports_function_calling:
            conditions.append(AIModel.supports_function_calling.is_(True))

        if min_context_window is not None:
            conditions.append(AIModel.context_window >= min_context_window)

        stmt = (
            select(AIModel)
            .where(*conditions)
            .options(selectinload(AIModel.provider))
            .order_by(
                # 同 provider 优先
                (AIModel.provider_id != preferred_provider_id).asc()
                if preferred_provider_id
                else AIModel.id.asc(),
                nulls_last(AIModel.input_price_per_1k.asc()),
                AIModel.id.asc(),
            )
            .limit(1)
        )

        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_first_active_embedding_with_provider(self) -> AIModel | None:
        """
        获取第一个可用的 embedding 模型（预加载 provider）/ Get the first active embedding model with provider.
        """
        stmt = (
            select(AIModel)
            .where(
                AIModel.type == ModelTypeEnum.EMBEDDING.value,
                AIModel.is_active.is_(True),
                AIModel.is_deleted.is_(False),
            )
            .options(selectinload(AIModel.provider))
            .order_by(
                nulls_last(AIModel.input_price_per_1k.asc()),
                AIModel.id.asc(),
            )
            .limit(1)
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()


__all__ = [
    "AIModelRepository",
]
