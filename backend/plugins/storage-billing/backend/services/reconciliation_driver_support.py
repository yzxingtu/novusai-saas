"""Driver gating and provider config support for reconciliation."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select

from app.models.system.plugin import Plugin
from app.plugins.crypto import decrypt_plugin_config

from ..constants import EXCLUDED_DRIVERS, SUPPORTED_CLOUD_DRIVERS
from .reconciliation_shared import (
    PLUGIN_NAME,
    _read_platform_storage_context,
    _stringify,
)


class StorageBillingReconciliationDriverSupportMixin:
    """Provider-driver selection helpers."""

    async def _load_plugin_config(self) -> dict[str, Any]:
        result = await self._db.execute(
            select(Plugin.config, Plugin.manifest).where(
                Plugin.name == PLUGIN_NAME,
                Plugin.is_deleted.is_(False),
            )
        )
        row = result.one_or_none()
        if row is None:
            return {}

        config = row[0] or {}
        manifest = row[1] or {}
        config_schema = manifest.get("config_schema") if isinstance(manifest, dict) else None
        if config_schema:
            config = decrypt_plugin_config(config, config_schema)
        return dict(config or {})

    async def _get_billable_drivers(
        self,
        *,
        period_type: str,
        provider_codes: list[str] | str | None = None,
    ) -> list[dict[str, Any]]:
        if self._host_read is None:
            return []

        raw_provider_codes = (
            [provider_codes]
            if isinstance(provider_codes, str)
            else list(provider_codes or [])
        )
        requested_codes = {
            _stringify(item)
            for item in raw_provider_codes
            if _stringify(item)
        }
        platform_storage_context = await _read_platform_storage_context(self._host_read)
        active_storage_driver = _stringify(
            dict(platform_storage_context.get("storage_config") or {}).get("driver")
        )
        if not active_storage_driver:
            return []
        if active_storage_driver in EXCLUDED_DRIVERS:
            return []
        if active_storage_driver and active_storage_driver not in SUPPORTED_CLOUD_DRIVERS:
            return []

        drivers = await self._host_read.get_enabled_storage_drivers()
        result: list[dict[str, Any]] = []
        for item in drivers:
            code = str(item.get("code") or "").strip()
            if code in EXCLUDED_DRIVERS:
                continue
            if code not in SUPPORTED_CLOUD_DRIVERS:
                continue
            if not item.get("is_available", True):
                continue
            if active_storage_driver and code != active_storage_driver:
                continue
            if requested_codes and code not in requested_codes:
                continue
            profile = await self._profile_service.get_provider_runtime_profile(code)
            supported_period_types = {
                _stringify(value)
                for value in (profile.get("supported_period_types") or [])
                if _stringify(value)
            }
            if _stringify(period_type) not in supported_period_types:
                continue
            result.append(item)
        return result
