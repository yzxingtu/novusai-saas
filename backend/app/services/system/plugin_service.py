"""
插件 Service

封装插件安装/启停/卸载/配置/租户分配等业务逻辑。
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from app.core.base_service import BaseService
from app.core.logging import get_logger
from app.exceptions.base import NotFoundException, BusinessException
from app.models.system.plugin import Plugin
from app.repositories.system.plugin_repository import PluginRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)


class PluginService(BaseService[Plugin, PluginRepository]):
    """插件业务服务"""

    model = Plugin
    repository_class = PluginRepository

    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)
        from app.plugins.lifecycle import PluginLifecycle
        from app.plugins.loader import PluginLoader

        self._lifecycle = PluginLifecycle(db)
        self._loader = PluginLoader()

    # ── 安装/启停/卸载 ──

    async def install_from_path(
        self,
        source_path: Path,
        config: dict | None = None,
        capabilities: list[str] | None = None,
    ) -> Plugin:
        """
        安装插件

        Args:
            source_path: 插件源目录
            config: 初始配置
            capabilities: 授权能力列表
        """
        plugin = await self._lifecycle.install(source_path, config)
        if capabilities:
            plugin.granted_capabilities = capabilities
            await self.db.flush()
        return plugin

    async def enable_plugin(self, plugin_id: int) -> None:
        """启用插件"""
        await self._lifecycle.enable(plugin_id)

    async def disable_plugin(self, plugin_id: int) -> None:
        """禁用插件"""
        await self._lifecycle.disable(plugin_id)

    async def uninstall_plugin(
        self, plugin_id: int, confirm_data_delete: bool = False
    ) -> None:
        """卸载插件"""
        await self._lifecycle.uninstall(plugin_id, confirm_data_delete)

    # ── 配置 ──

    async def update_plugin_config(
        self, plugin_id: int, config: dict
    ) -> Plugin:
        """更新插件全局配置（自动加密敏感字段）"""
        from app.plugins.crypto import encrypt_plugin_config

        plugin = await self.repo.get_by_id(plugin_id)
        if not plugin:
            raise NotFoundException(message="plugin.error.not_found")

        manifest_data = plugin.manifest or {}
        config_schema = manifest_data.get("config_schema")
        if config_schema:
            config = encrypt_plugin_config(config, config_schema)

        plugin.config = config
        await self.db.flush()
        return plugin

    async def update_capabilities(
        self, plugin_id: int, capabilities: list[str]
    ) -> Plugin:
        """更新插件授权能力列表"""
        plugin = await self.repo.get_by_id(plugin_id)
        if not plugin:
            raise NotFoundException(message="plugin.error.not_found")

        plugin.granted_capabilities = capabilities
        await self.db.flush()
        return plugin

    # ── 租户分配 ──

    async def assign_tenants(
        self, plugin_id: int, tenant_ids: list[int]
    ) -> int:
        """
        批量分配租户

        Returns:
            实际新增的分配数量
        """
        from sqlalchemy import select

        from app.models.system.plugin_tenant_assignment import PluginTenantAssignment

        plugin = await self.repo.get_by_id(plugin_id)
        if not plugin:
            raise NotFoundException(message="plugin.error.not_found")

        # 查询已有分配
        result = await self.db.execute(
            select(PluginTenantAssignment.tenant_id).where(
                PluginTenantAssignment.plugin_id == plugin_id,
            )
        )
        existing = {row for row in result.scalars()}

        count = 0
        for tid in tenant_ids:
            if tid not in existing:
                self.db.add(PluginTenantAssignment(
                    plugin_id=plugin_id,
                    tenant_id=tid,
                    is_active=True,
                    config={},
                ))
                count += 1

        if count:
            await self.db.flush()
        return count

    async def unassign_tenant(self, plugin_id: int, tenant_id: int) -> None:
        """取消租户分配"""
        from sqlalchemy import delete

        from app.models.system.plugin_tenant_assignment import PluginTenantAssignment

        await self.db.execute(
            delete(PluginTenantAssignment).where(
                PluginTenantAssignment.plugin_id == plugin_id,
                PluginTenantAssignment.tenant_id == tenant_id,
            )
        )
        await self.db.flush()

    async def toggle_tenant_assignment(
        self, plugin_id: int, tenant_id: int, is_active: bool
    ) -> None:
        """切换租户分配启用状态"""
        from sqlalchemy import select, update

        from app.models.system.plugin_tenant_assignment import PluginTenantAssignment

        await self.db.execute(
            update(PluginTenantAssignment).where(
                PluginTenantAssignment.plugin_id == plugin_id,
                PluginTenantAssignment.tenant_id == tenant_id,
            ).values(is_active=is_active)
        )
        await self.db.flush()

    # ── License ──

    async def activate_license(
        self, plugin_id: int, license_key: str
    ) -> None:
        """激活插件 License"""
        from app.core.base_model import utc_now
        from app.models.system.plugin_license import PluginLicense

        plugin = await self.repo.get_by_id(plugin_id)
        if not plugin:
            raise NotFoundException(message="plugin.error.not_found")

        # 简单验证（Phase 4 实现 Ed25519 签名验证）
        if not license_key or len(license_key) < 10:
            raise BusinessException(message="plugin.error.license_invalid")

        license_record = PluginLicense(
            plugin_id=plugin_id,
            license_key=license_key,
            license_type="perpetual",
            is_valid=True,
            activated_at=utc_now(),
        )
        self.db.add(license_record)
        await self.db.flush()

    # ── 查询辅助 ──

    async def get_readme(
        self, plugin_id: int, locale: str = "zh-CN"
    ) -> str | None:
        """获取插件 README"""
        plugin = await self.repo.get_by_id(plugin_id)
        if not plugin:
            raise NotFoundException(message="plugin.error.not_found")
        return self._loader.load_readme(plugin.name, locale)

    async def get_by_name(self, name: str) -> Plugin | None:
        """根据名称查询插件"""
        return await self.repo.get_by_name(name)

    async def list_enabled(self) -> list[Plugin]:
        """查询所有已启用的插件"""
        return await self.repo.list_enabled()
