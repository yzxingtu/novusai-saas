"""
租户插件仓储

提供租户插件实例的数据访问操作
"""

from app.core.base_repository import BaseRepository
from app.models.system.tenant_plugin import TenantPlugin


class TenantPluginRepository(BaseRepository[TenantPlugin]):
    """
    租户插件仓储
    """

    model = TenantPlugin

    _scope_fields = {
        "admin": {
            "id", "tenant_id", "plugin_id", "is_active", "created_at",
        },
        "tenant": {
            "id", "plugin_id", "is_active", "created_at",
        },
    }

    async def get_by_tenant_and_plugin(
        self, tenant_id: int, plugin_id: int
    ) -> TenantPlugin | None:
        """根据租户 ID 和插件 ID 获取记录"""
        return await self.get_one_by(tenant_id=tenant_id, plugin_id=plugin_id)

    async def get_tenant_active_plugins(
        self, tenant_id: int
    ) -> list[TenantPlugin]:
        """获取租户已启用的插件列表"""
        return await self.get_multi_by(tenant_id=tenant_id, is_active=True)

    async def get_plugin_tenants(
        self, plugin_id: int
    ) -> list[TenantPlugin]:
        """获取启用了某插件的所有租户记录"""
        return await self.get_multi_by(plugin_id=plugin_id, is_active=True)
