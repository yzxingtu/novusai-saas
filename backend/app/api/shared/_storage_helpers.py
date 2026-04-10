"""
存储配置共享辅助函数 / Storage Configuration Shared Helpers

供 admin 和 tenant 配置控制器共用。
Shared by admin and tenant configuration controllers.
从数据库查询已知的插件存储驱动。
Query known plugin storage drivers from the database.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.system.plugin_read_model_service import PluginReadModelService


async def get_known_plugin_storage_drivers(db: AsyncSession) -> list[dict]:
    """
    查询所有声明了 storage_drivers 扩展的插件 / Query all plugins that declare storage_drivers extension.

    返回字典列表，每项包含：
        name, display_name, plugin_name, plugin_status
    供 StorageManager.get_all_driver_info_list() 合并展示。
    Returns a list of dictionaries, each containing:
        name, display_name, plugin_name, plugin_status
    for StorageManager.get_all_driver_info_list() to merge and display.
    """
    return await PluginReadModelService(db).get_known_storage_drivers()
