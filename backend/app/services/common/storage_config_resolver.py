"""
Storage configuration resolver

Centralizes storage config resolution logic shared by:
- tenant/attachment_service.py
- tenant/attachment_download_service.py
- system/attachment_service.py
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
    avoiding duplication across multiple attachment services.
    """

    def __init__(self, db: AsyncSession):
        self._config_service = ConfigService(db)

    async def get_storage_mode(self, tenant_id: int) -> str:
        """
        Get tenant storage mode (platform or custom)

        Args:
            tenant_id: Tenant ID

        Returns:
            "platform" or "custom"
        """
        mode = await self._config_service.get_tenant_config(
            tenant_id,
            "tenant_storage_mode",
            default="platform",
        )
        return "custom" if str(mode) == "custom" else "platform"

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
        Resolve tenant custom storage configuration

        Args:
            tenant_id: Tenant ID

        Returns:
            StorageConfig for the tenant's custom storage driver

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

    async def resolve_config(
        self, storage_mode: str, tenant_id: int = 0
    ) -> StorageConfig:
        """
        Resolve storage config based on mode

        Args:
            storage_mode: "platform" or "custom"
            tenant_id: Tenant ID (required for custom mode)

        Returns:
            StorageConfig
        """
        if storage_mode == "custom" and tenant_id:
            return await self.resolve_tenant_config(tenant_id)
        return await self.resolve_platform_config()

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
            if storage_mode == "custom":
                return await self.resolve_tenant_config(tenant_id)
        return await self.resolve_platform_config()


__all__ = ["StorageConfigResolver"]
