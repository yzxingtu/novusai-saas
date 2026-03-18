"""
CRUD 代码生成配置仓储 / Codegen Config Repository

提供代码生成配置的数据访问操作
Provides codegen config data access operations.
"""

from sqlalchemy import select

from app.core.base_repository import BaseRepository
from app.models.system.codegen_config import CodegenConfig


class CodegenConfigRepository(BaseRepository[CodegenConfig]):
    """
    CRUD 代码生成配置仓储 / Codegen config repository.

    平台级仓储，无企业隔离
    Platform-level repository, no tenant isolation.
    """

    model = CodegenConfig

    async def get_by_resource(self, resource: str) -> CodegenConfig | None:
        """
        根据资源名获取配置 / Get config by resource name.

        Args:
            resource: 资源名 (snake_case)

        Returns:
            配置实例或 None / Config instance or None
        """
        return await self.get_one_by(resource=resource)

    async def get_by_status(self, status: str) -> list[CodegenConfig]:
        """
        根据状态获取配置列表 / Get configs by status.

        Args:
            status: 状态值 (draft/generated/applied/rolled_back)

        Returns:
            配置列表 / List of config instances
        """
        return await self.get_list(status=status, limit=1000)


__all__ = ["CodegenConfigRepository"]
