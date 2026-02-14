"""
插件仓储

提供插件的数据访问操作
"""

from sqlalchemy import select

from app.core.base_repository import BaseRepository
from app.models.system.plugin import Plugin


class PluginRepository(BaseRepository[Plugin]):
    """
    插件仓储
    """

    model = Plugin

    _scope_fields = {
        "admin": {
            "id", "name", "display_name", "plugin_type", "status",
            "is_system", "author", "version", "created_at",
        },
    }

    async def get_by_name(self, name: str) -> Plugin | None:
        return await self.get_one_by(name=name)

    async def get_enabled_plugins(self) -> list[Plugin]:
        """获取所有已启用的插件"""
        from app.enums.plugin import PluginStatusEnum
        return await self.get_multi_by(status=PluginStatusEnum.ENABLED.value)

    async def get_by_type(self, plugin_type: str) -> list[Plugin]:
        """按类型获取插件"""
        return await self.get_multi_by(plugin_type=plugin_type)

    async def get_all_active(self) -> list[Plugin]:
        """获取所有未删除的插件（用于依赖/冲突检查）"""
        stmt = select(self.model).where(self.model.is_deleted.is_(False))
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_system_plugins(self) -> list[Plugin]:
        """获取系统内置插件"""
        return await self.get_multi_by(is_system=True)
