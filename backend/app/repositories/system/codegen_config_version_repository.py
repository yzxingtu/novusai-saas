"""
CRUD 代码生成配置版本仓储 / Codegen Config Version Repository

提供配置版本历史的数据访问
Provides codegen config version history data access.
"""

from sqlalchemy import desc, select

from app.core.base_repository import BaseRepository
from app.models.system.codegen_config_version import CodegenConfigVersion


class CodegenConfigVersionRepository(BaseRepository[CodegenConfigVersion]):
    """
    CRUD 代码生成配置版本仓储 / Codegen config version repository.
    """

    model = CodegenConfigVersion

    async def list_by_config_id(
        self,
        config_id: int,
        limit: int = 50,
    ) -> list[CodegenConfigVersion]:
        """
        获取配置的版本列表（按创建时间倒序）/ List versions for config, newest first.
        """
        stmt = (
            select(CodegenConfigVersion)
            .where(CodegenConfigVersion.config_id == config_id)
            .order_by(desc(CodegenConfigVersion.created_at))
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_version(
        self, config_id: int, version_id: int
    ) -> CodegenConfigVersion | None:
        """
        获取指定版本 / Get version by id, ensuring it belongs to config.
        """
        stmt = select(CodegenConfigVersion).where(
            CodegenConfigVersion.id == version_id,
            CodegenConfigVersion.config_id == config_id,
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()


__all__ = ["CodegenConfigVersionRepository"]
