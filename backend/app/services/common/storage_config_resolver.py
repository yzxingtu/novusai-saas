"""
存储配置解析器 / Storage Configuration Resolver

集中存储配置解析逻辑 / Centralizes storage config resolution logic shared by:
- tenant/attachment_service.py
- tenant/attachment_download_service.py
- system/attachment_service.py

Three-mode resolution chain (priority high → low):
1. custom      — tenant self-configured storage (Mode 3)
2. admin_override — admin-specified per-tenant storage (Mode 2)
3. platform    — global platform storage (Mode 1)
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.configs.service import ConfigService
from app.core.i18n import _
from app.enums import ErrorCode
from app.exceptions import BusinessException
from app.storage import StorageConfig


class StorageConfigResolver:
    """
    Shared storage configuration resolver

    Resolves StorageConfig from platform or tenant settings,
    supporting three modes: platform / admin_override / custom.
    """

    def __init__(self, db: AsyncSession):
        self._config_service = ConfigService(db)

    async def get_storage_mode(self, tenant_id: int) -> str:
        """
        获取企业有效存储模式

        解析规则：
        1. tenant_storage_mode == 'custom' 且该企业的 self_config 开关打开 → 'custom'
        2. tenant_storage_mode == 'admin_override' 且该企业有驱动配置 → 'admin_override'
        3. 其他情况 → 'platform'

        注意：自主配置权限是逐企业控制的（tenant_storage_self_config_enabled），
        不依赖全局开关，管理员可以为个别企业单独开启。

        Returns:
            'platform' | 'admin_override' | 'custom'
        """
        mode = await self._config_service.get_tenant_config(
            tenant_id,
            "tenant_storage_mode",
            default="platform",
        )
        mode = str(mode)

        if mode == "custom":
            tenant_enabled = await self._config_service.get_tenant_config(
                tenant_id, "tenant_storage_self_config_enabled", default=False
            )
            if tenant_enabled:
                return "custom"
            return "platform"

        if mode == "admin_override":
            driver = await self._config_service.get_tenant_config(
                tenant_id, "tenant_storage_driver", default=None
            )
            if driver:
                return "admin_override"
            return "platform"

        return "platform"

    async def resolve_platform_config(self) -> StorageConfig:
        """
        Resolve platform-managed storage configuration

        Returns:
            StorageConfig for the platform storage driver
        """
        driver = await self._config_service.get_platform_config(
            "platform_storage_driver", default="local"
        )
        if str(driver) == "local":
            from app.storage import LOCAL_STORAGE_ROOT
            root_path = str(LOCAL_STORAGE_ROOT)
        else:
            root_path = await self._config_service.get_platform_config(
                "platform_storage_root_path", default=""
            )
        base_url = await self._config_service.get_platform_config(
            "platform_storage_base_url", default=None
        )
        options = await self._config_service.get_platform_config(
            "platform_storage_options", default={}
        )
        return StorageConfig(
            driver=str(driver),
            root_path=str(root_path),
            base_url=base_url,
            options=options or {},
        )

    async def resolve_tenant_config(self, tenant_id: int) -> StorageConfig:
        """
        Resolve tenant-level storage configuration (Mode 2 or Mode 3)

        Used for both admin_override and custom modes — they share the same
        tenant_storage_* config keys.

        Args:
            tenant_id: Tenant ID

        Returns:
            StorageConfig for the tenant's storage driver

        Raises:
            BusinessException: If driver is local or root_path is empty
        """
        driver = await self._config_service.get_tenant_config(
            tenant_id, "tenant_storage_driver", default="s3"
        )
        if str(driver) == "local":
            raise BusinessException(
                message=_("error.common.invalid_parameter"),
                code=ErrorCode.INVALID_PARAMETER,
            )
        root_path = await self._config_service.get_tenant_config(
            tenant_id, "tenant_storage_root_path", default=""
        )
        if not root_path:
            raise BusinessException(
                message=_("error.common.invalid_parameter"),
                code=ErrorCode.INVALID_PARAMETER,
            )
        base_url = await self._config_service.get_tenant_config(
            tenant_id, "tenant_storage_base_url", default=None
        )
        options = await self._config_service.get_tenant_config(
            tenant_id, "tenant_storage_options", default={}
        )
        return StorageConfig(
            driver=str(driver),
            root_path=str(root_path),
            base_url=base_url,
            options=options or {},
        )

    def _check_driver_available(self, config: StorageConfig) -> None:
        """
        Verify the driver in config is actually registered in StorageManager.

        Raises BusinessException with friendly message if driver plugin is
        not installed/enabled, instead of letting StorageManager raise a
        raw StorageConfigError that becomes a 500.
        """
        from app.storage.manager import storage_manager

        if not storage_manager.has_driver(config.driver):
            raise BusinessException(
                message=_(
                    "storage.error.driver_error"
                ),
                code=ErrorCode.INVALID_PARAMETER,
                detail=f"Storage driver '{config.driver}' is not available. "
                       f"The corresponding plugin may not be installed or enabled.",
            )

    async def resolve_config(
        self, storage_mode: str, tenant_id: int = 0
    ) -> StorageConfig:
        """
        Resolve storage config based on mode

        Args:
            storage_mode: 'platform' | 'admin_override' | 'custom'
            tenant_id: Tenant ID (required for non-platform modes)

        Returns:
            StorageConfig
        """
        if storage_mode in ("custom", "admin_override") and tenant_id:
            config = await self.resolve_tenant_config(tenant_id)
        else:
            config = await self.resolve_platform_config()
        self._check_driver_available(config)
        return config

    async def resolve_context(
        self, tenant_id: int
    ) -> tuple[str, StorageConfig, bool]:
        """
        Resolve full storage context for a tenant

        Returns:
            (storage_mode, storage_config, apply_quota)
            apply_quota is always True — storage quota from tenant plan
            applies globally regardless of storage mode
        """
        storage_mode = await self.get_storage_mode(tenant_id)
        storage_config = await self.resolve_config(storage_mode, tenant_id)
        apply_quota = True
        return storage_mode, storage_config, apply_quota

    async def resolve_for_attachment(
        self, driver: str, tenant_id: int = 0
    ) -> StorageConfig:
        """
        Resolve storage config for an existing attachment

        Core principle: always use the driver that matches the attachment's
        original storage, regardless of the tenant's current storage mode.
        This ensures that files uploaded under a previous storage config
        (e.g. local) remain accessible after the platform/tenant switches
        to a different storage driver (e.g. S3/OSS).

        Resolution order:
        1. driver == "local" → always return local StorageConfig
        2. driver matches tenant config → use tenant config
        3. driver matches platform config → use platform config
        4. driver registered but no matching config → construct minimal config
        5. driver not registered → raise error

        Args:
            driver: The driver recorded on the attachment
            tenant_id: Tenant ID

        Returns:
            StorageConfig matching the attachment's storage driver
        """
        # Local files always live on local disk, regardless of current config
        if driver == "local":
            from app.storage import LOCAL_STORAGE_ROOT
            return StorageConfig(
                driver="local",
                root_path=str(LOCAL_STORAGE_ROOT),
                base_url=None,
                options={},
            )

        # For cloud drivers, try tenant config first if applicable
        if tenant_id:
            storage_mode = await self.get_storage_mode(tenant_id)
            if storage_mode in ("custom", "admin_override"):
                try:
                    config = await self.resolve_tenant_config(tenant_id)
                    if config.driver == driver:
                        self._check_driver_available(config)
                        return config
                except BusinessException:
                    pass

        # Fall back to platform config
        config = await self.resolve_platform_config()
        if config.driver == driver:
            self._check_driver_available(config)
            return config

        # Driver mismatch: attachment was stored on a different driver
        # than the current config. This happens after a storage migration.
        # Still try to use platform config if it was the original source.
        # As last resort, check if the driver is at least registered.
        from app.storage.manager import storage_manager
        if storage_manager.has_driver(driver):
            # Driver is available (plugin enabled) but no matching config.
            # Return platform config — the caller will get a driver instance
            # but it won't have the right credentials for this driver.
            # Log a warning so admins are aware of the config gap.
            from app.core.logging import LogManager
            logger = LogManager.get_logger("storage")
            logger.warning(
                "Attachment driver '%s' does not match current config driver '%s'. "
                "File may not be accessible. Consider migrating old attachments.",
                driver, config.driver,
            )
        self._check_driver_available(config)
        return config


__all__ = ["StorageConfigResolver"]
