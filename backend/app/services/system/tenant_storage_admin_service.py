"""Tenant storage admin service. / 平台企业存储配置服务。"""

from __future__ import annotations

import io
import uuid
from typing import Any

from app.configs.service import ConfigService
from app.core.i18n import _
from app.core.response import build_inline_error_result
from app.enums.error_code import ErrorCode
from app.exceptions import BusinessException


class TenantStorageAdminService:
    """Owns admin-side tenant storage workflows outside the controller file."""

    _CONFIG_KEY_MAP = {
        "tenant_storage_mode": "tenant_storage_mode",
        "tenant_storage_driver": "tenant_storage_driver",
        "tenant_storage_root_path": "tenant_storage_root_path",
        "tenant_storage_base_url": "tenant_storage_base_url",
        "tenant_storage_options": "tenant_storage_options",
        "tenant_storage_self_config_enabled": "tenant_storage_self_config_enabled",
    }

    def __init__(self, db) -> None:
        self._db = db
        self._config_service = ConfigService(db)

    async def get_tenant_storage_config(self, tenant_id: int) -> dict[str, Any]:
        from app.services.common.storage_config_resolver import StorageConfigResolver

        resolver = StorageConfigResolver(self._db)
        mode = await resolver.get_storage_mode(tenant_id)
        tenant_driver = await self._config_service.get_tenant_config(
            tenant_id,
            "tenant_storage_driver",
            default=None,
        )
        tenant_root_path = await self._config_service.get_tenant_config(
            tenant_id,
            "tenant_storage_root_path",
            default="",
        )
        tenant_base_url = await self._config_service.get_tenant_config(
            tenant_id,
            "tenant_storage_base_url",
            default="",
        )
        tenant_options = await self._config_service.get_tenant_config(
            tenant_id,
            "tenant_storage_options",
            default={},
        )
        tenant_mode = await self._config_service.get_tenant_config(
            tenant_id,
            "tenant_storage_mode",
            default="platform",
        )
        tenant_self_enabled = await self._config_service.get_tenant_config(
            tenant_id,
            "tenant_storage_self_config_enabled",
            default=False,
        )
        return {
            "tenant_id": tenant_id,
            "effective_mode": mode,
            "tenant_storage_mode": str(tenant_mode),
            "tenant_storage_driver": str(tenant_driver) if tenant_driver else None,
            "tenant_storage_root_path": str(tenant_root_path),
            "tenant_storage_base_url": str(tenant_base_url),
            "tenant_storage_options": tenant_options or {},
            "tenant_storage_self_config_enabled": bool(tenant_self_enabled),
        }

    async def update_tenant_storage_config(self, *, data: dict[str, Any], tenant_id: int) -> None:
        mode = data.get("tenant_storage_mode")
        if mode == "admin_override":
            driver = data.get("tenant_storage_driver")
            root_path = data.get("tenant_storage_root_path", "")
            if not driver or not root_path or not str(root_path).strip():
                raise BusinessException(
                    message=_("error.common.invalid_parameter"),
                    code=ErrorCode.INVALID_PARAMETER,
                )
            if driver == "local":
                raise BusinessException(
                    message=_("config.storage.local_not_allowed_for_tenant"),
                    code=ErrorCode.INVALID_PARAMETER,
                )

        for field, config_key in self._CONFIG_KEY_MAP.items():
            if field in data:
                await self._config_service.set_tenant_config(
                    tenant_id=tenant_id,
                    key=config_key,
                    value=data[field],
                )
        await self._db.commit()

    async def test_tenant_storage_connection(
        self,
        *,
        base_url: str,
        config: dict[str, Any],
        driver: str,
        root_path: str,
    ) -> dict[str, Any]:
        from app.storage import storage_manager
        from app.storage.base import StorageConfig

        if driver == "local":
            return build_inline_error_result(_("config.storage.local_not_allowed_for_tenant"))

        try:
            storage_config = StorageConfig(
                driver=driver,
                root_path=root_path or config.get("bucket", "test"),
                base_url=base_url or None,
                options=config,
            )
            driver_instance = storage_manager.get_driver(storage_config)
            test_key = f".novusai-test/{uuid.uuid4().hex[:8]}.txt"
            test_content = io.BytesIO(b"NovusAI tenant storage test")
            await driver_instance.put(test_key, test_content, mime_type="text/plain")
            exists = await driver_instance.exists(test_key)
            if not exists:
                return build_inline_error_result(_("config.storage.test_file_not_found"))
            await driver_instance.delete(test_key)
            return {"success": True}
        except Exception as exc:
            return build_inline_error_result(
                exc,
                fallback_message=_("common.server_error"),
            )


__all__ = ["TenantStorageAdminService"]
