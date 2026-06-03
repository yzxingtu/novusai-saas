"""
任务定义仓储 / Task Definition Repository
"""

from app.core.base_repository import BaseRepository
from app.models.system.task_definition import TaskDefinition


class TaskDefinitionRepository(BaseRepository[TaskDefinition]):
    """
    任务定义仓储 / Task definition repository.
    """

    model = TaskDefinition

    async def get_by_code(self, code: str) -> TaskDefinition | None:
        return await self.get_one_by(code=code)


__all__ = ["TaskDefinitionRepository"]
