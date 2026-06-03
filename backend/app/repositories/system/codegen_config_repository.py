"""
CRUD 代码生成配置仓储 / Codegen Config Repository

提供代码生成配置的数据访问操作
Provides codegen config data access operations.
"""

from sqlalchemy import select
from sqlalchemy.orm import load_only

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

    async def list_workbench_rows(self) -> list[CodegenConfig]:
        """
        获取工作台统计所需的最小字段集合 / Load minimal fields for workbench summary.

        按最近更新时间倒序，供 summary 统计与关注事项使用。
        Ordered by latest updates for summary stats and focus lists.
        """
        query = (
            select(self.model)
            .options(
                load_only(
                    self.model.id,
                    self.model.name,
                    self.model.resource,
                    self.model.status,
                    self.model.last_generated_at,
                    self.model.generation_count,
                    self.model.generated_files,
                    self.model.last_error,
                    self.model.updated_at,
                )
            )
            .where(self.model.is_deleted.is_(False))
            .order_by(self.model.updated_at.desc(), self.model.id.desc())
        )
        result = await self.db.execute(query)
        return list(result.scalars().all())


__all__ = ["CodegenConfigRepository"]
