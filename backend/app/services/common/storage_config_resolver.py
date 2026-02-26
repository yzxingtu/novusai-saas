"""
Storage configuration resolver

Centralizes storage config resolution logic shared by:
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
        Get tenant effective storage mode.

        Resolution:
        1. If tenant_storage_mode == 'custom' AND both platform + tenant
           self-config switches are on → 'custom'
        2. If tenant_storage_mode == 'admin_override' AND tenant has
           a driver configured → 'admin_override'
        3. Otherwise → 'platform'

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
            platform_enabled = await self._config_service.get_platform_config(
                "platform_tenant_storage_self_config_enabled", default=False
            )
            tenant_enabled = await self._config_service.get_tenant_config(
                tenant_id, "tenant_storage_self_config_enabled", default=False
            )
            if platform_enabled and tenant_enabled:
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
            apply_quota is True when using platform storage
        """
        storage_mode = await self.get_storage_mode(tenant_id)
        storage_config = await self.resolve_config(storage_mode, tenant_id)
        apply_quota = storage_mode == "platform"
        return storage_mode, storage_config, apply_quota

    async def resolve_for_attachment(
        self, driver: str, tenant_id: int = 0
    ) -> StorageConfig:
        """
        Resolve storage config for an existing attachment

        Used by download service to determine which driver to use.

        Args:
            driver: The driver recorded on the attachment
            tenant_id: Tenant ID

        Returns:
            StorageConfig matching the attachment's storage driver
        """
        if driver == "local":
            return await self.resolve_platform_config()
        if tenant_id:
            storage_mode = await self.get_storage_mode(tenant_id)
            if storage_mode in ("custom", "admin_override"):
                config = await self.resolve_tenant_config(tenant_id)
                self._check_driver_available(config)
                return config
        config = await self.resolve_platform_config()
        self._check_driver_available(config)
        return config


__all__ = ["StorageConfigResolver"]
