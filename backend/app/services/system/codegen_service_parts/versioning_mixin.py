"""Versioning concerns for CodegenService. / CodegenService 版本治理职责。"""

from __future__ import annotations

from typing import Any

from app.core.i18n import _
from app.core.response import serialize_datetime_for_api
from app.enums.codegen import CodegenConfigStatusEnum
from app.exceptions import NotFoundException
from app.models.system.codegen_config import CodegenConfig
from app.repositories.system.codegen_config_version_repository import (
    CodegenConfigVersionRepository,
)


class CodegenVersioningMixin:
    """Versioning mixin / 版本管理混入。"""

    async def _save_version(
        self, config: CodegenConfig, note: str | None = None
    ) -> None:
        """保存配置版本快照 / Save config version snapshot."""
        version_repo = CodegenConfigVersionRepository(self.repo.db)
        await version_repo.create(
            {
                "config_id": config.id,
                "config_json": dict(config.config_json) if config.config_json else {},
                "note": note,
            }
        )

    async def _after_create(self, instance: CodegenConfig) -> None:
        await super()._after_create(instance)
        await self._save_version(instance, note=_("codegen.version_initial"))

    async def _after_update(self, instance: CodegenConfig) -> None:
        await super()._after_update(instance)
        await self._save_version(instance)

    async def list_versions(self, config_id: int, limit: int = 50) -> list[dict]:
        """获取配置的版本列表 / List config versions."""
        version_repo = CodegenConfigVersionRepository(self.repo.db)
        versions = await version_repo.list_by_config_id(config_id, limit=limit)
        return [
            {
                "id": v.id,
                "config_id": v.config_id,
                "created_at": serialize_datetime_for_api(v.created_at),
                "note": v.note,
            }
            for v in versions
        ]

    async def get_version_config(self, config_id: int, version_id: int) -> dict | None:
        """获取指定版本的 config_json / Get config_json of a version."""
        version_repo = CodegenConfigVersionRepository(self.repo.db)
        version = await version_repo.get_version(config_id, version_id)
        if not version:
            return None
        return version.config_json

    async def restore_version(
        self, config_id: int, version_id: int
    ) -> CodegenConfig | None:
        """恢复配置到指定版本；同步顶层 name/resource/module/display_name 与 config_json。"""
        config_json = await self.get_version_config(config_id, version_id)
        if config_json is None:
            return None
        update_data: dict[str, Any] = {
            "config_json": config_json,
            "status": CodegenConfigStatusEnum.DRAFT.value,
            "generated_files": None,
            "last_error": None,
            "last_generated_at": None,
        }
        if isinstance(config_json, dict):
            if "display_name" in config_json:
                update_data["display_name"] = config_json["display_name"]
            if "display_name_en" in config_json:
                update_data["display_name_en"] = config_json["display_name_en"]
            if "resource" in config_json:
                update_data["resource"] = config_json["resource"]
            if "module" in config_json:
                update_data["module"] = config_json["module"]
            if "name" in config_json:
                update_data["name"] = config_json["name"]
        return await self.update(config_id, update_data)

    async def duplicate(self, id: int) -> CodegenConfig:
        """
        复制配置 / Duplicate config.

        创建一份配置的副本，名称追加 " (副本)"，状态重置为 draft。
        同步 config_json 中的 resource/module/display_name 与顶层字段一致。
        Creates a copy with name suffixed " (副本)", status reset to draft.
        Syncs config_json.resource/module/display_name to match top-level fields.

        Args:
            id: 源配置 ID

        Returns:
            新创建的配置

        Raises:
            NotFoundException: 源配置不存在
        """
        source = await self.get_by_id(id)
        if not source:
            raise NotFoundException(message=_("codegen.config_not_found"))

        duplicate_suffix = _("codegen.duplicate_suffix")
        new_resource = await self._allocate_duplicate_resource(source.resource)
        new_name = await self._allocate_duplicate_name(source.name, duplicate_suffix)
        config_json = dict(source.config_json) if source.config_json else {}
        config_json["resource"] = new_resource
        config_json["module"] = source.module
        config_json["display_name"] = source.display_name
        config_json["display_name_en"] = source.display_name_en

        copy_data: dict[str, Any] = {
            "name": new_name,
            "resource": new_resource,
            "module": source.module,
            "display_name": source.display_name,
            "display_name_en": source.display_name_en,
            "status": CodegenConfigStatusEnum.DRAFT.value,
            "config_json": config_json,
            "generation_count": 0,
        }
        return await self.create(copy_data)

    async def _allocate_duplicate_resource(self, base_resource: str) -> str:
        """Allocate a unique resource name for duplicates / 为复制配置分配唯一 resource."""
        candidate = f"{base_resource}_copy"
        index = 2
        while await self.get_by_resource(candidate):
            candidate = f"{base_resource}_copy_{index}"
            index += 1
        return candidate

    async def _allocate_duplicate_name(self, base_name: str, suffix: str) -> str:
        """Allocate a unique config name for duplicates / 为复制配置分配唯一名称."""
        existing = await self.get_list(limit=2000)
        existing_names = {str(item.name or "").strip() for item in existing}
        candidate = f"{base_name}{suffix}"
        index = 2
        while candidate in existing_names:
            candidate = f"{base_name}{suffix} {index}"
            index += 1
        return candidate

