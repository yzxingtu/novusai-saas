"""
存储配置共享辅助函数

管理端和租户端配置控制器共用，从数据库查询已知的插件存储驱动。
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.system.plugin import Plugin


async def get_known_plugin_storage_drivers(db: AsyncSession) -> list[dict]:
    """
    查询所有声明了 storage_drivers 扩展的插件。

    返回字典列表，每项包含：
        name, display_name, plugin_name, plugin_status
    供 StorageManager.get_all_driver_info_list() 合并展示。
    """
    stmt = select(Plugin).where(
        Plugin.is_deleted.is_(False),
    )
    result = await db.execute(stmt)
    plugins = result.scalars().all()

    drivers: list[dict] = []
    for p in plugins:
        manifest = p.manifest or {}
        extensions = manifest.get("extensions", {})
        for sd in extensions.get("storage_drivers", []):
            code = sd.get("code", "")
            if not code:
                continue
            display = sd.get("display_name", {})
            if isinstance(display, dict):
                display_str = display.get("zh-CN") or display.get("en") or code
            else:
                display_str = str(display) if display else code
            drivers.append({
                "name": code,
                "display_name": display_str,
                "plugin_name": p.name,
                "plugin_status": p.status,
            })
    return drivers
