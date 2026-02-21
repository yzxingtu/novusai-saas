"""
租户插件服务

提供租户级插件内部查询（管理端全盘控制后，此服务仅用于内部查询）
"""

from app.core.base_service import GlobalService
from app.models.system.tenant_plugin import TenantPlugin
from app.repositories.system.tenant_plugin_repository import TenantPluginRepository


class TenantPluginService(GlobalService[TenantPlugin, TenantPluginRepository]):
    """
    租户插件服务（仅内部查询）

    租户端插件管理功能已移除，所有插件控制权归管理端。
    此服务仅保留 get_tenant_active_plugins() 供内部查询使用。
    """

    model = TenantPlugin
    repository_class = TenantPluginRepository

    async def get_tenant_active_plugins(
        self, tenant_id: int
    ) -> list[TenantPlugin]:
        """获取租户已启用的插件列表"""
        return await self.repo.get_tenant_active_plugins(tenant_id)
