"""Config sync concerns for CodegenService. / CodegenService 配置同步职责。"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from app.codegen.config_parser import ConfigParser


class CodegenConfigSyncMixin:
    """Config sync mixin / 配置同步混入。"""

    @staticmethod
    def _derive_top_level_fields(config_json: dict[str, Any]) -> dict[str, Any]:
        """从 config_json 派生顶层字段，统一以 config_json 为事实源 / Derive top-level fields from config_json."""
        parsed = ConfigParser().parse(config_json)
        display_name = parsed.display_name or parsed.resource
        display_name_en = (
            parsed.display_name_en or parsed.resource.replace("_", " ").title()
        )
        return {
            "name": config_json.get("name") or display_name,
            "resource": parsed.resource,
            "module": parsed.module,
            "display_name": display_name,
            "display_name_en": display_name_en,
        }

    @classmethod
    def _sync_data_from_config_json(cls, data: dict[str, Any]) -> None:
        """若包含 config_json，则同步顶层字段 / Sync top-level fields from config_json when present."""
        config_json = data.get("config_json")
        if isinstance(config_json, dict):
            data.update(cls._derive_top_level_fields(config_json))

    @staticmethod
    def _sync_config_json_from_top_level(
        base_config_json: dict[str, Any] | None,
        data: dict[str, Any],
    ) -> dict[str, Any] | None:
        """当仅更新顶层字段时，回写到 config_json / Push top-level field updates back into config_json."""
        tracked_fields = (
            "name",
            "resource",
            "module",
            "display_name",
            "display_name_en",
        )
        if not any(
            field in data and data[field] is not None for field in tracked_fields
        ):
            return None
        config_json = dict(base_config_json or {})
        for field in tracked_fields:
            if field in data and data[field] is not None:
                config_json[field] = data[field]
        return config_json

    async def _before_create(self, data: dict[str, Any]) -> None:
        """创建前计算 config_hash / Compute config_hash before create."""
        await super()._before_create(data)
        self._sync_data_from_config_json(data)
        if config_json := data.get("config_json"):
            data["config_hash"] = hashlib.sha256(
                json.dumps(config_json, sort_keys=True).encode()
            ).hexdigest()[:16]

    async def _before_update(self, id: int, data: dict[str, Any]) -> None:
        """更新前计算 config_hash（当 config_json 变更时）/ Compute config_hash when config_json changes."""
        await super()._before_update(id, data)
        if "config_json" in data and isinstance(data.get("config_json"), dict):
            self._sync_data_from_config_json(data)
        else:
            current = await self.get_by_id(id)
            if current:
                synced_config = self._sync_config_json_from_top_level(
                    current.config_json, data
                )
                if synced_config is not None:
                    data["config_json"] = synced_config
                    self._sync_data_from_config_json(data)
        if config_json := data.get("config_json"):
            data["config_hash"] = hashlib.sha256(
                json.dumps(config_json, sort_keys=True).encode()
            ).hexdigest()[:16]

