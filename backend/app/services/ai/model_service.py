"""
AI 模型 Service

处理 AI 模型业务逻辑
"""

from app.core.base_service import BaseService
from app.core.i18n import _
from app.exceptions import NotFoundException, ConflictException, BusinessException
from app.repositories.ai import AIModelRepository
from app.schemas.ai.model import (
    AIModelCreate,
    AIModelUpdate,
)
from app.models.ai import AIModel


class AIModelService(BaseService[AIModel, AIModelRepository]):
    """
    AI 模型 Service

    提供 AI 模型的业务逻辑操作
    """

    model = AIModel
    repository_class = AIModelRepository

    async def get_by_code(self, code: str) -> AIModel | None:
        """
        根据代码获取模型

        Args:
            code: 模型代码

        Returns:
            AIModel 实例或 None
        """
        return await self.repo.get_by_code(code)

    async def get_by_provider(
        self,
        provider_id: int,
        include_deleted: bool = False,
    ) -> list[AIModel]:
        """
        获取供应商的所有模型

        Args:
            provider_id: 供应商 ID
            include_deleted: 是否包含已删除的记录

        Returns:
            AIModel 列表
        """
        return await self.repo.get_by_provider(
            provider_id,
            include_deleted=include_deleted,
        )

    async def create_model(self, data: AIModelCreate) -> AIModel:
        """
        创建模型

        Args:
            data: 创建请求

        Returns:
            AIModel 实例

        Raises:
            ConflictException: 代码已存在
        """
        if await self.repo.code_exists(data.code):
            raise ConflictException(message=_("ai.error.model_code_exists"))

        model_obj = AIModel(**data.model_dump())
        self.db.add(model_obj)
        await self.db.flush()
        return model_obj

    @staticmethod
    def _validate_fallback(model_id: int, update_data: dict) -> None:
        """校验 fallback_model_id 不可自引用"""
        fallback_id = update_data.get("fallback_model_id")
        if fallback_id is not None and fallback_id == model_id:
            raise BusinessException(message=_("ai.error.fallback_self_reference"))

    async def update_model(self, id: int, data: AIModelUpdate) -> AIModel:
        """
        更新模型

        Args:
            id: 模型 ID
            data: 更新请求

        Returns:
            AIModel 实例

        Raises:
            NotFoundException: 模型不存在
            ConflictException: 代码冲突
        """
        model_obj = await self.get_by_id(id)
        if not model_obj:
            raise NotFoundException(message=_("ai.error.model_not_found"))

        update_data = data.model_dump(exclude_unset=True)

        # 校验 fallback 不可自引用
        self._validate_fallback(id, update_data)

        if "code" in update_data and update_data["code"] != model_obj.code:
            if await self.repo.code_exists(update_data["code"], exclude_id=id):
                raise ConflictException(message=_("ai.error.model_code_exists"))

        model_obj.update_from_dict(update_data)
        await self.db.flush()
        return model_obj

    async def delete_model(self, id: int) -> None:
        """
        删除模型（软删除）

        Args:
            id: 模型 ID

        Raises:
            NotFoundException: 模型不存在
        """
        model_obj = await self.get_by_id(id)
        if not model_obj:
            raise NotFoundException(message=_("ai.error.model_not_found"))

        model_obj.soft_delete()
        await self.db.flush()


__all__ = [
    "AIModelService",
]
